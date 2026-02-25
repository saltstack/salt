# Salt Development Environment Setup

This guide covers setting up your local development environment for Salt development.

## Virtual Environment Requirements

Salt development requires setting up **two** virtual environments:

- **venv310 (Python 3.10)**: For running tests on 3006.x and 3007.x branches
- **venv311 (Python 3.11)**: For running tests on master branch AND running pre-commit hooks

## Prerequisites

- Python 3.10 and Python 3.11 installed on your system
- Git repository cloned
- Internet connection for downloading dependencies

## Setup venv310 (Python 3.10)

This environment is used for testing on 3006.x and 3007.x branches.

```bash
# Create virtual environment
python3.10 -m venv venv310

# Activate
source venv310/bin/activate

# Upgrade pip
pip install --upgrade pip setuptools wheel

# Install platform-specific dependencies (choose your OS)
# Linux:
pip install -r requirements/static/pkg/py3.10/linux.txt

# macOS:
pip install -r requirements/static/pkg/py3.10/darwin.txt

# Windows:
pip install -r requirements/static/pkg/py3.10/windows.txt

# Install pytest requirements
pip install -r requirements/pytest.txt

# Install Salt in editable mode
pip install -e .

# Install tools dependencies (for using tools/ commands)
pip install -r requirements/static/ci/py3.10/tools.txt

# Install pre-commit and python-tools-scripts
pip install pre-commit python-tools-scripts

# Deactivate
deactivate
```

## Setup venv311 (Python 3.11)

This environment is used for testing on master branch and running pre-commit hooks.

```bash
# Create virtual environment
python3.11 -m venv venv311

# Activate
source venv311/bin/activate

# Upgrade pip
pip install --upgrade pip setuptools wheel

# Install platform-specific dependencies (choose your OS)
# Linux:
pip install -r requirements/static/pkg/py3.11/linux.txt

# macOS:
pip install -r requirements/static/pkg/py3.11/darwin.txt

# Windows:
pip install -r requirements/static/pkg/py3.11/windows.txt

# Install pytest requirements
pip install -r requirements/pytest.txt

# Install Salt in editable mode
pip install -e .

# Install tools dependencies
pip install -r requirements/static/ci/py3.11/tools.txt

# Install pre-commit and python-tools-scripts
pip install pre-commit python-tools-scripts

# Install pre-commit hooks
pre-commit install

# Deactivate
deactivate
```

## Environment Usage

### venv310 is used for:
- Running tests on 3006.x and 3007.x branches
- Direct pytest execution on older branches
- Tools commands (`python -m tools`)

### venv311 is used for:
- Running tests on master branch
- Running pre-commit hooks
- Code formatting and linting checks
- Pre-commit validation before commits

## Verify Installation

```bash
# Test Salt import
./venv310/bin/python -c "import salt.version; print(salt.version.__version__)"

# Run a simple test
./venv310/bin/pytest tests/pytests/unit/test_loader.py -v

# Test tools
./venv310/bin/python -m tools --help
```

## IMPORTANT: Using Virtual Environments

When running tests or tools, always use the full path to the venv executable or activate the venv first. This ensures you're using the correct Python environment with all dependencies installed.

**Good examples:**
```bash
./venv310/bin/pytest tests/pytests/unit/test_foo.py -v
./venv311/bin/pre-commit run --files salt/loader/lazy.py
./venv310/bin/python -m tools ts pytest run tests/pytests/unit/
```

**Alternatively, activate first:**
```bash
source venv310/bin/activate
pytest tests/pytests/unit/test_foo.py -v
deactivate
```

## Troubleshooting

### ModuleNotFoundError: No module named 'ptscripts'

If you see this error when running `python -m tools`, you need to install the tools dependencies:

```bash
./venv310/bin/pip install -r requirements/static/ci/py3.10/tools.txt
./venv310/bin/pip install python-tools-scripts
```

### venv not found

If you get "No such file or directory" for venv paths, make sure you've created the virtual environment and are running commands from the repository root directory.

### Permission errors

On some systems you may need to use `python3.10` and `python3.11` explicitly instead of just `python3`.

### Pre-commit hooks not running

Make sure you've run `pre-commit install` in the venv311 environment:

```bash
source venv311/bin/activate
pre-commit install
deactivate
```
