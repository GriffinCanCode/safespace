"""
Dependency management module for SafeSpace.

This module provides functionality for managing Python dependencies in SafeSpace environments,
including integration with package managers like pip and poetry.
"""

import os
import subprocess
import sys
import json
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union, Any

from .utils import log_status, run_command, Colors
from .environment import SafeEnvironment


class DependencyManager:
    """
    Manages Python dependencies for SafeSpace environments.
    
    This class provides functionality for:
    - Creating and managing requirements files
    - Installing dependencies with pip
    - Managing Poetry projects
    - Checking for dependency conflicts
    - Creating isolated dependency environments
    """
    
    def __init__(self, project_dir: Union[str, Path], venv_path: Optional[Union[str, Path]] = None):
        """
        Initialize the dependency manager.
        
        Args:
            project_dir: The project directory to manage dependencies for
            venv_path: Path to a virtual environment (optional)
        """
        self.project_dir = Path(project_dir)
        self.venv_path = Path(venv_path) if venv_path else None
        self.pip_executable = self._get_pip_executable()
        self.poetry_executable = self._get_poetry_executable()
        
    def _get_pip_executable(self) -> str:
        """Get the appropriate pip executable based on environment."""
        if self.venv_path:
            # Always recheck the platform when getting the executable
            if sys.platform == "win32":
                return str(self.venv_path / "Scripts" / "pip.exe")
            else:  # unix-like systems (Linux, macOS)
                return str(self.venv_path / "bin" / "pip")
        return "pip"
    
    def _get_poetry_executable(self) -> Optional[str]:
        """Get the poetry executable if available."""
        poetry_path = shutil.which("poetry")
        return poetry_path
    
    def has_poetry(self) -> bool:
        """Check if Poetry is available."""
        return self.poetry_executable is not None
    
    def has_pyproject_toml(self) -> bool:
        """Check if the project has a pyproject.toml file."""
        return (self.project_dir / "pyproject.toml").exists()
    
    def has_requirements_txt(self) -> bool:
        """Check if the project has a requirements.txt file."""
        return (self.project_dir / "requirements.txt").exists()
    
    def create_requirements_file(self, dependencies: List[str], output_path: Optional[Union[str, Path]] = None) -> Path:
        """
        Create a requirements.txt file with the specified dependencies.
        
        Args:
            dependencies: List of dependencies in pip format
            output_path: Path to write the requirements file to (defaults to requirements.txt in project_dir)
            
        Returns:
            Path to the created requirements file
        """
        if output_path is None:
            output_path = self.project_dir / "requirements.txt"
        else:
            output_path = Path(output_path)
            
        with open(output_path, "w") as f:
            f.write("\n".join(dependencies) + "\n")
            
        log_status(f"Created requirements file at {output_path}", Colors.GREEN)
        return output_path
    
    def install_requirements(self, 
                            requirements_path: Optional[Union[str, Path]] = None, 
                            upgrade: bool = False, 
                            dev: bool = False) -> bool:
        """
        Install dependencies from a requirements file.
        
        Args:
            requirements_path: Path to requirements file (defaults to requirements.txt in project_dir)
            upgrade: Whether to upgrade existing packages
            dev: Whether to install development dependencies
            
        Returns:
            True if installation was successful, False otherwise
        """
        if requirements_path is None:
            requirements_path = self.project_dir / "requirements.txt"
        
        if not Path(requirements_path).exists():
            log_status(f"Requirements file {requirements_path} does not exist", Colors.RED)
            return False
        
        cmd = [self.pip_executable, "install", "-r", str(requirements_path)]
        
        if upgrade:
            cmd.append("--upgrade")
            
        result = run_command(cmd, shell=False, capture_output=True)
        
        if result.returncode != 0:
            log_status(f"Failed to install requirements: {result.stderr}", Colors.RED)
            return False
            
        log_status(f"Successfully installed dependencies from {requirements_path}", Colors.GREEN)
        return True
    
    def install_package(self, 
                       package: str, 
                       version: Optional[str] = None, 
                       upgrade: bool = False) -> bool:
        """
        Install a single package.
        
        Args:
            package: Package name
            version: Specific version to install
            upgrade: Whether to upgrade existing package
            
        Returns:
            True if installation was successful, False otherwise
        """
        cmd = [self.pip_executable, "install"]
        
        if version:
            cmd.append(f"{package}=={version}")
        else:
            cmd.append(package)
            
        if upgrade:
            cmd.append("--upgrade")
            
        result = run_command(cmd, shell=False, capture_output=True)
        
        if result.returncode != 0:
            log_status(f"Failed to install {package}: {result.stderr}", Colors.RED)
            return False
            
        log_status(f"Successfully installed {package}", Colors.GREEN)
        return True
    
    def list_installed_packages(self) -> Dict[str, str]:
        """
        List all installed packages and their versions.
        
        Returns:
            Dictionary mapping package names to versions
        """
        cmd = [self.pip_executable, "list", "--format=json"]
        result = run_command(cmd, shell=False, capture_output=True)
        
        if result.returncode != 0:
            log_status(f"Failed to list packages: {result.stderr}", Colors.RED)
            return {}
            
        packages = json.loads(result.stdout)
        return {pkg["name"]: pkg["version"] for pkg in packages}
    
    def check_dependency_conflicts(self, requirements_path: Optional[Union[str, Path]] = None) -> List[str]:
        """
        Check for dependency conflicts.
        
        Args:
            requirements_path: Path to requirements file to check
            
        Returns:
            List of conflict messages, empty if no conflicts
        """
        if requirements_path is None:
            requirements_path = self.project_dir / "requirements.txt"
            
        if not Path(requirements_path).exists():
            return [f"Requirements file {requirements_path} does not exist"]
            
        cmd = [self.pip_executable, "check"]
        result = run_command(cmd, shell=False, capture_output=True)
        
        if result.returncode != 0:
            return result.stdout.strip().split("\n")
            
        return []
    
    def export_environment(self, output_path: Union[str, Path]) -> bool:
        """
        Export the current environment to a requirements file.
        
        Args:
            output_path: Path to write the requirements file to
            
        Returns:
            True if export was successful, False otherwise
        """
        cmd = [self.pip_executable, "freeze"]
        result = run_command(cmd, shell=False, capture_output=True)
        
        if result.returncode != 0:
            log_status(f"Failed to export environment: {result.stderr}", Colors.RED)
            return False
            
        with open(output_path, "w") as f:
            f.write(result.stdout)
            
        log_status(f"Exported environment to {output_path}", Colors.GREEN)
        return True
    
    # Poetry integration methods
    
    def init_poetry_project(self, 
                           name: str, 
                           version: str = "0.1.0",
                           description: str = "",
                           author: str = "",
                           dependencies: Optional[List[str]] = None) -> bool:
        """
        Initialize a Poetry project.
        
        Args:
            name: Project name
            version: Project version
            description: Project description
            author: Project author
            dependencies: Initial dependencies to add
            
        Returns:
            True if initialization was successful, False otherwise
        """
        if not self.has_poetry():
            log_status("Poetry is not installed", Colors.RED)
            return False
            
        if self.has_pyproject_toml():
            log_status("pyproject.toml already exists", Colors.YELLOW)
            return False
            
        cmd = [self.poetry_executable, "init", 
               "--name", name, 
               "--version", version]
               
        if description:
            cmd.extend(["--description", description])
            
        if author:
            cmd.extend(["--author", author])
        
        # Create project without interaction    
        cmd.append("--no-interaction")
        
        result = run_command(cmd, shell=False, capture_output=True, cwd=str(self.project_dir))
        
        if result.returncode != 0:
            log_status(f"Failed to initialize Poetry project: {result.stderr}", Colors.RED)
            return False
            
        # Add dependencies if specified
        if dependencies:
            for dep in dependencies:
                self.poetry_add_dependency(dep)
                
        log_status(f"Initialized Poetry project at {self.project_dir}", Colors.GREEN)
        return True
    
    def poetry_add_dependency(self, 
                             dependency: str, 
                             dev: bool = False, 
                             group: Optional[str] = None) -> bool:
        """
        Add a dependency to a Poetry project.
        
        Args:
            dependency: Dependency specification
            dev: Whether this is a development dependency
            group: Dependency group (Poetry >= 1.2.0)
            
        Returns:
            True if the dependency was added successfully, False otherwise
        """
        if not self.has_poetry():
            log_status("Poetry is not installed", Colors.RED)
            return False
            
        if not self.has_pyproject_toml():
            log_status("No pyproject.toml found", Colors.RED)
            return False
            
        cmd = [self.poetry_executable, "add", dependency]
        
        if dev:
            cmd.append("--dev")
            
        if group:
            cmd.extend(["--group", group])
            
        result = run_command(cmd, shell=False, capture_output=True, cwd=str(self.project_dir))
        
        if result.returncode != 0:
            log_status(f"Failed to add dependency {dependency}: {result.stderr}", Colors.RED)
            return False
            
        log_status(f"Added dependency {dependency}", Colors.GREEN)
        return True
    
    def poetry_install(self, dev: bool = True, no_root: bool = False) -> bool:
        """
        Install dependencies from Poetry project.
        
        Args:
            dev: Whether to install development dependencies
            no_root: Whether to skip installing the root package
            
        Returns:
            True if installation was successful, False otherwise
        """
        if not self.has_poetry():
            log_status("Poetry is not installed", Colors.RED)
            return False
            
        if not self.has_pyproject_toml():
            log_status("No pyproject.toml found", Colors.RED)
            return False
            
        cmd = [self.poetry_executable, "install"]
        
        if not dev:
            cmd.append("--no-dev")
            
        if no_root:
            cmd.append("--no-root")
            
        result = run_command(cmd, shell=False, capture_output=True, cwd=str(self.project_dir))
        
        if result.returncode != 0:
            log_status(f"Failed to install dependencies: {result.stderr}", Colors.RED)
            return False
            
        log_status("Successfully installed dependencies", Colors.GREEN)
        return True
    
    def convert_requirements_to_poetry(self, requirements_path: Union[str, Path]) -> bool:
        """
        Convert a requirements.txt file to Poetry format.
        
        Args:
            requirements_path: Path to requirements.txt file
            
        Returns:
            True if conversion was successful, False otherwise
        """
        if not self.has_poetry():
            log_status("Poetry is not installed", Colors.RED)
            return False
            
        if not Path(requirements_path).exists():
            log_status(f"Requirements file {requirements_path} does not exist", Colors.RED)
            return False
            
        # Initialize Poetry project if not already initialized
        if not self.has_pyproject_toml():
            project_name = self.project_dir.name
            self.init_poetry_project(project_name)
            
        # Read requirements
        with open(requirements_path, "r") as f:
            requirements = f.read().strip().split("\n")
            
        # Add each requirement to Poetry
        success = True
        for req in requirements:
            if req and not req.startswith("#"):
                if not self.poetry_add_dependency(req):
                    success = False
                    
        return success
    
    def convert_poetry_to_requirements(self, output_path: Union[str, Path]) -> bool:
        """
        Convert a Poetry project to requirements.txt format.
        
        Args:
            output_path: Path to write requirements.txt to
            
        Returns:
            True if conversion was successful, False otherwise
        """
        if not self.has_poetry():
            log_status("Poetry is not installed", Colors.RED)
            return False
            
        if not self.has_pyproject_toml():
            log_status("No pyproject.toml found", Colors.RED)
            return False
            
        cmd = [self.poetry_executable, "export", "--format", "requirements.txt", "--output", str(output_path)]
        result = run_command(cmd, shell=False, capture_output=True, cwd=str(self.project_dir))
        
        if result.returncode != 0:
            log_status(f"Failed to export requirements: {result.stderr}", Colors.RED)
            return False
            
        log_status(f"Exported requirements to {output_path}", Colors.GREEN)
        return True
    
    # Environment isolation methods
    
    def create_isolated_environment(self, venv_path: Union[str, Path], requirements_path: Optional[Union[str, Path]] = None) -> bool:
        """
        Create an isolated virtual environment with dependencies.
        
        Args:
            venv_path: Path to create the virtual environment at
            requirements_path: Path to requirements file to install (optional)
            
        Returns:
            True if creation was successful, False otherwise
        """
        venv_path_obj = Path(venv_path)
        
        # Create the virtual environment using the built-in venv module
        try:
            log_status(f"Creating virtual environment at {venv_path_obj}", Colors.YELLOW)
            subprocess.run([sys.executable, "-m", "venv", str(venv_path_obj)], check=True)
            
            # Update dependency manager with new venv
            self.venv_path = venv_path_obj
            self.pip_executable = self._get_pip_executable()
            
            # Install requirements if specified
            if requirements_path and Path(requirements_path).exists():
                return self.install_requirements(requirements_path)
                
            return True
        except subprocess.CalledProcessError as e:
            log_status(f"Failed to create virtual environment: {e}", Colors.RED)
            return False
        except Exception as e:
            log_status(f"Error creating virtual environment: {e}", Colors.RED)
            return False
    
    def is_package_installed(self, package_name: str) -> bool:
        """
        Check if a package is installed.
        
        Args:
            package_name: Name of the package to check
            
        Returns:
            True if the package is installed, False otherwise
        """
        installed_packages = self.list_installed_packages()
        return package_name.lower() in {pkg.lower() for pkg in installed_packages}
    
    def get_package_version(self, package_name: str) -> Optional[str]:
        """
        Get the installed version of a package.
        
        Args:
            package_name: Name of the package
            
        Returns:
            Version string if installed, None otherwise
        """
        installed_packages = self.list_installed_packages()
        for pkg, version in installed_packages.items():
            if pkg.lower() == package_name.lower():
                return version
        return None


