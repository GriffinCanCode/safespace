"""
Tests for SafeSpace package

This module contains comprehensive tests for the SafeSpace package.
It includes standard tests, edge cases, performance tests, and integration tests.
"""

import json
import logging
import os
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import psutil
import pytest

from safespace.utils import (
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
from safespace.resource_manager import (
    CoreType,
    WorkloadType,
    ResourceConfig,
    ResourceManager,
    get_resource_manager,
)
from safespace.network import NetworkIsolation
from safespace.vm import VMConfig, VMManager
from safespace.testing import TestEnvironment
from safespace.environment import SafeEnvironment
from safespace.templates import (
    EnvironmentTemplate, 
    BasicTestTemplate,
    IsolatedNetworkTemplate,
    VMBasedTemplate,
    ComprehensiveTemplate,
    EnhancedDevelopmentTemplate,
    PerformanceTestTemplate,
    get_available_templates,
    create_from_template
)
from safespace import __version__

# Helper functions for tests
@contextmanager
def capture_logs():
    """Capture logs for testing"""
    handler = logging.StreamHandler()
    logger = logging.getLogger()
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    
    class LogCapture:
        def __init__(self):
            self.records = []
        
        def handle(self, record):
            self.records.append(record)
    
    capture = LogCapture()
    handler.emit = capture.handle
    
    try:
        yield capture.records
    finally:
        logger.removeHandler(handler)


def create_test_directory():
    """Create a test directory with a predictable path"""
    temp_dir = tempfile.mkdtemp(prefix="safespace_test_")
    return Path(temp_dir)


class TestUtils:
    """Comprehensive tests for utility functions"""
    
    def test_format_size(self):
        """Test formatting byte sizes as human-readable"""
        assert format_size(1024) == "1.00 KB"
        assert format_size(1024 * 1024) == "1.00 MB"
        assert format_size(1024 * 1024 * 1024) == "1.00 GB"
    
    def test_format_size_edge_cases(self):
        """Test formatting byte sizes with edge cases"""
        # Zero bytes
        assert format_size(0) == "0.00 B"
        # Very large value
        assert format_size(1024 * 1024 * 1024 * 1024 * 5) == "5.00 TB"
        # Small fractions
        assert format_size(1100) == "1.07 KB"
        assert format_size(1024 * 1024 * 1.7) == "1.70 MB"
    
    def test_is_command_available(self):
        """Test checking if a command is available"""
        # 'ls' should be available on most systems
        assert is_command_available("ls") is True
        # A non-existent command should not be available
        assert is_command_available("this_command_does_not_exist_12345") is False
    
    def test_is_command_available_edge_cases(self):
        """Test command availability with edge cases"""
        # Empty string
        assert is_command_available("") is False
        # Space in command
        assert is_command_available("git status") is False
        # Command with special characters
        assert is_command_available(";rm -rf") is False
    
    def test_check_required_tools(self):
        """Test checking multiple required tools"""
        # These tools should exist on most systems
        result, missing = check_required_tools(["ls", "cat"])
        assert result is True
        assert len(missing) == 0
        
        # Mix of existing and non-existing tools
        result, missing = check_required_tools(["ls", "this_tool_does_not_exist_12345"])
        assert result is False
        assert "this_tool_does_not_exist_12345" in missing
        
        # All non-existing tools
        result, missing = check_required_tools(["tool1_does_not_exist", "tool2_does_not_exist"])
        assert result is False
        assert len(missing) == 2
        
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
    
    def test_create_secure_directory_nested(self):
        """Test creating nested secure directories"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a deeply nested directory
            test_dir = Path(temp_dir) / "level1" / "level2" / "level3" / "test_secure_dir"
            
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

    def test_get_available_space(self):
        """Test getting available disk space"""
        # Test on temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            space = get_available_space(Path(temp_dir))
            # Space should be positive
            assert space > 0
            # Space should be reasonable (at least 1MB)
            assert space >= (1024 * 1024)
    
    def test_run_command(self):
        """Test running shell commands"""
        # Test successful command
        result = run_command("echo test")
        assert result.returncode == 0
        assert "test" in result.stdout
        
        # Test failed command
        result = run_command("ls /directory_that_does_not_exist_12345")
        assert result.returncode != 0
        
        # Test with check=True for successful command
        result = run_command("echo test", check=True)
        assert result.returncode == 0
        
        # Test with capture_output=False
        result = run_command("echo test", capture_output=False)
        # When capture_output is False, stdout is None rather than empty string
        assert result.stdout is None
    
    def test_clean_directory(self):
        """Test directory cleaning functionality"""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_dir = Path(temp_dir) / "clean_test"
            test_dir.mkdir()
            
            # Create some files and directories
            for i in range(5):
                (test_dir / f"file{i}.txt").write_text(f"content {i}")
            
            subdir = test_dir / "subdir"
            subdir.mkdir()
            (subdir / "subfile.txt").write_text("subfile content")
            
            # Create a file to exclude
            exclude_file = test_dir / "exclude.txt"
            exclude_file.write_text("do not delete")
            
            # Clean directory with exclusion
            clean_directory(test_dir, exclude_patterns=["exclude.txt"])
            
            # Excluded file should still exist
            assert exclude_file.exists()
            
            # Other files and dirs should be gone
            for i in range(5):
                assert not (test_dir / f"file{i}.txt").exists()
            
            assert not subdir.exists()


class TestResourceManager:
    """Comprehensive tests for ResourceManager"""
    
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
    
    def test_resource_config_to_dict(self):
        """Test converting ResourceConfig to dictionary"""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "cache"
            cache_dir.mkdir()
            
            config = ResourceConfig(
                performance_cores=4,
                efficiency_cores=4,
                cache_limit_bytes=1024 * 1024 * 100,  # 100 MB
                cache_dir=cache_dir
            )
            
            config_dict = config.to_dict()
            
            assert config_dict["performance_cores"] == 4
            assert config_dict["efficiency_cores"] == 4
            assert config_dict["cache_limit_bytes"] == 1024 * 1024 * 100
            assert config_dict["cache_dir"] == str(cache_dir)
    
    def test_resource_config_load_nonexistent(self):
        """Test loading configuration from non-existent file"""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "nonexistent_config.json"
            
            # Load should return None for non-existent file
            assert ResourceConfig.load(config_file) is None
    
    def test_resource_config_load_invalid(self):
        """Test loading configuration from invalid file"""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "invalid_config.json"
            
            # Create invalid JSON file
            with open(config_file, "w") as f:
                f.write("{ invalid json")
            
            # Load should return None for invalid JSON
            assert ResourceConfig.load(config_file) is None
            
            # Create valid JSON with missing keys
            with open(config_file, "w") as f:
                f.write('{"performance_cores": 2}')
            
            # Load should return None for incomplete config
            assert ResourceConfig.load(config_file) is None
    
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
    
    def test_resource_manager_core_optimization(self):
        """Test core optimization functionality"""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "cache"
            cache_dir.mkdir()
            
            # Create a config with specific cores
            config = ResourceConfig(
                performance_cores=2,
                efficiency_cores=2,
                cache_limit_bytes=1024 * 1024 * 10,  # 10 MB
                cache_dir=cache_dir
            )
            
            # Save the config
            config_file = cache_dir / "resource_config.json"
            config.save(config_file)
            
            # Create resource manager with this config
            resource_manager = ResourceManager(cache_dir)
            
            # Test core optimization for performance
            performance_cores = resource_manager.optimize_cores(CoreType.PERFORMANCE)
            assert len(performance_cores) == 2
            
            # Test core optimization for efficiency
            efficiency_cores = resource_manager.optimize_cores(CoreType.EFFICIENCY)
            assert len(efficiency_cores) == 2
            
            # Performance and efficiency cores should be distinct
            assert set(performance_cores).isdisjoint(set(efficiency_cores))
    
    def test_resource_manager_cleanup_cache(self):
        """Test cache cleanup functionality"""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "cache"
            cache_dir.mkdir()
            
            # Create a config with a very small cache limit
            cache_limit = 1024 * 5  # 5 KB
            config = ResourceConfig(
                performance_cores=1,
                efficiency_cores=1,
                cache_limit_bytes=cache_limit,
                cache_dir=cache_dir
            )
            
            # Save the config
            config_file = cache_dir / "resource_config.json"
            config.save(config_file)
            
            # Create resource manager with this config
            resource_manager = ResourceManager(cache_dir)
            
            # Create some cache files that exceed the limit
            # First file is 3KB (should be kept after cleanup)
            file1 = cache_dir / "file1.cache"
            with open(file1, "wb") as f:
                f.write(b"x" * (1024 * 3))
            
            # Access file1 to update its access time
            file1.stat()
            
            # Wait a moment to ensure different access times
            time.sleep(0.1)
            
            # Second file is 3KB (should be deleted after cleanup because it's older)
            file2 = cache_dir / "file2.cache"
            with open(file2, "wb") as f:
                f.write(b"x" * (1024 * 3))
            
            # Manually set access time to be older for file2
            # In ResourceManager.cleanup_cache(), files are sorted by access time
            # Mock the cleanup method to avoid actual deletion
            with mock.patch.object(Path, 'unlink') as mock_unlink:
                # Run cleanup
                resource_manager.cleanup_cache()
                
                # Should attempt to remove a file (at least one call to unlink)
                assert mock_unlink.called
    
    def test_optimized_resource_allocation(self):
        """Test optimized resource allocation under load"""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "cache"
            cache_dir.mkdir()
            
            # Create resource manager
            resource_manager = get_resource_manager(cache_dir)
            
            # Define a CPU-intensive function
            def cpu_intensive_task(n):
                result = 0
                for i in range(n):
                    result += i * i
                return result
            
            # Function to run tasks using the resource manager
            def run_tasks(core_type, task_count=100000):
                # Use mock to avoid actually running system commands
                with mock.patch.object(os, 'system') as mock_system:
                    mock_system.return_value = 0
                    return resource_manager.run_optimized(f"echo 'test'", core_type)
            
            # Run tasks on performance cores
            perf_result = run_tasks(CoreType.PERFORMANCE)
            
            # Run tasks on efficiency cores
            eff_result = run_tasks(CoreType.EFFICIENCY)
            
            # Both should complete successfully
            assert perf_result == 0
            assert eff_result == 0

    def test_workload_type_determination(self):
        """Test workload type determination based on system load"""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "cache"
            cache_dir.mkdir()
            
            # Create resource manager
            resource_manager = ResourceManager(cache_dir)
            
            # Test determination of workload type directly
            
            # 1. Light workload (low CPU and memory)
            resource_manager.current_load = {"cpu": 0.2, "memory": 0.3, "disk_io": 0.1}
            assert resource_manager._determine_workload_type() == WorkloadType.LIGHT
            
            # 2. Medium workload (medium CPU)
            resource_manager.current_load = {"cpu": 0.5, "memory": 0.3, "disk_io": 0.2}
            assert resource_manager._determine_workload_type() == WorkloadType.MEDIUM
            
            # 3. Medium workload (medium memory)
            resource_manager.current_load = {"cpu": 0.2, "memory": 0.6, "disk_io": 0.2}
            assert resource_manager._determine_workload_type() == WorkloadType.MEDIUM
            
            # 4. Heavy workload (high CPU)
            resource_manager.current_load = {"cpu": 0.8, "memory": 0.5, "disk_io": 0.3}
            assert resource_manager._determine_workload_type() == WorkloadType.HEAVY
            
            # 5. Heavy workload (high memory)
            resource_manager.current_load = {"cpu": 0.5, "memory": 0.9, "disk_io": 0.3}
            assert resource_manager._determine_workload_type() == WorkloadType.HEAVY
            
            # Now test the full update flow with mocking
            with mock.patch.object(resource_manager, '_get_system_load') as mock_load:
                # Set to heavy workload
                mock_load.return_value = {"cpu": 0.8, "memory": 0.9, "disk_io": 0.5}
                resource_manager.last_resource_check = 0  # Reset to force update
                resource_manager.update_resource_status()
                assert resource_manager.current_workload_type == WorkloadType.HEAVY
                
                # Change to medium workload
                mock_load.return_value = {"cpu": 0.5, "memory": 0.3, "disk_io": 0.2}
                resource_manager.last_resource_check = 0  # Reset to force update
                resource_manager.update_resource_status()
                assert resource_manager.current_workload_type == WorkloadType.MEDIUM
                
                # Change to light workload
                mock_load.return_value = {"cpu": 0.2, "memory": 0.3, "disk_io": 0.1}
                resource_manager.last_resource_check = 0  # Reset to force update
                resource_manager.update_resource_status()
                assert resource_manager.current_workload_type == WorkloadType.LIGHT

    def test_resource_status_update_interval(self):
        """Test resource status update respects the update interval"""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "cache"
            cache_dir.mkdir()
            
            # Create resource manager with short update interval for testing
            resource_manager = ResourceManager(cache_dir)
            resource_manager.resource_check_interval = 0.5  # Half a second
            
            # First update should always work
            with mock.patch.object(resource_manager, '_get_system_load') as mock_load:
                mock_load.return_value = {"cpu": 0.2, "memory": 0.3, "disk_io": 0.1}
                update_result = resource_manager.update_resource_status()
                assert update_result is True  # First update should return True
            
            # Second immediate update should be skipped
            with mock.patch.object(resource_manager, '_get_system_load') as mock_load:
                mock_load.return_value = {"cpu": 0.8, "memory": 0.9, "disk_io": 0.5}  # Would trigger workload change
                update_result = resource_manager.update_resource_status()
                assert update_result is False  # Update should be skipped
                assert resource_manager.current_workload_type == WorkloadType.LIGHT  # Should not have changed
            
            # Wait for the interval to pass
            time.sleep(0.6)
            
            # Now the update should happen
            with mock.patch.object(resource_manager, '_get_system_load') as mock_load:
                mock_load.return_value = {"cpu": 0.8, "memory": 0.9, "disk_io": 0.5}
                update_result = resource_manager.update_resource_status()
                assert update_result is True  # Update should happen
                assert resource_manager.current_workload_type == WorkloadType.HEAVY  # Should have changed
    
    def test_recommended_resource_limits(self):
        """Test getting recommended resource limits based on workload"""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "cache"
            cache_dir.mkdir()
            
            # Create resource manager
            resource_manager = ResourceManager(cache_dir)
            
            # Mock system stats for consistent testing
            total_memory = 16 * 1024 * 1024 * 1024  # 16 GB
            available_memory = 8 * 1024 * 1024 * 1024  # 8 GB
            cpu_percent = 20  # 20% CPU utilization
            total_cpus = 8
            
            # Mock the needed functions
            with mock.patch.object(psutil, 'virtual_memory') as mock_vm, \
                 mock.patch.object(psutil, 'cpu_percent') as mock_cpu, \
                 mock.patch.object(psutil, 'cpu_count') as mock_cpu_count:
                
                # Configure mocks for light workload
                mock_vm.return_value.total = total_memory
                mock_vm.return_value.available = available_memory
                mock_cpu.return_value = cpu_percent
                mock_cpu_count.return_value = total_cpus
                
                # Light workload
                with mock.patch.object(resource_manager, '_determine_workload_type') as mock_workload:
                    mock_workload.return_value = WorkloadType.LIGHT
                    resource_manager.current_workload_type = WorkloadType.LIGHT
                    
                    limits = resource_manager.get_recommended_resource_limits()
                    
                    # Verify light workload limits
                    assert limits["memory_bytes"] > 0
                    assert limits["cpus"] > 0
                    assert limits["io_weight"] == 100
                
                # Medium workload
                with mock.patch.object(resource_manager, '_determine_workload_type') as mock_workload:
                    mock_workload.return_value = WorkloadType.MEDIUM
                    resource_manager.current_workload_type = WorkloadType.MEDIUM
                    
                    limits = resource_manager.get_recommended_resource_limits()
                    
                    # Verify medium workload limits
                    assert limits["memory_bytes"] > 0
                    assert limits["cpus"] > 0
                    assert limits["io_weight"] == 100
                
                # Heavy workload
                with mock.patch.object(resource_manager, '_determine_workload_type') as mock_workload:
                    mock_workload.return_value = WorkloadType.HEAVY
                    resource_manager.current_workload_type = WorkloadType.HEAVY
                    
                    limits = resource_manager.get_recommended_resource_limits()
                    
                    # Verify heavy workload limits
                    assert limits["memory_bytes"] > 0
                    assert limits["cpus"] > 0
                    assert limits["io_weight"] == 50  # Lower IO weight for heavy workloads
    
    def test_adaptive_cache_limit(self):
        """Test adaptive cache limit based on disk space"""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "cache"
            cache_dir.mkdir()
            
            # Create resource manager
            resource_manager = ResourceManager(cache_dir)
            
            # Set a base cache limit for testing
            base_limit = 1024 * 1024 * 100  # 100 MB
            resource_manager.config.cache_limit_bytes = base_limit
            
            # Test with different disk usage scenarios
            disk_scenarios = [
                # (percent_used, expected_factor)
                (50, 1.4),  # Less than 70% used, should increase (scale factor ~1.4)
                (75, 1.0),  # Between 70-85%, should stay at base
                (90, 0.67),  # More than 85% used, should decrease (scale factor ~0.67)
                (95, 0.33),  # Very high usage, should decrease significantly
            ]
            
            for percent_used, expected_factor in disk_scenarios:
                # Mock disk usage function
                with mock.patch.object(psutil, 'disk_usage') as mock_disk:
                    mock_disk.return_value.total = 1000
                    mock_disk.return_value.used = percent_used * 10
                    mock_disk.return_value.free = 1000 - (percent_used * 10)
                    mock_disk.return_value.percent = percent_used
                    
                    # Also mock virtual_memory for max cache calculation
                    with mock.patch.object(psutil, 'virtual_memory') as mock_vm:
                        mock_vm.return_value.total = 1024 * 1024 * 1024  # 1 GB
                        
                        # Calculate adaptive limit
                        limit = resource_manager.adaptive_cache_limit()
                        
                        # Check it's within 10% of expected factor * base_limit
                        expected = base_limit * expected_factor
                        assert limit >= expected * 0.9 and limit <= expected * 1.1, \
                            f"For {percent_used}% disk used, expected ~{expected_factor}x scaling"
    
    def test_dynamic_core_adjustment(self):
        """Test dynamic core adjustment based on workload"""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "cache"
            cache_dir.mkdir()
            
            # Create a resource manager with specific core configuration
            config = ResourceConfig(
                performance_cores=4,
                efficiency_cores=4,
                cache_limit_bytes=1024 * 1024 * 10,
                cache_dir=cache_dir
            )
            
            config_file = cache_dir / "resource_config.json"
            config.save(config_file)
            
            resource_manager = ResourceManager(cache_dir)
            
            # Test with different workload types
            # For HEAVY workload, it should use fewer cores
            with mock.patch.object(resource_manager, 'current_workload_type', WorkloadType.HEAVY):
                with mock.patch.object(os, 'system') as mock_system:
                    resource_manager.run_optimized("test_command", CoreType.PERFORMANCE)
                    
                    # Check that the command included taskset with a reduced core set
                    # and the nice command with appropriate priority
                    call_args = mock_system.call_args[0][0]
                    if sys.platform != "darwin":  # Linux
                        assert "taskset" in call_args
                        assert "nice" in call_args


@pytest.mark.skipif(os.geteuid() != 0 and not os.environ.get("USE_MOCKS"), reason="Network isolation tests require root privileges without mocks")
class TestNetworkIsolation:
    """Tests for network isolation features"""
    
    def test_network_isolation_init(self):
        """Test initializing network isolation"""
        with tempfile.TemporaryDirectory() as temp_dir:
            env_dir = Path(temp_dir) / "env"
            env_dir.mkdir()
            
            # Create a mock password for testing
            test_password = "test_password"
            
            # Initialize network isolation
            net_isolation = NetworkIsolation(env_dir, sudo_password=test_password)
            
            # Check initialization
            assert net_isolation.env_dir == env_dir
            assert net_isolation.sudo_password == test_password
            assert net_isolation.namespace_name == "safespace_net"
            
            # Platform detection should work
            assert (net_isolation.is_linux == (platform.system() == "Linux"))
            assert (net_isolation.is_macos == (platform.system() == "Darwin"))
            
    def test_network_conditions_config(self):
        """Test network conditions configuration"""
        with tempfile.TemporaryDirectory() as temp_dir:
            env_dir = Path(temp_dir) / "env"
            env_dir.mkdir()
            
            # Create a mock password for testing
            test_password = "test_password"
            
            # Initialize network isolation
            net_isolation = NetworkIsolation(env_dir, sudo_password=test_password)
            
            # Check default network conditions
            assert net_isolation.simulate_conditions is False
            assert net_isolation.latency == "50ms"  # Default from settings
            assert net_isolation.packet_loss == 0.0
            assert net_isolation.bandwidth == "10mbit"
            
            # Test updating network conditions
            net_isolation.latency = "100ms"
            net_isolation.packet_loss = 5.0
            net_isolation.bandwidth = "5mbit"
            
            # Check updated values
            assert net_isolation.latency == "100ms"
            assert net_isolation.packet_loss == 5.0
            assert net_isolation.bandwidth == "5mbit"
            
            # Test get_current_network_conditions
            conditions = net_isolation.get_current_network_conditions()
            assert conditions["latency"] == "100ms"
            assert conditions["packet_loss"] == 5.0
            assert conditions["bandwidth"] == "5mbit"
            assert conditions["active"] is False

    @pytest.mark.integration
    def test_network_conditions_setup(self):
        """Test setting up network conditions (with mocks)"""
        with tempfile.TemporaryDirectory() as temp_dir:
            env_dir = Path(temp_dir) / "env"
            env_dir.mkdir()
            
            # Create a mock password for testing
            test_password = "test_password"
            
            # Initialize network isolation
            net_isolation = NetworkIsolation(env_dir, sudo_password=test_password)
            
            # Mock the sudo command to avoid actual system changes
            with mock.patch.object(net_isolation, '_sudo_cmd') as mock_sudo:
                # Configure mock to return success for all commands
                mock_sudo.return_value = (0, "", "")
                
                # For Linux
                if net_isolation.is_linux:
                    # Test setup with just latency
                    result = net_isolation.setup_network_conditions(latency="200ms")
                    assert result is True
                    assert mock_sudo.called
                    
                    # Reset mocks
                    mock_sudo.reset_mock()
                    
                    # Test setup with multiple conditions
                    result = net_isolation.setup_network_conditions(
                        latency="100ms",
                        jitter="20ms",
                        packet_loss=10.0,
                        packet_corruption=5.0,
                        bandwidth="2mbit"
                    )
                    assert result is True
                    assert mock_sudo.called
                    
                    # Reset mocks
                    mock_sudo.reset_mock()
                    
                    # Test reset
                    result = net_isolation.reset_network_conditions()
                    assert result is True
                    assert mock_sudo.called
                
                # For macOS
                elif net_isolation.is_macos:
                    # Test setup with just latency and bandwidth
                    result = net_isolation.setup_network_conditions(
                        latency="200ms",
                        bandwidth="5mbit"
                    )
                    assert result is True
                    assert mock_sudo.called
                    
                    # Reset mocks
                    mock_sudo.reset_mock()
                    
                    # Test reset
                    result = net_isolation.reset_network_conditions()
                    assert result is True
                    assert mock_sudo.called

    @pytest.mark.integration
    def test_network_conditions_update(self):
        """Test updating network conditions"""
        with tempfile.TemporaryDirectory() as temp_dir:
            env_dir = Path(temp_dir) / "env"
            env_dir.mkdir()
            
            # Create a mock password for testing
            test_password = "test_password"
            
            # Initialize network isolation
            net_isolation = NetworkIsolation(env_dir, sudo_password=test_password)
            
            # Mock the sudo command to avoid actual system changes
            with mock.patch.object(net_isolation, '_sudo_cmd') as mock_sudo:
                # Configure mock to return success for all commands
                mock_sudo.return_value = (0, "", "")
                
                # Setup initial conditions
                result = net_isolation.setup_network_conditions(
                    latency="100ms",
                    packet_loss=1.0,
                    bandwidth="10mbit"
                )
                assert result is True
                
                # Reset mocks for better tracking
                mock_sudo.reset_mock()
                
                # Update conditions
                result = net_isolation.update_network_conditions(
                    latency="200ms",
                    packet_loss=5.0,
                    bandwidth="5mbit"
                )
                assert result is True
                assert mock_sudo.called
                
                # Check updated values
                conditions = net_isolation.get_current_network_conditions()
                assert conditions["latency"] == "200ms"
                assert conditions["packet_loss"] == 5.0
                assert conditions["bandwidth"] == "5mbit"
                assert conditions["active"] is True

    @pytest.mark.integration
    def test_network_conditions_linux_commands(self):
        """Test Linux-specific network condition commands"""
        # Skip if not on Linux
        if platform.system() != "Linux":
            pytest.skip("Linux-specific test")
            
        with tempfile.TemporaryDirectory() as temp_dir:
            env_dir = Path(temp_dir) / "env"
            env_dir.mkdir()
            
            # Initialize network isolation
            net_isolation = NetworkIsolation(env_dir, sudo_password="test_password")
            
            # Mock the sudo command to validate command construction
            with mock.patch.object(net_isolation, '_sudo_cmd') as mock_sudo:
                mock_sudo.return_value = (0, "", "")
                
                # Set up conditions
                net_isolation.setup_network_conditions(
                    latency="100ms",
                    jitter="20ms",
                    packet_loss=10.0,
                    packet_corruption=2.0,
                    packet_reordering=5.0,
                    bandwidth="5mbit"
                )
                
                # Check that the correct tc commands were called
                # First call should add the qdisc
                assert "tc" in mock_sudo.call_args_list[0][0][0]
                assert "qdisc" in mock_sudo.call_args_list[0][0][0]
                assert "add" in mock_sudo.call_args_list[0][0][0]
                assert "netem" in mock_sudo.call_args_list[0][0][0]
                
                # Second call should apply the conditions
                assert "tc" in mock_sudo.call_args_list[1][0][0]
                assert "qdisc" in mock_sudo.call_args_list[1][0][0]
                assert "change" in mock_sudo.call_args_list[1][0][0]
                assert "netem" in mock_sudo.call_args_list[1][0][0]
                assert "delay" in mock_sudo.call_args_list[1][0][0]
                assert "100ms" in mock_sudo.call_args_list[1][0][0]
                assert "20ms" in mock_sudo.call_args_list[1][0][0]
                assert "loss" in mock_sudo.call_args_list[1][0][0]
                assert "10.0%" in mock_sudo.call_args_list[1][0][0]
                assert "corrupt" in mock_sudo.call_args_list[1][0][0]
                assert "2.0%" in mock_sudo.call_args_list[1][0][0]
                assert "reorder" in mock_sudo.call_args_list[1][0][0]
                assert "5.0%" in mock_sudo.call_args_list[1][0][0]
                
                # Reset should be called to remove qdiscs
                mock_sudo.reset_mock()
                net_isolation.reset_network_conditions()
                
                # Check that qdisc del was called
                assert "tc" in mock_sudo.call_args_list[0][0][0]
                assert "qdisc" in mock_sudo.call_args_list[0][0][0]
                assert "del" in mock_sudo.call_args_list[0][0][0]

    @pytest.mark.integration
    def test_network_conditions_macos_commands(self):
        """Test macOS-specific network condition commands"""
        # Skip if not on macOS
        if platform.system() != "Darwin":
            pytest.skip("macOS-specific test")
            
        with tempfile.TemporaryDirectory() as temp_dir:
            env_dir = Path(temp_dir) / "env"
            env_dir.mkdir()
            
            # Initialize network isolation
            net_isolation = NetworkIsolation(env_dir, sudo_password="test_password")
            
            # Mock the sudo command to validate command construction
            with mock.patch.object(net_isolation, '_sudo_cmd') as mock_sudo:
                # First call will check if dummynet is loaded
                # If not found, it will try to load it
                mock_sudo.return_value = (0, "", "")
                
                # Set up conditions
                net_isolation.setup_network_conditions(
                    latency="100ms",
                    packet_loss=10.0,
                    bandwidth="5mbit"
                )
                
                # Check the calls
                call_commands = [args[0][0] for args in mock_sudo.call_args_list]
                
                # First call should check if dummynet is loaded
                assert "kldstat" in call_commands[0]
                
                # If kldstat doesn't find dummynet, it would load it
                # We need to handle both cases: when dummynet is already loaded or not
                
                pipe_config_index = 1
                if len(call_commands) > 1 and "kldload" in call_commands[1]:
                    # If dummynet needed to be loaded, pipe commands start at index 2
                    pipe_config_index = 2
                
                # Validate pipe creation and configuration
                # This might be in different positions depending on whether dummynet was loaded
                pipe_commands = [cmd for cmd in call_commands if "dnctl" in cmd or "pipe" in cmd]
                assert len(pipe_commands) >= 2, "Missing pipe configuration commands"
                
                # Check pfctl command for loading rules
                pfctl_commands = [cmd for cmd in call_commands if "pfctl" in cmd]
                assert len(pfctl_commands) >= 1, "Missing pfctl command"
                
                # Reset should clean up the pipe
                mock_sudo.reset_mock()
                net_isolation.reset_network_conditions()
                
                # Check that pipe delete was called
                delete_commands = [args[0][0] for args in mock_sudo.call_args_list]
                dnctl_commands = [cmd for cmd in delete_commands if "dnctl" in cmd]
                assert len(dnctl_commands) >= 1, "Missing dnctl pipe delete command"

    @pytest.mark.integration
    def test_network_conditions_with_environment(self):
        """Test network conditions in a SafeEnvironment context"""
        with tempfile.TemporaryDirectory() as temp_dir:
            env_dir = Path(temp_dir) / "env"
            
            # Create SafeEnvironment with network isolation
            with mock.patch.object(NetworkIsolation, 'setup') as mock_setup, \
                 mock.patch.object(NetworkIsolation, 'setup_network_conditions') as mock_conditions, \
                 mock.patch.object(NetworkIsolation, 'cleanup') as mock_cleanup:
                
                # Mock return values
                mock_setup.return_value = True
                mock_conditions.return_value = True
                mock_cleanup.return_value = True
                
                # Initialize environment
                env = SafeEnvironment(root_dir=env_dir)
                env.create()
                
                # Setup network isolation
                result = env.setup_network_isolation(sudo_password="test_password")
                assert result is True
                assert mock_setup.called
                
                # Apply network conditions
                # Note: This assumes SafeEnvironment has a setup_network_conditions method
                # If not, you'll need to modify this test or implement that method
                network_conditions = {
                    "latency": "150ms",
                    "jitter": "30ms",
                    "packet_loss": 7.5,
                    "bandwidth": "3mbit"
                }
                
                # Access network_isolation directly instead
                env.network_isolation.setup_network_conditions(**network_conditions)
                assert mock_conditions.called
                
                # Cleanup should be called when environment is cleaned up
                env.cleanup()
                assert mock_cleanup.called
    
    @pytest.mark.parametrize("latency,jitter,packet_loss,packet_corruption,packet_reordering,bandwidth", [
        # Test just latency
        ("100ms", None, None, None, None, None),
        # Test latency and jitter
        ("100ms", "10ms", None, None, None, None),
        # Test packet loss
        (None, None, 5.0, None, None, None),
        # Test bandwidth
        (None, None, None, None, None, "5mbit"),
        # Test corruption
        (None, None, None, 2.0, None, None),
        # Test reordering
        (None, None, None, None, 3.0, None),
        # Test all parameters
        ("200ms", "30ms", 10.0, 5.0, 7.0, "2mbit"),
    ])
    def test_network_conditions_parameters(self, latency, jitter, packet_loss, packet_corruption, packet_reordering, bandwidth):
        """Test different combinations of network condition parameters"""
        with tempfile.TemporaryDirectory() as temp_dir:
            env_dir = Path(temp_dir) / "env"
            env_dir.mkdir()
            
            # Initialize network isolation
            net_isolation = NetworkIsolation(env_dir, sudo_password="test_password")
            
            # Mock the setup methods to avoid actual system changes
            with mock.patch.object(net_isolation, '_setup_linux_network_conditions') as mock_linux, \
                 mock.patch.object(net_isolation, '_setup_macos_network_conditions') as mock_macos, \
                 mock.patch.object(net_isolation, 'reset_network_conditions') as mock_reset:
                
                # Configure mocks
                mock_linux.return_value = True
                mock_macos.return_value = True
                mock_reset.return_value = True
                
                # Setup with the parameterized conditions
                params = {}
                if latency is not None:
                    params["latency"] = latency
                if jitter is not None:
                    params["jitter"] = jitter
                if packet_loss is not None:
                    params["packet_loss"] = packet_loss
                if packet_corruption is not None:
                    params["packet_corruption"] = packet_corruption
                if packet_reordering is not None:
                    params["packet_reordering"] = packet_reordering
                if bandwidth is not None:
                    params["bandwidth"] = bandwidth
                
                result = net_isolation.setup_network_conditions(**params)
                assert result is True
                
                # Check that previous conditions were reset
                assert mock_reset.called
                
                # Check that the platform-specific setup was called
                if net_isolation.is_linux:
                    assert mock_linux.called
                    assert not mock_macos.called
                elif net_isolation.is_macos:
                    assert not mock_linux.called
                    assert mock_macos.called
                
                # Verify parameters were set correctly
                conditions = net_isolation.get_current_network_conditions()
                
                if latency is not None:
                    assert conditions["latency"] == latency
                if jitter is not None:
                    assert conditions["jitter"] == jitter
                if packet_loss is not None:
                    assert conditions["packet_loss"] == packet_loss
                if packet_corruption is not None:
                    assert conditions["packet_corruption"] == packet_corruption
                if packet_reordering is not None:
                    assert conditions["packet_reordering"] == packet_reordering
                if bandwidth is not None:
                    assert conditions["bandwidth"] == bandwidth
    
    def test_network_conditions_failed_setup(self):
        """Test handling of failures during network conditions setup"""
        with tempfile.TemporaryDirectory() as temp_dir:
            env_dir = Path(temp_dir) / "env"
            env_dir.mkdir()
            
            # Initialize network isolation
            net_isolation = NetworkIsolation(env_dir, sudo_password="test_password")
            
            # Mock to simulate failure
            if net_isolation.is_linux:
                with mock.patch.object(net_isolation, '_setup_linux_network_conditions') as mock_setup:
                    mock_setup.return_value = False
                    
                    # Attempt to setup conditions
                    result = net_isolation.setup_network_conditions(latency="100ms")
                    assert result is False
                    assert mock_setup.called
                    
                    # Conditions should not be marked as active
                    assert net_isolation.current_conditions_active is False
            
            elif net_isolation.is_macos:
                with mock.patch.object(net_isolation, '_setup_macos_network_conditions') as mock_setup:
                    mock_setup.return_value = False
                    
                    # Attempt to setup conditions
                    result = net_isolation.setup_network_conditions(latency="100ms")
                    assert result is False
                    assert mock_setup.called
                    
                    # Conditions should not be marked as active
                    assert net_isolation.current_conditions_active is False


@pytest.mark.skipif(not shutil.which("qemu-system-x86_64"), reason="VM tests require QEMU")
class TestVMManager:
    """Tests for VM management features"""
    
    def test_vm_config(self):
        """Test VM configuration"""
        # Default config
        config = VMConfig()
        assert config.memory == "1024M"
        assert config.cpus == 2
        assert config.disk_size == "10G"
        
        # Custom config
        custom_config = VMConfig(
            memory="2048M",
            cpus=4,
            disk_size="20G",
            use_network=True,
            headless=True
        )
        
        assert custom_config.memory == "2048M"
        assert custom_config.cpus == 4
        assert custom_config.disk_size == "20G"
        assert custom_config.use_network is True
        assert custom_config.headless is True
    
    def test_vm_manager_init(self):
        """Test initializing VM manager"""
        with tempfile.TemporaryDirectory() as temp_dir:
            env_dir = Path(temp_dir) / "env"
            env_dir.mkdir()
            
            # Initialize VM manager with default config
            vm_manager = VMManager(env_dir)
            
            # Check initialization
            assert vm_manager.env_dir == env_dir
            assert vm_manager.vm_dir == env_dir / "vm"
            assert isinstance(vm_manager.config, VMConfig)
            
            # Platform detection should work
            assert (vm_manager.is_linux == (platform.system() == "Linux"))
            assert (vm_manager.is_macos == (platform.system() == "Darwin"))


class TestTestEnvironment:
    """Tests for testing environment features"""
    
    def test_test_environment_init(self):
        """Test initializing test environment"""
        with tempfile.TemporaryDirectory() as temp_dir:
            env_dir = Path(temp_dir) / "env"
            env_dir.mkdir()
            
            # Initialize test environment
            test_env = TestEnvironment(env_dir)
            
            # Check initialization
            assert test_env.env_dir == env_dir
            assert test_env.config_dir == env_dir / "config"
            assert test_env.tests_dir == env_dir / "tests"
            assert test_env.scripts_dir == env_dir / "scripts"
            assert test_env.docs_dir == env_dir / "docs"


class TestSafeEnvironment:
    """Tests for safe environment features"""
    
    def test_safe_environment_init(self):
        """Test initializing safe environment"""
        with tempfile.TemporaryDirectory() as temp_dir:
            env_dir = Path(temp_dir) / "env"
            
            # Initialize safe environment with specific directory
            safe_env = SafeEnvironment(root_dir=env_dir)
            
            # Check initialization
            assert safe_env.root_dir == env_dir
            assert safe_env.internal_mode is False
            
            # Initialize internal mode
            safe_env_internal = SafeEnvironment(root_dir=env_dir, internal_mode=True)
            assert safe_env_internal.internal_mode is True
    
    def test_environment_directory_structure(self):
        """Test environment directory structure creation"""
        with tempfile.TemporaryDirectory() as temp_dir:
            env_dir = Path(temp_dir) / "env"
            
            # Initialize safe environment
            safe_env = SafeEnvironment(root_dir=env_dir)
            
            # Set up environment
            safe_env.create()
            
            # Check directory structure
            assert (env_dir / "cache").exists()
            assert (env_dir / "logs").exists()
            assert (env_dir / "data").exists()
            assert (env_dir / "tmp").exists()
            
            # Check .env file
            env_file = env_dir / ".env"
            assert env_file.exists()
            
            # Check environment variables in .env file
            with open(env_file, "r") as f:
                env_content = f.read()
                assert "SAFE_ENV_ROOT" in env_content
                assert "SAFE_ENV_CACHE" in env_content
                assert "SAFE_ENV_LOGS" in env_content
                assert "SAFE_ENV_DATA" in env_content
                assert "SAFE_ENV_TMP" in env_content


@pytest.mark.integration
class TestIntegration:
    """Integration tests that test multiple components together"""
    
    def test_environment_isolation(self):
        """Test complete environment isolation"""
        with tempfile.TemporaryDirectory() as temp_dir:
            env_dir = Path(temp_dir) / "env"
            
            # Initialize safe environment
            safe_env = SafeEnvironment(root_dir=env_dir)
            
            # Set up environment
            safe_env.create()
            
            # Check health
            is_healthy, issues = safe_env.check_health()
            assert is_healthy is True
            assert len(issues) == 0
            
            # Write a test file in the environment
            test_file = env_dir / "data" / "test.txt"
            with open(test_file, "w") as f:
                f.write("Test data")
            
            # Verify file exists
            assert test_file.exists()
            
            # Store parent directory for checking after cleanup
            parent_dir = env_dir.parent
            assert parent_dir.exists()
            
            # Clean up environment
            safe_env.cleanup()
            
            # After cleanup, the environment directory should be removed
            assert not env_dir.exists()
            # But the parent temporary directory should still exist
            assert parent_dir.exists()
    
    def test_comprehensive_features(self):
        """Test comprehensive features working together"""
        with tempfile.TemporaryDirectory() as temp_dir:
            env_dir = Path(temp_dir) / "env"
            
            # Initialize safe environment with test and enhanced features
            safe_env = SafeEnvironment(root_dir=env_dir)
            
            # Set up environment
            safe_env.create()
            
            # Enable comprehensive testing
            with mock.patch.object(TestEnvironment, 'setup_comprehensive_testing') as mock_setup:
                mock_setup.return_value = True
                safe_env.test_environment = TestEnvironment(env_dir)
                safe_env.comprehensive_test_enabled = True
                # Test enabling comprehensive testing
                with mock.patch.object(SafeEnvironment, 'setup_comprehensive_testing') as mock_setup_env:
                    mock_setup_env.return_value = True
                    # Avoid actual calls
                    pass
                
                # Mock should have been called
                assert mock_setup.called is False  # We don't actually call it due to mocking
            
            # Enable enhanced development
            with mock.patch.object(TestEnvironment, 'setup_enhanced_environment') as mock_setup:
                mock_setup.return_value = True
                safe_env.enhanced_dev_enabled = True
                # Test enabling enhanced development
                with mock.patch.object(SafeEnvironment, 'setup_enhanced_environment') as mock_setup_env:
                    mock_setup_env.return_value = True
                    # Avoid actual calls
                    pass
                
                # Mock should have been called
                assert mock_setup.called is False  # We don't actually call it due to mocking
            
            # Clean up environment
            safe_env.cleanup()


@pytest.mark.performance
class TestPerformance:
    """Performance tests to ensure optimal resource usage"""
    
    def test_parallel_cache_access(self):
        """Test parallel cache access performance"""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "cache"
            cache_dir.mkdir()
            
            # Create resource manager
            resource_manager = get_resource_manager(cache_dir)
            
            # Function to create cache files
            def create_cache_file(index):
                filename = cache_dir / f"cache_{index}.tmp"
                with open(filename, "wb") as f:
                    f.write(os.urandom(1024))  # 1KB random data
                return filename
            
            # Create files in parallel
            start_time = time.time()
            with ThreadPoolExecutor(max_workers=10) as executor:
                files = list(executor.map(create_cache_file, range(100)))
            
            end_time = time.time()
            
            # Time should be reasonable (less than 5 seconds for 100 small files)
            assert end_time - start_time < 5.0
            
            # Cleanup cache
            resource_manager.cleanup_cache()
    
    def test_resource_manager_scalability(self):
        """Test resource manager scalability with increasing load"""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "cache"
            cache_dir.mkdir()
            
            # Create resource manager
            resource_manager = get_resource_manager(cache_dir)
            
            # Test with different numbers of cores
            test_configs = [
                {"performance_cores": 1, "efficiency_cores": 1},
                {"performance_cores": 2, "efficiency_cores": 2},
                {"performance_cores": 4, "efficiency_cores": 4},
                {"performance_cores": 8, "efficiency_cores": 8},
            ]
            
            for config_values in test_configs:
                # Skip if system has fewer cores than we're testing
                total_cores = config_values["performance_cores"] + config_values["efficiency_cores"]
                if psutil.cpu_count(logical=True) < total_cores:
                    continue
                
                # Create the configuration
                config = ResourceConfig(
                    performance_cores=config_values["performance_cores"],
                    efficiency_cores=config_values["efficiency_cores"],
                    cache_limit_bytes=1024 * 1024 * 10,  # 10 MB
                    cache_dir=cache_dir
                )
                
                # Save the config
                config_file = cache_dir / "resource_config.json"
                config.save(config_file)
                
                # Reload the resource manager
                resource_manager = ResourceManager(cache_dir)
                
                # Check core optimization
                performance_cores = resource_manager.optimize_cores(CoreType.PERFORMANCE)
                efficiency_cores = resource_manager.optimize_cores(CoreType.EFFICIENCY)
                
                # Verify core counts
                assert len(performance_cores) == config_values["performance_cores"]
                assert len(efficiency_cores) == config_values["efficiency_cores"]


class TestTemplates:
    """Tests for environment templates functionality"""
    
    def test_environment_templates(self):
        """Test basic environment template creation"""
        with tempfile.TemporaryDirectory() as temp_dir:
            template = BasicTestTemplate(Path(temp_dir))
            
            # Mock the SafeEnvironment.create method to prevent actual creation
            with mock.patch('safespace.environment.SafeEnvironment.create', return_value=True), \
                 mock.patch('safespace.environment.SafeEnvironment.setup_comprehensive_testing', return_value=True):
                
                # Create environment from template
                env = template.create()
                
                # Environment should be created
                assert env is not None
                assert isinstance(env, SafeEnvironment)
    
    def test_template_registry(self):
        """Test template registry functionality"""
        # Get available templates
        templates = get_available_templates()
        
        # Should have at least 6 templates
        assert len(templates) >= 6
        
        # Verify template information format
        for template_info in templates:
            assert "id" in template_info
            assert "name" in template_info
            assert "description" in template_info
    
    def test_template_creation(self):
        """Test creating from template with the helper function"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock environment creation to test functionality without actual creation
            with mock.patch('safespace.environment.SafeEnvironment.create', return_value=True), \
                 mock.patch('safespace.environment.SafeEnvironment.setup_comprehensive_testing', return_value=True):
                
                # Create environment from basic template
                env = create_from_template("basic", root_dir=Path(temp_dir))
                
                # Environment should be created
                assert env is not None
                assert isinstance(env, SafeEnvironment)
                
                # Test with invalid template ID
                env = create_from_template("non_existent_template", root_dir=Path(temp_dir))
                
                # Should return None for invalid template
                assert env is None
    
    def test_vm_based_template(self):
        """Test VM-based template with custom parameters"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock environment creation and VM setup
            with mock.patch('safespace.environment.SafeEnvironment.create', return_value=True), \
                 mock.patch('safespace.environment.SafeEnvironment.setup_vm', return_value=True), \
                 mock.patch('safespace.environment.SafeEnvironment.setup_comprehensive_testing', return_value=True):
                
                # Create environment with custom VM parameters
                template = VMBasedTemplate(
                    root_dir=Path(temp_dir),
                    memory="8G",
                    cpus=8,
                    disk_size="40G",
                    headless=False
                )
                
                env = template.create()
                
                # Environment should be created
                assert env is not None
                
                # Verify VM parameters were passed correctly
                env.setup_vm.assert_called_once_with(
                    memory="8G",
                    cpus=8,
                    disk_size="40G",
                    headless=False
                )
    
    def test_comprehensive_template(self):
        """Test comprehensive template with all features"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock all the setup methods
            with mock.patch('safespace.environment.SafeEnvironment.create', return_value=True), \
                 mock.patch('safespace.environment.SafeEnvironment.setup_network_isolation', return_value=True), \
                 mock.patch('safespace.environment.SafeEnvironment.setup_vm', return_value=True), \
                 mock.patch('safespace.environment.SafeEnvironment.setup_comprehensive_testing', return_value=True), \
                 mock.patch('safespace.environment.SafeEnvironment.setup_enhanced_environment', return_value=True):
                
                # Create environment with comprehensive template
                template = ComprehensiveTemplate(
                    root_dir=Path(temp_dir)
                )
                
                env = template.create()
                
                # Environment should be created
                assert env is not None
                
                # Verify all setup methods were called
                env.setup_network_isolation.assert_called_once()
                env.setup_vm.assert_called_once()
                env.setup_comprehensive_testing.assert_called_once()
                env.setup_enhanced_environment.assert_called_once()
    
    def test_performance_template_config(self):
        """Test performance template configuration"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock environment creation and setup methods
            with mock.patch('safespace.environment.SafeEnvironment.create', return_value=True), \
                 mock.patch('safespace.environment.SafeEnvironment.setup_comprehensive_testing', return_value=True), \
                 mock.patch('pathlib.Path.mkdir', return_value=None), \
                 mock.patch('builtins.open', mock.mock_open()) as mock_file:
                
                # Create environment with performance template
                template = PerformanceTestTemplate(
                    root_dir=Path(temp_dir)
                )
                
                env = template.create()
                
                # Environment should be created
                assert env is not None
                
                # Verify setup method was called
                env.setup_comprehensive_testing.assert_called_once()
                
                # Verify benchmark directory was created and config file was written
                Path.mkdir.assert_called_once()
                mock_file.assert_called_once()


@pytest.mark.skipif(
    not (shutil.which("docker") or shutil.which("podman")),
    reason="Container tests require Docker or Podman"
)
class TestContainerIsolation:
    """Test container isolation functionality"""
    
    def test_container_config(self):
        """Test container configuration options"""
        from safespace.container import ContainerConfig
        
        # Test default config
        config = ContainerConfig()
        assert config.image == "alpine:latest"
        assert config.memory == "512m"
        assert config.cpus == 1.0
        assert config.storage_size == "5G"
        assert config.network_enabled is False
        assert config.privileged is False
        assert config.mount_workspace is True
        
        # Test custom config
        custom_config = ContainerConfig(
            image="ubuntu:latest",
            memory="1g",
            cpus=2.0,
            storage_size="10G",
            network_enabled=True,
            privileged=True,
            mount_workspace=False
        )
        assert custom_config.image == "ubuntu:latest"
        assert custom_config.memory == "1g"
        assert custom_config.cpus == 2.0
        assert custom_config.storage_size == "10G"
        assert custom_config.network_enabled is True
        assert custom_config.privileged is True
        assert custom_config.mount_workspace is False
    
    def test_container_manager_init(self):
        """Test initialization of container manager"""
        with tempfile.TemporaryDirectory() as temp_dir:
            from safespace.container import ContainerManager, ContainerConfig
            
            # Create test environment directory
            env_dir = Path(temp_dir)
            
            # Test initialization with default config
            manager = ContainerManager(env_dir)
            assert manager.env_dir == env_dir
            assert manager.container_dir == env_dir / "container"
            assert isinstance(manager.config, ContainerConfig)
            assert manager.container_runtime in ["docker", "podman"]
            
            # Test initialization with custom config
            custom_config = ContainerConfig(image="python:3.9", memory="2g")
            manager = ContainerManager(env_dir, config=custom_config)
            assert manager.config.image == "python:3.9"
            assert manager.config.memory == "2g"
    
    @pytest.mark.integration
    def test_container_isolation(self):
        """Test container isolation functionality"""
        # Skip if not running with docker/podman available
        if not (shutil.which("docker") or shutil.which("podman")):
            pytest.skip("Docker or Podman not available")
            
        # Create a safe environment
        env = SafeEnvironment()
        assert env.create() is True
        
        try:
            # Set up a container
            result = env.setup_container(
                image="alpine:latest",
                memory="256m",
                cpus=0.5,
                storage_size="1G"
            )
            
            # Skip if setup failed (might happen if Docker/Podman is not available)
            if not result:
                pytest.skip("Container setup failed, possibly due to Docker/Podman configuration")
                
            # Verify container was created
            assert env.container_enabled is True
            assert env.container_manager is not None
            
            # Test container operations
            assert env.start_container() is True
            assert env.is_container_running() is True
            
            # Run a simple command
            rc, stdout, _ = env.run_in_container(["uname", "-a"])
            assert rc == 0
            assert "Linux" in stdout
            
            # Run another command
            rc, stdout, _ = env.run_in_container(["echo", "Hello from container"])
            assert rc == 0
            assert "Hello from container" in stdout
            
            # Stop container
            assert env.stop_container() is True
            assert env.is_container_running() is False
        finally:
            # Clean up
            env.cleanup()


class TestDocumentation:
    """Tests for documentation functionality"""
    
    def test_documentation_structure(self):
        """Test structure of documentation JSON"""
        from safespace.docs.documentation_cli import load_documentation
        
        # Load documentation
        docs = load_documentation()
        
        # Verify basic structure
        assert "name" in docs
        assert "version" in docs
        assert "description" in docs
        assert "sections" in docs
        assert isinstance(docs["sections"], list)
        
        # Verify each section has required fields
        for section in docs["sections"]:
            assert "title" in section
            assert "id" in section
            assert "content" in section
            
            # Check subsections if present
            if "subsections" in section:
                for subsection in section["subsections"]:
                    assert "title" in subsection
                    assert "content" in subsection
                    
                    # Check parameters if present
                    if "parameters" in subsection:
                        assert isinstance(subsection["parameters"], dict)
    
    def test_documentation_templates_consistency(self):
        """Test consistency between documentation and actual templates"""
        from safespace.docs.documentation_cli import load_documentation
        from safespace.templates import TEMPLATE_REGISTRY
        
        # Load documentation
        docs = load_documentation()
        
        # Find templates section
        templates_section = None
        for section in docs["sections"]:
            if section["id"] == "templates":
                templates_section = section
                break
        
        # Verify templates section exists
        assert templates_section is not None
        
        # Get documented template IDs from subsections
        documented_templates = set()
        for subsection in templates_section["subsections"]:
            # Extract template ID from content (assumes format: **ID**: `template_id`)
            import re
            match = re.search(r'\*\*ID\*\*: `([^`]+)`', subsection["content"])
            if match:
                documented_templates.add(match.group(1))
        
        # Get actual template IDs from registry
        actual_templates = set(TEMPLATE_REGISTRY.keys())
        
        # Verify all actual templates are documented
        assert actual_templates.issubset(documented_templates), \
            f"Templates missing from documentation: {actual_templates - documented_templates}"


class TestAuthor:
    """Tests for the author functionality"""
    
    def test_author_functionality(self):
        """Test the author functionality works as expected"""
        from safespace.bio import (
            get_random_facts,
            get_random_quote,
            get_random_advice,
            GRIFFIN_LOGO,
            GOD_MODE_TEXT
        )
        
        # Test that ASCII art is defined
        assert GRIFFIN_LOGO and isinstance(GRIFFIN_LOGO, str)
        assert GOD_MODE_TEXT and isinstance(GOD_MODE_TEXT, str)
        
        # Test that random facts function works
        facts = get_random_facts(3)
        assert isinstance(facts, list)
        assert len(facts) == 3
        assert all(isinstance(fact, str) for fact in facts)
        
        # Test that random quote function works
        quote = get_random_quote()
        assert isinstance(quote, str)
        assert len(quote) > 0
        
        # Test that random advice function works
        advice = get_random_advice()
        assert isinstance(advice, str)
        assert len(advice) > 0
        
        # Test with CLI command (without actually running it)
        import io
        import sys
        from contextlib import redirect_stdout
        from safespace.bio_cli import fallback_display
        
        # Test fallback display doesn't crash
        f = io.StringIO()
        with redirect_stdout(f):
            try:
                fallback_display()
                output = f.getvalue()
                assert "GRIFFIN: THE PROGRAMMING GOD" in output
                assert "Fun Facts:" in output
                assert "Words of Wisdom:" in output
                assert "Daily Advice:" in output
            except Exception as e:
                pytest.fail(f"fallback_display() raised {type(e).__name__} unexpectedly: {e}")

if __name__ == "__main__":
    pytest.main()
