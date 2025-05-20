#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.9"
# dependencies = [
#   "obsidiantools",
#   "python-dotenv",
#   "rich"
# ]
# ///

import os
import sys
import re
import json
import datetime
import obsidiantools.api as otools
from pathlib import Path
from rich.console import Console
from dotenv import load_dotenv

# Initialize rich console
console = Console()

class ObsidianAdapter:
    """
    An adapter class to interact with local Obsidian vault files, designed
    to provide similar functionality to the Notion API tools used in the
    original codebase.
    """
    
    def __init__(self, vault_path=None):
        """
        Initialize the Obsidian adapter with a path to the vault.
        
        Args:
            vault_path (str, optional): Path to Obsidian vault. If not provided,
                                        will try to load from OBSIDIAN_VAULT_PATH 
                                        environment variable.
        """
        load_dotenv()
        
        # Try to get vault path from args, then env var
        self.vault_path = vault_path or os.getenv("OBSIDIAN_VAULT_PATH")
        
        if not self.vault_path:
            console.print("[bold red]ERROR: Obsidian vault path not provided and OBSIDIAN_VAULT_PATH not found in environment variables.[/bold red]")
            sys.exit(1)
            
        # Validate the vault path
        if not os.path.isdir(self.vault_path):
            console.print(f"[bold red]ERROR: Obsidian vault path '{self.vault_path}' is not a valid directory.[/bold red]")
            sys.exit(1)
            
        console.print(f"[bold green]Connecting to Obsidian vault at: [/bold green][blue]{self.vault_path}[/blue]")
        
        try:
            # Connect to the vault
            self.vault = otools.Vault(self.vault_path).connect().gather()
            console.print(f"[bold green]Successfully connected to Obsidian vault with {len(self.vault.notes)} notes[/bold green]")
        except Exception as e:
            console.print(f"[bold red]ERROR: Failed to connect to Obsidian vault: {str(e)}[/bold red]")
            sys.exit(1)
            
    def search_pages(self, query):
        """
        Search for pages/notes in the Obsidian vault that match the query.
        
        Args:
            query (str): The search query (page name or content)
            
        Returns:
            list: List of dictionaries with page information
        """
        results = []
        
        for note_path in self.vault.notes:
            note_name = Path(note_path).stem
            
            # Simple case-insensitive search in filename
            if query.lower() in note_name.lower():
                source_text = self.vault.get_source_text(note_path)
                created_time = os.path.getctime(os.path.join(self.vault_path, note_path))
                last_modified = os.path.getmtime(os.path.join(self.vault_path, note_path))
                
                results.append({
                    "id": note_path,  # Using the path as the ID
                    "url": f"obsidian://open?vault={os.path.basename(self.vault_path)}&file={note_path}",
                    "title": note_name,
                    "created_time": datetime.datetime.fromtimestamp(created_time).isoformat(),
                    "last_edited_time": datetime.datetime.fromtimestamp(last_modified).isoformat(),
                    "preview": source_text[:100] + "..." if len(source_text) > 100 else source_text
                })
                
        return results
    
    def get_page(self, page_id):
        """
        Get detailed information about a specific page/note.
        
        Args:
            page_id (str): The ID (path) of the page
            
        Returns:
            dict: Page information
        """
        # Validate if the note exists
        if page_id not in self.vault.notes:
            console.print(f"[bold red]ERROR: Note with ID '{page_id}' not found in the vault.[/bold red]")
            return None
            
        note_path = page_id
        note_name = Path(note_path).stem
        source_text = self.vault.get_source_text(note_path)
        created_time = os.path.getctime(os.path.join(self.vault_path, note_path))
        last_modified = os.path.getmtime(os.path.join(self.vault_path, note_path))
        
        return {
            "id": note_path,
            "url": f"obsidian://open?vault={os.path.basename(self.vault_path)}&file={note_path}",
            "title": note_name,
            "created_time": datetime.datetime.fromtimestamp(created_time).isoformat(),
            "last_edited_time": datetime.datetime.fromtimestamp(last_modified).isoformat(),
            "content": source_text
        }
    
    def get_blocks(self, page_id):
        """
        Get the blocks (content sections) from a page.
        This simulates Notion's block structure by parsing Markdown.
        
        Args:
            page_id (str): The ID (path) of the page
            
        Returns:
            list: List of block dictionaries
        """
        if page_id not in self.vault.notes:
            console.print(f"[bold red]ERROR: Note with ID '{page_id}' not found in the vault.[/bold red]")
            return []
            
        source_text = self.vault.get_source_text(page_id)
        
        # Parse the Markdown content into blocks
        blocks = []
        lines = source_text.split('\n')
        
        # Process lines and identify to-do items and other blocks
        block_id = 0
        for i, line in enumerate(lines):
            block_id += 1
            
            # Process to-do items
            todo_match = re.match(r'^(-|\*) \[([ xX])\] (.+)$', line.strip())
            if todo_match:
                prefix, checked, content = todo_match.groups()
                blocks.append({
                    "id": f"{page_id}_{block_id}",
                    "type": "to_do",
                    "has_children": False,
                    "to_do": {
                        "checked": checked.lower() == 'x',
                        "text": content.strip()
                    },
                    "line_number": i
                })
                continue
                
            # Process headers
            header_match = re.match(r'^(#{1,6}) (.+)$', line.strip())
            if header_match:
                level, content = header_match.groups()
                blocks.append({
                    "id": f"{page_id}_{block_id}",
                    "type": "heading",
                    "has_children": False,
                    "heading": {
                        "level": len(level),
                        "text": content.strip()
                    },
                    "line_number": i
                })
                continue
                
            # Process paragraphs (non-empty lines that don't match other patterns)
            if line.strip():
                blocks.append({
                    "id": f"{page_id}_{block_id}",
                    "type": "paragraph",
                    "has_children": False,
                    "paragraph": {
                        "text": line.strip()
                    },
                    "line_number": i
                })
                
        return blocks
    
    def update_block(self, block_id, properties):
        """
        Update a block in an Obsidian note.
        
        Args:
            block_id (str): The ID of the block in format "page_id_block_number"
            properties (dict): Properties to update
            
        Returns:
            dict: Updated block information
        """
        try:
            # Parse the block ID to get the page ID and line number
            page_id, block_num = block_id.rsplit('_', 1)
            
            if page_id not in self.vault.notes:
                console.print(f"[bold red]ERROR: Note with ID '{page_id}' not found in the vault.[/bold red]")
                return None
                
            # Read the current content
            file_path = os.path.join(self.vault_path, page_id)
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            # Get the blocks to find the line number
            blocks = self.get_blocks(page_id)
            target_block = next((b for b in blocks if b["id"] == block_id), None)
            
            if not target_block:
                console.print(f"[bold red]ERROR: Block with ID '{block_id}' not found in the note.[/bold red]")
                return None
                
            line_number = target_block["line_number"]
            
            # Update the line based on block type
            if target_block["type"] == "to_do":
                if "checked" in properties.get("to_do", {}):
                    checked = properties["to_do"]["checked"]
                    checkbox = "[x]" if checked else "[ ]"
                    
                    # Extract the prefix and content from the original line
                    original_line = lines[line_number]
                    todo_match = re.match(r'^(-|\*) \[[ xX]\] (.+)$', original_line.strip())
                    
                    if todo_match:
                        prefix, content = todo_match.groups()
                        lines[line_number] = f"{prefix} {checkbox} {content}\n"
            
            # Write the updated content back
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
                
            console.print(f"[bold green]Updated block in note: [/bold green][blue]{page_id}[/blue]")
            
            # Return the updated block
            return self.get_blocks(page_id)[target_block["line_number"]]
            
        except Exception as e:
            console.print(f"[bold red]ERROR: Failed to update block: {str(e)}[/bold red]")
            return None

