"""
Container Isolation Module for SafeSpace

This module provides container isolation functionality for the SafeSpace package.
It creates isolated Docker/Podman containers for a middle ground between
filesystem isolation and full VMs.
"""

import logging
import os
import platform
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any, Union

from .utils import log_status, Colors, run_command, sudo_command, is_command_available

# Set up logging
logger = logging.getLogger(__name__)

@dataclass
class ContainerConfig:
    """Container Configuration"""
    image: str = "alpine:latest"
    memory: str = "512m"
    cpus: float = 1.0
    storage_size: str = "5G"
    network_enabled: bool = False
    privileged: bool = False
    mount_workspace: bool = True


class ContainerManager:
    """Manages containers for SafeSpace environments"""
    
    def __init__(
        self, 
        env_dir: Path, 
        sudo_password: Optional[str] = None,
        config: Optional[ContainerConfig] = None
    ) -> None:
        """
        Initialize ContainerManager.
        
        Args:
            env_dir: Path to the environment directory
            sudo_password: Optional sudo password for privileged operations
            config: Optional container configuration
        """
        self.env_dir = env_dir
        self.sudo_password = sudo_password
        self.container_dir = env_dir / "container"
        self.config = config or ContainerConfig()
        self.is_linux = platform.system() == "Linux"
        self.is_macos = platform.system() == "Darwin"
        self.container_name = f"safespace_{os.urandom(4).hex()}"
        self.container_network = "safespace_net"
        
        # Determine if Docker or Podman is available
        self.use_podman = is_command_available("podman")
        self.use_docker = is_command_available("docker")
        self.container_runtime = "podman" if self.use_podman else "docker"
    
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
        if not self.use_docker and not self.use_podman:
            log_status("Neither Docker nor Podman found. Please install one of them.", Colors.RED)
            return False
            
        # Check if user has permission to use Docker/Podman
        cmd = f"{self.container_runtime} ps"
        result = run_command(cmd)
        
        if result.returncode != 0:
            # Try with sudo
            if self.sudo_password:
                cmd = f"sudo -S {self.container_runtime} ps"
                result = sudo_command(cmd, self.sudo_password)
                if result.returncode != 0:
                    log_status(f"Cannot run {self.container_runtime} even with sudo. Check installation.", Colors.RED)
                    return False
            else:
                log_status(f"Cannot run {self.container_runtime}. You may need sudo privileges.", Colors.RED)
                return False
        
        return True
    
    def setup(self) -> bool:
        """
        Set up the container environment.
        
        Returns:
            bool: True if setup was successful, False otherwise
        """
        log_status(f"Setting up container environment using {self.container_runtime}...", Colors.YELLOW)
        
        # Check requirements
        if not self._check_requirements():
            return False
        
        # Create container directory
        self.container_dir.mkdir(parents=True, exist_ok=True)
        
        # Pull container image
        pull_cmd = f"{self.container_runtime} pull {self.config.image}"
        result = run_command(pull_cmd)
        if result.returncode != 0:
            if self.sudo_password:
                result = sudo_command(pull_cmd, self.sudo_password)
                if result.returncode != 0:
                    log_status(f"Failed to pull container image: {result.stderr}", Colors.RED)
                    return False
            else:
                log_status(f"Failed to pull container image: {result.stderr}", Colors.RED)
                return False
        
        # Create container network if network is enabled
        if self.config.network_enabled:
            network_cmd = f"{self.container_runtime} network create {self.container_network}"
            result = run_command(network_cmd)
            if result.returncode != 0:
                if self.sudo_password:
                    result = sudo_command(network_cmd, self.sudo_password)
                    if result.returncode != 0:
                        log_status(f"Failed to create container network: {result.stderr}", Colors.RED)
                        # Non-critical error, continue without network
                        self.config.network_enabled = False
            
        # Create container run script
        self._create_container_script()
        
        # Add container info to environment file
        self._update_env_file({
            "CONTAINER_ENABLED": "true",
            "CONTAINER_RUNTIME": self.container_runtime,
            "CONTAINER_NAME": self.container_name,
            "CONTAINER_IMAGE": self.config.image,
            "CONTAINER_NETWORK": self.container_network if self.config.network_enabled else "host"
        })
        
        log_status("Container environment setup complete", Colors.GREEN)
        return True
    
    def _create_container_script(self) -> None:
        """Create container run script"""
        # Create container run script
        script_path = self.container_dir / "run_container.sh"
        
        with open(script_path, "w") as f:
            f.write(f"""#!/bin/bash
# SafeSpace Container Runner

CONTAINER_NAME="{self.container_name}"

# Check if container already exists
if {self.container_runtime} ps -a --format '{{{{.Names}}}}' | grep -q "^$CONTAINER_NAME$"; then
    echo "Container $CONTAINER_NAME already exists. Starting it..."
    {self.container_runtime} start $CONTAINER_NAME
    exit $?
fi

# Container doesn't exist, create it
CONTAINER_OPTS="--name $CONTAINER_NAME"
CONTAINER_OPTS+=" --memory={self.config.memory}"
CONTAINER_OPTS+=" --cpus={self.config.cpus}"
""")
            
            # Add network options
            if self.config.network_enabled:
                f.write(f'CONTAINER_OPTS+=" --network={self.container_network}"\n')
            
            # Add storage options
            f.write(f'CONTAINER_OPTS+=" --storage-opt size={self.config.storage_size}"\n')
            
            # Add privileged mode if requested
            if self.config.privileged:
                f.write(f'CONTAINER_OPTS+=" --privileged"\n')
            
            # Add volume mounts
            f.write(f'CONTAINER_OPTS+=" -v {self.container_dir}:/safespace"\n')
            
            # Add workspace mount if requested
            if self.config.mount_workspace:
                f.write(f'CONTAINER_OPTS+=" -v {self.env_dir}:/workspace"\n')
            
            # Command to run
            f.write(f"""
# Create and start the container
echo "Creating container $CONTAINER_NAME..."
{self.container_runtime} run -d $CONTAINER_OPTS {self.config.image} sleep infinity
exit $?
""")
        
        # Make script executable
        os.chmod(script_path, 0o755)
        
        # Create exec script for running commands in containers
        exec_script_path = self.container_dir / "exec_container.sh"
        
        with open(exec_script_path, "w") as f:
            f.write(f"""#!/bin/bash
# SafeSpace Container Command Executor

CONTAINER_NAME="{self.container_name}"

# Check if container exists
if ! {self.container_runtime} ps -a --format '{{{{.Names}}}}' | grep -q "^$CONTAINER_NAME$"; then
    echo "Container $CONTAINER_NAME does not exist. Please run it first."
    exit 1
fi

# Check if container is running
if ! {self.container_runtime} ps --format '{{{{.Names}}}}' | grep -q "^$CONTAINER_NAME$"; then
    echo "Container $CONTAINER_NAME is not running. Starting it..."
    {self.container_runtime} start $CONTAINER_NAME
    if [ $? -ne 0 ]; then
        echo "Failed to start container."
        exit 1
    fi
fi

# Execute command in container
{self.container_runtime} exec -it $CONTAINER_NAME "$@"
""")
        
        # Make script executable
        os.chmod(exec_script_path, 0o755)
    
    def start(self) -> bool:
        """
        Start the container.
        
        Returns:
            bool: True if container was started successfully, False otherwise
        """
        log_status("Starting container...", Colors.YELLOW)
        
        # Check if container is already running
        if self.is_running():
            log_status("Container is already running", Colors.YELLOW)
            return True
        
        # Start container
        script_path = self.container_dir / "run_container.sh"
        result = run_command(str(script_path))
        
        if result.returncode != 0:
            if self.sudo_password:
                result = sudo_command(str(script_path), self.sudo_password)
                if result.returncode != 0:
                    log_status(f"Failed to start container: {result.stderr}", Colors.RED)
                    return False
            else:
                log_status(f"Failed to start container: {result.stderr}", Colors.RED)
                return False
        
        log_status(f"Container {self.container_name} started successfully", Colors.GREEN)
        return True
    
    def stop(self) -> bool:
        """
        Stop the container.
        
        Returns:
            bool: True if container was stopped successfully, False otherwise
        """
        log_status("Stopping container...", Colors.YELLOW)
        
        # Check if container is running
        if not self.is_running():
            log_status("Container is not running", Colors.YELLOW)
            return True
        
        # Stop container
        cmd = f"{self.container_runtime} stop {self.container_name}"
        result = run_command(cmd)
        
        if result.returncode != 0:
            if self.sudo_password:
                result = sudo_command(cmd, self.sudo_password)
                if result.returncode != 0:
                    log_status(f"Failed to stop container: {result.stderr}", Colors.RED)
                    return False
            else:
                log_status(f"Failed to stop container: {result.stderr}", Colors.RED)
                return False
        
        log_status("Container stopped", Colors.GREEN)
        return True
    
    def is_running(self) -> bool:
        """
        Check if container is running.
        
        Returns:
            bool: True if container is running, False otherwise
        """
        cmd = f"{self.container_runtime} ps --format '{{{{.Names}}}}' | grep -q '^{self.container_name}$'"
        result = run_command(cmd)
        return result.returncode == 0
    
    def cleanup(self) -> bool:
        """
        Clean up container resources.
        
        Returns:
            bool: True if cleanup was successful, False otherwise
        """
        log_status("Cleaning up container environment...", Colors.YELLOW)
        
        # Stop container if running
        if self.is_running():
            self.stop()
        
        # Remove container
        cmd = f"{self.container_runtime} rm -f {self.container_name}"
        run_command(cmd)
        
        # Remove network if it exists
        if self.config.network_enabled:
            cmd = f"{self.container_runtime} network rm {self.container_network}"
            run_command(cmd)
        
        log_status("Container environment cleaned up", Colors.GREEN)
        return True
    
    def run_command(self, cmd: List[str]) -> Tuple[int, str, str]:
        """
        Run a command inside the container.
        
        Args:
            cmd: Command to run as a list of strings
            
        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        if not self.is_running():
            if not self.start():
                return 1, "", "Failed to start container"
        
        # Create a temporary script to handle the command execution
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp:
            temp_path = temp.name
            cmd_str = " ".join(cmd)
            temp.write(f"""#!/bin/bash
{self.container_runtime} exec {self.container_name} {cmd_str}
""")
        
        os.chmod(temp_path, 0o755)
        
        # Run the temporary script
        result = run_command(temp_path)
        os.unlink(temp_path)
        
        return result.returncode, result.stdout, result.stderr
    
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