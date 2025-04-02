"""
Virtual Machine Management for SafeSpace

This module provides virtual machine management functionality for the SafeSpace package.
It creates lightweight virtual machines using QEMU/KVM for complete isolation.
"""

import logging
import os
import platform
import random
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any, Union

from .utils import log_status, Colors, run_command, sudo_command
from .settings import get_settings

# Set up logging
logger = logging.getLogger(__name__)

@dataclass
class VMConfig:
    """Virtual Machine Configuration"""
    memory: str
    cpus: int
    disk_size: str
    iso_url: Optional[str]
    iso_sha256_url: Optional[str]
    mac_address: Optional[str]
    use_network: bool
    use_kvm: bool
    headless: bool
    
    @classmethod
    def from_settings(cls) -> "VMConfig":
        """Create a VM configuration from settings"""
        settings = get_settings()
        vm_settings = settings.vm
        
        return cls(
            memory=vm_settings.default_memory,
            cpus=vm_settings.default_cpus,
            disk_size=vm_settings.default_disk_size,
            iso_url=None,  # Will be set later based on Alpine version
            iso_sha256_url=None,  # Will be set later based on Alpine version
            mac_address=None,  # Will be generated randomly
            use_network=False,  # Default to false, will be configured if needed
            use_kvm=vm_settings.default_use_kvm,
            headless=vm_settings.default_headless
        )


