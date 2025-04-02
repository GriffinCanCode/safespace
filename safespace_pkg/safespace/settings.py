"""
Settings Module for SafeSpace

This module manages user settings for SafeSpace using YAML configuration files.
It provides functionality to load, save, and manage settings from the user's
home directory.
"""

import logging
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

import yaml
from .utils import log_status, Colors, create_secure_directory

# Set up logging
logger = logging.getLogger(__name__)

# Default settings file location
DEFAULT_SETTINGS_DIR = Path.home() / ".config" / "safespace"
DEFAULT_SETTINGS_FILE = DEFAULT_SETTINGS_DIR / "config.yaml"

@dataclass
class NetworkSettings:
    """Network isolation settings"""
    default_enabled: bool = False
    default_subnet: str = "192.168.100.0/24"
    default_dns_servers: List[str] = field(default_factory=lambda: ["8.8.8.8", "1.1.1.1"])
    enable_nat: bool = True
    create_tap_device: bool = True
    # Network condition simulation settings
    simulate_conditions: bool = False
    default_latency: str = "50ms"  # Default added latency 
    default_jitter: str = "10ms"   # Default jitter for latency
    default_packet_loss: float = 0.0  # Default packet loss as percentage (0-100)
    default_packet_corruption: float = 0.0  # Default packet corruption as percentage (0-100)
    default_packet_reordering: float = 0.0  # Default packet reordering as percentage (0-100)
    default_bandwidth: str = "10mbit"  # Default bandwidth limit

@dataclass
class VMSettings:
    """VM settings"""
    default_enabled: bool = False
    default_memory: str = "1024M"
    default_cpus: int = 2
    default_disk_size: str = "10G"
    default_use_kvm: bool = True
    default_headless: bool = True
    default_alpine_version: str = "3.19.1"
    vm_dir: Optional[str] = None  # Custom directory for VM images

@dataclass
class ContainerSettings:
    """Container settings"""
    default_enabled: bool = False
    default_image: str = "alpine:latest"
    default_memory: str = "512m"
    default_cpus: float = 1.0
    default_storage_size: str = "5G"
    default_network_enabled: bool = False
    default_privileged: bool = False
    default_mount_workspace: bool = True
    prefer_podman: bool = False  # If both Docker and Podman are available, prefer Podman

@dataclass
class TestingSettings:
    """Testing environment settings"""
    default_enabled: bool = False
    install_dependencies: bool = True
    create_example_tests: bool = True
    setup_pre_commit: bool = True
    default_test_runner: str = "pytest"

@dataclass
class EnhancedDevSettings:
    """Enhanced development environment settings"""
    default_enabled: bool = False
    setup_vscode: bool = True
    setup_github_actions: bool = True
    setup_dev_scripts: bool = True
    setup_pre_commit: bool = True

@dataclass
class ResourceSettings:
    """Resource allocation settings"""
    performance_cores_percent: int = 50  # Percentage of cores to use for performance tasks
    max_cache_size_percent: int = 10  # Percentage of total RAM to use for cache
    auto_cleanup_logs: bool = True
    log_retention_days: int = 7
    warn_disk_space_threshold_mb: int = 500  # Warn when less than this much space is available

@dataclass
class GeneralSettings:
    """General settings"""
    sudo_password_timeout: int = 15  # Minutes to cache sudo password
    default_log_level: str = "INFO"
    default_internal_mode: bool = False
    enable_colors: bool = True
    enable_detailed_output: bool = True