# Example usage
if __name__ == "__main__":
    # Test the adapter functionality
    if len(sys.argv) < 2:
        console.print("[bold red]ERROR: Please provide an Obsidian vault path or set the OBSIDIAN_VAULT_PATH environment variable.[/bold red]")
        console.print("Usage: python obsidian_adapter.py <obsidian_vault_path>")
        sys.exit(1)
        
    vault_path = sys.argv[1]
    adapter = ObsidianAdapter(vault_path)
    
    # Test search
    console.print("\n[bold]Testing search functionality:[/bold]")
    results = adapter.search_pages("test")
    console.print(f"Found {len(results)} notes with 'test' in the name")
    
    if results:
        # Get the first result for further testing
        first_result = results[0]
        page_id = first_result["id"]
        
        # Test getting page details
        console.print(f"\n[bold]Testing page details for:[/bold] {first_result['title']}")
        page = adapter.get_page(page_id)
        console.print(f"Page title: {page['title']}")
        console.print(f"Content preview: {page['content'][:50]}...")
        
        # Test getting blocks
        console.print(f"\n[bold]Testing block retrieval for:[/bold] {first_result['title']}")
        blocks = adapter.get_blocks(page_id)
        console.print(f"Found {len(blocks)} blocks")
        
        # Test updating a todo block if any exists
        todo_blocks = [b for b in blocks if b["type"] == "to_do"]
        if todo_blocks:
            console.print(f"\n[bold]Testing block update for:[/bold] {todo_blocks[0]['to_do']['text']}")
            updated = adapter.update_block(todo_blocks[0]["id"], {"to_do": {"checked": not todo_blocks[0]["to_do"]["checked"]}})
            if updated:
                console.print("[bold green]Successfully updated todo item[/bold green]")
            else:
                console.print("[bold red]Failed to update todo item[/bold red]")