# Helper functions for dependency management

def detect_package_manager() -> str:
    """
    Detect available package managers.
    
    Returns:
        String indicating the best available package manager: "poetry", "pip", or "none"
    """
    if shutil.which("poetry"):
        return "poetry"
    elif shutil.which("pip"):
        return "pip"
    else:
        return "none"

def install_package_manager(manager: str = "pip") -> bool:
    """
    Install a package manager if not already available.
    
    Args:
        manager: Package manager to install ("pip" or "poetry")
        
    Returns:
        True if installation was successful or already installed, False otherwise
    """
    if manager == "pip":
        if shutil.which("pip"):
            return True
            
        try:
            # Install pip using ensurepip
            subprocess.run([sys.executable, "-m", "ensurepip", "--upgrade"], check=True)
            return True
        except subprocess.CalledProcessError:
            log_status("Failed to install pip", Colors.RED)
            return False
            
    elif manager == "poetry":
        if shutil.which("poetry"):
            return True
            
        try:
            # Install poetry using pip (pip must be available)
            if not shutil.which("pip"):
                if not install_package_manager("pip"):
                    return False
                    
            subprocess.run(["pip", "install", "poetry"], check=True)
            return True
        except subprocess.CalledProcessError:
            log_status("Failed to install poetry", Colors.RED)
            return False
            
    return False 