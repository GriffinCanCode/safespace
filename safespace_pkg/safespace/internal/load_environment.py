"""
Environment Loader for SafeSpace

This module loads environment variables and configuration for SafeSpace.
"""

import os
import sys
import logging
from pathlib import Path
from typing import Dict, Optional

# Set up logging
logger = logging.getLogger(__name__)

def find_environment_file(start_dir: Optional[Path] = None) -> Optional[Path]:
    """Find the environment file by searching upward from the current directory"""
    if start_dir is None:
        start_dir = Path.cwd()
    
    current_dir = start_dir
    max_depth = 10  # Prevent infinite loops
    
    for _ in range(max_depth):
        env_file = current_dir / ".env"
        if env_file.exists():
            return env_file
        
        # Look for .internal/.env if it exists
        internal_env_file = current_dir / ".internal" / ".env"
        if internal_env_file.exists():
            return internal_env_file
        
        # Stop at filesystem root
        if current_dir.parent == current_dir:
            break
        
        current_dir = current_dir.parent
    
    return None

def load_environment_file(env_file: Path) -> Dict[str, str]:
    """Load environment variables from a file"""
    if not env_file.exists():
        return {}
    
    env_vars = {}
    try:
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                
                key, value = line.split("=", 1)
                env_vars[key.strip()] = value.strip()
    except (OSError, ValueError) as e:
        logger.warning(f"Error loading environment file {env_file}: {e}")
    
    return env_vars

def set_environment_variables(env_vars: Dict[str, str]) -> None:
    """Set environment variables from a dictionary"""
    for key, value in env_vars.items():
        os.environ[key] = value

def load_environment(env_file: Optional[Path] = None) -> Dict[str, str]:
    """Load the environment configuration"""
    if env_file is None:
        env_file = find_environment_file()
    
    if env_file is None:
        logger.warning("No environment file found")
        return {}
    
    env_vars = load_environment_file(env_file)
    set_environment_variables(env_vars)
    
    # Add environment directory to Python path if it exists
    if "SAFE_ENV_ROOT" in env_vars:
        root_dir = Path(env_vars["SAFE_ENV_ROOT"])
        if root_dir.exists():
            # Add root dir to Python path
            if str(root_dir) not in sys.path:
                sys.path.insert(0, str(root_dir))
    
    return env_vars

def get_environment_variable(name: str, default: Optional[str] = None) -> Optional[str]:
    """Get an environment variable with fallback to default"""
    return os.environ.get(name, default)

def is_environment_loaded() -> bool:
    """Check if the environment is loaded"""
    return "SAFE_ENV_ROOT" in os.environ

def get_safe_env_root() -> Optional[Path]:
    """Get the root directory of the safe environment"""
    root_dir = get_environment_variable("SAFE_ENV_ROOT")
    if root_dir is None:
        return None
    return Path(root_dir)

def in_safe_environment() -> bool:
    """Check if we're running inside a safe environment"""
    root_dir = get_safe_env_root()
    if root_dir is None:
        return False
    
    return root_dir.exists()
