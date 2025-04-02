"""
Command Line Interface for SafeSpace

This module provides the command-line interface for the SafeSpace package.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Optional

import click

from . import __version__
from .environment import SafeEnvironment
from .utils import Colors, log_status, setup_logging

# Set up logging
logger = logging.getLogger(__name__)

@click.group(invoke_without_command=True)
@click.option("-n", "--network", is_flag=True, help="Enable network isolation")
@click.option("-v", "--vm", is_flag=True, help="Enable VM mode")
@click.option("-c", "--cleanup", is_flag=True, help="Clean up environment (for internal mode)")
@click.option("--test", is_flag=True, help="Enable comprehensive testing mode")
@click.option("--enhanced", is_flag=True, help="Enable enhanced development environment")
@click.option("--memory", help="Specify VM memory size (e.g., '2G')")
@click.option("--cpus", type=int, help="Specify number of CPUs for VM")
@click.option("--disk", help="Specify VM disk size (e.g., '20G')")
@click.option("--debug", is_flag=True, help="Enable debug logging")
@click.option("--wordspace", "--ws", is_flag=True, help="Show comprehensive documentation")
@click.option("--wordspace-section", help="Show specific documentation section")
@click.option("--wordspace-subsection", help="Show specific documentation subsection")
@click.option("--wordspace-tree", is_flag=True, help="Show documentation in tree view")
@click.option("--wordspace-interactive", is_flag=True, help="Show documentation in interactive mode")
@click.version_option(version=__version__)
@click.pass_context
def main(
    ctx: click.Context,
    network: bool,
    vm: bool,
    cleanup: bool,
    test: bool,
    enhanced: bool,
    memory: Optional[str],
    cpus: Optional[int],
    disk: Optional[str],
    debug: bool,
    wordspace: bool,
    wordspace_section: Optional[str],
    wordspace_subsection: Optional[str],
    wordspace_tree: bool,
    wordspace_interactive: bool,
) -> None:
    """
    SafeSpace - Safe Environment Creator and Manager
    
    This tool creates isolated testing environments with various safety features.
    """
    # Set up logging
    log_level = logging.DEBUG if debug else logging.INFO
    setup_logging(log_level)
    
    # Store options in context
    ctx.ensure_object(dict)
    ctx.obj["network"] = network
    ctx.obj["vm"] = vm
    ctx.obj["cleanup"] = cleanup
    ctx.obj["test"] = test
    ctx.obj["enhanced"] = enhanced
    ctx.obj["vm_memory"] = memory
    ctx.obj["vm_cpus"] = cpus
    ctx.obj["vm_disk"] = disk
    ctx.obj["debug"] = debug
    ctx.obj["wordspace"] = wordspace
    ctx.obj["wordspace_section"] = wordspace_section
    ctx.obj["wordspace_subsection"] = wordspace_subsection
    ctx.obj["wordspace_tree"] = wordspace_tree
    ctx.obj["wordspace_interactive"] = wordspace_interactive
    
    # Check if wordspace documentation is requested
    if (wordspace or wordspace_section is not None or 
        wordspace_subsection is not None or wordspace_tree or 
        wordspace_interactive):
        from .docs.documentation_cli import display_documentation
        
        # If subsection is specified but section is not, show an error
        if wordspace_subsection is not None and wordspace_section is None:
            click.echo(click.style(
                "Error: --wordspace-subsection requires --wordspace-section",
                fg="red"
            ))
            sys.exit(1)
            
        # Call the documentation display function with all options
        display_documentation(
            section_id=wordspace_section or (None if not wordspace else "core-concepts"),
            subsection_id=wordspace_subsection,
            tree_view=wordspace_tree,
            interactive=wordspace_interactive or (not wordspace_tree and wordspace_section is None)
        )
        sys.exit(0)
    
    # Print banner if not running a subcommand
    if ctx.invoked_subcommand is None:
        print_banner()
        
        # Get sudo password if needed
        sudo_password = None
        if network or vm:
            sudo_password = os.environ.get("SUDO_PASSWORD")
            if sudo_password is None and (sys.platform != "win32"):
                sudo_password = click.prompt(
                    "Sudo password (needed for network/VM operations)",
                    hide_input=True,
                    default="",
                    show_default=False,
                )
        
        # Create and configure environment
        env = SafeEnvironment(sudo_password=sudo_password)
        
        if env.create():
            # Run in the created environment
            result = run_in_environment(
                env, 
                network=network, 
                vm=vm, 
                test=test, 
                enhanced=enhanced,
                vm_memory=memory,
                vm_cpus=cpus,
                vm_disk=disk
            )
            
            # Cleanup on exit unless explicitly disabled
            env.cleanup()
            sys.exit(0 if result else 1)

def print_banner() -> None:
    """Print the SafeSpace banner"""
    banner = f"""
    ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃               SafeSpace v{__version__}                 ┃
    ┃          Safe Environment Creator & Manager          ┃
    ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
    """
    print(banner)

def run_in_environment(
    env: SafeEnvironment,
    network: bool = False,
    vm: bool = False,
    test: bool = False,
    enhanced: bool = False,
    vm_memory: Optional[str] = None,
    vm_cpus: Optional[int] = None,
    vm_disk: Optional[str] = None,
) -> bool:
    """Run operations in the created environment"""
    # Check environment health
    healthy, issues = env.check_health()
    if not healthy:
        log_status("Environment health check failed:", Colors.RED)
        for issue in issues:
            log_status(f"  - {issue}", Colors.RED)
        return False
    
    # Setup network isolation if requested
    if network:
        log_status("Setting up network isolation...", Colors.YELLOW)
        if not env.setup_network_isolation():
            log_status("Failed to set up network isolation", Colors.RED)
            return False
        log_status("Network isolation configured successfully", Colors.GREEN)
    
    # Setup VM if requested
    if vm:
        log_status("Setting up VM environment...", Colors.YELLOW)
        if not env.setup_vm(memory=vm_memory, cpus=vm_cpus, disk_size=vm_disk):
            log_status("Failed to set up VM environment", Colors.RED)
            return False
        log_status("VM environment configured successfully", Colors.GREEN)
        
        # Ask if user wants to start the VM
        if click.confirm("Do you want to start the VM now?", default=True):
            if env.start_vm():
                log_status("VM started successfully", Colors.GREEN)
                log_status("VM will continue running in the background", Colors.YELLOW)
                log_status("Use 'Ctrl+C' to stop and cleanup when done", Colors.YELLOW)
            else:
                log_status("Failed to start VM", Colors.RED)
    
    # Setup comprehensive testing environment if requested
    if test:
        log_status("Setting up comprehensive testing environment...", Colors.YELLOW)
        if not env.setup_comprehensive_testing():
            log_status("Failed to set up comprehensive testing environment", Colors.RED)
            return False
    
    # Setup enhanced development environment if requested
    if enhanced:
        log_status("Setting up enhanced development environment...", Colors.YELLOW)
        if not env.setup_enhanced_environment():
            log_status("Failed to set up enhanced development environment", Colors.RED)
            return False
    
    log_status("Environment is ready", Colors.GREEN)
    
    # Show environment information
    if network:
        log_status("\nNetwork Isolation Information:", Colors.GREEN)
        log_status("  - Inside the network namespace, you have a private network", Colors.GREEN)
        log_status("  - Default route goes through the host system", Colors.GREEN)
        log_status("  - To run commands in the isolated network:", Colors.GREEN)
        log_status("    safespace --network -- <command>", Colors.GREEN)
        
        # Example network check
        try:
            import subprocess
            log_status("\nRunning network connectivity test...", Colors.YELLOW)
            
            # In network namespace
            log_status("Network namespace:", Colors.CYAN)
            rc, stdout, stderr = env.run_in_network(["ip", "addr"])
            if rc == 0:
                for line in stdout.splitlines():
                    log_status(f"  {line}", Colors.GREEN)
            else:
                log_status(f"Error: {stderr}", Colors.RED)
                
            # Test connectivity
            log_status("\nTesting connectivity:", Colors.CYAN)
            rc, stdout, stderr = env.run_in_network(["ping", "-c", "1", "-W", "2", "8.8.8.8"])
            if rc == 0:
                log_status("  Network connectivity: OK", Colors.GREEN)
            else:
                log_status("  Network connectivity: Failed", Colors.RED)
                log_status(f"  {stderr}", Colors.RED)
        except Exception as e:
            log_status(f"Test failed: {e}", Colors.RED)
    
    if vm:
        log_status("\nVM Information:", Colors.GREEN)
        log_status(f"  - VM memory: {vm_memory or '1024M'}", Colors.GREEN)
        log_status(f"  - VM CPUs: {vm_cpus or 2}", Colors.GREEN)
        log_status(f"  - VM disk size: {vm_disk or '10G'}", Colors.GREEN)
        if network:
            log_status("  - VM network: Connected to isolated network", Colors.GREEN)
        else:
            log_status("  - VM network: Using user-mode networking", Colors.GREEN)
        
        # Show VM status
        if env.is_vm_running():
            log_status("  - VM status: Running", Colors.GREEN)
        else:
            log_status("  - VM status: Stopped", Colors.YELLOW)
            
        log_status("\nVM Control Commands:", Colors.CYAN)
        log_status("  - Start VM: safespace --vm --start", Colors.CYAN)
        log_status("  - Stop VM: safespace --vm --stop", Colors.CYAN)
        log_status("  - Check status: safespace --vm --status", Colors.CYAN)
    
    # For comprehensive testing mode, provide additional instructions
    if test:
        log_status("\nComprehensive Testing Environment:", Colors.GREEN)
        log_status("  - Run tests: ./run_tests.sh", Colors.GREEN)
        log_status("  - Directory structure:", Colors.GREEN)
        log_status("    - tests/: For test files", Colors.GREEN)
        log_status("    - src/: For source code under test", Colors.GREEN)
        log_status("  - Available tools:", Colors.GREEN)
        log_status("    - pytest, pytest-cov, pytest-benchmark", Colors.GREEN)
        log_status("    - black, isort, mypy, ruff", Colors.GREEN)
        log_status("    - safety, bandit", Colors.GREEN)
        
        # Check if user wants to see full test environment details
        if click.confirm("Do you want to see details about the testing environment?", default=False):
            # Show setup.cfg content
            setup_cfg_path = env.root_dir / "setup.cfg"
            if setup_cfg_path.exists():
                log_status("\nsetup.cfg configuration:", Colors.CYAN)
                with open(setup_cfg_path, "r") as f:
                    for line in f.readlines()[:10]:  # Show first 10 lines
                        log_status(f"  {line.rstrip()}", Colors.WHITE)
                log_status("  ...", Colors.WHITE)
                    
            # Show available test commands
            log_status("\nAvailable testing commands:", Colors.CYAN)
            log_status("  - ./run_tests.sh - Run complete test suite", Colors.WHITE)
            log_status("  - pytest tests/ - Run basic tests", Colors.WHITE)
            log_status("  - pytest tests/ --benchmark-only - Run benchmarks", Colors.WHITE)
            log_status("  - pre-commit run --all-files - Run all pre-commit hooks", Colors.WHITE)
            log_status("  - tox - Run tests in multiple Python versions", Colors.WHITE)
    
    # For enhanced mode, provide additional instructions
    if enhanced:
        log_status("\nEnhanced Development Environment:", Colors.GREEN)
        log_status("  - IDE support: VS Code settings in .vscode/", Colors.GREEN)
        log_status("  - Git hooks: Pre-commit configuration in .pre-commit-config.yaml", Colors.GREEN)
        log_status("  - Development scripts:", Colors.GREEN)
        log_status("    - scripts/setup_dev.sh - Set up development environment", Colors.GREEN)
        log_status("    - scripts/update_deps.sh - Update dependencies", Colors.GREEN)
        
        # Check if user wants to see full enhanced environment details
        if click.confirm("Do you want to see details about the enhanced environment?", default=False):
            # Show directory structure
            import subprocess
            
            log_status("\nDirectory structure:", Colors.CYAN)
            try:
                result = subprocess.run(
                    ["find", str(env.root_dir), "-type", "d", "-not", "-path", "*/\\.*", "-maxdepth", "2"],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    for line in result.stdout.splitlines():
                        if str(env.root_dir) != line:  # Skip root directory
                            rel_path = Path(line).relative_to(env.root_dir)
                            log_status(f"  - {rel_path}/", Colors.WHITE)
            except Exception:
                pass
            
            # Show setup commands
            log_status("\nSetup commands:", Colors.CYAN)
            log_status("  1. cd " + str(env.root_dir), Colors.WHITE)
            log_status("  2. python -m venv venv", Colors.WHITE)
            log_status("  3. source venv/bin/activate  # or venv\\Scripts\\activate on Windows", Colors.WHITE)
            log_status("  4. ./scripts/setup_dev.sh", Colors.WHITE)
    
    return True

@main.command()
@click.option("-c", "--cleanup", is_flag=True, help="Clean up the internal environment")
@click.pass_context
def internal(ctx: click.Context, cleanup: bool) -> None:
    """Create or manage an internal testing environment"""
    # Print banner
    print_banner()
    
    # Create environment in internal mode
    env = SafeEnvironment(internal_mode=True)
    
    if cleanup or ctx.obj["cleanup"]:
        # Clean up the internal environment
        env.cleanup_internal()
    else:
        # Create and set up the internal environment
        if env.create():
            env.setup_internal()
        else:
            log_status("Failed to create internal environment", Colors.RED)
            sys.exit(1)

@main.command(name="wordspace")
@click.option("--section", help="Show specific documentation section")
@click.option("--subsection", help="Show specific documentation subsection")
@click.option("--tree", is_flag=True, help="Show documentation in tree view")
@click.option("--no-interactive", is_flag=True, help="Disable interactive mode")
@click.pass_context
def wordspace_command(ctx: click.Context, section: Optional[str] = None, 
                      subsection: Optional[str] = None, tree: bool = False, 
                      no_interactive: bool = False) -> None:
    """Show comprehensive documentation"""
    # Import the documentation CLI module
    from .docs.documentation_cli import display_documentation
    
    # If subsection is specified but section is not, show an error
    if subsection is not None and section is None:
        click.echo(click.style(
            "Error: --subsection requires --section",
            fg="red"
        ))
        sys.exit(1)
    
    # Call the documentation display function with all options
    display_documentation(
        section_id=section or "core-concepts",
        subsection_id=subsection,
        tree_view=tree,
        interactive=not (tree or no_interactive)
    )
    sys.exit(0)

@main.command(name="ws")
@click.option("--section", help="Show specific documentation section")
@click.option("--subsection", help="Show specific documentation subsection")
@click.option("--tree", is_flag=True, help="Show documentation in tree view")
@click.option("--no-interactive", is_flag=True, help="Disable interactive mode")
@click.pass_context
def ws_command(ctx: click.Context, section: Optional[str] = None, 
              subsection: Optional[str] = None, tree: bool = False, 
              no_interactive: bool = False) -> None:
    """Show comprehensive documentation (shorthand for wordspace)"""
    # Import the documentation CLI module
    from .docs.documentation_cli import display_documentation
    
    # If subsection is specified but section is not, show an error
    if subsection is not None and section is None:
        click.echo(click.style(
            "Error: --subsection requires --section",
            fg="red"
        ))
        sys.exit(1)
    
    # Call the documentation display function with all options
    display_documentation(
        section_id=section or "core-concepts",
        subsection_id=subsection,
        tree_view=tree,
        interactive=not (tree or no_interactive)
    )
    sys.exit(0)

@main.command()
@click.pass_context
def foreclose(ctx: click.Context) -> None:
    """Completely remove an environment and all backups"""
    # Print banner
    print_banner()
    
    # Confirm action
    if not click.confirm("This will completely remove the environment and all backups. Are you sure?"):
        log_status("Operation cancelled", Colors.YELLOW)
        sys.exit(0)
    
    # Create environment in internal mode
    env = SafeEnvironment(internal_mode=True)
    
    # Foreclose the environment
    env.foreclose()

if __name__ == "__main__":
    main()