class VMManager:
    """Manages virtual machines for SafeSpace environments"""
    
    def __init__(
        self, 
        env_dir: Path, 
        sudo_password: Optional[str] = None,
        config: Optional[VMConfig] = None
    ) -> None:
        """
        Initialize VMManager.
        
        Args:
            env_dir: Path to the environment directory
            sudo_password: Optional sudo password for privileged operations
            config: Optional VM configuration
        """
        # Get settings
        settings = get_settings()
        vm_settings = settings.vm
        
        self.env_dir = env_dir
        self.sudo_password = sudo_password
        self.vm_dir = env_dir / "vm"
        self.config = config or VMConfig.from_settings()
        self.is_linux = platform.system() == "Linux"
        self.is_macos = platform.system() == "Darwin"
        self.network_namespace = None
        self.vm_process = None
        self.vm_pid_file = self.vm_dir / "vm.pid"
        self.vm_monitor_socket = self.vm_dir / "monitor.sock"
        self.vm_disk = self.vm_dir / "disk.qcow2"
        self.tap_interface = "tap0"
        
        # Set default Alpine Linux image if none specified
        if not self.config.iso_url:
            alpine_version = vm_settings.default_alpine_version
            self.config.iso_url = f"https://dl-cdn.alpinelinux.org/alpine/v{alpine_version.split('.')[0]}.{alpine_version.split('.')[1]}/releases/x86_64/alpine-virt-{alpine_version}-x86_64.iso"
            self.config.iso_sha256_url = f"https://dl-cdn.alpinelinux.org/alpine/v{alpine_version.split('.')[0]}.{alpine_version.split('.')[1]}/releases/x86_64/alpine-virt-{alpine_version}-x86_64.iso.sha256"
    
    def _sudo_cmd(self, cmd: List[str]) -> Tuple[int, str, str]:
        """
        Run a command with sudo privileges.
        
        Args:
            cmd: Command to run as a list of strings
            
        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        if not self.sudo_password:
            logger.error("No sudo password set")
            return 1, "", "No sudo password provided"
            
        result = sudo_command(" ".join(cmd), self.sudo_password)
        return result.returncode, result.stdout, result.stderr
    
    def _check_requirements(self) -> bool:
        """
        Check if required tools are available.
        
        Returns:
            bool: True if all requirements are met, False otherwise
        """
        required_tools = ["qemu-img", "qemu-system-x86_64", "wget", "sha256sum" if self.is_linux else "shasum -a 256"]
        
        for tool in required_tools:
            cmd = f"which {tool.split()[0]}"
            result = run_command(cmd)
            if result.returncode != 0:
                log_status(f"Required tool '{tool}' not found", Colors.RED)
                return False
        
        return True
    
    def setup(self) -> bool:
        """
        Set up the VM environment.
        
        Returns:
            bool: True if setup was successful, False otherwise
        """
        log_status("Setting up VM environment...", Colors.YELLOW)
        
        # Check requirements
        if not self._check_requirements():
            return False
        
        # Create VM directory
        self.vm_dir.mkdir(parents=True, exist_ok=True)
        
        # Download Alpine Linux for testing if not exists
        iso_filename = Path(self.config.iso_url).name
        iso_path = self.vm_dir / iso_filename
        
        if not iso_path.exists():
            log_status(f"Downloading VM image: {iso_filename}...", Colors.YELLOW)
            
            # Download ISO
            wget_cmd = f"wget -q -O {iso_path} {self.config.iso_url}"
            result = run_command(wget_cmd)
            if result.returncode != 0:
                log_status(f"Failed to download VM image: {result.stderr}", Colors.RED)
                return False
                
            # Download checksum
            sha_path = self.vm_dir / f"{iso_filename}.sha256"
            wget_cmd = f"wget -q -O {sha_path} {self.config.iso_sha256_url}"
            result = run_command(wget_cmd)
            if result.returncode != 0:
                log_status(f"Failed to download checksum: {result.stderr}", Colors.RED)
                return False
                
            # Verify checksum
            log_status("Verifying VM image integrity...", Colors.YELLOW)
            
            # Different verification command based on OS
            if self.is_linux:
                verify_cmd = f"cd {self.vm_dir} && sha256sum -c {iso_filename}.sha256"
            else:  # macOS
                # Extract expected hash from the sha file
                with open(sha_path, 'r') as f:
                    hash_line = f.readline().strip()
                    expected_hash = hash_line.split()[0]
                
                verify_cmd = f"cd {self.vm_dir} && echo '{expected_hash}  {iso_filename}' | shasum -a 256 -c"
            
            result = run_command(verify_cmd)
            if result.returncode != 0:
                log_status("VM image verification failed", Colors.RED)
                os.unlink(iso_path)
                os.unlink(sha_path)
                return False
                
            log_status("VM image verified successfully", Colors.GREEN)
        
        # Create VM disk
        log_status("Creating VM disk image...", Colors.YELLOW)
        qemu_img_cmd = f"qemu-img create -f qcow2 {self.vm_disk} {self.config.disk_size}"
        result = run_command(qemu_img_cmd)
        if result.returncode != 0:
            log_status(f"Failed to create VM disk: {result.stderr}", Colors.RED)
            return False
        
        # Generate unique MAC address for VM if not provided
        if not self.config.mac_address:
            self.config.mac_address = self._generate_mac_address()
        
        # Create VM startup script
        self._create_vm_scripts()
        
        # Setup VM networking if needed
        if self.config.use_network:
            if not self._setup_vm_network():
                log_status("Failed to set up VM networking", Colors.RED)
                return False
        
        # Add VM info to environment file
        self._update_env_file({
            "VM_ENABLED": "true",
            "VM_MEMORY": self.config.memory,
            "VM_CPUS": str(self.config.cpus),
            "VM_DISK_SIZE": self.config.disk_size,
            "VM_MAC": self.config.mac_address
        })
        
        log_status("VM environment setup complete", Colors.GREEN)
        return True
    
    def _generate_mac_address(self) -> str:
        """
        Generate a unique MAC address for the VM.
        
        Returns:
            str: MAC address in the format 52:54:00:XX:XX:XX
        """
        return f"52:54:00:{random.randint(0, 255):02X}:{random.randint(0, 255):02X}:{random.randint(0, 255):02X}"
    
    def _setup_vm_network(self) -> bool:
        """
        Set up VM networking.
        
        Returns:
            bool: True if setup was successful, False otherwise
        """
        log_status("Setting up VM networking...", Colors.YELLOW)
        
        # Create tap interface for VM
        rc, _, stderr = self._sudo_cmd(["ip", "tuntap", "add", self.tap_interface, "mode", "tap"])
        if rc != 0:
            logger.error(f"Failed to create tap interface: {stderr}")
            return False
            
        # Bring up tap interface
        rc, _, stderr = self._sudo_cmd(["ip", "link", "set", self.tap_interface, "up"])
        if rc != 0:
            logger.error(f"Failed to bring up tap interface: {stderr}")
            return False
            
        # Add tap interface to network namespace if one is specified
        if self.network_namespace:
            rc, _, stderr = self._sudo_cmd(["ip", "link", "set", self.tap_interface, "netns", self.network_namespace])
            if rc != 0:
                logger.error(f"Failed to move tap interface to network namespace: {stderr}")
                return False
                
            # Configure tap interface in namespace
            rc, _, stderr = self._sudo_cmd(["ip", "netns", "exec", self.network_namespace, 
                                          "ip", "addr", "add", "192.168.100.3/24", "dev", self.tap_interface])
            if rc != 0:
                logger.error(f"Failed to configure tap interface in namespace: {stderr}")
                return False
                
            # Bring up tap interface in namespace
            rc, _, stderr = self._sudo_cmd(["ip", "netns", "exec", self.network_namespace, 
                                          "ip", "link", "set", self.tap_interface, "up"])
            if rc != 0:
                logger.error(f"Failed to bring up tap interface in namespace: {stderr}")
                return False
        else:
            # Configure tap interface directly on host
            rc, _, stderr = self._sudo_cmd(["ip", "addr", "add", "192.168.100.3/24", "dev", self.tap_interface])
            if rc != 0:
                logger.error(f"Failed to configure tap interface: {stderr}")
                return False
        
        log_status("VM networking setup complete", Colors.GREEN)
        return True
    
    def _create_vm_scripts(self) -> None:
        """Create VM startup and control scripts"""
        # Create VM startup script
        iso_filename = Path(self.config.iso_url).name
        
        with open(self.vm_dir / "start_vm.sh", "w") as f:
            f.write(f"""#!/bin/bash
