# Salt Test MCP Server

Model Context Protocol (MCP) server for Salt testing tools.

## Overview

This MCP server exposes Salt testing capabilities to AI agents, enabling:

1. **Quick Local Testing** - Run pytest directly for fast iteration
2. **CI Failure Discovery** - Analyze failing tests from PRs and CI runs
3. **CI Reproduction** - Reproduce failures in CI containers exactly as they occur in GitHub Actions

## Available Tools

### Local Testing (Quick & Dirty)

#### `pytest_run`
Run pytest directly with a test path.

**Parameters:**
- `test_path` (required): Test file, directory, or specific test
- `venv_path` (optional): Path to virtual environment (defaults to ./venv310)
- `extra_args` (optional): Additional pytest arguments

**Example:**
```json
{
  "test_path": "tests/pytests/unit/test_loader.py::test_load_modules",
  "extra_args": ["-v", "-x"]
}
```

#### `pytest_last_failed`
Re-run only tests that failed in the last run.

**Parameters:**
- `venv_path` (optional): Path to virtual environment
- `extra_args` (optional): Additional pytest arguments

#### `pytest_pattern`
Run tests matching a pattern (uses pytest -k).

**Parameters:**
- `pattern` (required): Test name pattern
- `test_path` (optional): Path to search within
- `venv_path` (optional): Virtual environment path
- `extra_args` (optional): Additional arguments

**Example:**
```json
{
  "pattern": "auth",
  "extra_args": ["-v"]
}
```

#### `pytest_list`
List test files matching a glob pattern.

**Parameters:**
- `pattern` (optional): Glob pattern (defaults to "test_*.py")
- `path` (optional): Base path to search

### CI Failure Discovery

#### `ci_pr_failures`
Get all failing tests from a PR's CI runs.

**Parameters:**
- `pr_number` (required): Pull request number
- `repository` (optional): Repository (defaults to "saltstack/salt")
- `json_output` (optional): Return as JSON

**Example:**
```json
{
  "pr_number": 68562
}
```

#### `ci_run_failures`
Get failing tests from a specific CI run.

**Parameters:**
- `run_id` (required): Workflow run ID
- `repository` (optional): Repository
- `json_output` (optional): Return as JSON

#### `ci_failure_summary`
Get a human-readable summary of PR failures.

**Parameters:**
- `pr_number` (required): Pull request number
- `repository` (optional): Repository

### Container Testing (CI Reproduction)

#### `ci_setup_container`
Setup a container for testing (decompress dependencies, create relenv symlink).

**Parameters:**
- `container_name` (required): Name of container to setup
- `arch` (optional): Architecture (x86_64 or arm64, defaults to x86_64)
- `python_version` (optional): Python version (e.g., "3.11") - determines if relenv symlink is needed

**Example:**
```json
{
  "container_name": "salt-test-debian-11",
  "arch": "x86_64",
  "python_version": "3.11"
}
```

#### `ci_run_test`
Run a test in a CI container.

**Parameters:**
- `container_name` (required): Container name
- `test_path` (required): Test path to run
- `extra_args` (optional): Additional arguments (e.g., ["--run-slow", "-x", "-v"])

**Example:**
```json
{
  "container_name": "salt-test-debian-11",
  "test_path": "tests/pytests/functional/test_version.py::test_salt_extensions_in_versions_report",
  "extra_args": ["--run-slow", "-x", "-v"]
}
```

#### `ci_cleanup`
Clean up artifacts and/or containers.

**Parameters:**
- `artifacts` (optional): Clean up downloaded artifacts
- `containers` (optional): Pattern to match container names (e.g., "salt-test-*")

**Example:**
```json
{
  "artifacts": true,
  "containers": "salt-test-*"
}
```

#### `ci_list_platforms`
List available CI container platforms.

**Parameters:** None

## Workflows

### Workflow 1: Discover PR Failures
```
1. ci_pr_failures(pr_number=68562)
   → Returns list of failing tests by platform

2. Analyze results to identify common failures
```

