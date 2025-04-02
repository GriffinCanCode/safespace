"""
Environment Management for SafeSpace

This module provides functionality for creating and managing isolated environments.
"""

import logging
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any
import uuid

from .utils import (
    Colors, 
    log_status, 
    create_secure_directory, 
    check_directory_permissions,
    check_directory_writable,
    get_available_space,
    format_size,
    run_command,
    sudo_command,
    clean_directory
)
from .network import NetworkIsolation
from .vm import VMManager, VMConfig
from .container import ContainerManager, ContainerConfig
from .testing import TestEnvironment
from .settings import get_settings
from .state_db import get_state_db

# Set up logging
logger = logging.getLogger(__name__)

class SafeEnvironment:
    """Manages an isolated environment for testing and development"""
    
    def __init__(
        self, 
        root_dir: Optional[Path] = None, 
        internal_mode: bool = False,
        sudo_password: Optional[str] = None,
        persistent: bool = False,
        env_id: Optional[str] = None,
        env_name: Optional[str] = None
    ) -> None:
        """Initialize a safe environment"""
        # Get settings
        settings = get_settings()
        
        self.internal_mode = internal_mode or settings.general.default_internal_mode
        self.sudo_password = sudo_password
        self.env_vars: Dict[str, str] = {}
        self.network_isolation: Optional[NetworkIsolation] = None
        self.network_enabled = False
        self.vm_manager: Optional[VMManager] = None
        self.vm_enabled = False
        self.container_manager: Optional[ContainerManager] = None
        self.container_enabled = False
        self.test_environment: Optional[TestEnvironment] = None
        self.comprehensive_test_enabled = False
        self.enhanced_dev_enabled = False
        
        # Persistence settings
        self.persistent = persistent
        self.env_id = env_id or str(uuid.uuid4())
        self.env_name = env_name
        
        # Create or set the root directory
        if root_dir is None:
            if internal_mode:
                self.root_dir = Path.cwd() / ".internal"
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                random_suffix = os.urandom(4).hex()
                self.root_dir = Path(tempfile.gettempdir()) / f"safe_env_{timestamp}_{random_suffix}"
        else:
            self.root_dir = root_dir
    
    def create(self) -> bool:
        """Create the safe environment directory structure"""
        log_status(f"Creating safe environment at {self.root_dir}", Colors.YELLOW)
        
        # If internal mode and directory exists, create a backup
        if self.internal_mode and self.root_dir.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = self.root_dir.parent / f"{self.root_dir.name}_backup_{timestamp}"
            
            log_status(f"Creating backup of existing environment at {backup_dir}", Colors.YELLOW)
            
            try:
                shutil.move(str(self.root_dir), str(backup_dir))
            except (OSError, shutil.Error) as e:
                logger.error(f"Failed to create backup: {e}")
                
                # If backup fails, try to remove the existing directory
                log_status("Removing existing directory instead", Colors.RED)
                try:
                    shutil.rmtree(self.root_dir)
                except OSError as e:
                    logger.error(f"Failed to remove existing directory: {e}")
                    return False
        
        # Create the main directory
        try:
            create_secure_directory(self.root_dir)
        except OSError as e:
            logger.error(f"Failed to create secure directory: {e}")
            return False
        
        # Create subdirectories
        subdirs = ["cache", "logs", "data", "tmp"]
        for subdir in subdirs:
            try:
                subdir_path = self.root_dir / subdir
                create_secure_directory(subdir_path)
            except OSError as e:
                logger.error(f"Failed to create subdirectory {subdir}: {e}")
                return False
        
        # Create environment variables file
        self._create_env_file()
        
        # If persistent mode is enabled, save the initial state
        if self.persistent:
            self.save_state()
        
        log_status(f"Safe environment created successfully at {self.root_dir}", Colors.GREEN)
        return True
    
    def _create_env_file(self) -> None:
        """Create a .env file with environment variables"""
        self.env_vars = {
            "SAFE_ENV_ROOT": str(self.root_dir),
            "SAFE_ENV_CACHE": str(self.root_dir / "cache"),
            "SAFE_ENV_LOGS": str(self.root_dir / "logs"),
            "SAFE_ENV_DATA": str(self.root_dir / "data"),
            "SAFE_ENV_TMP": str(self.root_dir / "tmp"),
            "SAFE_ENV_CREATED_AT": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        }
        
        # Add persistence information if enabled
        if self.persistent:
            self.env_vars["SAFE_ENV_PERSISTENT"] = "true"
            self.env_vars["SAFE_ENV_ID"] = self.env_id
            if self.env_name:
                self.env_vars["SAFE_ENV_NAME"] = self.env_name
        
        env_file = self.root_dir / ".env"
        with open(env_file, "w") as f:
            for key, value in self.env_vars.items():
                f.write(f"{key}={value}\n")
    
    def check_health(self) -> Tuple[bool, List[str]]:
        """Check the health of the environment directory"""
        issues: List[str] = []
        
        # Check if directory exists
        if not self.root_dir.exists():
            issues.append("Environment directory does not exist")
            return False, issues
        
        # Check directory permissions
        if not check_directory_permissions(self.root_dir, 0o700):
            issues.append("Directory permissions are not secure (should be 700)")
        
        # Check if directory is writable
        if not check_directory_writable(self.root_dir):
            issues.append("Directory is not writable")
        
        # Check available space
        available_space = get_available_space(self.root_dir)
        if available_space < 1024 * 1024 * 1024:  # Less than 1GB
            issues.append(f"Less than 1GB of space available ({format_size(available_space)})")
        
        # Check subdirectories
        for subdir in ["cache", "logs", "data", "tmp"]:
            subdir_path = self.root_dir / subdir
            if not subdir_path.exists():
                issues.append(f"Subdirectory '{subdir}' does not exist")
        
        return len(issues) == 0, issues
    
    def clean_cache(self) -> None:
        """Clean cache and temporary files"""
        clean_directory(self.root_dir / "cache")
        clean_directory(self.root_dir / "tmp")
        log_status("Cache and temporary files cleared", Colors.GREEN)
    
    def perform_gc(self) -> None:
        """Perform garbage collection"""
        # Remove old log files (older than 1 day)
        log_dir = self.root_dir / "logs"
        if log_dir.exists():
            for log_file in log_dir.glob("*"):
                if log_file.is_file():
                    file_age = datetime.now().timestamp() - log_file.stat().st_mtime
                    if file_age > 86400:  # Older than 1 day (24h * 60m * 60s)
                        try:
                            log_file.unlink()
                        except OSError as e:
                            logger.warning(f"Failed to remove old log file {log_file}: {e}")
        
        # Clear any temporary files older than 1 hour
        tmp_dir = self.root_dir / "tmp"
        if tmp_dir.exists():
            for tmp_file in tmp_dir.glob("*"):
                if tmp_file.is_file():
                    file_age = datetime.now().timestamp() - tmp_file.stat().st_mtime
                    if file_age > 3600:  # Older than 1 hour (60m * 60s)
                        try:
                            tmp_file.unlink()
                        except OSError as e:
                            logger.warning(f"Failed to remove old temporary file {tmp_file}: {e}")
        
        log_status("Garbage collection completed", Colors.GREEN)
    
    def setup_network_isolation(self, sudo_password: Optional[str] = None) -> bool:
        """
        Set up network isolation for the environment.
        
        Args:
            sudo_password: Optional sudo password for privileged operations
            
        Returns:
            bool: True if setup was successful, False otherwise
        """
        if self.network_isolation is not None:
            logger.warning("Network isolation already set up")
            return True
            
        # Use provided sudo_password or the one set in the environment
        sudo_pwd = sudo_password or self.sudo_password
        self.network_isolation = NetworkIsolation(self.root_dir, sudo_pwd)
        if self.network_isolation.setup():
            self.network_enabled = True
            
            # Add to environment variables
            with open(self.root_dir / ".env", "a") as f:
                f.write("NETWORK_ENABLED=true\n")
                
            return True
        return False
    
    def setup_network_conditions(self, 
                                latency: Optional[str] = None, 
                                jitter: Optional[str] = None,
                                packet_loss: Optional[float] = None,
                                packet_corruption: Optional[float] = None,
                                packet_reordering: Optional[float] = None,
                                bandwidth: Optional[str] = None) -> bool:
        """
        Set up network condition simulation.
        
        Args:
            latency: Added latency (e.g., "100ms")
            jitter: Jitter for latency (e.g., "10ms")
            packet_loss: Packet loss as percentage (0-100)
            packet_corruption: Packet corruption as percentage (0-100)
            packet_reordering: Packet reordering as percentage (0-100)
            bandwidth: Bandwidth limit (e.g., "1mbit")
            
        Returns:
            bool: True if setup was successful, False otherwise
        """
        if not self.network_enabled or self.network_isolation is None:
            logger.error("Network isolation not enabled or not set up")
            return False
            
        # Set up network conditions through the network isolation instance
        result = self.network_isolation.setup_network_conditions(
            latency=latency,
            jitter=jitter,
            packet_loss=packet_loss,
            packet_corruption=packet_corruption,
            packet_reordering=packet_reordering,
            bandwidth=bandwidth
        )
        
        if result:
            # Add to environment variables
            with open(self.root_dir / ".env", "a") as f:
                f.write("NETWORK_CONDITIONS_ENABLED=true\n")
                if latency:
                    f.write(f"NETWORK_LATENCY={latency}\n")
                if packet_loss:
                    f.write(f"NETWORK_PACKET_LOSS={packet_loss}\n")
                if bandwidth:
                    f.write(f"NETWORK_BANDWIDTH={bandwidth}\n")
                
            log_status(f"Network conditions simulation enabled", Colors.GREEN)
            return True
            
        return False
        
    def update_network_conditions(self,
                                 latency: Optional[str] = None, 
                                 jitter: Optional[str] = None,
                                 packet_loss: Optional[float] = None,
                                 packet_corruption: Optional[float] = None,
                                 packet_reordering: Optional[float] = None,
                                 bandwidth: Optional[str] = None) -> bool:
        """
        Update network condition simulation parameters.
        
        Args:
            latency: Added latency (e.g., "100ms")
            jitter: Jitter for latency (e.g., "10ms")
            packet_loss: Packet loss as percentage (0-100)
            packet_corruption: Packet corruption as percentage (0-100)
            packet_reordering: Packet reordering as percentage (0-100)
            bandwidth: Bandwidth limit (e.g., "1mbit")
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        if not self.network_enabled or self.network_isolation is None:
            logger.error("Network isolation not enabled or not set up")
            return False
            
        return self.network_isolation.update_network_conditions(
            latency=latency,
            jitter=jitter,
            packet_loss=packet_loss,
            packet_corruption=packet_corruption,
            packet_reordering=packet_reordering,
            bandwidth=bandwidth
        )
        
    def reset_network_conditions(self) -> bool:
        """
        Reset network conditions to normal operation.
        
        Returns:
            bool: True if reset was successful, False otherwise
        """
        if not self.network_enabled or self.network_isolation is None:
            logger.error("Network isolation not enabled or not set up")
            return False
            
        result = self.network_isolation.reset_network_conditions()
        
        if result:
            log_status("Network conditions reset to normal", Colors.GREEN)
            
        return result
        
    def get_network_conditions(self) -> Dict[str, Any]:
        """
        Get current network condition settings.
        
        Returns:
            Dict[str, Any]: Dictionary of current network conditions or empty dict if not enabled
        """
        if not self.network_enabled or self.network_isolation is None:
            logger.warning("Network isolation not enabled or not set up")
            return {}
            
        return self.network_isolation.get_current_network_conditions()
    
    def setup_vm(self, 
                memory: Optional[str] = None, 
                cpus: Optional[int] = None, 
                disk_size: Optional[str] = None,
                headless: bool = False
                ) -> bool:
        """
        Set up a virtual machine for the environment.
        
        Args:
            memory: Memory size for the VM (e.g., '2G')
            cpus: Number of CPUs for the VM
            disk_size: Disk size for the VM (e.g., '20G')
            headless: Whether to run the VM in headless mode
            
        Returns:
            bool: True if setup was successful, False otherwise
        """
        if self.vm_manager is not None:
            logger.warning("VM already set up")
            return True
            
        # Create VM configuration
        vm_config = VMConfig(
            memory=memory or "1024M",
            cpus=cpus or 2,
            disk_size=disk_size or "10G",
            use_network=self.network_enabled,
            headless=headless
        )
        
        # Create VM manager
        self.vm_manager = VMManager(self.root_dir, self.sudo_password, vm_config)
        
        # If network is enabled, set the namespace
        if self.network_enabled and self.network_isolation is not None:
            self.vm_manager.set_network_namespace(self.network_isolation.namespace_name)
        
        # Set up VM
        if self.vm_manager.setup():
            self.vm_enabled = True
            return True
        
        self.vm_manager = None
        return False
    
    def setup_container(self,
                      image: Optional[str] = None,
                      memory: Optional[str] = None, 
                      cpus: Optional[float] = None, 
                      storage_size: Optional[str] = None,
                      network_enabled: bool = False,
                      privileged: bool = False,
                      mount_workspace: bool = True
                      ) -> bool:
        """
        Set up a container for the environment.
        
        Args:
            image: Container image to use (e.g., 'alpine:latest')
            memory: Memory limit for the container (e.g., '512m')
            cpus: CPU limit for the container (e.g., 1.0)
            storage_size: Storage size for the container (e.g., '5G')
            network_enabled: Whether to enable networking
            privileged: Whether to run in privileged mode
            mount_workspace: Whether to mount the workspace directory
            
        Returns:
            bool: True if setup was successful, False otherwise
        """
        if self.container_manager is not None:
            logger.warning("Container already set up")
            return True
            
        # Create container configuration
        container_config = ContainerConfig(
            image=image or "alpine:latest",
            memory=memory or "512m",
            cpus=cpus or 1.0,
            storage_size=storage_size or "5G",
            network_enabled=network_enabled,
            privileged=privileged,
            mount_workspace=mount_workspace
        )
        
        # Create container manager
        self.container_manager = ContainerManager(self.root_dir, self.sudo_password, container_config)
        
        # Set up container
        if self.container_manager.setup():
            self.container_enabled = True
            return True
        
        self.container_manager = None
        return False
    
    def setup_comprehensive_testing(self) -> bool:
        """
        Set up a comprehensive testing environment.
        
        Returns:
            bool: True if setup was successful, False otherwise
        """
        # Get settings
        settings = get_settings()
        testing_settings = settings.testing
        
        if self.test_environment is not None and self.comprehensive_test_enabled:
            logger.warning("Comprehensive testing environment already set up")
            return True
            
        # Create test environment manager if it doesn't exist
        if self.test_environment is None:
            self.test_environment = TestEnvironment(self.root_dir)
        
        # Set up comprehensive testing environment
        if self.test_environment.setup_comprehensive_testing():
            self.comprehensive_test_enabled = True
            
            # Add to environment variables
            with open(self.root_dir / ".env", "a") as f:
                f.write("COMPREHENSIVE_TEST_ENABLED=true\n")
                
            return True
        return False
    
    def setup_enhanced_environment(self) -> bool:
        """
        Set up an enhanced development environment.
        
        Returns:
            bool: True if setup was successful, False otherwise
        """
        # Get settings
        settings = get_settings()
        enhanced_dev_settings = settings.enhanced_dev
        
        if self.test_environment is not None and self.enhanced_dev_enabled:
            logger.warning("Enhanced development environment already set up")
            return True
            
        # Create test environment manager if it doesn't exist
        if self.test_environment is None:
            self.test_environment = TestEnvironment(self.root_dir)
        
        # Set up enhanced development environment
        if self.test_environment.setup_enhanced_environment():
            self.enhanced_dev_enabled = True
            
            # Add to environment variables
            with open(self.root_dir / ".env", "a") as f:
                f.write("ENHANCED_DEV_ENABLED=true\n")
                
            return True
        return False
    
    def start_vm(self) -> bool:
        """
        Start the virtual machine.
        
        Returns:
            bool: True if VM was started successfully, False otherwise
        """
        if not self.vm_enabled or self.vm_manager is None:
            logger.error("VM not enabled or not set up")
            return False
            
        return self.vm_manager.start()
    
    def stop_vm(self) -> bool:
        """
        Stop the virtual machine.
        
        Returns:
            bool: True if VM was stopped successfully, False otherwise
        """
        if not self.vm_enabled or self.vm_manager is None:
            logger.error("VM not enabled or not set up")
            return False
            
        return self.vm_manager.stop()
    
    def is_vm_running(self) -> bool:
        """
        Check if the virtual machine is running.
        
        Returns:
            bool: True if VM is running, False otherwise
        """
        if not self.vm_enabled or self.vm_manager is None:
            return False
            
        return self.vm_manager.is_running()
    
    def start_container(self) -> bool:
        """
        Start the container.
        
        Returns:
            bool: True if container was started successfully, False otherwise
        """
        if not self.container_enabled or self.container_manager is None:
            logger.error("Container not enabled or not set up")
            return False
            
        return self.container_manager.start()
    
    def stop_container(self) -> bool:
        """
        Stop the container.
        
        Returns:
            bool: True if container was stopped successfully, False otherwise
        """
        if not self.container_enabled or self.container_manager is None:
            logger.error("Container not enabled or not set up")
            return False
            
        return self.container_manager.stop()
    
    def is_container_running(self) -> bool:
        """
        Check if the container is running.
        
        Returns:
            bool: True if container is running, False otherwise
        """
        if not self.container_enabled or self.container_manager is None:
            return False
            
        return self.container_manager.is_running()
        
    def run_in_network(self, cmd: List[str]) -> Tuple[int, str, str]:
        """
        Run a command in the isolated network namespace.
        
        Args:
            cmd: Command to run as a list of strings
            
        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        if not self.network_enabled or self.network_isolation is None:
            logger.error("Network isolation not enabled")
            return 1, "", "Network isolation not enabled"
            
        return self.network_isolation.run_command(cmd)
    
    def run_in_container(self, cmd: List[str]) -> Tuple[int, str, str]:
        """
        Run a command in the container.
        
        Args:
            cmd: Command to run as a list of strings
            
        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        if not self.container_enabled or self.container_manager is None:
            logger.error("Container isolation not enabled")
            return 1, "", "Container isolation not enabled"
            
        return self.container_manager.run_command(cmd)
    
    def cleanup(self, keep_dir: bool = False) -> None:
        """Clean up the environment"""
        # Clean up testing artifacts if enabled
        if (self.comprehensive_test_enabled or self.enhanced_dev_enabled) and self.test_environment is not None:
            self.test_environment.cleanup()
            self.comprehensive_test_enabled = False
            self.enhanced_dev_enabled = False
        
        # Clean up container if enabled
        if self.container_enabled and self.container_manager is not None:
            self.container_manager.cleanup()
            self.container_enabled = False
            self.container_manager = None
        
        # Clean up VM if enabled
        if self.vm_enabled and self.vm_manager is not None:
            self.vm_manager.cleanup()
            self.vm_enabled = False
            self.vm_manager = None
        
        # Clean up network isolation if enabled
        if self.network_enabled and self.network_isolation is not None:
            self.network_isolation.cleanup()
            self.network_enabled = False
            self.network_isolation = None
            
        # Don't cleanup if in internal mode unless explicitly requested
        if self.internal_mode and not keep_dir:
            return
        
        # If persistent mode is enabled, save the final state
        if self.persistent:
            self.save_state()
            log_status(f"Environment preserved for future use. ID: {self.env_id}", Colors.GREEN)
            if self.env_name:
                log_status(f"Name: {self.env_name}", Colors.GREEN)
            # Don't remove the directory in persistent mode
            return
        
        # Kill any processes still using the directory
        if self.root_dir.exists():
            # This uses lsof on Unix systems to find processes using the directory
            cmd = f"lsof +D {self.root_dir} | awk 'NR>1 {{print $2}}'"
            result = run_command(cmd)
            
            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().split("\n")
                # Kill the processes
                pid_list = " ".join(pids)
                if self.sudo_password:
                    sudo_command(f"kill -9 {pid_list}", self.sudo_password)
                else:
                    run_command(f"kill -9 {pid_list}")
        
        if not keep_dir and self.root_dir.exists():
            log_status("Cleaning up environment...", Colors.YELLOW)
            try:
                shutil.rmtree(self.root_dir)
                log_status("Environment cleaned up successfully", Colors.GREEN)
            except OSError as e:
                logger.error(f"Failed to clean up environment: {e}")
                if self.sudo_password:
                    # Try with sudo
                    sudo_command(f"rm -rf {self.root_dir}", self.sudo_password)
    
    def save_state(self) -> bool:
        """
        Save the current environment state to the database.
        Only available in persistent mode.
        
        Returns:
            bool: True if state was saved successfully, False otherwise
        """
        if not self.persistent:
            logger.warning("Cannot save state: Environment is not in persistent mode")
            return False
            
        # Collect state information
        state = {
            "env_vars": self.env_vars,
            "network_enabled": self.network_enabled,
            "vm_enabled": self.vm_enabled,
            "container_enabled": self.container_enabled,
            "comprehensive_test_enabled": self.comprehensive_test_enabled,
            "enhanced_dev_enabled": self.enhanced_dev_enabled,
        }
        
        # Collect metadata
        metadata = {
            "internal_mode": self.internal_mode,
            "created_at": self.env_vars.get("SAFE_ENV_CREATED_AT", datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")),
            "last_saved": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        }
        
        # Save to database
        db = get_state_db()
        result = db.save_environment(
            env_id=self.env_id,
            name=self.env_name,
            root_dir=self.root_dir,
            state=state,
            metadata=metadata
        )
        
        if result:
            log_status(f"Environment state saved successfully with ID: {self.env_id}", Colors.GREEN)
        else:
            log_status("Failed to save environment state", Colors.RED)
            
        return result
    
    @classmethod
    def load_from_state(cls, 
                       env_id: Optional[str] = None, 
                       env_name: Optional[str] = None) -> Optional['SafeEnvironment']:
        """
        Load an environment from a saved state.
        
        Args:
            env_id: The ID of the environment to load
            env_name: The name of the environment to load
            
        Returns:
            SafeEnvironment instance if found, None otherwise
        """
        if not env_id and not env_name:
            logger.error("Either env_id or env_name must be provided")
            return None
            
        # Load from database
        db = get_state_db()
        env_data = db.get_environment(env_id=env_id, name=env_name)
        
        if not env_data:
            return None
            
        # Extract data
        state = env_data['state']
        metadata = env_data['metadata']
        root_dir = Path(env_data['root_dir'])
        
        # Check if directory exists
        if not root_dir.exists():
            log_status(f"Environment directory {root_dir} does not exist", Colors.RED)
            return None
            
        # Create environment instance
        env = cls(
            root_dir=root_dir,
            internal_mode=metadata.get('internal_mode', False),
            persistent=True,
            env_id=env_data['id'],
            env_name=env_data['name']
        )
        
        # Restore state
        env.env_vars = state.get('env_vars', {})
        env.network_enabled = state.get('network_enabled', False)
        env.vm_enabled = state.get('vm_enabled', False)
        env.container_enabled = state.get('container_enabled', False)
        env.comprehensive_test_enabled = state.get('comprehensive_test_enabled', False)
        env.enhanced_dev_enabled = state.get('enhanced_dev_enabled', False)
        
        log_status(f"Environment loaded successfully from state: {env_data['id']}", Colors.GREEN)
        return env
    
    @staticmethod
    def list_saved_environments() -> List[Dict[str, Any]]:
        """
        List all saved environments.
        
        Returns:
            List of dictionaries containing environment summary information
        """
        db = get_state_db()
        environments = db.list_environments()
        return environments
    
    def delete_saved_state(self) -> bool:
        """
        Delete this environment's saved state from the database.
        Does not delete the actual environment directory.
        
        Returns:
            bool: True if deletion was successful, False otherwise
        """
        if not self.persistent:
            logger.warning("Environment is not in persistent mode")
            return False
            
        db = get_state_db()
        result = db.delete_environment(self.env_id)
        
        if result:
            log_status(f"Environment state deleted: {self.env_id}", Colors.GREEN)
        else:
            log_status(f"Failed to delete environment state: {self.env_id}", Colors.RED)
            
        return result
    
    def setup_internal(self) -> bool:
        """Set up an internal testing environment"""
        if not self.internal_mode:
            logger.error("setup_internal can only be called in internal mode")
            return False
        
        log_status("Setting up internal environment...", Colors.YELLOW)
        
        # Create additional directories for internal mode
        for subdir in ["src", "tests", "config", "logs"]:
            create_secure_directory(self.root_dir / subdir)
        
        # Create example configuration, tests, and other files
        self._create_internal_files()
        
        log_status("Internal testing environment setup complete", Colors.GREEN)
        log_status(f"Use 'cd {self.root_dir}' to enter the testing environment", Colors.GREEN)
        return True
    
    def _create_internal_files(self) -> None:
        """Create example files for the internal testing environment"""
        # Create basic configuration files
        config_dir = self.root_dir / "config"
        
        # Create test config
        with open(config_dir / "test_config.json", "w") as f:
            f.write('''{
    "test_mode": "development",
    "logging": {
        "level": "DEBUG",
        "file": "../logs/test.log"
    },
    "data": {
        "path": "../data"
    }
}''')
        
        # Create Python test environment
        tests_dir = self.root_dir / "tests"
        
        # Create conftest.py
        with open(tests_dir / "conftest.py", "w") as f:
            f.write('''import pytest
import sys
import os
import json
from pathlib import Path

@pytest.fixture(scope="session")
def test_config():
    config_path = Path(__file__).parent.parent / "config" / "test_config.json"
    with open(config_path) as f:
        return json.load(f)

@pytest.fixture(scope="session")
def test_data_dir(test_config):
    data_dir = Path(__file__).parent.parent / "data"
    data_dir.mkdir(exist_ok=True)
    return data_dir

@pytest.fixture(scope="session")
def test_log_dir():
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    return log_dir
''')
        
        # Create example test file
        with open(tests_dir / "test_example.py", "w") as f:
            f.write('''import pytest
from pathlib import Path

def test_environment(test_config, test_data_dir, test_log_dir):
    assert test_config["test_mode"] == "development"
    assert test_data_dir.exists()
    assert test_log_dir.exists()
''')
        
        # Create requirements.txt
        with open(self.root_dir / "requirements.txt", "w") as f:
            f.write('''# Testing Framework
pytest>=7.0.0
pytest-cov>=4.0.0
pytest-xdist>=3.0.0
pytest-timeout>=2.1.0
pytest-benchmark>=4.0.0
pytest-mock>=3.10.0
pytest-asyncio>=0.21.0
hypothesis>=6.75.3  # Property-based testing

# Code Quality
black>=23.3.0  # Code formatting
isort>=5.12.0  # Import sorting
flake8>=6.0.0  # Style guide enforcement
mypy>=1.2.0  # Static type checking
pylint>=2.17.0  # Code analysis
bandit>=1.7.5  # Security testing

# Test Utilities
coverage>=7.2.0  # Code coverage
tox>=4.5.1  # Test automation
faker>=18.9.0  # Test data generation
freezegun>=1.2.0  # Time freezing
responses>=0.23.0  # Mock HTTP requests

# Development Tools
python-dotenv>=1.0.0  # Environment management
pre-commit>=3.2.0  # Git hooks
rich>=13.3.5  # Rich text and formatting
''')
        
        # Create .gitignore
        with open(self.root_dir / ".gitignore", "w") as f:
            f.write('''__pycache__/
*.py[cod]
*$py.class
.pytest_cache/
.coverage
htmlcov/
.env
.venv
venv/
ENV/
logs/*.log
data/*
!data/.gitkeep
''')
        
        # Create empty files to preserve directory structure
        data_dir = self.root_dir / "data"
        data_dir.mkdir(exist_ok=True)
        (data_dir / ".gitkeep").touch()
        
        logs_dir = self.root_dir / "logs"
        logs_dir.mkdir(exist_ok=True)
        (logs_dir / ".gitkeep").touch()
        
        # Create README
        with open(self.root_dir / "README.md", "w") as f:
            f.write(f'''# Internal Testing Environment

This is an isolated testing environment created by safespace.

## Directory Structure
- `src/`: Source code under test
- `tests/`: Test files and fixtures
- `data/`: Test data directory
- `config/`: Configuration files
- `logs/`: Log files

## Environment Management
- Create/recreate environment: `safespace internal`
- Clean environment: `safespace internal cleanup` or `safespace internal -c`
  - Removes cache files, logs, and temporary data
  - Cleans virtual environment
  - Preserves source code and tests
  - Resets permissions
- Remove environment completely: `safespace foreclose`
  - Completely removes the environment and all backups
  - Cleans up all associated cache files
  - Removes environment entries from .gitignore
  - Cannot be undone

## Setup
1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # or 'venv\\Scripts\\activate' on Windows
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up pre-commit hooks:
   ```bash
   pre-commit install
   ```

## Development Tools
- **Code Formatting**: Black and isort
- **Linting**: Flake8, Pylint
- **Type Checking**: MyPy
- **Security**: Bandit
- **Testing**: Pytest with plugins for coverage, benchmarking, async, and property-based testing
- **Test Data**: Faker for generating test data
- **Mocking**: pytest-mock and responses for HTTP mocking
- **Development**: Rich for better output formatting

## Running Tests
Basic test run:
```bash
pytest tests/
```

With coverage report:
```bash
pytest tests/ --cov=src --cov-report=html
```

Run benchmarks:
```bash
pytest tests/ --benchmark-only
```

Property-based tests:
```bash
pytest tests/ -v -k "test_property"
```

## Code Quality
Run all quality checks:
```bash
# Format code
black .
isort .

# Run linters
flake8
pylint src tests

# Type checking
mypy src tests

# Security check
bandit -r src
```

## Configuration
- `setup.cfg`: Contains configuration for pytest, coverage, mypy, and other tools
- `.pre-commit-config.yaml`: Git pre-commit hook configuration
- `requirements.txt`: Project dependencies
''')
    
    def cleanup_internal(self) -> None:
        """Clean up the internal environment"""
        if not self.internal_mode:
            logger.error("cleanup_internal can only be called in internal mode")
            return
        
        log_status("Cleaning up internal environment...", Colors.YELLOW)
        
        # Stop any running processes
        cmd = f"lsof +D {self.root_dir} | awk 'NR>1 {{print $2}}' | sort -u"
        result = run_command(cmd)
        
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split("\n")
            # Kill the processes
            pid_list = " ".join(pids)
            run_command(f"kill -9 {pid_list}")
        
        # Remove pytest cache
        for cache_dir in self.root_dir.glob("**/__pycache__"):
            if cache_dir.is_dir():
                shutil.rmtree(cache_dir)
        
        for pytest_cache in self.root_dir.glob("**/.pytest_cache"):
            if pytest_cache.is_dir():
                shutil.rmtree(pytest_cache)
        
        # Clean coverage data
        for coverage_file in self.root_dir.glob(".coverage*"):
            coverage_file.unlink()
        
        htmlcov_dir = self.root_dir / "htmlcov"
        if htmlcov_dir.exists():
            shutil.rmtree(htmlcov_dir)
        
        # Clean logs and temporary data
        clean_directory(self.root_dir / "logs", exclude_patterns=["*.gitkeep"])
        clean_directory(self.root_dir / "tmp")
        clean_directory(self.root_dir / "data", exclude_patterns=["*.gitkeep"])
        
        # Touch gitkeep files to make sure they exist
        (self.root_dir / "data" / ".gitkeep").touch()
        (self.root_dir / "logs" / ".gitkeep").touch()
        
        # Clean virtual environment
        venv_dir = self.root_dir / "venv"
        if venv_dir.exists():
            shutil.rmtree(venv_dir)
        
        # Reset permissions
        run_command(f"chmod -R 700 {self.root_dir}")
        run_command(f"chown -R $(whoami):$(id -gn) {self.root_dir}")
        
        log_status("Internal environment cleaned successfully", Colors.GREEN)
        log_status("You can now recreate the environment with 'safespace internal'", Colors.GREEN)
    
    def foreclose(self) -> None:
        """Completely remove the environment and all backups"""
        if not self.internal_mode:
            logger.error("foreclose can only be called in internal mode")
            return
        
        log_status("Starting environment foreclosure process...", Colors.YELLOW)
        
        # First, run cleanup to ensure all processes are stopped
        self.cleanup_internal()
        
        # Get the current directory
        current_dir = Path.cwd()
        internal_dir = current_dir / ".internal"
        backup_pattern = ".internal_backup_*"
        
        # Find all backup directories
        backup_dirs = list(current_dir.glob(backup_pattern))
        
        # Remove all backup directories
        if backup_dirs:
            log_status("Removing backup directories...", Colors.YELLOW)
            for backup_dir in backup_dirs:
                log_status(f"Removing backup: {backup_dir}", Colors.YELLOW)
                try:
                    shutil.rmtree(backup_dir)
                except OSError:
                    if self.sudo_password:
                        sudo_command(f"rm -rf {backup_dir}", self.sudo_password)
                    else:
                        log_status(f"Failed to remove backup directory: {backup_dir}", Colors.RED)
        
        # Remove the main environment directory
        if internal_dir.exists():
            log_status("Removing internal environment...", Colors.YELLOW)
            try:
                shutil.rmtree(internal_dir)
            except OSError:
                if self.sudo_password:
                    sudo_command(f"rm -rf {internal_dir}", self.sudo_password)
                else:
                    log_status("Failed to remove environment directory", Colors.RED)
