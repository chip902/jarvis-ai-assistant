#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.9"
# dependencies = [
#   "python-dotenv",
#   "rich",
#   "obsidiantools"
# ]
# ///

import os
import sys
import json
from obsidian_adapter import ObsidianAdapter
from rich.console import Console

# Initialize rich console
console = Console()

def update_todo(vault_path, block_id, checked=True):
    """
    Update a todo item in an Obsidian note.
    
    Args:
        vault_path (str): Path to the Obsidian vault
        block_id (str): ID of the block to update
        checked (bool, optional): Whether to mark as checked or unchecked. Defaults to True.
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Initialize the adapter
        adapter = ObsidianAdapter(vault_path)
        
        # Update the block
        result = adapter.update_block(block_id, {"to_do": {"checked": checked}})
        
        if result:
            console.print(f"[bold green]✅ Successfully updated todo with ID: {block_id}[/bold green]")
            return True
        else:
            console.print(f"[bold red]❌ Failed to update todo with ID: {block_id}[/bold red]")
            return False
    
    except Exception as e:
        console.print(f"[bold red]❌ Error updating todo: {str(e)}[/bold red]")
        return False

if __name__ == "__main__":
    # Check arguments
    if len(sys.argv) < 3:
        console.print("[bold red]ERROR: Missing required arguments.[/bold red]")
        console.print("Usage: python update_obsidian_todo.py <vault_path> <block_id> [checked]")
        sys.exit(1)
    
    vault_path = sys.argv[1]
    block_id = sys.argv[2]
    
    # Optional checked argument (defaults to True)
    checked = True
    if len(sys.argv) > 3:
        checked = sys.argv[3].lower() in ("true", "t", "yes", "y", "1")
    
    if update_todo(vault_path, block_id, checked):
        sys.exit(0)
    else:
        sys.exit(1)