"""
Utility functions for SafeSpace

This module provides common utility functions used throughout the SafeSpace package.
"""

import logging
import os
import shutil
import stat
import subprocess
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

# Set up logging
logger = logging.getLogger(__name__)

# Color codes for terminal output
class Colors:
    """ANSI color codes for terminal output"""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    MAGENTA = '\033[0;35m'
    CYAN = '\033[0;36m'
    RESET = '\033[0m'  # Reset to default

def setup_logging(log_level: int = logging.INFO) -> None:
    """Set up logging configuration for the application"""
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def log_status(message: str, color: str = Colors.RESET) -> None:
    """Print a colored status message to the console"""
    print(f"{color}{message}{Colors.RESET}")

def run_command(
    command: str, 
    shell: bool = True, 
    capture_output: bool = True,
    check: bool = False
) -> subprocess.CompletedProcess:
    """Run a shell command with proper error handling"""
    try:
        result = subprocess.run(
            command,
            shell=shell,
            check=check,
            capture_output=capture_output,
            text=True
        )
        return result
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {command}")
        logger.error(f"Error output: {e.stderr}")
        if check:
            raise
        return e

def sudo_command(
    command: str, 
    password: Optional[str] = None, 
    shell: bool = True
) -> subprocess.CompletedProcess:
    """Run a command with sudo privileges"""
    if password:
        # Use echo to pipe the password to sudo
        full_command = f"echo '{password}' | sudo -S {command}"
    else:
        # Use sudo directly (will prompt for password)
        full_command = f"sudo {command}"
    
    return run_command(full_command, shell=shell)

def create_secure_directory(path: Path) -> Path:
    """Create a secure directory with restricted permissions"""
    # Create the directory if it doesn't exist
    path.mkdir(parents=True, exist_ok=True)
    
    # Set permissions to 700 (rwx------)
    path.chmod(0o700)
    
    return path

def check_directory_permissions(path: Path, mode: int = 0o700) -> bool:
    """Check if a directory has the expected permissions"""
    try:
        # Get the current permissions
        current_mode = path.stat().st_mode & 0o777
        
        # Check if permissions match expected
        return current_mode == mode
    except OSError:
        return False

def check_directory_writable(path: Path) -> bool:
    """Check if a directory is writable by creating a test file"""
    if not path.exists():
        return False
    
    test_file = path / ".write_test"
    try:
        with test_file.open("w") as f:
            f.write("test")
        test_file.unlink()
        return True
    except OSError:
        return False

def get_available_space(path: Path) -> int:
    """Get available space in bytes at the specified path"""
    stats = shutil.disk_usage(path)
    return stats.free

def format_size(size_bytes: int) -> str:
    """
    Format a size in bytes to a human-readable format.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        str: Human-readable size
    """
    if size_bytes == 0:
        return "0 B"
        
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024
        i += 1
        
    return f"{size_bytes:.2f} {size_names[i]}"

def is_command_available(command: str) -> bool:
    """Check if a command is available in the system PATH"""
    return shutil.which(command) is not None

def check_required_tools(tools: List[str]) -> Tuple[bool, List[str]]:
    """Check if all required tools are available"""
    missing = []
    for tool in tools:
        if not is_command_available(tool):
            missing.append(tool)
    
    return len(missing) == 0, missing

def clean_directory(path: Path, exclude_patterns: List[str] = None) -> None:
    """Clean a directory by removing all files and subdirectories"""
    if not path.exists():
        return
    
    exclude_patterns = exclude_patterns or []
    
    for item in path.iterdir():
        # Skip excluded patterns
        if any(item.match(pattern) for pattern in exclude_patterns):
            continue
        
        if item.is_file():
            item.unlink()
        elif item.is_dir():
            shutil.rmtree(item)
