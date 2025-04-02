"""
Documentation CLI for SafeSpace

This module provides a CLI interface for displaying the SafeSpace documentation.
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

# Set up logging
logger = logging.getLogger(__name__)

# Constants
DOCS_DIR = Path(__file__).parent
DOCUMENTATION_FILE = DOCS_DIR / "documentation.json"

def load_documentation() -> Dict[str, Any]:
    """
    Load the documentation from the JSON file.
    
    Returns:
        Dict[str, Any]: The documentation data
    """
    try:
        with open(DOCUMENTATION_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load documentation: {e}")
        return {
            "name": "SafeSpace",
            "version": "current",
            "description": "Documentation not available.",
            "sections": []
        }

def display_section(section: Dict[str, Any], console: Console) -> None:
    """
    Display a section of the documentation.
    
    Args:
        section: The section to display
        console: The rich console to display on
    """
    # Display section title and content
    console.print(Panel(
        Markdown(f"# {section['title']}\n\n{section['content']}"),
        title=f"[bold]{section['title']}[/bold]",
        expand=False
    ))
    
    # Display subsections
    if "subsections" in section and section["subsections"]:
        for subsection in section["subsections"]:
            console.print()
            console.print(Panel(
                Markdown(f"## {subsection['title']}\n\n{subsection['content']}"),
                title=f"[bold]{subsection['title']}[/bold]",
                expand=False
            ))
            
            # Display parameters if available
            if "parameters" in subsection and subsection["parameters"]:
                console.print()
                params_table = Table(title="Parameters", show_header=True)
                params_table.add_column("Parameter", style="cyan")
                params_table.add_column("Description", style="green")
                
                for param, desc in subsection["parameters"].items():
                    params_table.add_row(param, desc)
                
                console.print(params_table)

def display_menu(docs: Dict[str, Any], console: Console) -> None:
    """
    Display the main menu of the documentation.
    
    Args:
        docs: The documentation data
        console: The rich console to display on
    """
    console.print(Panel(
        Markdown(f"# {docs['name']} Documentation\n\n{docs['description']}"),
        title=f"[bold]{docs['name']} v{docs['version']}[/bold]",
        expand=False
    ))
    
    console.print("\n[bold]Available Sections:[/bold]")
    
    section_table = Table(show_header=True)
    section_table.add_column("ID", style="cyan")
    section_table.add_column("Title", style="green")
    section_table.add_column("Description", style="yellow")
    
    for section in docs["sections"]:
        section_table.add_row(
            section["id"],
            section["title"],
            section["content"].split("\n")[0]
        )
    
    console.print(section_table)
    console.print("\n[bold]Usage:[/bold] safespace --wordspace [section_id]")

def display_section_tree(docs: Dict[str, Any], console: Console) -> None:
    """
    Display a tree view of all sections and subsections.
    
    Args:
        docs: The documentation data
        console: The rich console to display on
    """
    tree = Tree(f"[bold]{docs['name']} Documentation[/bold]")
    
    for section in docs["sections"]:
        section_node = tree.add(f"[cyan]{section['title']}[/cyan]")
        
        if "subsections" in section and section["subsections"]:
            for subsection in section["subsections"]:
                subsection_node = section_node.add(f"[green]{subsection['title']}[/green]")
                
                # Add parameters if available
                if "parameters" in subsection and subsection["parameters"]:
                    params_node = subsection_node.add("[yellow]Parameters[/yellow]")
                    for param, desc in subsection["parameters"].items():
                        params_node.add(f"[blue]{param}[/blue]: {desc}")
    
    console.print(tree)

def find_section_by_id(docs: Dict[str, Any], section_id: str) -> Optional[Dict[str, Any]]:
    """
    Find a section by its ID.
    
    Args:
        docs: The documentation data
        section_id: The ID of the section to find
        
    Returns:
        Optional[Dict[str, Any]]: The section if found, None otherwise
    """
    for section in docs["sections"]:
        if section["id"] == section_id:
            return section
    return None

def display_documentation(section_id: Optional[str] = None, tree_view: bool = False) -> None:
    """
    Display the documentation.
    
    Args:
        section_id: The ID of the section to display (if None, display menu)
        tree_view: Whether to display a tree view of all sections
    """
    console = Console()
    docs = load_documentation()
    
    if tree_view:
        display_section_tree(docs, console)
    elif section_id is None:
        display_menu(docs, console)
    else:
        section = find_section_by_id(docs, section_id)
        if section is not None:
            display_section(section, console)
        else:
            console.print(f"[bold red]Section '{section_id}' not found.[/bold red]")
            display_menu(docs, console)

def main() -> None:
    """Main entry point for the documentation CLI"""
    import argparse
    
    parser = argparse.ArgumentParser(description="SafeSpace Documentation")
    parser.add_argument("section", nargs="?", help="Section ID to display")
    parser.add_argument("--tree", action="store_true", help="Display a tree view of all sections")
    
    args = parser.parse_args()
    display_documentation(args.section, args.tree)

if __name__ == "__main__":
    main() 