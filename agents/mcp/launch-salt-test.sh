#!/bin/bash
# Launcher for the salt-test MCP server that works across checkouts/worktrees.

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# Project root is two levels up from agents/mcp/
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

# Ensure we're in the project root
cd "$PROJECT_ROOT"

# Check for the expected virtualenv
VENV_PYTHON="$PROJECT_ROOT/venv310/bin/python"
if [ ! -f "$VENV_PYTHON" ]; then
    # Fallback to system python if venv310 isn't found
    VENV_PYTHON=$(which python3)
fi

# Set PYTHONPATH to the project root so we can import the agents package
export PYTHONPATH="$PROJECT_ROOT"

# Execute the MCP server
exec "$VENV_PYTHON" -m agents.mcp.salt_test.server "$@"
