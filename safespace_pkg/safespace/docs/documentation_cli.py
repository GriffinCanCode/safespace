"""
Documentation CLI for SafeSpace

This module provides a CLI interface for displaying the SafeSpace documentation.
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree
from rich.prompt import Prompt
from rich.layout import Layout
from rich.box import ROUNDED
from rich.style import Style
from rich import box

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

def find_subsection_by_id(section: Dict[str, Any], subsection_id: str) -> Optional[Dict[str, Any]]:
    """
    Find a subsection by its ID.
    
    Args:
        section: The section to search in
        subsection_id: The ID of the subsection to find
        
    Returns:
        Optional[Dict[str, Any]]: The subsection if found, None otherwise
    """
    if "subsections" in section:
        for subsection in section["subsections"]:
            if subsection.get("id") == subsection_id:
                return subsection
    return None

def display_navigation_bar(navigation: Dict[str, str], console: Console, docs: Dict[str, Any]) -> None:
    """
    Display a navigation bar with links to other sections.
    
    Args:
        navigation: Navigation links (previous, next, parent)
        console: The rich console to display on
        docs: The documentation data
    """
    nav_table = Table(box=box.SIMPLE, show_header=False, show_edge=False, expand=True)
    nav_table.add_column("Previous", style="cyan", justify="left")
    nav_table.add_column("Up", style="green", justify="center")
    nav_table.add_column("Next", style="cyan", justify="right")
    
    # Previous link
    prev_text = ""
    if "previous" in navigation:
        prev_id = navigation["previous"]
        prev_section = find_section_by_id(docs, prev_id)
        if prev_section:
            prev_text = f"← {prev_section['title']}"
    
    # Parent link
    parent_text = ""
    if "parent" in navigation:
        parent_id = navigation["parent"]
        parent_section = find_section_by_id(docs, parent_id)
        if parent_section:
            parent_text = f"↑ {parent_section['title']}"
    
    # Next link
    next_text = ""
    if "next" in navigation:
        next_id = navigation["next"]
        next_section = find_section_by_id(docs, next_id)
        if next_section:
            next_text = f"{next_section['title']} →"
    
    nav_table.add_row(prev_text, parent_text, next_text)
    console.print(nav_table)

def display_subsection(subsection: Dict[str, Any], console: Console, docs: Dict[str, Any]) -> None:
    """
    Display a subsection of the documentation.
    
    Args:
        subsection: The subsection to display
        console: The rich console to display on
        docs: The documentation data
    """
    # Display subsection title and content
    console.print(Panel(
        Markdown(f"## {subsection['title']}\n\n{subsection['content']}"),
        title=f"[bold]{subsection['title']}[/bold]",
        box=ROUNDED,
        expand=False
    ))
    
    # Display parameters if available
    if "parameters" in subsection and subsection["parameters"]:
        console.print()
        params_table = Table(title="Parameters", show_header=True, box=box.ROUNDED)
        params_table.add_column("Parameter", style="cyan")
        params_table.add_column("Description", style="green")
        
        for param, desc in subsection["parameters"].items():
            params_table.add_row(param, desc)
        
        console.print(params_table)
    
    # Display navigation if available
    if "navigation" in subsection:
        console.print()
        display_navigation_bar(subsection["navigation"], console, docs)

def display_section(section: Dict[str, Any], console: Console, docs: Dict[str, Any], 
                  subsection_id: Optional[str] = None) -> None:
    """
    Display a section of the documentation.
    
    Args:
        section: The section to display
        console: The rich console to display on
        docs: The documentation data
        subsection_id: Optional ID of a specific subsection to display
    """
    # If a specific subsection is requested, display only that
    if subsection_id:
        subsection = find_subsection_by_id(section, subsection_id)
        if subsection:
            display_subsection(subsection, console, docs)
            return
    
    # Display section title and content
    console.print(Panel(
        Markdown(f"# {section['title']}\n\n{section['content']}"),
        title=f"[bold]{section['title']}[/bold]",
        box=ROUNDED,
        expand=False
    ))
    
    # Display navigation if available
    if "navigation" in section:
        console.print()
        display_navigation_bar(section["navigation"], console, docs)
    
    # Display subsections
    if "subsections" in section and section["subsections"]:
        # Display a table of subsections
        console.print("\n[bold]Subsections:[/bold]")
        subsection_table = Table(show_header=True, box=box.ROUNDED)
        subsection_table.add_column("ID", style="cyan")
        subsection_table.add_column("Title", style="green")
        
        for subsection in section["subsections"]:
            subsection_id = subsection.get("id", "")
            subsection_table.add_row(
                subsection_id,
                subsection["title"]
            )
        
        console.print(subsection_table)
        
        # Show usage hint
        console.print("\n[bold]Usage:[/bold] safespace --wordspace-section " + 
                     f"{section['id']} --wordspace-subsection <subsection_id>")

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
        box=ROUNDED,
        expand=False
    ))
    
    console.print("\n[bold]Available Sections:[/bold]")
    
    section_table = Table(show_header=True, box=box.ROUNDED)
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
    console.print("\n[bold]Usage:[/bold]")
    console.print("  safespace --wordspace [section_id]")
    console.print("  safespace --wordspace-section [section_id]")
    console.print("  safespace --wordspace-section [section_id] --wordspace-subsection [subsection_id]")
    console.print("  safespace --wordspace-tree")
    console.print("  safespace --wordspace-interactive")

def display_section_tree(docs: Dict[str, Any], console: Console) -> None:
    """
    Display a tree view of all sections and subsections.
    
    Args:
        docs: The documentation data
        console: The rich console to display on
    """
    tree = Tree(f"[bold]{docs['name']} Documentation[/bold]")
    
    for section in docs["sections"]:
        section_id = section.get("id", "")
        section_node = tree.add(f"[cyan]{section['title']}[/cyan] [dim]({section_id})[/dim]")
        
        if "subsections" in section and section["subsections"]:
            for subsection in section["subsections"]:
                subsection_id = subsection.get("id", "")
                subsection_text = f"[green]{subsection['title']}[/green]"
                if subsection_id:
                    subsection_text += f" [dim]({subsection_id})[/dim]"
                subsection_node = section_node.add(subsection_text)
                
                # Add parameters if available
                if "parameters" in subsection and subsection["parameters"]:
                    params_node = subsection_node.add("[yellow]Parameters[/yellow]")
                    for param, desc in subsection["parameters"].items():
                        # Shorten description if too long
                        short_desc = desc
                        if len(short_desc) > 50:
                            short_desc = short_desc[:47] + "..."
                        params_node.add(f"[blue]{param}[/blue]: {short_desc}")
    
    console.print(tree)

def run_interactive_mode(docs: Dict[str, Any]) -> None:
    """
    Run an interactive documentation browser.
    
    Args:
        docs: The documentation data
    """
    console = Console()
    current_section = None
    current_subsection = None
    history = []
    
    while True:
        console.clear()
        
        # Display current content
        if current_section is None:
            display_menu(docs, console)
            prompt = "Enter section ID (or 'q' to quit, 't' for tree view): "
        elif current_subsection is None:
            section = find_section_by_id(docs, current_section)
            if section:
                display_section(section, console, docs)
                prompt = "Enter subsection ID (or 'b' to go back, 'q' to quit): "
            else:
                console.print(f"[bold red]Section '{current_section}' not found.[/bold red]")
                current_section = None
                continue
        else:
            section = find_section_by_id(docs, current_section)
            if section:
                subsection = find_subsection_by_id(section, current_subsection)
                if subsection:
                    display_subsection(subsection, console, docs)
                    prompt = "Press 'b' to go back, 'q' to quit: "
                else:
                    console.print(f"[bold red]Subsection '{current_subsection}' not found.[/bold red]")
                    current_subsection = None
                    continue
            else:
                console.print(f"[bold red]Section '{current_section}' not found.[/bold red]")
                current_section = None
                continue
        
        # Get user input
        user_input = Prompt.ask(prompt)
        
        # Process input
        if user_input.lower() == 'q':
            break
        elif user_input.lower() == 'b':
            if current_subsection is not None:
                current_subsection = None
            elif current_section is not None:
                current_section = None
            elif history:
                last = history.pop()
                current_section = last[0]
                current_subsection = last[1]
        elif user_input.lower() == 't' and current_section is None:
            console.clear()
            display_section_tree(docs, console)
            input("Press Enter to continue...")
        elif current_section is None:
            # Trying to navigate to a section
            section = find_section_by_id(docs, user_input)
            if section:
                current_section = user_input
            else:
                console.print(f"[bold red]Section '{user_input}' not found.[/bold red]")
                input("Press Enter to continue...")
        elif current_subsection is None:
            # Trying to navigate to a subsection
            section = find_section_by_id(docs, current_section)
            if section:
                subsection = find_subsection_by_id(section, user_input)
                if subsection:
                    history.append((current_section, current_subsection))
                    current_subsection = user_input
                else:
                    console.print(f"[bold red]Subsection '{user_input}' not found.[/bold red]")
                    input("Press Enter to continue...")
            else:
                console.print(f"[bold red]Section '{current_section}' not found.[/bold red]")
                current_section = None
        else:
            # Already at subsection level, any input goes back
            current_subsection = None

def display_documentation(section_id: Optional[str] = None, subsection_id: Optional[str] = None,
                        tree_view: bool = False, interactive: bool = False) -> None:
    """
    Display the documentation.
    
    Args:
        section_id: The ID of the section to display (if None, display menu)
        subsection_id: The ID of the subsection to display (requires section_id)
        tree_view: Whether to display a tree view of all sections
        interactive: Whether to run in interactive mode
    """
    console = Console()
    docs = load_documentation()
    
    if interactive:
        run_interactive_mode(docs)
    elif tree_view:
        display_section_tree(docs, console)
    elif section_id is None:
        display_menu(docs, console)
    else:
        section = find_section_by_id(docs, section_id)
        if section is not None:
            display_section(section, console, docs, subsection_id)
        else:
            console.print(f"[bold red]Section '{section_id}' not found.[/bold red]")
            display_menu(docs, console)

def main() -> None:
    """Main entry point for the documentation CLI"""
    import argparse
    
    parser = argparse.ArgumentParser(description="SafeSpace Documentation")
    parser.add_argument("section", nargs="?", help="Section ID to display")
    parser.add_argument("--tree", action="store_true", help="Display a tree view of all sections")
    parser.add_argument("--subsection", help="Subsection ID to display")
    parser.add_argument("--interactive", action="store_true", help="Run in interactive mode")
    
    args = parser.parse_args()
    display_documentation(
        args.section, 
        args.subsection, 
        args.tree, 
        args.interactive
    )

if __name__ == "__main__":
    main() 