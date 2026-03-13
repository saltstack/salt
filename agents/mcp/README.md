# Salt AI Agent MCP Servers

This directory contains Model Context Protocol (MCP) servers that expose Salt development tools to AI agents.

## What is MCP?

Model Context Protocol (MCP) is a standard for connecting AI assistants to external tools and data sources. MCP servers expose functionality that AI agents can discover and use.

## Available Servers

### salt-test

Testing tools for Salt development:
- Direct pytest execution (quick local testing)
- CI failure discovery (analyze PR failures)
- Container testing (reproduce CI failures exactly)

See [salt_test/README.md](salt_test/README.md) for details.

## Setup

### 1. Set Up Virtual Environments

**REQUIRED:** The Salt repository needs two virtual environments:
- **venv310**: For running tests on 3006.x/3007.x branches
- **venv311**: For running tests on master branch AND pre-commit hooks

```bash
cd /path/to/salt/repo

# Setup venv310
python3.10 -m venv venv310
source venv310/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements/static/pkg/py3.10/linux.txt  # or darwin.txt / windows.txt
pip install -r requirements/pytest.txt
pip install -r requirements/static/ci/py3.10/tools.txt
pip install pre-commit python-tools-scripts
pip install -e .
deactivate

# Setup venv311 (for master branch testing + pre-commit)
python3.11 -m venv venv311
source venv311/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements/static/pkg/py3.11/linux.txt  # or darwin.txt / windows.txt
pip install -r requirements/pytest.txt
pip install -r requirements/static/ci/py3.11/tools.txt
pip install pre-commit python-tools-scripts
pip install -e .
pre-commit install
deactivate

# Verify
./venv310/bin/python -m tools --help
```

See [salt_test/README.md](salt_test/README.md) for detailed setup instructions.

### 2. Install MCP SDK

```bash
pip install mcp
```

### 3. Configure Claude Code

Add the servers to your Claude Code MCP configuration. The location depends on your setup:

**For this repository (relative paths):**
Create or edit `~/.config/claude-code/mcp_config.json`:

```json
{
  "mcpServers": {
    "salt-test": {
      "command": "python3",
      "args": ["-m", "agents.mcp.salt_test.server"],
      "cwd": "/absolute/path/to/salt/repo",
      "env": {
        "PYTHONPATH": "/absolute/path/to/salt/repo"
      }
    }
  }
}
```

**Alternative (using absolute path to server):**
```json
{
  "mcpServers": {
    "salt-test": {
      "command": "python3",
      "args": ["/absolute/path/to/salt/repo/agents/mcp/salt_test/server.py"],
      "cwd": "/absolute/path/to/salt/repo",
      "env": {}
    }
  }
}
```

### 4. Set GitHub Token (for CI failure discovery)

For accessing GitHub API to discover CI failures:

```bash
# Option 1: Set environment variable
export GITHUB_TOKEN="your_github_token"

# Option 2: Configure gh CLI
gh auth login
```

### 5. Restart Claude Code

After configuration, restart Claude Code to load the MCP servers.

## Verifying Setup

Once configured, you can verify the servers are loaded by asking Claude:

```
"What MCP tools are available?"
```

You should see the `salt-test` tools listed.

## Usage Examples

### Quick Local Testing

```
"Run tests/pytests/unit/test_loader.py with verbose output"
```

Claude will use `pytest_run` to execute the test locally.

### Discover PR Failures

```
"What tests are failing in PR #68562?"
```

Claude will use `ci_pr_failures` to analyze the PR's CI runs.

### Reproduce CI Failure

```
"Reproduce the test_version.py failure from PR #68562 on debian-11"
```

Claude will:
1. Discover the failing test
2. Guide you through downloading artifacts
3. Setup the container
4. Run the test

## Development

### Adding New Tools

1. Add functionality to `tools/testsuite/` (following existing patterns)
2. Register the module in `tools/__init__.py`
3. Add corresponding MCP tool to `salt_test/server.py`:
   - Add tool definition in `list_tools()`
   - Add command mapping in `call_tool()`
4. Document in `salt_test/README.md`

### Testing MCP Servers Locally

```bash
# Test the server directly
cd /path/to/salt/repo
python3 -m agents.mcp.salt_test.server

# Test with MCP inspector (if available)
mcp-inspector agents.mcp.salt_test.server
```

## Troubleshooting

### Server Not Loading

1. Check Python path is correct in configuration
2. Verify `mcp` package is installed: `pip install mcp`
3. Check Claude Code logs for errors

### Tools Not Working

1. Verify you're in the Salt repository directory
2. Check that `tools/` infrastructure is working: `python3 -m tools --help`
3. For container tools, verify Docker is running: `docker info`
4. For CI failure tools, verify GitHub token: `echo $GITHUB_TOKEN`

### Container Issues

1. Ensure Docker is installed and running
2. Check container exists: `docker ps -a | grep salt-test`
3. Verify artifacts downloaded: `ls artifacts/`

## Architecture

```
agents/mcp/
├── salt_test/
│   ├── server.py          # MCP server implementation
│   ├── README.md          # Tool documentation
│   └── __init__.py
└── README.md              # This file

tools/testsuite/           # Underlying CLI tools
├── pytest.py              # Direct pytest execution
├── ci_failure.py          # CI failure discovery
└── container_test.py      # Container testing
```

The MCP servers are thin wrappers around the existing `tools/` CLI infrastructure, ensuring consistency between CLI and AI agent usage.

## Contributing

When adding new testing capabilities:

1. Implement in `tools/testsuite/` first (can be used standalone)
2. Expose via MCP for AI agent access
3. Document both CLI and MCP usage
4. Update agent instruction files (CLAUDE.md, etc.) if needed

## Resources

- MCP Specification: https://modelcontextprotocol.io/
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
- Claude Code MCP Guide: https://docs.anthropic.com/claude-code/mcp
