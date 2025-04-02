"""
Configuration for pytest

This module provides configuration for pytest tests in the SafeSpace package.
"""

import pytest
import os
import tempfile
from pathlib import Path

from safespace.testing import TestEnvironment
from safespace.artifact_cache import get_test_artifact_cache


def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "integration: mark tests that integrate multiple components"
    )
    config.addinivalue_line(
        "markers", "performance: mark tests that measure performance"
    )
    config.addinivalue_line(
        "markers", "network: mark tests that require network isolation"
    )
    config.addinivalue_line(
        "markers", "vm: mark tests that require VM functionality"
    )


@pytest.fixture
def temp_safe_environment(tmp_path):
    """
    Create a temporary SafeSpace environment for tests.
    
    Args:
        tmp_path: pytest fixture for temporary directory
        
    Returns:
        Tuple of (SafeEnvironment instance, Path to environment dir)
    """
    from safespace.environment import SafeEnvironment
    
    env_dir = tmp_path / "safe_env"
    env = SafeEnvironment(root_dir=env_dir)
    env.create()
    
    yield env, env_dir
    
    # Cleanup after test
    try:
        env.cleanup()
    except:
        pass


@pytest.fixture
def mock_network_isolation(monkeypatch):
    """
    Mock network isolation for tests.
    
    Args:
        monkeypatch: pytest fixture for patching
        
    Returns:
        Mock object for NetworkIsolation
    """
    from unittest.mock import MagicMock
    from safespace.network import NetworkIsolation
    
    mock_network = MagicMock(spec=NetworkIsolation)
    mock_network.setup.return_value = True
    mock_network.cleanup.return_value = True
    
    # Patch the NetworkIsolation class
    monkeypatch.setattr("safespace.network.NetworkIsolation", lambda *args, **kwargs: mock_network)
    
    return mock_network


@pytest.fixture
def mock_vm_manager(monkeypatch):
    """
    Mock VM manager for tests.
    
    Args:
        monkeypatch: pytest fixture for patching
        
    Returns:
        Mock object for VMManager
    """
    from unittest.mock import MagicMock
    from safespace.vm import VMManager
    
    mock_vm = MagicMock(spec=VMManager)
    mock_vm.setup.return_value = True
    mock_vm.cleanup.return_value = True
    mock_vm.start.return_value = True
    mock_vm.stop.return_value = True
    mock_vm.is_running.return_value = True
    
    # Patch the VMManager class
    monkeypatch.setattr("safespace.vm.VMManager", lambda *args, **kwargs: mock_vm)
    
    return mock_vm


@pytest.fixture(scope="session")
def test_cache_dir():
    """
    Fixture for the test artifact cache directory.
    
    Returns:
        Path: Path to the test cache directory
    """
    # Use a cache directory in the user's home directory
    cache_dir = Path.home() / ".safespace" / "test_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


@pytest.fixture(scope="session")
def test_artifact_cache(test_cache_dir):
    """
    Fixture for the test artifact cache.
    
    Args:
        test_cache_dir: The test cache directory
        
    Returns:
        TestArtifactCache: The test artifact cache
    """
    return get_test_artifact_cache(test_cache_dir)


@pytest.fixture(scope="function")
def test_env(test_artifact_cache):
    """
    Fixture for a test environment.
    
    This fixture creates a temporary test environment for each test,
    and cleans it up after the test is done.
    
    Args:
        test_artifact_cache: The test artifact cache
        
    Returns:
        TestEnvironment: The test environment
    """
    # Create temporary directory for the test
    with tempfile.TemporaryDirectory() as tmpdir:
        env = TestEnvironment(Path(tmpdir))
        env.setup()
        yield env
        env.cleanup() 