### Workflow 2: Reproduce Specific Failure
```
1. ci_pr_failures(pr_number=68562)
   → Get run_id and failing test

2. Download artifacts (use existing tools container create/ts setup)

3. ci_setup_container(container_name="salt-test-debian-11", python_version="3.11")

4. ci_run_test(
     container_name="salt-test-debian-11",
     test_path="tests/pytests/functional/test_version.py::test_failure",
     extra_args=["--run-slow", "-x", "-v"]
   )
```

### Workflow 3: Quick Local Test
```
1. pytest_run(
     test_path="tests/pytests/unit/test_loader.py",
     extra_args=["-v", "-x"]
   )

2. If failures, analyze and fix

3. pytest_last_failed()
   → Re-run only failed tests
```

## Installation

1. Install MCP Python SDK:
   ```bash
   pip install mcp
   ```

2. Configure Claude Code to use this server (see `../mcp-config.json`)

3. The server will automatically use the Salt repository's tools infrastructure

## Usage with Claude Code

Once configured, you can ask Claude:

- "What tests are failing in PR #68562?"
- "Run the loader tests locally"
- "Reproduce the test_version failure from PR #68562 on debian-11"
- "Re-run the last failed tests"

## Requirements

- Python 3.10 and 3.11 installed
- MCP Python SDK (`pip install mcp`)
- Salt repository with tools/ infrastructure
- **Virtual environments setup** (see below)
- Docker (for container-based testing)
- GitHub token for CI failure discovery (set `GITHUB_TOKEN` or configure `gh` CLI)

### Setting Up Virtual Environments

The Salt repository requires **two** virtual environments:
- **venv310 (Python 3.10)**: For running tests on 3006.x and 3007.x branches
- **venv312 (Python 3.12)**: For running tests on master branch AND pre-commit hooks

**Setup venv310 (Python 3.10) - For Testing:**
```bash
cd /path/to/salt/repo
python3.10 -m venv venv310
source venv310/bin/activate
pip install --upgrade pip setuptools wheel

# Install platform-specific dependencies (choose your OS):
pip install -r requirements/static/pkg/py3.10/linux.txt      # Linux
pip install -r requirements/static/pkg/py3.10/darwin.txt     # macOS
pip install -r requirements/static/pkg/py3.10/windows.txt    # Windows

# Install pytest and tools requirements:
pip install -r requirements/pytest.txt
pip install -r requirements/static/ci/py3.10/tools.txt

# Install pre-commit and python-tools-scripts:
pip install pre-commit python-tools-scripts

# Install Salt in editable mode:
pip install -e .

deactivate
```

**Setup venv312 (Python 3.12) - For Master Branch Testing & Pre-commit:**
```bash
python3.12 -m venv venv312
source venv312/bin/activate
pip install --upgrade pip setuptools wheel

# Install platform-specific dependencies (choose your OS):
pip install -r requirements/static/pkg/py3.12/linux.txt      # Linux
pip install -r requirements/static/pkg/py3.12/darwin.txt     # macOS
pip install -r requirements/static/pkg/py3.12/windows.txt    # Windows

# Install pytest and tools requirements:
pip install -r requirements/pytest.txt
pip install -r requirements/static/ci/py3.12/tools.txt

# Install pre-commit and python-tools-scripts:
pip install pre-commit python-tools-scripts

# Install Salt in editable mode:
pip install -e .

# Install pre-commit hooks:
pre-commit install

deactivate
```

**Environment Usage:**
- **venv310**: For running tests on 3006.x/3007.x branches, pytest, tools commands
- **venv312**: For running tests on master branch, pre-commit hooks, code formatting, linting

**Verify setup:**
```bash
./venv312/bin/python -c "import salt.version; print(salt.version.__version__)"
./venv312/bin/pytest tests/pytests/unit/test_loader.py -v
./venv310/bin/python -m tools --help
```

**CRITICAL:** The MCP server uses the `tools/` infrastructure which requires these virtual environments to be set up. Without them, the pytest and tools commands will fail.

## Development

The MCP server is a thin wrapper around the existing `tools/` CLI infrastructure:
- `tools/testsuite/pytest.py` - Direct pytest execution
- `tools/testsuite/ci_failure.py` - CI failure discovery
- `tools/testsuite/container_test.py` - Container testing

This ensures consistency between CLI and MCP usage.
