"""
Command-line interface for environment health monitoring.

This module provides CLI commands for checking and maintaining
the health of SafeSpace environments.
"""

import sys
from pathlib import Path
from typing import Optional

import click

from .environment import SafeEnvironment
from .utils import Colors, log_status, clean_directory, check_directory_permissions, check_directory_writable, get_available_space, format_size, create_secure_directory


@click.group()
def health_cli():
    """Check and maintain the health of SafeSpace environments."""
    pass


@health_cli.command(name="check")
@click.option("--environment", "-e", help="Path to environment directory. Uses current or latest if not specified.")
@click.option("--id", help="ID of a persistent environment to check")
@click.option("--name", help="Name of a persistent environment to check")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
@click.option("--detailed", "-d", is_flag=True, help="Show detailed health information")
def check_health(
    environment: Optional[str] = None,
    id: Optional[str] = None,
    name: Optional[str] = None,
    json_output: bool = False,
    detailed: bool = False
):
    """
    Check the health of a SafeSpace environment.
    
    This command runs a comprehensive health check on a SafeSpace environment,
    verifying directory permissions, available space, and resource integrity.
    """
    # Load environment
    env = None
    
    if id or name:
        # Try to load from persistent state
        env = SafeEnvironment.load_from_state(env_id=id, env_name=name)
        if not env:
            log_status(f"Environment not found: {id or name}", Colors.RED)
            sys.exit(1)
    elif environment:
        # Load from specified directory
        env_path = Path(environment)
        if not env_path.exists():
            log_status(f"Environment directory not found: {environment}", Colors.RED)
            sys.exit(1)
        env = SafeEnvironment(root_dir=env_path)
    else:
        # Try to find an environment
        env = SafeEnvironment()
    
    # Run health check
    healthy, issues = env.check_health()
    
    if json_output:
        import json
        result = {
            "healthy": healthy,
            "issues": issues,
            "environment": str(env.root_dir)
        }
        if detailed:
            result["details"] = {
                "directory_exists": env.root_dir.exists(),
                "available_space": get_available_space(env.root_dir) if env.root_dir.exists() else 0,
                "directory_writable": check_directory_writable(env.root_dir) if env.root_dir.exists() else False,
                "secure_permissions": check_directory_permissions(env.root_dir, 0o700) if env.root_dir.exists() else False,
                "subdirectories": {
                    subdir: (env.root_dir / subdir).exists() if env.root_dir.exists() else False
                    for subdir in ["cache", "logs", "data", "tmp"]
                }
            }
        print(json.dumps(result, indent=2))
    else:
        if healthy:
            log_status(f"Environment health check: PASSED", Colors.GREEN)
            log_status(f"Environment: {env.root_dir}", Colors.GREEN)
        else:
            log_status(f"Environment health check: FAILED", Colors.RED)
            log_status(f"Environment: {env.root_dir}", Colors.RED)
            log_status("Issues found:", Colors.RED)
            for issue in issues:
                log_status(f"  - {issue}", Colors.RED)
        
        if detailed and env.root_dir.exists():
            # Add detailed information
            log_status("\nDetailed Health Information:", Colors.CYAN)
            
            # Directory permissions
            if check_directory_permissions(env.root_dir, 0o700):
                log_status("  Directory permissions: Secure (700)", Colors.GREEN)
            else:
                log_status("  Directory permissions: Insecure", Colors.RED)
            
            # Available space
            available_space = get_available_space(env.root_dir)
            if available_space >= 1024 * 1024 * 1024:  # 1GB
                log_status(f"  Available space: {format_size(available_space)}", Colors.GREEN)
            else:
                log_status(f"  Available space: {format_size(available_space)} (Low)", Colors.YELLOW)
            
            # Directory writability
            if check_directory_writable(env.root_dir):
                log_status("  Directory writable: Yes", Colors.GREEN)
            else:
                log_status("  Directory writable: No", Colors.RED)
            
            # Subdirectories
            log_status("  Subdirectories:", Colors.CYAN)
            for subdir in ["cache", "logs", "data", "tmp"]:
                subdir_path = env.root_dir / subdir
                if subdir_path.exists():
                    log_status(f"    - {subdir}: Present", Colors.GREEN)
                else:
                    log_status(f"    - {subdir}: Missing", Colors.RED)
    
    # Return exit code based on health
    sys.exit(0 if healthy else 1)


