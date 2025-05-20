#!/bin/bash

# Check if a note name was provided
if [ $# -eq 0 ]; then
    echo "ERROR: Please provide an Obsidian note name as an argument."
    echo "Usage: ./run.sh \"Your Note Name\""
    exit 1
fi

# Load environment variables from .env file if it exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Run the docker-compose command
docker-compose run --rm obsidian-claude-agent "$1"