QEMU_OPTS="-m {self.config.memory} -smp {self.config.cpus} {'-enable-kvm' if self.config.use_kvm else ''}"
QEMU_OPTS+=" -drive file={self.vm_disk},if=virtio"
QEMU_OPTS+=" -cdrom {self.vm_dir / iso_filename}"
QEMU_OPTS+=" -boot d"
QEMU_OPTS+=" -device virtio-net-pci,mac={self.config.mac_address}"

if [ "{self.config.use_network}" = "True" ]; then
    QEMU_OPTS+=" -netdev tap,id=net0,ifname={self.tap_interface},script=no,downscript=no"
else
    QEMU_OPTS+=" -netdev user,id=net0"
fi

QEMU_OPTS+=" {'-nographic' if self.config.headless else '-display curses'}"
QEMU_OPTS+=" -monitor unix:{self.vm_monitor_socket},server,nowait"

exec qemu-system-x86_64 $QEMU_OPTS
""")
        
        # Make script executable
        os.chmod(self.vm_dir / "start_vm.sh", 0o755)
        
        # Create VM control functions
        with open(self.vm_dir / "vm_functions.sh", "w") as f:
            f.write(f"""#!/bin/bash

vm_start() {{
    "{self.vm_dir}/start_vm.sh" &
    VM_PID=$!
    echo $VM_PID > "{self.vm_pid_file}"
    echo "VM started with PID $VM_PID"
}}

vm_stop() {{
    if [ -f "{self.vm_pid_file}" ]; then
        local pid=$(cat "{self.vm_pid_file}")
        kill $pid 2>/dev/null || true
        rm -f "{self.vm_pid_file}"
        echo "VM stopped"
    fi
}}

vm_status() {{
    if [ -f "{self.vm_pid_file}" ]; then
        local pid=$(cat "{self.vm_pid_file}")
        if kill -0 $pid 2>/dev/null; then
            echo "VM is running (PID $pid)"
        else
            echo "VM is not running"
            rm -f "{self.vm_pid_file}"
        fi
    else
        echo "VM is not running"
    fi
}}

