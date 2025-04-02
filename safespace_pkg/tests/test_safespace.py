"""
Tests for SafeSpace package

This module contains tests for the SafeSpace package.
"""

import os
import shutil
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from safespace.utils import (
    check_directory_permissions,
    check_directory_writable,
    create_secure_directory,
    format_size,
    is_command_available,
)
from safespace.resource_manager import ResourceConfig, ResourceManager, get_resource_manager


class TestUtils:
    """Tests for utility functions"""
    
    def test_format_size(self):
        """Test formatting byte sizes as human-readable"""
        assert format_size(1024) == "1.00 KB"
        assert format_size(1024 * 1024) == "1.00 MB"
        assert format_size(1024 * 1024 * 1024) == "1.00 GB"
    
    def test_is_command_available(self):
        """Test checking if a command is available"""
        # 'ls' should be available on most systems
        assert is_command_available("ls") is True
        # A non-existent command should not be available
        assert is_command_available("this_command_does_not_exist_12345") is False
    
    def test_create_secure_directory(self):
        """Test creating a secure directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_dir = Path(temp_dir) / "test_secure_dir"
            
            # Create the directory
            created_dir = create_secure_directory(test_dir)
            
            # Directory should exist
            assert created_dir.exists()
            assert created_dir.is_dir()
            
            # Check permissions (700 on Unix systems)
            if os.name == "posix":
                assert check_directory_permissions(created_dir, 0o700) is True
    
    def test_check_directory_writable(self):
        """Test checking if a directory is writable"""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_dir = Path(temp_dir)
            
            # Directory should be writable
            assert check_directory_writable(test_dir) is True
            
            # Non-existent directory should not be writable
            non_existent_dir = test_dir / "non_existent"
            assert check_directory_writable(non_existent_dir) is False
            
            # Read-only directory should not be writable on Unix systems
            if os.name == "posix":
                readonly_dir = test_dir / "readonly"
                readonly_dir.mkdir()
                readonly_dir.chmod(0o500)  # r-x------
                
                assert check_directory_writable(readonly_dir) is False


class TestResourceManager:
    """Tests for ResourceManager"""
    
    def test_resource_config_from_system(self):
        """Test creating resource configuration from system"""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "cache"
            cache_dir.mkdir()
            
            config = ResourceConfig.from_system(cache_dir)
            
            # Config should have reasonable values
            assert config.performance_cores >= 1
            assert config.efficiency_cores >= 1
            assert config.cache_limit_bytes > 0
            assert config.cache_dir == cache_dir
    
    def test_resource_config_save_load(self):
        """Test saving and loading resource configuration"""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "cache"
            cache_dir.mkdir()
            
            # Create a config
            config = ResourceConfig(
                performance_cores=2,
                efficiency_cores=2,
                cache_limit_bytes=1024 * 1024 * 10,  # 10 MB
                cache_dir=cache_dir
            )
            
            # Save the config
            config_file = cache_dir / "test_config.json"
            config.save(config_file)
            
            # Load the config
            loaded_config = ResourceConfig.load(config_file)
            
            # Check that the loaded config matches the original
            assert loaded_config is not None
            assert loaded_config.performance_cores == config.performance_cores
            assert loaded_config.efficiency_cores == config.efficiency_cores
            assert loaded_config.cache_limit_bytes == config.cache_limit_bytes
            assert loaded_config.cache_dir == config.cache_dir
    
    def test_resource_manager_init(self):
        """Test initializing resource manager"""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "cache"
            
            # Get resource manager
            resource_manager = get_resource_manager(cache_dir)
            
            # Cache directory should exist
            assert cache_dir.exists()
            
            # Config file should be created
            config_file = cache_dir / "resource_config.json"
            assert config_file.exists()
            
            # Resource manager should have a valid config
            assert resource_manager.config is not None
            assert resource_manager.config.performance_cores >= 1
            assert resource_manager.config.efficiency_cores >= 1
            assert resource_manager.config.cache_limit_bytes > 0