@health_cli.command(name="fix")
@click.option("--environment", "-e", help="Path to environment directory")
@click.option("--id", help="ID of a persistent environment to fix")
@click.option("--name", help="Name of a persistent environment to fix")
@click.option("--permissions", is_flag=True, help="Fix directory permissions")
@click.option("--directories", is_flag=True, help="Create missing directories")
@click.option("--all", "fix_all", is_flag=True, help="Fix all issues")
def fix_environment(
    environment: Optional[str] = None,
    id: Optional[str] = None,
    name: Optional[str] = None,
    permissions: bool = False,
    directories: bool = False,
    fix_all: bool = False
):
    """
    Fix common health issues in a SafeSpace environment.
    
    This command attempts to fix common health issues like incorrect
    permissions, missing directories, and other configuration problems.
    """
    # Load environment
    env = None
    
    if id or name:
        # Try to load from persistent state
        env = SafeEnvironment.load_from_state(env_id=id, env_name=name)
        if not env:
            log_status(f"Environment not found: {id or name}", Colors.RED)
            sys.exit(1)
    elif environment:
        # Load from specified directory
        env_path = Path(environment)
        if not env_path.exists():
            log_status(f"Environment directory not found: {environment}", Colors.RED)
            sys.exit(1)
        env = SafeEnvironment(root_dir=env_path)
    else:
        # Try to find an environment
        env = SafeEnvironment()
    
    # Check if directory exists
    if not env.root_dir.exists():
        log_status(f"Environment directory does not exist: {env.root_dir}", Colors.RED)
        log_status("Cannot fix non-existent environment", Colors.RED)
        sys.exit(1)
    
    fixed_issues = 0
    
    # Fix permissions if requested
    if fix_all or permissions:
        log_status("Fixing directory permissions...", Colors.YELLOW)
        try:
            env.root_dir.chmod(0o700)
            log_status("Fixed main directory permissions", Colors.GREEN)
            fixed_issues += 1
        except Exception as e:
            log_status(f"Failed to fix main directory permissions: {e}", Colors.RED)
    
    # Fix directories if requested
    if fix_all or directories:
        log_status("Checking for missing directories...", Colors.YELLOW)
        for subdir in ["cache", "logs", "data", "tmp"]:
            subdir_path = env.root_dir / subdir
            if not subdir_path.exists():
                try:
                    create_secure_directory(subdir_path)
                    log_status(f"Created missing directory: {subdir}", Colors.GREEN)
                    fixed_issues += 1
                except Exception as e:
                    log_status(f"Failed to create directory {subdir}: {e}", Colors.RED)
    
    # Run health check after fixes
    healthy, issues = env.check_health()
    
    if healthy:
        log_status(f"Environment is now healthy: {env.root_dir}", Colors.GREEN)
    else:
        log_status(f"Environment still has issues: {env.root_dir}", Colors.YELLOW)
        for issue in issues:
            log_status(f"  - {issue}", Colors.YELLOW)
    
    log_status(f"Fixed {fixed_issues} issues", Colors.GREEN if fixed_issues > 0 else Colors.YELLOW)
    
    # Return exit code based on health
    sys.exit(0 if healthy else 1)


@health_cli.command(name="clean")
@click.option("--environment", "-e", help="Path to environment directory")
@click.option("--id", help="ID of a persistent environment to clean")
@click.option("--name", help="Name of a persistent environment to clean")
@click.option("--cache", is_flag=True, help="Clean cache directory")
@click.option("--logs", is_flag=True, help="Clean logs directory")
@click.option("--tmp", is_flag=True, help="Clean temporary files")
@click.option("--all", "clean_all", is_flag=True, help="Clean all cache, logs, and temp files")
def clean_environment(
    environment: Optional[str] = None,
    id: Optional[str] = None,
    name: Optional[str] = None,
    cache: bool = False,
    logs: bool = False,
    tmp: bool = False,
    clean_all: bool = False
):
    """
    Clean cache and temporary files in a SafeSpace environment.
    
    This command removes temporary files, logs, and cache data
    to free up space and improve environment performance.
    """
    # Load environment
    env = None
    
    if id or name:
        # Try to load from persistent state
        env = SafeEnvironment.load_from_state(env_id=id, env_name=name)
        if not env:
            log_status(f"Environment not found: {id or name}", Colors.RED)
            sys.exit(1)
    elif environment:
        # Load from specified directory
        env_path = Path(environment)
        if not env_path.exists():
            log_status(f"Environment directory not found: {environment}", Colors.RED)
            sys.exit(1)
        env = SafeEnvironment(root_dir=env_path)
    else:
        # Try to find an environment
        env = SafeEnvironment()
    
    # Check if directory exists
    if not env.root_dir.exists():
        log_status(f"Environment directory does not exist: {env.root_dir}", Colors.RED)
        sys.exit(1)
    
    cleaned_dirs = 0
    
    # Clean cache if requested
    if clean_all or cache:
        log_status("Cleaning cache directory...", Colors.YELLOW)
        cache_dir = env.root_dir / "cache"
        if cache_dir.exists():
            clean_directory(cache_dir)
            log_status("Cache directory cleaned", Colors.GREEN)
            cleaned_dirs += 1
        else:
            log_status("Cache directory does not exist", Colors.YELLOW)
    
    # Clean logs if requested
    if clean_all or logs:
        log_status("Cleaning logs directory...", Colors.YELLOW)
        logs_dir = env.root_dir / "logs"
        if logs_dir.exists():
            clean_directory(logs_dir)
            log_status("Logs directory cleaned", Colors.GREEN)
            cleaned_dirs += 1
        else:
            log_status("Logs directory does not exist", Colors.YELLOW)
    
    # Clean temporary files if requested
    if clean_all or tmp:
        log_status("Cleaning temporary files...", Colors.YELLOW)
        tmp_dir = env.root_dir / "tmp"
        if tmp_dir.exists():
            clean_directory(tmp_dir)
            log_status("Temporary files cleaned", Colors.GREEN)
            cleaned_dirs += 1
        else:
            log_status("Temporary directory does not exist", Colors.YELLOW)
    
    log_status(f"Cleaned {cleaned_dirs} directories", Colors.GREEN if cleaned_dirs > 0 else Colors.YELLOW)
    
    # Run health check after cleaning
    healthy, issues = env.check_health()
    
    if healthy:
        log_status(f"Environment is healthy: {env.root_dir}", Colors.GREEN)
    else:
        log_status(f"Environment has issues: {env.root_dir}", Colors.YELLOW)
        for issue in issues:
            log_status(f"  - {issue}", Colors.YELLOW)
    
    sys.exit(0)


if __name__ == "__main__":
    health_cli() 