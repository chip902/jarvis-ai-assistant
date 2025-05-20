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
import subprocess
import json
from dotenv import load_dotenv
from rich.console import Console
from rich.syntax import Syntax
from rich import print as rprint
from pathlib import Path

# Import the ObsidianAdapter
from obsidian_adapter import ObsidianAdapter

# Initialize rich console
console = Console()

# Load environment variables
load_dotenv()
OBSIDIAN_VAULT_PATH = os.getenv("OBSIDIAN_VAULT_PATH")
if not OBSIDIAN_VAULT_PATH:
    console.print(
        "[bold red]ERROR: OBSIDIAN_VAULT_PATH not found in environment variables.[/bold red]"
    )
    console.print(
        "Please set the OBSIDIAN_VAULT_PATH environment variable to the path of your Obsidian vault."
    )
    sys.exit(1)

# Check for the page name argument
if len(sys.argv) < 2:
    console.print(
        "[bold red]ERROR: Please provide an Obsidian note name as an argument.[/bold red]"
    )
    console.print(
        "Usage: uv run claude_code_is_programmable_obsidian.py <obsidian_note_name>")
    sys.exit(1)

page_name = sys.argv[1]

# Define the allowed tools for Claude
allowed_tools = [
    # Standard Claude Code tools
    "Bash",
    "Edit",
    "Read",
    "Glob",
    "Grep",
    "LS",
    "Batch",
    "Task",
    "Write",
    "WebFetch",
    "TodoRead",
    "TodoWrite",
    "WebSearch"
]

# Initialize the Obsidian adapter
try:
    adapter = ObsidianAdapter(OBSIDIAN_VAULT_PATH)
    console.print(f"[bold green]✅ Connected to Obsidian vault at: {OBSIDIAN_VAULT_PATH}[/bold green]")
except Exception as e:
    console.print(f"[bold red]❌ Failed to connect to Obsidian vault: {str(e)}[/bold red]")
    sys.exit(1)

# Search for the requested page
pages = adapter.search_pages(page_name)
if not pages:
    console.print(f"[bold red]❌ Page not found: {page_name}[/bold red]")
    sys.exit(1)

# Find the best match (exact match or first result)
page = next((p for p in pages if p["title"].lower() == page_name.lower()), pages[0])
console.print(f"[bold green]✅ Found page: {page['title']} ({page['id']})[/bold green]")

# Get the blocks (content) from the page
blocks = adapter.get_blocks(page["id"])
console.print(f"[bold green]✅ Retrieved {len(blocks)} blocks from the page[/bold green]")

# Extract all uncompleted todo items
todo_items = [b for b in blocks if b["type"] == "to_do" and not b["to_do"]["checked"]]
console.print(f"[bold green]Found {len(todo_items)} uncompleted todo items[/bold green]")

if not todo_items:
    console.print("[bold yellow]No uncompleted todo items found on the page.[/bold yellow]")
    sys.exit(0)

# Create a JSON file with todo data to make it accessible to Claude
todo_data_file = "_temp_obsidian_todos.json"
with open(todo_data_file, "w") as f:
    json.dump(todo_items, f, indent=2)

# Create the prompt for Claude
prompt = f"""
# Obsidian Todo Code Generation Agent

## Objective
You are an agent that will:
1. Process todo items from an Obsidian page named "{page['title']}"
2. For each incomplete todo, implement the code changes described in the todo
3. Commit the changes with a descriptive message
4. Mark the todo item as complete in the Obsidian page
5. Continue to the next todo item

## Process - Follow these steps exactly:

### Step 1: Load todo items
- The todo items have already been extracted from the Obsidian page
- They are available in the file "{todo_data_file}"
- Load this file to get the list of todos to process

### Step 2: Process each todo
For each todo item:
1. Read and understand the todo description
2. Implement the code changes described:
   - Use Glob, Grep, Read to explore the codebase
   - Use Edit or Write to modify or create files
   - Use Bash when necessary to run commands
3. Test your implementation if tests are available
4. Stage and commit your changes with a descriptive message:
   ```bash
   git add .
   git commit -m "Descriptive message about what was implemented"
   ```
5. Mark the todo as complete in Obsidian by:
   - Using the Bash tool to run the update_obsidian_todo.py script:
   - Command: python update_obsidian_todo.py "{OBSIDIAN_VAULT_PATH}" "BLOCK_ID"
   - Replace BLOCK_ID with the actual block ID from the todo item

### Step 3: Wrap up
- Provide a summary of all todos processed and changes made

## Important Notes:
- Process todos in the order they appear on the page
- Make one commit per todo item
- Ensure each commit message clearly describes what was implemented
- If a todo cannot be completed, note why but don't mark it as complete

Now begin your task by loading the todo items from "{todo_data_file}" and processing them one by one.
"""

# Execute the Claude command with stream-json output format
try:
    console.print(
        f"[bold blue]🤖 Starting Claude Code to process todos from Obsidian page:[/bold blue] [yellow]{page['title']}[/yellow]"
    )

    cmd = [
        "claude",
        "-p",
        prompt,
        "--output-format",
        "stream-json",
        "--allowedTools",
    ] + allowed_tools

    # Start the process and read output as it comes
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,  # Line buffered
    )

    # Process and display JSON output in real-time
    console.print("\n[bold green]📊 Streaming Claude output:[/bold green]")
    while True:
        line = process.stdout.readline()
        if not line and process.poll() is not None:
            break

        syntax = Syntax(line, "json", theme="monokai", line_numbers=False)
        console.print(syntax)

    # Check for any errors
    stderr = process.stderr.read()
    if stderr:
        console.print(
            f"[bold red]⚠️ Error output from Claude:[/bold red]\n{stderr}")

    # Get return code
    return_code = process.wait()
    
    # Clean up the temporary file
    if os.path.exists(todo_data_file):
        os.remove(todo_data_file)
        
    if return_code == 0:
        console.print(
            f"[bold green]✅ Claude Code completed successfully[/bold green]")
    else:
        console.print(
            f"[bold red]❌ Claude Code failed with exit code: {return_code}[/bold red]"
        )
        sys.exit(return_code)

except subprocess.CalledProcessError as e:
    console.print(
        f"[bold red]❌ Error executing Claude Code: {str(e)}[/bold red]")
    sys.exit(1)
except Exception as e:
    console.print(f"[bold red]❌ Unexpected error: {str(e)}[/bold red]")
    sys.exit(1)
finally:
    # Make sure we clean up the temporary file
    if os.path.exists(todo_data_file):
        os.remove(todo_data_file)