@dataclass
class SafeSpaceSettings:
    """SafeSpace main settings container"""
    general: GeneralSettings = field(default_factory=GeneralSettings)
    network: NetworkSettings = field(default_factory=NetworkSettings)
    vm: VMSettings = field(default_factory=VMSettings)
    container: ContainerSettings = field(default_factory=ContainerSettings)
    testing: TestingSettings = field(default_factory=TestingSettings)
    enhanced_dev: EnhancedDevSettings = field(default_factory=EnhancedDevSettings)
    resources: ResourceSettings = field(default_factory=ResourceSettings)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary"""
        return {
            "general": asdict(self.general),
            "network": asdict(self.network),
            "vm": asdict(self.vm),
            "container": asdict(self.container),
            "testing": asdict(self.testing),
            "enhanced_dev": asdict(self.enhanced_dev),
            "resources": asdict(self.resources),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Dict[str, Any]]) -> "SafeSpaceSettings":
        """Create settings from dictionary"""
        settings = cls()
        
        if "general" in data:
            settings.general = GeneralSettings(**data["general"])
        if "network" in data:
            settings.network = NetworkSettings(**data["network"])
        if "vm" in data:
            settings.vm = VMSettings(**data["vm"])
        if "container" in data:
            settings.container = ContainerSettings(**data["container"])
        if "testing" in data:
            settings.testing = TestingSettings(**data["testing"])
        if "enhanced_dev" in data:
            settings.enhanced_dev = EnhancedDevSettings(**data["enhanced_dev"])
        if "resources" in data:
            settings.resources = ResourceSettings(**data["resources"])
        
        return settings

def load_settings(settings_file: Path = DEFAULT_SETTINGS_FILE) -> SafeSpaceSettings:
    """
    Load settings from the config file.
    
    Args:
        settings_file: Path to the settings file
        
    Returns:
        SafeSpaceSettings: Loaded settings
    """
    if not settings_file.exists():
        return create_default_settings(settings_file)
    
    try:
        with open(settings_file, "r") as f:
            data = yaml.safe_load(f)
        
        if not data:
            return create_default_settings(settings_file)
            
        return SafeSpaceSettings.from_dict(data)
    except Exception as e:
        logger.error(f"Failed to load settings: {e}")
        return create_default_settings(settings_file)

def save_settings(settings: SafeSpaceSettings, settings_file: Path = DEFAULT_SETTINGS_FILE) -> bool:
    """
    Save settings to the config file.
    
    Args:
        settings: Settings to save
        settings_file: Path to the settings file
        
    Returns:
        bool: True if settings were saved successfully, False otherwise
    """
    # Create directory if it doesn't exist
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(settings_file, "w") as f:
            yaml.dump(settings.to_dict(), f, default_flow_style=False, sort_keys=False)
        return True
    except Exception as e:
        logger.error(f"Failed to save settings: {e}")
        return False

def create_default_settings(settings_file: Path = DEFAULT_SETTINGS_FILE) -> SafeSpaceSettings:
    """
    Create default settings and save them to the config file.
    
    Args:
        settings_file: Path to the settings file
        
    Returns:
        SafeSpaceSettings: Default settings
    """
    settings = SafeSpaceSettings()
    
    # Create the settings directory if it doesn't exist
    create_secure_directory(settings_file.parent)
    
    # Save settings to file
    save_settings(settings, settings_file)
    
    log_status(f"Created default settings file at {settings_file}", Colors.GREEN)
    return settings

def update_setting(settings_file: Path, section: str, setting: str, value: Any) -> bool:
    """
    Update a specific setting.
    
    Args:
        settings_file: Path to the settings file
        section: Section name (e.g., 'general', 'vm')
        setting: Setting name (e.g., 'default_memory')
        value: New value
        
    Returns:
        bool: True if the setting was updated successfully, False otherwise
    """
    # Load current settings
    settings = load_settings(settings_file)
    
    # Get the section
    if not hasattr(settings, section):
        logger.error(f"Invalid section: {section}")
        return False
    
    section_obj = getattr(settings, section)
    
    # Update the setting
    if not hasattr(section_obj, setting):
        logger.error(f"Invalid setting: {setting}")
        return False
    
    # Convert value to the correct type
    current_value = getattr(section_obj, setting)
    value_type = type(current_value)
    
    try:
        if value_type == bool:
            if isinstance(value, str):
                value = value.lower() in ("true", "yes", "y", "1")
        else:
            value = value_type(value)
    except (ValueError, TypeError):
        logger.error(f"Invalid value type for {setting}. Expected {value_type.__name__}.")
        return False
    
    # Set the value
    setattr(section_obj, setting, value)
    
    # Save settings
    return save_settings(settings, settings_file)

def get_sections() -> List[str]:
    """Get all available settings sections"""
    settings = SafeSpaceSettings()
    return [section for section in settings.to_dict().keys()]

def get_settings_in_section(section: str) -> Dict[str, Any]:
    """
    Get all settings in a specific section.
    
    Args:
        section: Section name
        
    Returns:
        Dict[str, Any]: Dictionary of settings in the section
    """
    settings = SafeSpaceSettings()
    
    if not hasattr(settings, section):
        logger.error(f"Invalid section: {section}")
        return {}
    
    section_obj = getattr(settings, section)
    return asdict(section_obj)

def reset_settings(settings_file: Path = DEFAULT_SETTINGS_FILE) -> bool:
    """
    Reset settings to defaults.
    
    Args:
        settings_file: Path to the settings file
        
    Returns:
        bool: True if settings were reset successfully, False otherwise
    """
    # Create default settings
    settings = SafeSpaceSettings()
    
    # Save settings
    return save_settings(settings, settings_file)

# Global settings instance
_settings_instance = None

def get_settings() -> SafeSpaceSettings:
    """
    Get the global settings instance.
    
    Returns:
        SafeSpaceSettings: Global settings instance
    """
    global _settings_instance
    
    if _settings_instance is None:
        _settings_instance = load_settings()
    
    return _settings_instance

def reload_settings() -> SafeSpaceSettings:
    """
    Reload settings from the config file.
    
    Returns:
        SafeSpaceSettings: Reloaded settings
    """
    global _settings_instance
    _settings_instance = load_settings()
    return _settings_instance 