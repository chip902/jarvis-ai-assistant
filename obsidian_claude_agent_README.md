# Obsidian Claude Agent

This project provides a refactored version of the original Notion-based Claude Code integration, adapted to work with a local Obsidian vault instead.

## Overview

The Obsidian Claude Agent allows you to:

1. Create todo lists in Obsidian notes
2. Process these todos with Claude Code to implement code changes
3. Mark todos as complete in the Obsidian note when finished

This is particularly useful for tracking coding tasks in Obsidian and having Claude Code automatically implement them.

## Prerequisites

- Python 3.9+
- A local Obsidian vault
- Claude Code CLI installed (`pip install claude-cli`)
- Uv package manager (`pip install uv`)

## Setup

1. Clone this repository
2. Create a `.env` file with the following content:
   ```
   OBSIDIAN_VAULT_PATH=/path/to/your/obsidian/vault
   ```
3. Install dependencies:
   ```bash
   uv pip install -r requirements.txt
   ```

## Usage

### Creating Todo Items in Obsidian

Create a note in your Obsidian vault with todo items. Each todo item should describe a specific code change or implementation task. For example:

```markdown
# Project Tasks

- [ ] Implement a logging function in utils.py
- [ ] Add error handling to the API client
- [ ] Create unit tests for the calculator module
```

### Running the Agent

Run the agent with the name of your Obsidian note:

```bash
uv run claude_code_is_programmable_obsidian.py "Project Tasks"
```

The agent will:
1. Find the note in your Obsidian vault
2. Extract all uncompleted todo items
3. Process each todo item one by one
4. Implement the required code changes
5. Commit the changes to git
6. Mark the todo as complete in your Obsidian note

## Files Overview

- `obsidian_adapter.py` - A Python module that interfaces with your local Obsidian vault
- `claude_code_is_programmable_obsidian.py` - The main script that launches Claude Code to process todos
- `update_obsidian_todo.py` - A utility script to mark todos as complete in Obsidian

## How It Works

1. The adapter locates your Obsidian note and parses its content
2. It identifies todo items using Markdown's `- [ ]` syntax
3. Todo items are saved to a temporary JSON file
4. Claude Code is launched with instructions to process the todos
5. Claude implements the required code changes
6. The update script is called to mark the todo as complete in Obsidian

## Customization

You can modify the adapter and scripts to suit your specific needs:

- Change the todo format by modifying the regex in `obsidian_adapter.py`
- Add additional functionality to the prompt in `claude_code_is_programmable_obsidian.py`
- Modify the commit message format or git workflow in the Claude Code prompt

## Troubleshooting

**Problem**: Cannot find Obsidian vault
**Solution**: Check that the `OBSIDIAN_VAULT_PATH` in your `.env` file points to a valid Obsidian vault

**Problem**: Todo items not being identified
**Solution**: Ensure your todos follow the format `- [ ] Task description`

**Problem**: Claude Code not running
**Solution**: Make sure Claude Code CLI is installed and working properly

## Contributing

Contributions are welcome! Feel free to submit issues or pull requests to improve this tool.

## License

This project is open source and available under the MIT License.