vm_monitor() {{
    if [ -S "{self.vm_monitor_socket}" ]; then
        socat - UNIX-CONNECT:"{self.vm_monitor_socket}"
    else
        echo "VM monitor socket not found"
    fi
}}
""")
        
        # Make script executable
        os.chmod(self.vm_dir / "vm_functions.sh", 0o755)
    
    def start(self) -> bool:
        """
        Start the VM.
        
        Returns:
            bool: True if VM was started successfully, False otherwise
        """
        log_status("Starting VM...", Colors.YELLOW)
        
        # Check if VM is already running
        if self.is_running():
            log_status("VM is already running", Colors.YELLOW)
            return True
        
        # Start VM
        cmd = f"{self.vm_dir}/start_vm.sh"
        process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Save PID
        self.vm_process = process
        with open(self.vm_pid_file, "w") as f:
            f.write(str(process.pid))
        
        log_status(f"VM started with PID {process.pid}", Colors.GREEN)
        return True
    
    def stop(self) -> bool:
        """
        Stop the VM.
        
        Returns:
            bool: True if VM was stopped successfully, False otherwise
        """
        log_status("Stopping VM...", Colors.YELLOW)
        
        # Check if VM is running
        if not self.is_running():
            log_status("VM is not running", Colors.YELLOW)
            return True
        
        # Stop VM
        pid = None
        if self.vm_pid_file.exists():
            with open(self.vm_pid_file, "r") as f:
                pid = f.read().strip()
        
        if pid:
            try:
                os.kill(int(pid), 15)  # SIGTERM
                log_status("VM stopped", Colors.GREEN)
                
                # Remove PID file
                self.vm_pid_file.unlink(missing_ok=True)
                return True
            except ProcessLookupError:
                log_status("VM process not found, removing stale PID file", Colors.YELLOW)
                self.vm_pid_file.unlink(missing_ok=True)
                return True
            except Exception as e:
                log_status(f"Failed to stop VM: {e}", Colors.RED)
                return False
        
        return False
    
    def is_running(self) -> bool:
        """
        Check if VM is running.
        
        Returns:
            bool: True if VM is running, False otherwise
        """
        if not self.vm_pid_file.exists():
            return False
            
        with open(self.vm_pid_file, "r") as f:
            pid = f.read().strip()
            
        try:
            os.kill(int(pid), 0)  # Check if process exists
            return True
        except (ProcessLookupError, ValueError):
            # Process doesn't exist or invalid PID
            self.vm_pid_file.unlink(missing_ok=True)
            return False
        except Exception:
            return False
    
    def cleanup(self) -> bool:
        """
        Clean up VM resources.
        
        Returns:
            bool: True if cleanup was successful, False otherwise
        """
        log_status("Cleaning up VM environment...", Colors.YELLOW)
        
        # Stop VM if running
        if self.is_running():
            self.stop()
        
        # Remove tap interface if it exists
        if self.config.use_network:
            try:
                cmd = f"ip link show {self.tap_interface}"
                result = run_command(cmd)
                if result.returncode == 0:
                    # Interface exists, try to delete it
                    self._sudo_cmd(["ip", "link", "delete", self.tap_interface])
            except Exception as e:
                logger.warning(f"Error checking tap interface: {e}")
        
        log_status("VM environment cleaned up", Colors.GREEN)
        return True
    
    def _update_env_file(self, env_vars: Dict[str, str]) -> None:
        """
        Update environment file with new variables.
        
        Args:
            env_vars: Dictionary of environment variables to add
        """
        env_file = self.env_dir / ".env"
        try:
            with open(env_file, "a") as f:
                for key, value in env_vars.items():
                    f.write(f"{key}={value}\n")
        except Exception as e:
            logger.error(f"Failed to update environment file: {e}")
    
    def set_network_namespace(self, namespace: str) -> None:
        """
        Set network namespace for VM networking.
        
        Args:
            namespace: Name of the network namespace
        """
        self.network_namespace = namespace
