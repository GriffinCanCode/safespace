"""
SafeSpace - Safe Environment Creator and Manager

This package creates isolated testing environments with comprehensive safety features.
It provides isolation for network, filesystem, and system resources.
"""

__version__ = "0.1.0"
__author__ = "Griffin"
__email__ = "griffin@griffin-code.com"
__license__ = "MIT"

# Import all components for easier access
from .environment import SafeEnvironment
from .templates import create_from_template, get_available_templates
from .resource_manager import ResourceManager, ResourceConfig, get_resource_manager
from .network import NetworkIsolation
from .vm import VMConfig, VMManager
from .testing import TestEnvironment
from .utils import (
    check_directory_permissions,
    check_directory_writable,
    check_required_tools,
    clean_directory,
    create_secure_directory,
    format_size,
    get_available_space,
    is_command_available,
    log_status,
    run_command,
    setup_logging,
    sudo_command,
)
from .docs.documentation_cli import display_documentation


