"""
Settings CLI for SafeSpace

This module provides a command-line interface for managing SafeSpace settings.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import click
import yaml

from .settings import (
    DEFAULT_SETTINGS_FILE,
    get_sections,
    get_settings,
    get_settings_in_section,
    load_settings,
    reset_settings,
    update_setting,
)
from .utils import Colors, log_status

# Set up logging
logger = logging.getLogger(__name__)


@click.group(name="settings")
@click.option(
    "--config-file",
    "-c",
    help="Custom config file path",
    type=click.Path(),
    default=None,
)
@click.pass_context
def settings_cli(ctx: click.Context, config_file: Optional[str] = None) -> None:
    """
    Manage SafeSpace settings.
    
    This command allows you to view, update, and reset SafeSpace settings.
    Settings are stored in YAML format in ~/.config/safespace/config.yaml by default.
    """
    if config_file:
        ctx.obj = {"config_file": Path(config_file)}
    else:
        ctx.obj = {"config_file": DEFAULT_SETTINGS_FILE}


@settings_cli.command(name="list")
@click.option("--section", "-s", help="Section to list settings for")
@click.option("--json", "as_json", is_flag=True, help="Output in JSON format")
@click.pass_context
def list_settings(ctx: click.Context, section: Optional[str] = None, as_json: bool = False) -> None:
    """
    List current settings.
    
    If no section is specified, lists all sections.
    """
    config_file = ctx.obj["config_file"]
    
    # Load settings
    settings = load_settings(config_file)
    
    if section:
        # List settings for specific section
        if not hasattr(settings, section):
            log_status(f"Invalid section: {section}", Colors.RED)
            return
        
        section_settings = get_settings_in_section(section)
        
        if as_json:
            click.echo(json.dumps(section_settings, indent=2))
        else:
            log_status(f"Settings for section: {section}", Colors.CYAN)
            for key, value in section_settings.items():
                click.echo(f"  {key}: {value}")
    else:
        # List all sections and their settings
        settings_dict = settings.to_dict()
        
        if as_json:
            click.echo(json.dumps(settings_dict, indent=2))
        else:
            log_status("Available sections:", Colors.CYAN)
            for section_name in get_sections():
                click.echo(f"  {section_name}")
            
            click.echo("\nUse 'safespace settings list --section SECTION_NAME' to see settings in a section.")


@settings_cli.command(name="get")
@click.argument("section")
@click.argument("setting")
@click.pass_context
def get_setting(ctx: click.Context, section: str, setting: str) -> None:
    """
    Get a specific setting value.
    
    SECTION is the settings section (e.g., general, vm, network).
    SETTING is the specific setting name.
    """
    config_file = ctx.obj["config_file"]
    
    # Load settings
    settings = load_settings(config_file)
    
    # Check if section exists
    if not hasattr(settings, section):
        log_status(f"Invalid section: {section}", Colors.RED)
        return
    
    section_obj = getattr(settings, section)
    
    # Check if setting exists
    if not hasattr(section_obj, setting):
        log_status(f"Invalid setting: {setting}", Colors.RED)
        return
    
    # Get the value
    value = getattr(section_obj, setting)
    
    # Display the value
    click.echo(f"{value}")


@settings_cli.command(name="set")
@click.argument("section")
@click.argument("setting")
@click.argument("value")
@click.pass_context
def set_setting(ctx: click.Context, section: str, setting: str, value: str) -> None:
    """
    Set a specific setting value.
    
    SECTION is the settings section (e.g., general, vm, network).
    SETTING is the specific setting name.
    VALUE is the new value to set.
    """
    config_file = ctx.obj["config_file"]
    
    # Update the setting
    result = update_setting(config_file, section, setting, value)
    
    if result:
        log_status(f"Setting updated: {section}.{setting} = {value}", Colors.GREEN)
    else:
        log_status(f"Failed to update setting: {section}.{setting}", Colors.RED)


@settings_cli.command(name="reset")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
@click.pass_context
def reset_all_settings(ctx: click.Context, yes: bool = False) -> None:
    """Reset all settings to defaults."""
    config_file = ctx.obj["config_file"]
    
    if not yes:
        if not click.confirm("Are you sure you want to reset all settings to defaults?"):
            log_status("Reset cancelled", Colors.YELLOW)
            return
    
    # Reset settings
    result = reset_settings(config_file)
    
    if result:
        log_status("Settings reset to defaults", Colors.GREEN)
    else:
        log_status("Failed to reset settings", Colors.RED)


@settings_cli.command(name="import")
@click.argument("import_file", type=click.Path(exists=True))
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
@click.pass_context
def import_settings(ctx: click.Context, import_file: str, yes: bool = False) -> None:
    """
    Import settings from a YAML or JSON file.
    
    IMPORT_FILE is the path to the file to import settings from.
    """
    config_file = ctx.obj["config_file"]
    import_path = Path(import_file)
    
    # Check if file exists
    if not import_path.exists():
        log_status(f"File does not exist: {import_file}", Colors.RED)
        return
    
    # Confirm import
    if not yes:
        if not click.confirm(f"Import settings from {import_file}?"):
            log_status("Import cancelled", Colors.YELLOW)
            return
    
    # Read the file
    try:
        with open(import_path, "r") as f:
            # Load based on file extension
            if import_path.suffix in (".yaml", ".yml"):
                data = yaml.safe_load(f)
            elif import_path.suffix == ".json":
                data = json.load(f)
            else:
                log_status("Unsupported file format. Use YAML or JSON.", Colors.RED)
                return
        
        if not data:
            log_status("Empty file", Colors.RED)
            return
            
        # Load current settings
        settings = load_settings(config_file)
        
        # Update all sections
        for section, section_data in data.items():
            if not hasattr(settings, section):
                log_status(f"Skipping unknown section: {section}", Colors.YELLOW)
                continue
            
            section_obj = getattr(settings, section)
            
            for key, value in section_data.items():
                if not hasattr(section_obj, key):
                    log_status(f"Skipping unknown setting: {section}.{key}", Colors.YELLOW)
                    continue
                
                # Set the value
                setattr(section_obj, key, value)
        
        # Save settings
        from .settings import save_settings
        if save_settings(settings, config_file):
            log_status(f"Settings imported from {import_file}", Colors.GREEN)
        else:
            log_status(f"Failed to save settings", Colors.RED)
    except Exception as e:
        log_status(f"Failed to import settings: {e}", Colors.RED)


@settings_cli.command(name="export")
@click.argument("export_file", type=click.Path())
@click.option("--format", "-f", type=click.Choice(["yaml", "json"]), default="yaml", help="Export format")
@click.pass_context
def export_settings(ctx: click.Context, export_file: str, format: str = "yaml") -> None:
    """
    Export settings to a file.
    
    EXPORT_FILE is the path to save settings to.
    """
    config_file = ctx.obj["config_file"]
    export_path = Path(export_file)
    
    # Load settings
    settings = load_settings(config_file)
    settings_dict = settings.to_dict()
    
    # Export settings
    try:
        with open(export_path, "w") as f:
            if format == "yaml":
                yaml.dump(settings_dict, f, default_flow_style=False, sort_keys=False)
            else:  # json
                json.dump(settings_dict, f, indent=2)
        
        log_status(f"Settings exported to {export_file}", Colors.GREEN)
    except Exception as e:
        log_status(f"Failed to export settings: {e}", Colors.RED)


@settings_cli.command(name="examples")
@click.pass_context
def show_examples(ctx: click.Context) -> None:
    """Show example settings commands."""
    click.echo("Example SafeSpace settings commands:")
    click.echo("")
    click.echo("  # List all settings sections")
    click.echo("  safespace settings list")
    click.echo("")
    click.echo("  # List settings in the VM section")
    click.echo("  safespace settings list --section vm")
    click.echo("")
    click.echo("  # Get a specific setting")
    click.echo("  safespace settings get vm default_memory")
    click.echo("")
    click.echo("  # Set a specific setting")
    click.echo("  safespace settings set vm default_memory 2048M")
    click.echo("")
    click.echo("  # Reset all settings to defaults")
    click.echo("  safespace settings reset")
    click.echo("")
    click.echo("  # Export settings to a file")
    click.echo("  safespace settings export my_settings.yaml")
    click.echo("")
    click.echo("  # Import settings from a file")
    click.echo("  safespace settings import my_settings.yaml") 