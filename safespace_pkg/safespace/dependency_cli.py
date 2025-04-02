"""
Command-line interface for the dependency management module.

This module provides a CLI for the dependency management functionality.
"""

import os
import sys
import click
from pathlib import Path
from typing import Optional

from .dependency_manager import DependencyManager, detect_package_manager, install_package_manager
from .utils import log_status


@click.group()
def dependency_cli():
    """Manage Python dependencies for SafeSpace environments."""
    pass


@dependency_cli.command()
@click.option("--name", "-n", help="Project name")
@click.option("--version", "-v", default="0.1.0", help="Project version")
@click.option("--description", "-d", default="", help="Project description")
@click.option("--author", "-a", default="", help="Project author")
@click.option("--manager", "-m", type=click.Choice(["pip", "poetry", "auto"]), default="auto", 
              help="Package manager to use (auto will select best available)")
@click.option("--directory", "-dir", default=".", help="Project directory")
def init(name: Optional[str], version: str, description: str, author: str, manager: str, directory: str):
    """Initialize dependency management for a project."""
    project_dir = Path(directory).resolve()
    
    # Get project name from directory if not specified
    if not name:
        name = project_dir.name
    
    # Detect package manager if set to auto
    if manager == "auto":
        manager = detect_package_manager()
        if manager == "none":
            manager = "pip"  # Default to pip if nothing is available
    
    # Ensure package manager is available
    if not install_package_manager(manager):
        log_status(f"Failed to ensure {manager} is available", level="error")
        sys.exit(1)
    
    dep_manager = DependencyManager(project_dir=project_dir)
    
    if manager == "poetry":
        if not dep_manager.has_poetry():
            log_status("Poetry installation detected but not available for use", level="error")
            sys.exit(1)
        
        if dep_manager.has_pyproject_toml():
            log_status("Project already initialized with pyproject.toml", level="info")
        else:
            log_status(f"Initializing Poetry project: {name} v{version}")
            if not dep_manager.init_poetry_project(name=name, version=version, 
                                                  description=description, author=author):
                log_status("Failed to initialize Poetry project", level="error")
                sys.exit(1)
    else:  # pip
        # Create or update requirements.txt if doesn't exist
        if not dep_manager.has_requirements_txt():
            log_status("Creating initial requirements.txt")
            dep_manager.create_requirements_file(dependencies=[])
        else:
            log_status("Project already has requirements.txt", level="info")
    
    log_status(f"Project initialized with {manager} in {project_dir}")


@dependency_cli.command()
@click.argument("package", nargs=-1)
@click.option("--dev", "-d", is_flag=True, help="Install as development dependency")
@click.option("--group", "-g", help="Dependency group (Poetry only)")
@click.option("--directory", "-dir", default=".", help="Project directory")
@click.option("--venv", help="Virtual environment path")
def add(package, dev: bool, group: Optional[str], directory: str, venv: Optional[str]):
    """Add a dependency to the project."""
    if not package:
        log_status("No packages specified", level="error")
        sys.exit(1)
    
    project_dir = Path(directory).resolve()
    dep_manager = DependencyManager(project_dir=project_dir, venv_path=venv)
    
    if dep_manager.has_pyproject_toml() and dep_manager.has_poetry():
        # Using Poetry
        for pkg in package:
            log_status(f"Adding {pkg} with Poetry")
            if not dep_manager.poetry_add_dependency(dependency=pkg, dev=dev, group=group):
                log_status(f"Failed to add {pkg}", level="error")
                sys.exit(1)
    else:
        # Using pip
        # First get existing requirements
        if dep_manager.has_requirements_txt():
            with open(project_dir / "requirements.txt", "r") as f:
                current_reqs = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        else:
            current_reqs = []
        
        # Add new packages
        for pkg in package:
            if pkg not in current_reqs:
                current_reqs.append(pkg)
            
            # Also install the package in the current environment if venv is specified
            if venv:
                log_status(f"Installing {pkg} with pip in virtual environment")
                if not dep_manager.install_package(package=pkg):
                    log_status(f"Failed to install {pkg}", level="error")
                    sys.exit(1)
        
        # Update requirements.txt
        dep_manager.create_requirements_file(dependencies=current_reqs)
    
    log_status(f"Added {len(package)} package(s) to the project")


@dependency_cli.command()
@click.option("--venv", help="Virtual environment path")
@click.option("--upgrade", "-u", is_flag=True, help="Upgrade existing packages")
@click.option("--dev", "-d", is_flag=True, help="Include development dependencies")
@click.option("--directory", "-dir", default=".", help="Project directory")
def install(venv: Optional[str], upgrade: bool, dev: bool, directory: str):
    """Install dependencies from requirements."""
    project_dir = Path(directory).resolve()
    dep_manager = DependencyManager(project_dir=project_dir, venv_path=venv)
    
    if dep_manager.has_pyproject_toml() and dep_manager.has_poetry():
        # Using Poetry
        log_status("Installing dependencies with Poetry")
        if not dep_manager.poetry_install(dev=dev):
            log_status("Failed to install dependencies with Poetry", level="error")
            sys.exit(1)
    else:
        # Using pip
        if not dep_manager.has_requirements_txt():
            log_status("No requirements.txt found", level="error")
            sys.exit(1)
        
        log_status("Installing dependencies with pip")
        if not dep_manager.install_requirements(upgrade=upgrade):
            log_status("Failed to install dependencies with pip", level="error")
            sys.exit(1)
    
    log_status("Dependencies installed successfully")


