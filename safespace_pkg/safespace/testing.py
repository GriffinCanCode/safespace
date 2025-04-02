"""
Testing Environment Module for SafeSpace

This module provides functionality for creating and managing comprehensive testing
and enhanced development environments.
"""

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any, Union

from .utils import log_status, Colors, run_command, create_secure_directory
from .settings import get_settings

# Set up logging
logger = logging.getLogger(__name__)

class TestEnvironment:
    """Manages testing and development environments for SafeSpace"""
    
    def __init__(self, env_dir: Path):
        """
        Initialize TestEnvironment.
        
        Args:
            env_dir: Path to the environment directory
        """
        # Get settings
        self.settings = get_settings()
        self.testing_settings = self.settings.testing
        self.enhanced_dev_settings = self.settings.enhanced_dev
        
        self.env_dir = env_dir
        self.config_dir = env_dir / "config"
        self.tests_dir = env_dir / "tests"
        self.scripts_dir = env_dir / "scripts"
        self.docs_dir = env_dir / "docs"
        self.src_dir = env_dir / "src"
        self.tools_dir = env_dir / "tools"
        self.notebooks_dir = env_dir / "notebooks"
        self.github_dir = env_dir / ".github"
        self.vscode_dir = env_dir / ".vscode"
    
    def setup_comprehensive_testing(self) -> bool:
        """
        Set up a comprehensive testing environment.
        
        Returns:
            bool: True if setup was successful, False otherwise
        """
        log_status("Setting up comprehensive testing environment...", Colors.YELLOW)
        
        try:
            # Create directories
            create_secure_directory(self.config_dir / "test")
            create_secure_directory(self.tests_dir)
            
            # Create setup.cfg
            self._create_setup_cfg()
            
            # Create tox configuration
            self._create_tox_ini()
            
            # Create test runner script
            self._create_test_runner()
            
            # Create requirements.txt
            self._create_testing_requirements()
            
            # Create example benchmark test
            self._create_benchmark_test()
            
            log_status("Comprehensive testing environment setup complete", Colors.GREEN)
            self._print_testing_info()
            return True
        except Exception as e:
            logger.error(f"Failed to set up comprehensive testing environment: {e}")
            return False
    
    def setup_enhanced_environment(self) -> bool:
        """
        Set up an enhanced development environment.
        
        Returns:
            bool: True if setup was successful, False otherwise
        """
        log_status("Setting up enhanced development environment...", Colors.YELLOW)
        
        try:
            # Create enhanced directory structure
            directories = [
                self.vscode_dir,
                self.github_dir / "workflows",
                self.scripts_dir,
                self.docs_dir / "api",
                self.docs_dir / "guides",
                self.tools_dir,
                self.notebooks_dir
            ]
            
            for directory in directories:
                create_secure_directory(directory)
            
            # Create VS Code settings
            self._create_vscode_settings()
            
            # Create GitHub Actions workflow
            self._create_github_workflow()
            
            # Create development scripts
            self._create_dev_scripts()
            
            # Create pre-commit config
            self._create_precommit_config()
            
            log_status("Enhanced development environment setup complete", Colors.GREEN)
            self._print_enhanced_info()
            return True
        except Exception as e:
            logger.error(f"Failed to set up enhanced development environment: {e}")
            return False
    
    def _create_setup_cfg(self) -> None:
        """Create setup.cfg configuration file"""
        setup_cfg_content = """[flake8]
max-line-length = 88
extend-ignore = E203
exclude = .git,__pycache__,build,dist,*.egg-info

[pylint]
max-line-length = 88
disable = C0111,R0903,C0103
ignore = .git,__pycache__,build,dist,*.egg-info

[coverage:run]
branch = True
source = src
omit = tests/*,setup.py

[coverage:report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "if __name__ == .__main__.:",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
]
"""
        with open(self.env_dir / "setup.cfg", "w") as f:
            f.write(setup_cfg_content)
    
    def _create_tox_ini(self) -> None:
        """Create tox.ini configuration file"""
        tox_ini_content = """[tox]
envlist = py39, py310, py311, lint, type
isolated_build = True

[testenv]
deps =
    pytest>=7.0.0
    pytest-cov>=4.0.0
    pytest-xdist>=3.0.0
    pytest-timeout>=2.1.0
commands =
    pytest {posargs:tests}

[testenv:lint]
deps =
    black>=23.3.0
    isort>=5.12.0
    ruff>=0.0.260
    bandit>=1.7.5
commands =
    black .
    isort .
    ruff .
    bandit -r src tests

[testenv:type]
deps =
    mypy>=1.2.0
    types-all
commands =
    mypy src tests

[testenv:security]
deps =
    bandit>=1.7.5
    safety>=2.3.5
commands =
    bandit -r src tests
    safety check
"""
        with open(self.env_dir / "tox.ini", "w") as f:
            f.write(tox_ini_content)
    
    def _create_test_runner(self) -> None:
        """Create comprehensive test runner script"""
        test_runner_content = """#!/bin/bash
set -euo pipefail

# Colors for output
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
RED='\\033[0;31m'
NC='\\033[0m'

echo -e "${YELLOW}Running comprehensive test suite...${NC}"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Install pre-commit hooks
echo -e "${YELLOW}Setting up pre-commit hooks...${NC}"
pre-commit install

# Run static analysis
echo -e "${YELLOW}Running static analysis...${NC}"
echo "Running black..."
black . || true
echo "Running isort..."
isort . || true
echo "Running ruff..."
ruff . --fix || true
echo "Running mypy..."
mypy src tests || true

# Run security checks
echo -e "${YELLOW}Running security checks...${NC}"
echo "Running bandit..."
bandit -r src tests || true
echo "Running safety..."
safety check || true

# Run tests with coverage
echo -e "${YELLOW}Running tests with coverage...${NC}"
pytest tests/ --cov=src --cov-report=html --cov-report=term-missing -v

# Run performance profiling on tests
echo -e "${YELLOW}Running performance profiling...${NC}"
pyinstrument -r html -o profile_results.html -m pytest tests/

# Generate documentation
echo -e "${YELLOW}Generating documentation...${NC}"
if [ -f "docs/requirements.txt" ]; then
    pdoc --html --output-dir docs/api src/
fi

echo -e "${GREEN}Test suite completed!${NC}"
echo "- Coverage report: htmlcov/index.html"
echo "- Profile results: profile_results.html"
echo "- API documentation: docs/api/index.html"
"""
        script_path = self.env_dir / "run_tests.sh"
        with open(script_path, "w") as f:
            f.write(test_runner_content)
            
        # Make script executable
        os.chmod(script_path, 0o755)
    
    def _create_testing_requirements(self) -> None:
        """Create requirements.txt with comprehensive testing tools"""
        requirements_content = """# Testing
pytest>=7.0.0
pytest-cov>=4.0.0
pytest-xdist>=3.0.0
pytest-timeout>=2.1.0
pytest-benchmark>=4.0.0
hypothesis>=6.75.3

# Code Quality
black>=23.3.0
isort>=5.12.0
ruff>=0.0.260
mypy>=1.2.0
bandit>=1.7.5
radon>=5.1.0
vulture>=2.7

# Type Checking
types-all

# Security
safety>=2.3.5

# Documentation
pdoc>=12.3.1

# Profiling
pyinstrument>=4.4.0

# Development
pre-commit>=3.2.2
tox>=4.5.1
"""
        with open(self.env_dir / "requirements.txt", "w") as f:
            f.write(requirements_content)
    
    def _create_benchmark_test(self) -> None:
        """Create example benchmark test"""
        benchmark_test_content = """import pytest
from hypothesis import given, strategies as st

def fibonacci(n: int) -> int:
    if n < 2:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)

def test_fibonacci_benchmark(benchmark):
    result = benchmark(fibonacci, 10)
    assert result == 55

@given(st.integers(min_value=0, max_value=10))
def test_fibonacci_property(n):
    result = fibonacci(n)
    assert result >= 0
    if n <= 1:
        assert result == n
"""
        create_secure_directory(self.tests_dir)
        with open(self.tests_dir / "test_benchmark.py", "w") as f:
            f.write(benchmark_test_content)
    
    def _print_testing_info(self) -> None:
        """Print information about the testing environment"""
        log_status("\nAvailable testing commands:", Colors.CYAN)
        log_status("1. ./run_tests.sh - Run complete test suite with all checks", Colors.WHITE)
        log_status("2. pytest tests/ - Run basic tests", Colors.WHITE)
        log_status("3. pytest tests/ --benchmark-only - Run benchmarks", Colors.WHITE)
        log_status("4. pre-commit run --all-files - Run all pre-commit hooks", Colors.WHITE)
        log_status("5. tox - Run tests in multiple Python versions", Colors.WHITE)
        
        log_status("\nTesting artifacts:", Colors.CYAN)
        log_status("- Coverage report: htmlcov/index.html", Colors.WHITE)
        log_status("- Profile results: profile_results.html", Colors.WHITE)
        log_status("- API documentation: docs/api/index.html", Colors.WHITE)
    
    def _create_vscode_settings(self) -> None:
        """Create VS Code settings"""
        vscode_settings = """{
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": true,
    "python.linting.mypyEnabled": true,
    "python.linting.banditEnabled": true,
    "python.formatting.provider": "black",
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
        "source.organizeImports": true
    },
    "python.testing.pytestEnabled": true,
    "python.testing.unittestEnabled": false,
    "python.testing.nosetestsEnabled": false,
    "python.testing.pytestArgs": [
        "tests"
    ]
}"""
        with open(self.vscode_dir / "settings.json", "w") as f:
            f.write(vscode_settings)
    
    def _create_github_workflow(self) -> None:
        """Create GitHub Actions workflow"""
        github_workflow = """name: Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.9", "3.10", "3.11"]

    steps:
    - uses: actions/checkout@v3
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    - name: Run tests
      run: |
        pytest tests/ --cov=src --cov-report=xml
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
"""
        with open(self.github_dir / "workflows" / "test.yml", "w") as f:
            f.write(github_workflow)
    
    def _create_dev_scripts(self) -> None:
        """Create development scripts"""
        setup_dev_script = """#!/bin/bash
set -euo pipefail

# Install development tools
echo "Installing development tools..."
pip install -r requirements.txt

# Setup pre-commit
if command -v pre-commit &> /dev/null; then
    pre-commit install
else
    echo "Warning: pre-commit not found, skipping git hooks setup"
fi

# Create src and tests directories if they don't exist
mkdir -p src tests

echo "Development environment setup complete!"
"""
        
        update_deps_script = """#!/bin/bash
set -euo pipefail

# Update all dependencies to latest versions
echo "Updating all dependencies..."
pip install -U pip
pip install -U -r requirements.txt

# Check for security issues
if command -v safety &> /dev/null; then
    safety check
else
    echo "Warning: safety not installed, skipping security check"
fi

echo "Dependencies updated successfully!"
"""
        
        # Make scripts executable
        script_path = self.scripts_dir / "setup_dev.sh"
        with open(script_path, "w") as f:
            f.write(setup_dev_script)
        os.chmod(script_path, 0o755)
        
        script_path = self.scripts_dir / "update_deps.sh"
        with open(script_path, "w") as f:
            f.write(update_deps_script)
        os.chmod(script_path, 0o755)
    
    def _create_precommit_config(self) -> None:
        """Create pre-commit configuration"""
        precommit_config = """repos:
-   repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
    -   id: trailing-whitespace
    -   id: end-of-file-fixer
    -   id: check-yaml
    -   id: check-json
    -   id: check-added-large-files
    -   id: debug-statements
    -   id: check-case-conflict
    -   id: check-merge-conflict

-   repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
    -   id: black

-   repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
    -   id: isort

-   repo: https://github.com/charliermarsh/ruff-pre-commit
    rev: 'v0.0.262'
    hooks:
    -   id: ruff
        args: [--fix, --exit-non-zero-on-fix]

-   repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.2.0
    hooks:
    -   id: mypy
        additional_dependencies: [types-all]

-   repo: https://github.com/PyCQA/bandit
    rev: 1.7.5
    hooks:
    -   id: bandit
        args: ["-c", "pyproject.toml"]
        additional_dependencies: ["bandit[toml]"]
"""
        with open(self.env_dir / ".pre-commit-config.yaml", "w") as f:
            f.write(precommit_config)
    
    def _print_enhanced_info(self) -> None:
        """Print information about the enhanced environment"""
        log_status("\nEnhanced development environment created:", Colors.CYAN)
        log_status("- VS Code settings: .vscode/settings.json", Colors.WHITE)
        log_status("- GitHub Actions workflow: .github/workflows/test.yml", Colors.WHITE)
        log_status("- Development scripts: scripts/setup_dev.sh, scripts/update_deps.sh", Colors.WHITE)
        log_status("- Pre-commit config: .pre-commit-config.yaml", Colors.WHITE)
        
        log_status("\nTo set up the environment:", Colors.CYAN)
        log_status("1. Create a virtual environment: python -m venv venv", Colors.WHITE)
        log_status("2. Activate it: source venv/bin/activate (Linux/macOS) or venv\\Scripts\\activate (Windows)", Colors.WHITE)
        log_status("3. Run setup script: ./scripts/setup_dev.sh", Colors.WHITE)
    
    def cleanup(self) -> None:
        """Clean up testing environment artifacts"""
        log_status("Cleaning up testing environment artifacts...", Colors.YELLOW)
        
        # Remove pytest cache
        for cache_dir in self.env_dir.glob("**/__pycache__"):
            if cache_dir.is_dir():
                shutil.rmtree(cache_dir)
        
        for pytest_cache in self.env_dir.glob("**/.pytest_cache"):
            if pytest_cache.is_dir():
                shutil.rmtree(pytest_cache)
        
        # Clean coverage data
        for coverage_file in self.env_dir.glob(".coverage*"):
            coverage_file.unlink()
        
        htmlcov_dir = self.env_dir / "htmlcov"
        if htmlcov_dir.exists():
            shutil.rmtree(htmlcov_dir)
        
        # Remove any profiling results
        for profile_file in self.env_dir.glob("profile_results*.html"):
            profile_file.unlink()
        
        log_status("Testing environment artifacts cleaned up", Colors.GREEN)
