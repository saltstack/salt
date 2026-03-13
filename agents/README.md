# AI Agent Instructions for Salt Development

This directory contains instruction files for various AI coding assistants to help them better understand and work with the Salt codebase.

## Purpose

These files provide AI agents with:
- Salt's architecture and design patterns
- Coding conventions and best practices
- Testing guidelines and requirements
- Common pitfalls to avoid

## Available Instructions

- **CLAUDE.md** - Instructions for Anthropic's Claude (Claude Code, Claude.ai, etc.)
- **GEMINI.md** - Instructions for Google's Gemini
- **CURSOR.md** - Instructions for Cursor IDE
- **COPILOT.md** - Instructions for GitHub Copilot

Each instruction file provides a quick reference and links to detailed documentation (see below).

## Detailed Documentation

The `docs/` directory contains comprehensive guides that are referenced by all agent instruction files. This provides a single source of truth for detailed information:

- **[development-setup.md](docs/development-setup.md)** - Complete virtual environment setup
  - venv310 and venv311 setup instructions
  - Platform-specific dependencies
  - Installation verification steps
  - Common troubleshooting

- **[architecture.md](docs/architecture.md)** - Salt architecture deep dive
  - Master-minion architecture
  - All module types (execution, state, grains, pillar, beacon, engine, etc.)
  - Directory structure
  - Key components (state compiler, transport layer, event bus, loader system)

- **[module-templates.md](docs/module-templates.md)** - Complete code templates
  - Full execution module template with all patterns
  - Full state module template with flow diagram
  - All `__virtual__()` patterns (5 variations)
  - Error handling examples
  - Common decorators and utilities

- **[testing.md](docs/testing.md)** - Comprehensive testing guide
  - Test directory structure
  - Unit test templates (legacy and pytest styles)
  - Mocking patterns with examples
  - Running tests (Nox, venv, container)
  - Container testing for CI reproduction
  - Linting and formatting

- **[git-and-ci.md](docs/git-and-ci.md)** - Git workflow and CI
  - Commit guidelines (**NO AI attribution!**)
  - PR workflow with gh CLI commands
  - Branch strategy
  - CI failure reproduction workflow
  - Container setup and debugging

- **[troubleshooting.md](docs/troubleshooting.md)** - Common issues and solutions
  - Import order issues
  - Module discovery problems
  - ZeroMQ issues
  - Python 3.11+ compatibility gotchas
  - Container filesystem behavior
  - Lazy loading behavior
  - Common error messages and fixes

## How to Use

**Recommended approach:** Create a symlink from the root directory to the agent file you want to use.

### Symlink (Recommended)

Creating a symlink keeps your local setup in sync with updates to the canonical instructions:

```bash
# From the root of the Salt repository
ln -s agents/CLAUDE.md CLAUDE.md
# or
ln -s agents/CURSOR.md .cursorrules
# or
ln -s agents/GEMINI.md GEMINI.md
# or
ln -s agents/COPILOT.md COPILOT.md
```

**Why symlink?**
- Automatically receives updates when canonical files are updated
- Links to `agents/docs/` work correctly
- No maintenance required

### Alternative: IDE-Specific Configuration

Some tools may allow you to specify a custom path to instruction files in their settings. Consult your tool's documentation.

**Note:** If you need to customize the instructions, it's better to propose changes to the canonical files in `agents/` so everyone benefits, rather than maintaining a personal copy.

## MCP Servers

This directory also contains Model Context Protocol (MCP) servers that expose Salt development tools to AI agents:

- **mcp/salt_test/** - Testing tools server
  - Direct pytest execution (quick local testing)
  - CI failure discovery (analyze PR failures)
  - Container testing (reproduce CI failures)

See [mcp/README.md](mcp/README.md) for setup and usage instructions.

### Quick Setup

1. Install MCP SDK: `pip install mcp`
2. Configure in `~/.config/claude-code/mcp_config.json` (see `mcp/mcp-config.json` for template)
3. Set GitHub token for CI features: `export GITHUB_TOKEN="your_token"`

With MCP configured, you can ask Claude:
- "What tests are failing in PR #68562?"
- "Run the loader tests locally"
- "Reproduce the failure from PR #68562 on debian-11"

## .gitignore

The root-level instruction files (CLAUDE.md, GEMINI.md, etc.) are intentionally ignored by git to prevent personal configurations from being committed. Only the canonical versions in this directory are tracked.

## Contributing

If you discover better patterns, common issues, or ways to improve these instructions:

1. Edit the appropriate file in this `agents/` directory
2. Submit a pull request with your improvements
3. Include a brief explanation of what the change helps agents understand better

## File Naming Conventions

- **CLAUDE.md** - For Claude-based tools
- **GEMINI.md** - For Gemini-based tools
- **CURSOR.md** - For Cursor IDE (may also be named `.cursorrules`)
- **COPILOT.md** - For GitHub Copilot (may also be named `.github/copilot-instructions.md`)

Note: Some tools may use different filenames. Check your tool's documentation for the correct filename and location.
