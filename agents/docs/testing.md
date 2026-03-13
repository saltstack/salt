# Salt Testing Guide

Salt uses multiple test frameworks. All new code should include tests.

## Test Directory Structure

```
tests/
├── unit/               # Fast unit tests (no daemons, heavy mocking)
│   ├── modules/        # Tests for salt/modules/
│   ├── states/         # Tests for salt/states/
│   └── utils/          # Tests for salt/utils/
├── integration/        # Integration tests (with daemons)
│   ├── modules/        # Tests for salt/modules/
│   ├── states/         # Tests for salt/states/
│   └── ...
└── pytests/           # Pytest-based tests (newer style)
    ├── unit/
    ├── integration/
    └── functional/
```

## Unit Test Templates

### Legacy Style (TestCase)

```python
"""
Tests for salt.modules.mymodule
"""

import pytest

import salt.modules.mymodule as mymodule
from salt.exceptions import CommandExecutionError, SaltInvocationError
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class MyModuleTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.mymodule
    """

    def setup_loader_modules(self):
        """
        Setup loader modules - injects dunders
        """
        return {
            mymodule: {
                "__opts__": {"test": False},
                "__grains__": {"os": "Linux"},
                "__salt__": {},
            }
        }

    def test_simple_function(self):
        """
        Test simple function
        """
        result = mymodule.my_function("test")
        self.assertEqual(result, "expected")

    def test_with_mock(self):
        """
        Test with mocked subprocess call
        """
        mock_cmd = MagicMock(return_value={"retcode": 0, "stdout": "success"})
        with patch.dict(mymodule.__salt__, {"cmd.run_all": mock_cmd}):
            result = mymodule.my_function("test")
            self.assertTrue(result)
            mock_cmd.assert_called_once()

    def test_error_handling(self):
        """
        Test error conditions
        """
        with self.assertRaises(SaltInvocationError):
            mymodule.my_function(None)
```

### Pytest Style (Newer)

```python
"""
Tests for salt.modules.mymodule
"""

import pytest

import salt.modules.mymodule as mymodule
from salt.exceptions import SaltInvocationError


@pytest.fixture
def configure_loader_modules():
    """
    Setup module dunders
    """
    return {
        mymodule: {
            "__opts__": {"test": False},
            "__grains__": {"os": "Linux"},
            "__salt__": {},
        }
    }


def test_simple_function():
    """
    Test simple function
    """
    result = mymodule.my_function("test")
    assert result == "expected"


def test_error_handling():
    """
    Test error conditions
    """
    with pytest.raises(SaltInvocationError):
        mymodule.my_function(None)
```

## Mocking Patterns

### Basic Mocking

```python
from tests.support.mock import MagicMock, patch, call

# Mock a function call
mock_func = MagicMock(return_value="result")
with patch("salt.modules.mymodule.some_function", mock_func):
    result = mymodule.my_function()
    mock_func.assert_called_once_with("expected_arg")

# Mock dunder dict
with patch.dict(mymodule.__salt__, {"cmd.run": MagicMock(return_value="output")}):
    result = mymodule.my_function()

# Mock with side effects
mock_func = MagicMock(side_effect=[
    {"retcode": 1, "stdout": "error"},  # First call fails
    {"retcode": 0, "stdout": "success"},  # Second call succeeds
])
with patch.dict(mymodule.__salt__, {"cmd.run_all": mock_func}):
    result = mymodule.my_function()
```

## Test Best Practices

1. **One test per function behavior**: Test success cases, error cases, edge cases separately
2. **Use descriptive test names**: `test_function_name_when_condition_then_expected_result`
3. **Mock external dependencies**: File I/O, network calls, subprocess calls
4. **Test error handling**: Verify exceptions are raised correctly
5. **Test input validation**: Verify bad inputs are rejected
6. **Keep tests fast**: Unit tests should run in milliseconds
7. **Don't test implementation details**: Test the public API, not internal helpers

## Running Tests

### Using Nox (Recommended for CI Consistency)

```bash
# Run all tests
nox -e test-3

# Run specific test file
nox -e test-3 -- tests/pytests/unit/test_loader.py

# Run with pattern matching
nox -e test-3 -- -k test_auth

# Run specific test function
nox -e test-3 -- tests/pytests/unit/test_loader.py::test_load_modules

# Run last failed tests
nox -e test-3 -- --lf

# Run with specific Python version
nox -e test-3.10
nox -e test-3.11

# Run with specific transport
nox -e test-tcp-3
nox -e test-zeromq-3

# Run with coverage
nox -e test-3 --coverage
nox -e coverage-report
```

### Using Virtual Environment (Faster for Development)

If you have a local venv setup:

```bash
# Run tests directly with pytest
./venv310/bin/pytest tests/pytests/unit/test_foo.py::test_bar -v

# Run pre-commit checks on specific files
./venv310/bin/pre-commit run --files salt/loader/lazy.py
```

## Container Testing (Reproduce CI Failures)

To reproduce CI failures locally using the same container environment:

### 1. Download CI artifacts

```bash
./venv310/bin/python -m ptscripts ci download-artifacts --run-id <RUN-ID>
```

### 2. Create container

```bash
./venv310/bin/python -m ptscripts container create <IMAGE> --name <NAME>
docker start <NAME>
```

### 3. Setup container

```bash
# Decompress dependencies
docker exec <NAME> python3 -m nox -e decompress-dependencies -- linux x86_64

# Create relenv toolchain symlink (Python 3.11+ only)
docker exec <NAME> bash -c "mkdir -p /root/.local/relenv && ln -sf /root/.cache/relenv/toolchains /root/.local/relenv/toolchain"
```

### 4. Run tests

```bash
docker exec <NAME> python3 -m nox -e ci-test-onedir -- <TEST-PATH> --run-slow -x -v
```

### Example container images

- `ghcr.io/saltstack/salt-ci-containers/testing:debian-11`
- `ghcr.io/saltstack/salt-ci-containers/testing:ubuntu-22.04`
- `ghcr.io/saltstack/salt-ci-containers/testing:rockylinux-9`

## Linting and Formatting

### Black (Code Formatting)

```bash
# Format all code
black .

# Check without modifying
black --check .
```

Black uses 88 character line length by default.

### isort (Import Sorting)

```bash
# Sort all imports
isort .

# Check without modifying
isort --check .
```

isort is configured with profile 3 and trailing commas in `pyproject.toml`.

### Linting

```bash
# Lint both salt and tests
nox -e lint

# Lint Salt code only
nox -e lint-salt

# Lint tests only
nox -e lint-tests
```

## Example Test Files

For reference, see:
- Unit test example: `tests/unit/modules/test_systemd_service.py`
- Complex mocking: `tests/unit/modules/test_cron.py`
- Documentation: `doc/topics/tutorials/writing_tests.rst`
