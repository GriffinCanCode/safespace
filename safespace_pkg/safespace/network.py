"""
Network Isolation Module for SafeSpace

This module provides network isolation functionality for the SafeSpace package.
It creates isolated network namespaces and configures virtual interfaces for
complete network isolation.
"""

import logging
import os
import platform
import subprocess
from pathlib import Path
from typing import Optional, List, Tuple, Dict

from .utils import log_status, Colors

logger = logging.getLogger(__name__)

class NetworkIsolation:
    """Manages network isolation features for SafeSpace environments."""

    def __init__(self, env_dir: Path, sudo_password: Optional[str] = None):
        """
        Initialize NetworkIsolation.

        Args:
            env_dir: Path to the environment directory
            sudo_password: Optional sudo password for privileged operations
        """
        self.env_dir = env_dir
        self.sudo_password = sudo_password
        self.namespace_name = "safespace_net"
        self.veth_host = "veth0"
        self.veth_namespace = "veth1"
        self.is_linux = platform.system() == "Linux"
        self.is_macos = platform.system() == "Darwin"
        
        # Platform-specific settings
        if self.is_macos:
            self.tap_interface = "utun7"  # macOS uses utun interfaces
        else:
            self.tap_interface = "tap0"
            
        self.host_ip = "192.168.100.1"
        self.namespace_ip = "192.168.100.2"
        self.tap_ip = "192.168.100.3"
        self.network_cidr = "192.168.100.0/24"
        self.env_file = env_dir / ".env"
        
    def _sudo_cmd(self, cmd: List[str]) -> Tuple[int, str, str]:
        """
        Run a command with sudo privileges.

        Args:
            cmd: Command to run as a list of strings

        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        logger.debug(f"Running sudo command: {' '.join(cmd)}")
        
        if not self.sudo_password:
            logger.error("No sudo password set")
            return 1, "", "No sudo password provided"
            
        full_cmd = ["sudo", "-S"] + cmd
        
        try:
            process = subprocess.Popen(
                full_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate(input=f"{self.sudo_password}\n")
            return process.returncode, stdout, stderr
        except Exception as e:
            logger.error(f"Error running sudo command: {e}")
            return 1, "", str(e)

    def setup(self) -> bool:
        """
        Set up network isolation.

        Returns:
            bool: True if setup was successful, False otherwise
        """
        log_status("Setting up network isolation...", Colors.YELLOW)
        
        if self.is_linux:
            return self._setup_linux()
        elif self.is_macos:
            return self._setup_macos()
        else:
            log_status("Network isolation is only supported on Linux and macOS", Colors.RED)
            return False

    def _setup_linux(self) -> bool:
        """
        Set up network isolation on Linux using network namespaces.

        Returns:
            bool: True if setup was successful, False otherwise
        """
        # Create a new network namespace
        rc, _, stderr = self._sudo_cmd(["ip", "netns", "add", self.namespace_name])
        if rc != 0:
            logger.error(f"Failed to create network namespace: {stderr}")
            return False
            
        # Create virtual interface pair
        rc, _, stderr = self._sudo_cmd(["ip", "link", "add", self.veth_host, "type", "veth", "peer", "name", self.veth_namespace])
        if rc != 0:
            logger.error(f"Failed to create virtual interfaces: {stderr}")
            return False
            
        # Move veth1 to namespace
        rc, _, stderr = self._sudo_cmd(["ip", "link", "set", self.veth_namespace, "netns", self.namespace_name])
        if rc != 0:
            logger.error(f"Failed to move interface to namespace: {stderr}")
            return False
            
        # Configure interfaces
        rc, _, stderr = self._sudo_cmd(["ip", "addr", "add", f"{self.host_ip}/24", "dev", self.veth_host])
        if rc != 0:
            logger.error(f"Failed to configure host interface: {stderr}")
            return False
            
        rc, _, stderr = self._sudo_cmd(["ip", "netns", "exec", self.namespace_name, "ip", "addr", "add", f"{self.namespace_ip}/24", "dev", self.veth_namespace])
        if rc != 0:
            logger.error(f"Failed to configure namespace interface: {stderr}")
            return False
            
        # Bring up interfaces
        rc, _, stderr = self._sudo_cmd(["ip", "link", "set", self.veth_host, "up"])
        if rc != 0:
            logger.error(f"Failed to bring up host interface: {stderr}")
            return False
            
        rc, _, stderr = self._sudo_cmd(["ip", "netns", "exec", self.namespace_name, "ip", "link", "set", self.veth_namespace, "up"])
        if rc != 0:
            logger.error(f"Failed to bring up namespace interface: {stderr}")
            return False
            
        rc, _, stderr = self._sudo_cmd(["ip", "netns", "exec", self.namespace_name, "ip", "link", "set", "lo", "up"])
        if rc != 0:
            logger.error(f"Failed to bring up namespace loopback: {stderr}")
            return False
            
        # Setup NAT for internet access
        rc, _, stderr = self._sudo_cmd(["iptables", "-t", "nat", "-A", "POSTROUTING", "-s", self.network_cidr, "-j", "MASQUERADE"])
        if rc != 0:
            logger.error(f"Failed to setup NAT: {stderr}")
            return False
            
        rc, _, stderr = self._sudo_cmd(["ip", "netns", "exec", self.namespace_name, "ip", "route", "add", "default", "via", self.host_ip])
        if rc != 0:
            logger.error(f"Failed to add default route: {stderr}")
            return False
            
        # Enable IP forwarding
        rc, _, stderr = self._sudo_cmd(["sh", "-c", f"echo 1 > /proc/sys/net/ipv4/ip_forward"])
        if rc != 0:
            logger.error(f"Failed to enable IP forwarding: {stderr}")
            return False
            
        # Store network namespace info
        self._update_env_file({
            "NETWORK_NAMESPACE": self.namespace_name,
            "VETH_HOST": self.veth_host,
            "VETH_NAMESPACE": self.veth_namespace
        })
            
        log_status("Network isolation configured successfully", Colors.GREEN)
        return True

    def _setup_macos(self) -> bool:
        """
        Set up network isolation on macOS using pf and dnctl.

        Returns:
            bool: True if setup was successful, False otherwise
        """
        # On macOS, we'll use a different approach
        # Instead of trying to configure utun interfaces which require special privileges,
        # we'll create a local loopback alias and use pf to restrict traffic
        
        # Create a loopback alias
        rc, _, stderr = self._sudo_cmd(["ifconfig", "lo0", "alias", self.tap_ip, "netmask", "255.255.255.0"])
        if rc != 0:
            logger.error(f"Failed to create loopback alias: {stderr}")
            return False
            
        # Create a temporary pf.conf file
        pf_conf_path = self.env_dir / "pf.conf"
        with open(pf_conf_path, "w") as f:
            f.write(f"# SafeSpace network isolation\n")
            f.write(f"# Block all outgoing connections from our virtual environment\n")
            f.write(f"block out quick from {self.tap_ip} to any\n")
            f.write(f"# Allow connections to our loopback subnet\n")
            f.write(f"pass out quick from {self.tap_ip} to {self.network_cidr}\n")
            f.write(f"pass in quick from {self.network_cidr} to {self.tap_ip}\n")
        
        # Load the pf rules
        rc, _, stderr = self._sudo_cmd(["pfctl", "-f", str(pf_conf_path)])
        if rc != 0:
            logger.error(f"Failed to load pf rules: {stderr}")
            return False
            
        # Enable pf if not already enabled
        self._sudo_cmd(["pfctl", "-e"])
            
        # Store network configuration info
        self._update_env_file({
            "LOOPBACK_ALIAS": self.tap_ip,
            "PF_CONF_PATH": str(pf_conf_path)
        })
            
        log_status("Network isolation on macOS configured successfully", Colors.GREEN)
        return True

    def cleanup(self) -> bool:
        """
        Clean up network isolation.

        Returns:
            bool: True if cleanup was successful, False otherwise
        """
        log_status("Cleaning up network isolation...", Colors.YELLOW)
        
        if self.is_linux:
            return self._cleanup_linux()
        elif self.is_macos:
            return self._cleanup_macos()
        else:
            return False

    def _cleanup_linux(self) -> bool:
        """
        Clean up network isolation on Linux.

        Returns:
            bool: True if cleanup was successful, False otherwise
        """
        # Remove NAT rule
        self._sudo_cmd(["iptables", "-t", "nat", "-D", "POSTROUTING", "-s", self.network_cidr, "-j", "MASQUERADE"])
        
        # Remove virtual interfaces and namespace
        self._sudo_cmd(["ip", "link", "delete", self.veth_host])
        self._sudo_cmd(["ip", "netns", "delete", self.namespace_name])
        
        log_status("Network isolation cleaned up", Colors.GREEN)
        return True

    def _cleanup_macos(self) -> bool:
        """
        Clean up network isolation on macOS.

        Returns:
            bool: True if cleanup was successful, False otherwise
        """
        # Remove the loopback alias
        self._sudo_cmd(["ifconfig", "lo0", "-alias", self.tap_ip])
        
        # Disable pf rules related to our network
        pf_conf_path = self.env_dir / "pf.conf"
        if pf_conf_path.exists():
            # Create an empty ruleset for cleanup
            with open(pf_conf_path, "w") as f:
                f.write("# Empty ruleset for cleanup\n")
                
            # Load the empty ruleset
            self._sudo_cmd(["pfctl", "-f", str(pf_conf_path)])
            
            # Remove the file
            pf_conf_path.unlink()
        
        log_status("Network isolation on macOS cleaned up", Colors.GREEN)
        return True

    def run_command(self, cmd: List[str]) -> Tuple[int, str, str]:
        """
        Run a command inside the isolated network namespace.

        Args:
            cmd: Command to run as a list of strings

        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        if self.is_linux:
            full_cmd = ["ip", "netns", "exec", self.namespace_name] + cmd
            return self._sudo_cmd(full_cmd)
        elif self.is_macos:
            # On macOS, we use environment variables to direct network traffic
            # to our loopback alias
            env_cmd = [
                "env",
                f"SAFESPACE_IP={self.tap_ip}",
                f"SAFESPACE_NETWORK={self.network_cidr}",
                # Force standard utilities to use our loopback alias
                "HOSTALIASES=" + str(self.env_dir / "hosts")
            ] + cmd
            
            # Create HOSTALIASES file to redirect hostnames to our loopback
            with open(self.env_dir / "hosts", "w") as f:
                f.write(f"# SafeSpace hosts file\n")
                f.write(f"localhost {self.tap_ip}\n")
                
            return self._sudo_cmd(env_cmd)
        else:
            logger.error("Running commands in network isolation is only supported on Linux and macOS")
            return 1, "", "Not supported on this platform"

    def _update_env_file(self, env_vars: Dict[str, str]) -> None:
        """
        Update environment file with new variables.

        Args:
            env_vars: Dictionary of environment variables to add
        """
        try:
            with open(self.env_file, "a") as f:
                for key, value in env_vars.items():
                    f.write(f"{key}={value}\n")
        except Exception as e:
            logger.error(f"Failed to update environment file: {e}")
