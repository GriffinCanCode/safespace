"""
Environment Templates for SafeSpace

This module provides predefined environment templates for common testing scenarios.
These templates can be used to quickly set up specific testing environments.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Union, Any

from .environment import SafeEnvironment
from .vm import VMConfig
from .container import ContainerConfig
from .utils import log_status, Colors

# Set up logging
logger = logging.getLogger(__name__)

class EnvironmentTemplate:
    """Base class for environment templates"""
    
    name: str = "base"
    description: str = "Base environment template"
    
    def __init__(self, 
                root_dir: Optional[Path] = None, 
                internal_mode: bool = False,
                sudo_password: Optional[str] = None) -> None:
        """
        Initialize environment template.
        
        Args:
            root_dir: Root directory for the environment
            internal_mode: Whether to use internal mode
            sudo_password: Sudo password for operations requiring elevated privileges
        """
        self.root_dir = root_dir
        self.internal_mode = internal_mode
        self.sudo_password = sudo_password
        self.env = None
    
    def create(self) -> SafeEnvironment:
        """
        Create and configure the environment based on the template.
        
        Returns:
            SafeEnvironment: The configured environment
        """
        # Create base environment
        self.env = SafeEnvironment(
            root_dir=self.root_dir,
            internal_mode=self.internal_mode,
            sudo_password=self.sudo_password
        )
        
        # Set up the environment directory
        if not self.env.create():
            logger.error(f"Failed to create environment for template {self.name}")
            raise RuntimeError(f"Failed to create environment for template {self.name}")
        
        # Apply template-specific configurations
        self._configure()
        
        log_status(f"Created environment using template: {self.name}", Colors.GREEN)
        log_status(f"Description: {self.description}", Colors.RESET)
        
        return self.env
    
    def _configure(self) -> None:
        """
        Configure the environment according to the template.
        This is meant to be overridden by subclasses.
        """
        pass


class BasicTestTemplate(EnvironmentTemplate):
    """Basic testing environment template"""
    
    name = "basic_test"
    description = "Basic testing environment with minimal configuration"
    
    def _configure(self) -> None:
        """Configure basic testing environment"""
        # Set up comprehensive testing environment
        if not self.env.setup_comprehensive_testing():
            logger.warning("Failed to set up comprehensive testing environment")


class IsolatedNetworkTemplate(EnvironmentTemplate):
    """Template for network isolation testing"""
    
    name = "isolated_network"
    description = "Environment with network isolation for testing network boundaries"
    
    def _configure(self) -> None:
        """Configure network isolation environment"""
        # Set up network isolation
        if not self.env.setup_network_isolation():
            logger.warning("Failed to set up network isolation")
            
        # Set up comprehensive testing
        if not self.env.setup_comprehensive_testing():
            logger.warning("Failed to set up comprehensive testing environment")


class VMBasedTemplate(EnvironmentTemplate):
    """Template for VM-based testing"""
    
    name = "vm_based"
    description = "Environment with VM support for isolated execution testing"
    
    def __init__(self, 
                root_dir: Optional[Path] = None, 
                internal_mode: bool = False,
                sudo_password: Optional[str] = None,
                memory: str = "2G",
                cpus: int = 2,
                disk_size: str = "10G",
                headless: bool = True) -> None:
        """
        Initialize VM-based template.
        
        Args:
            root_dir: Root directory for the environment
            internal_mode: Whether to use internal mode
            sudo_password: Sudo password for operations requiring elevated privileges
            memory: Memory size for the VM
            cpus: Number of CPUs for the VM
            disk_size: Disk size for the VM
            headless: Whether to run the VM in headless mode
        """
        super().__init__(root_dir, internal_mode, sudo_password)
        self.memory = memory
        self.cpus = cpus
        self.disk_size = disk_size
        self.headless = headless
    
    def _configure(self) -> None:
        """Configure VM-based testing environment"""
        # Set up VM
        if not self.env.setup_vm(
            memory=self.memory,
            cpus=self.cpus,
            disk_size=self.disk_size,
            headless=self.headless
        ):
            logger.warning("Failed to set up VM")
        
        # Set up comprehensive testing
        if not self.env.setup_comprehensive_testing():
            logger.warning("Failed to set up comprehensive testing environment")


class ContainerBasedTemplate(EnvironmentTemplate):
    """Template for container-based testing"""
    
    name = "container_based"
    description = "Environment with container support for isolated execution testing"
    
    def __init__(self, 
                root_dir: Optional[Path] = None, 
                internal_mode: bool = False,
                sudo_password: Optional[str] = None,
                image: str = "alpine:latest",
                memory: str = "512m",
                cpus: float = 1.0,
                storage_size: str = "5G",
                network_enabled: bool = False,
                privileged: bool = False,
                mount_workspace: bool = True) -> None:
        """
        Initialize container-based template.
        
        Args:
            root_dir: Root directory for the environment
            internal_mode: Whether to use internal mode
            sudo_password: Sudo password for operations requiring elevated privileges
            image: Container image to use
            memory: Memory limit for the container
            cpus: CPU limit for the container
            storage_size: Storage size for the container
            network_enabled: Whether to enable networking
            privileged: Whether to run in privileged mode
            mount_workspace: Whether to mount the workspace directory
        """
        super().__init__(root_dir, internal_mode, sudo_password)
        self.image = image
        self.memory = memory
        self.cpus = cpus
        self.storage_size = storage_size
        self.network_enabled = network_enabled
        self.privileged = privileged
        self.mount_workspace = mount_workspace
    
    def _configure(self) -> None:
        """Configure container-based testing environment"""
        # Set up container
        if not self.env.setup_container(
            image=self.image,
            memory=self.memory,
            cpus=self.cpus,
            storage_size=self.storage_size,
            network_enabled=self.network_enabled,
            privileged=self.privileged,
            mount_workspace=self.mount_workspace
        ):
            logger.warning("Failed to set up container")
        
        # Set up comprehensive testing
        if not self.env.setup_comprehensive_testing():
            logger.warning("Failed to set up comprehensive testing environment")


class ComprehensiveTemplate(EnvironmentTemplate):
    """Template for comprehensive testing with all features enabled"""
    
    name = "comprehensive"
    description = "Full-featured environment with network isolation, VM, container, and enhanced testing"
    
    def __init__(self, 
                root_dir: Optional[Path] = None, 
                internal_mode: bool = False,
                sudo_password: Optional[str] = None,
                memory: str = "4G",
                cpus: int = 4,
                disk_size: str = "20G",
                headless: bool = True,
                container_image: str = "alpine:latest",
                container_memory: str = "1g",
                container_cpus: float = 2.0) -> None:
        """
        Initialize comprehensive template.
        
        Args:
            root_dir: Root directory for the environment
            internal_mode: Whether to use internal mode
            sudo_password: Sudo password for operations requiring elevated privileges
            memory: Memory size for the VM
            cpus: Number of CPUs for the VM
            disk_size: Disk size for the VM
            headless: Whether to run the VM in headless mode
            container_image: Container image to use
            container_memory: Memory limit for the container
            container_cpus: CPU limit for the container
        """
        super().__init__(root_dir, internal_mode, sudo_password)
        self.memory = memory
        self.cpus = cpus
        self.disk_size = disk_size
        self.headless = headless
        self.container_image = container_image
        self.container_memory = container_memory
        self.container_cpus = container_cpus
    
    def _configure(self) -> None:
        """Configure comprehensive testing environment"""
        # Set up network isolation
        if not self.env.setup_network_isolation():
            logger.warning("Failed to set up network isolation")
        
        # Set up VM
        if not self.env.setup_vm(
            memory=self.memory,
            cpus=self.cpus,
            disk_size=self.disk_size,
            headless=self.headless
        ):
            logger.warning("Failed to set up VM")
        
        # Set up container
        if not self.env.setup_container(
            image=self.container_image,
            memory=self.container_memory,
            cpus=self.container_cpus,
            network_enabled=True
        ):
            logger.warning("Failed to set up container")
        
        # Set up comprehensive testing environment
        if not self.env.setup_comprehensive_testing():
            logger.warning("Failed to set up comprehensive testing environment")
        
        # Set up enhanced development environment
        if not self.env.setup_enhanced_environment():
            logger.warning("Failed to set up enhanced development environment")


class EnhancedDevelopmentTemplate(EnvironmentTemplate):
    """Template for enhanced development environment"""
    
    name = "enhanced_dev"
    description = "Environment optimized for development with IDE integration and tooling"
    
    def _configure(self) -> None:
        """Configure enhanced development environment"""
        # Set up enhanced development environment
        if not self.env.setup_enhanced_environment():
            logger.warning("Failed to set up enhanced development environment")
        
        # Set up comprehensive testing as well
        if not self.env.setup_comprehensive_testing():
            logger.warning("Failed to set up comprehensive testing environment")


class PerformanceTestTemplate(EnvironmentTemplate):
    """Template for performance testing"""
    
    name = "performance_test"
    description = "Environment configured for performance benchmarking and testing"
    
    def _configure(self) -> None:
        """Configure performance testing environment"""
        # Set up comprehensive testing environment (includes benchmark tests)
        if not self.env.setup_comprehensive_testing():
            logger.warning("Failed to set up comprehensive testing environment")
            
        # Create additional benchmark configuration directory
        benchmark_dir = self.env.root_dir / "benchmarks"
        benchmark_dir.mkdir(exist_ok=True)
        
        # Create benchmark configuration file
        benchmark_config = {
            "iterations": 1000,
            "warmup_iterations": 100,
            "time_unit": "ms",
            "include_overhead": True,
            "save_results": True,
            "output_format": ["json", "csv"],
            "comparison_mode": "ratio"
        }
        
        with open(benchmark_dir / "benchmark_config.json", "w") as f:
            import json
            json.dump(benchmark_config, f, indent=2)


# Template registry
TEMPLATE_REGISTRY = {
    "basic": BasicTestTemplate,
    "network": IsolatedNetworkTemplate,
    "vm": VMBasedTemplate,
    "container": ContainerBasedTemplate,
    "comprehensive": ComprehensiveTemplate,
    "development": EnhancedDevelopmentTemplate,
    "performance": PerformanceTestTemplate
}


def get_available_templates() -> List[Dict[str, str]]:
    """
    Get information about all available templates.
    
    Returns:
        List[Dict[str, str]]: List of template information dictionaries
    """
    return [
        {"id": template_id, "name": template_class.name, "description": template_class.description}
        for template_id, template_class in TEMPLATE_REGISTRY.items()
    ]


def create_from_template(template_id: str, 
                        root_dir: Optional[Path] = None, 
                        internal_mode: bool = False,
                        sudo_password: Optional[str] = None,
                        **kwargs: Any) -> Optional[SafeEnvironment]:
    """
    Create a SafeEnvironment from a predefined template.
    
    Args:
        template_id: ID of the template to use
        root_dir: Root directory for the environment
        internal_mode: Whether to use internal mode
        sudo_password: Sudo password for operations requiring elevated privileges
        **kwargs: Additional template-specific arguments
        
    Returns:
        Optional[SafeEnvironment]: The created environment or None if template not found
    """
    template_class = TEMPLATE_REGISTRY.get(template_id)
    if template_class is None:
        logger.error(f"Template '{template_id}' not found")
        return None
    
    template = template_class(
        root_dir=root_dir,
        internal_mode=internal_mode,
        sudo_password=sudo_password,
        **kwargs
    )
    
    return template.create() 