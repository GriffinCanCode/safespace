#!/usr/bin/env python3
"""SafeSpace author command implementation for displaying information about the author.

This module provides a fun and entertaining UI that displays information about
the author, Griffin, 'A programming God...'
"""

import logging
from typing import Any, Optional

from .bio import (
    GRIFFIN_LOGO,
    GOD_MODE_TEXT,
    get_random_facts,
    get_random_quote,
    get_random_advice
)

# Set up logging
logger = logging.getLogger(__name__)

def fallback_display():
    """Display author information in plain text mode if GUI fails."""
    print("\n" + "=" * 40)
    print("  GRIFFIN: THE PROGRAMMING GOD")
    print("=" * 40)

    try:
        print("\nFun Facts:")
        for i, fact in enumerate(get_random_facts(3), 1):
            print(f"{i}. {fact}")

        print("\nWords of Wisdom:")
        print(f'"{get_random_quote()}"')

        print("\nDaily Advice:")
        print(get_random_advice())
    except Exception as e:
        logger.error(
            f"Error in fallback display: {str(e)}",
            extra={"command": "author", "error_type": type(e).__name__}
        )
        print("\nCouldn't load author data, but Griffin is still a programming god.")

    print("\n" + "=" * 40 + "\n")


class AuthorCommand:
    """Command to display information about the author."""

    def handle_error(self, error: Exception) -> None:
        """Handle errors in command execution.
        
        Args:
            error: The exception that occurred
        """
        logger.error(
            f"Error in author command: {str(error)}",
            extra={"command": "author", "error_type": type(error).__name__}
        )

    def execute(self, args: Optional[Any] = None) -> bool:
        """Execute the author command.
        
        Args:
            args: Command arguments (not used)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Log the command execution
            logger.info(
                "Displaying author information",
                extra={"command": "author"}
            )

            # Try to import and use the GUI module
            try:
                # This is a placeholder for potential GUI implementation
                # In a real implementation, you would import your GUI module
                # and call the appropriate function
                # Commented out since we don't have this module
                # from safespace.gui import show_author_screen
                # show_author_screen()
                
                # For now, always use fallback display
                fallback_display()
            except ImportError as e:
                logger.warning(
                    f"GUI module not available: {str(e)}",
                    extra={"command": "author", "error_type": "ImportError"}
                )
                fallback_display()
            except Exception as e:
                logger.error(
                    f"GUI display failed: {str(e)}",
                    extra={"command": "author", "error_type": type(e).__name__}
                )
                # If GUI fails, use fallback display
                fallback_display()

            return True

        except Exception as e:
            self.handle_error(e)
            # Ensure we still show something even if there's an error
            try:
                fallback_display()
            except:
                print("Error displaying author information. Please try again.")
            return False


def show_author() -> None:
    """Show information about the author."""
    command = AuthorCommand()
    command.execute(None)


if __name__ == "__main__":
    show_author()