@dependency_cli.command()
@click.option("--venv", help="Virtual environment path")
@click.option("--requirements", "-r", help="Path to requirements file")
@click.option("--directory", "-dir", default=".", help="Project directory")
def create_venv(venv: str, requirements: Optional[str], directory: str):
    """Create a new virtual environment with dependencies."""
    project_dir = Path(directory).resolve()
    dep_manager = DependencyManager(project_dir=project_dir)
    
    log_status(f"Creating virtual environment at {venv}")
    if not dep_manager.create_isolated_environment(venv_path=venv, requirements_path=requirements):
        log_status("Failed to create virtual environment", level="error")
        sys.exit(1)
    
    log_status(f"Virtual environment created at {venv}")


@dependency_cli.command()
@click.option("--output", "-o", required=True, help="Output file path")
@click.option("--directory", "-dir", default=".", help="Project directory")
@click.option("--venv", help="Virtual environment path")
def export(output: str, directory: str, venv: Optional[str]):
    """Export dependencies to a requirements file."""
    project_dir = Path(directory).resolve()
    dep_manager = DependencyManager(project_dir=project_dir, venv_path=venv)
    
    if dep_manager.has_pyproject_toml() and dep_manager.has_poetry():
        # Export from Poetry to requirements.txt
        log_status(f"Exporting dependencies from Poetry to {output}")
        if not dep_manager.convert_poetry_to_requirements(output_path=output):
            log_status("Failed to export dependencies from Poetry", level="error")
            sys.exit(1)
    else:
        # Export current environment
        log_status(f"Exporting current environment to {output}")
        if not dep_manager.export_environment(output_path=output):
            log_status("Failed to export environment", level="error")
            sys.exit(1)
    
    log_status(f"Dependencies exported to {output}")


@dependency_cli.command()
@click.option("--directory", "-dir", default=".", help="Project directory")
@click.option("--venv", help="Virtual environment path")
def list(directory: str, venv: Optional[str]):
    """List installed packages."""
    project_dir = Path(directory).resolve()
    dep_manager = DependencyManager(project_dir=project_dir, venv_path=venv)
    
    packages = dep_manager.list_installed_packages()
    
    if not packages:
        log_status("No packages installed or failed to retrieve package list", level="warning")
        return
    
    log_status(f"Installed packages ({len(packages)}):")
    max_name_len = max(len(name) for name in packages.keys())
    
    for name, version in sorted(packages.items()):
        click.echo(f"  {name:{max_name_len}} {version}")


@dependency_cli.command(name="check")
@click.option("--directory", "-dir", default=".", help="Project directory")
@click.option("--venv", help="Virtual environment path")
def check_deps(directory: str, venv: Optional[str]):
    """Check for dependency conflicts."""
    project_dir = Path(directory).resolve()
    dep_manager = DependencyManager(project_dir=project_dir, venv_path=venv)
    
    conflicts = dep_manager.check_dependency_conflicts()
    
    if not conflicts:
        log_status("No dependency conflicts found")
        return
    
    log_status(f"Found {len(conflicts)} dependency conflicts:", level="error")
    for conflict in conflicts:
        click.echo(f"  {conflict}")


@dependency_cli.command()
@click.argument("source", required=True)
@click.argument("target", required=True)
@click.option("--directory", "-dir", default=".", help="Project directory")
def convert(source: str, target: str, directory: str):
    """
    Convert between dependency formats.
    
    SOURCE and TARGET should be format identifiers: 'poetry' or 'requirements'
    """
    project_dir = Path(directory).resolve()
    dep_manager = DependencyManager(project_dir=project_dir)
    
    if source == "requirements" and target == "poetry":
        # Convert requirements.txt to Poetry
        req_file = project_dir / "requirements.txt"
        if not req_file.exists():
            log_status("requirements.txt not found", level="error")
            sys.exit(1)
        
        log_status("Converting requirements.txt to Poetry project")
        if not dep_manager.convert_requirements_to_poetry(requirements_path=req_file):
            log_status("Failed to convert requirements to Poetry", level="error")
            sys.exit(1)
    
    elif source == "poetry" and target == "requirements":
        # Convert Poetry to requirements.txt
        req_file = project_dir / "requirements.txt"
        
        log_status("Converting Poetry project to requirements.txt")
        if not dep_manager.convert_poetry_to_requirements(output_path=req_file):
            log_status("Failed to convert Poetry to requirements", level="error")
            sys.exit(1)
    
    else:
        log_status(f"Unsupported conversion: {source} to {target}", level="error")
        log_status("Supported conversions: 'requirements to poetry' or 'poetry to requirements'")
        sys.exit(1)
    
    log_status(f"Successfully converted {source} to {target}")


if __name__ == "__main__":
    dependency_cli() 