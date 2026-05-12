# GitHub Copilot Instructions for Salt Development

## Project Context

This is the Salt project - a Python-based configuration management and remote execution system using master-minion architecture with a dynamic loader system for plugins.

## Coding Philosophy

**CRITICAL**: Write code as a CPython core developer:
- Deep understanding of Python internals, memory management, GC
- Know performance implications of different implementations

**Zen of Python**: Readability counts. Explicit > implicit. Simple > complex. Errors never pass silently.

**TDD for Bug Fixes**: Write failing test → verify fail → fix bug → verify pass → run related tests

---

## Git Workflow

**CRITICAL: NO attribution lines**
- **NEVER** add "Generated with Claude Code", "Co-Authored-By: Claude", or any AI attribution
- Use imperative mood: "Fix bug" not "Fixed bug"
- Reference issues: `#NNNN`
- Small, focused commits
- Rebase before push

---

## Architecture

**Salt components:**
- **Master-Minion**: Central master controls distributed minions
- **Event Bus**: Real-time communication
- **Execution Modules** (`salt/modules/`): CLI commands (264+)
- **State Modules** (`salt/states/`): Declarative configuration (126+)
- **Utils** (`salt/utils/`): Shared utilities (170+)

**See [agents/docs/architecture.md](agents/docs/architecture.md) for complete details.**

---

## Code Patterns

### Execution Module
```python
import logging
import salt.exceptions
import salt.utils.platform

log = logging.getLogger(__name__)

def __virtual__():
    """Return True to load, False or (False, reason) to skip"""
    if not salt.utils.path.which("required_binary"):
        return False, "required_binary not found"
    return True

def function_name(param1, param2=None):
    """
    CLI Example::
        salt '*' module.function_name value
    """
    if not param1:
        raise salt.exceptions.SaltInvocationError("param1 required")
    return __salt__["cmd.run"](f"command {param1}")
```

### State Module Return
```python
def managed(name, value=None):
    ret = {"name": name, "result": False, "changes": {}, "comment": ""}

    # Validate → Check current → If correct return → If test mode return None → Apply → Return
    if not name:
        ret["comment"] = "Name required"
        return ret

    current = __salt__["module.get"](name)
    if current == value:
        ret["result"] = True
        ret["comment"] = "Already correct"
        return ret

    if __opts__["test"]:
        ret["result"] = None
        ret["changes"] = {"old": current, "new": value}
        ret["comment"] = "Would change"
        return ret

    try:
        __salt__["module.set"](name, value)
        ret["result"] = True
        ret["changes"] = {"old": current, "new": value}
        ret["comment"] = "Updated"
    except Exception as exc:
        ret["comment"] = str(exc)

    return ret
```

**See [agents/docs/module-templates.md](agents/docs/module-templates.md) for complete templates.**

---

## Dunder Variables

Salt injects these into module scope:

- `__opts__`: Config - `__opts__["test"]`, `__opts__.get("id")`
- `__grains__`: System data - `__grains__.get("os_family")`
- `__pillar__`: Secure data - `__pillar__.get("password")`
- `__context__`: Per-run cache for expensive operations
- `__salt__`: Execution modules - `__salt__["pkg.install"]("nginx")`
- `__utils__`: Utilities - `__utils__["files.is_text"](path)`
- `__states__`: State modules (states only)

**Context caching pattern:**
```python
if "pkg_list" not in __context__:
    __context__["pkg_list"] = expensive_fetch()
return __context__["pkg_list"]
```

---

## Required Elements

### Logging
```python
log = logging.getLogger(__name__)
log.debug("Processing: %s", filename)  # Good - lazy formatting
log.debug(f"Processing: {filename}")   # Bad - f-strings evaluated early
```
**Never log secrets.**

### Docstrings
Every function requires description, parameters, and CLI example:
```python
def my_function(name, value=None):
    """
    Description of functionality

    name
        Description of name parameter

    CLI Example::
        salt '*' module.my_function foo value=bar
    """
```

### Error Handling
```python
from salt.exceptions import (
    CommandExecutionError,    # Operation failures
    SaltInvocationError,      # Invalid arguments
    CommandNotFoundError,     # Missing binaries
)

if not required_param:
    raise SaltInvocationError("required_param must be provided")
```

### __virtual__ Function
Declare platform/dependency requirements:
```python
# Platform check
def __virtual__():
    if salt.utils.platform.is_windows():
        return False, "Not available on Windows"
    return True

# Virtual name (for interface modules)
__virtualname__ = "pkg"
def __virtual__():
    if __grains__.get("os_family") == "Debian":
        return __virtualname__
    return False
```

**See [agents/docs/module-templates.md](agents/docs/module-templates.md) for all patterns.**

---

## Development Environment

**Two environments required:**
- **venv310**: Testing 3006.x/3007.x branches
- **venv312**: Testing master branch + pre-commit

```bash
# venv310
python3.10 -m venv venv310 && source venv310/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements/static/pkg/py3.10/linux.txt  # or darwin.txt/windows.txt
pip install -r requirements/pytest.txt -r requirements/static/ci/py3.10/tools.txt
pip install pre-commit python-tools-scripts && pip install -e . && deactivate

# venv312
python3.12 -m venv venv312 && source venv312/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements/static/pkg/py3.11/linux.txt  # or darwin.txt/windows.txt
pip install -r requirements/pytest.txt -r requirements/static/ci/py3.11/tools.txt
pip install pre-commit python-tools-scripts && pip install -e . && pre-commit install && deactivate
```

**Always use full paths:** `./venv312/bin/pytest` (master); `./venv310/bin/pytest` (3006.x/3007.x)

**See [agents/docs/development-setup.md](agents/docs/development-setup.md) for complete setup.**

---

## Testing

### Pytest Fixture
```python
import pytest
import salt.modules.mymodule as mymodule

@pytest.fixture
def configure_loader_modules():
    return {
        mymodule: {
            "__opts__": {"test": False},
            "__grains__": {"os": "Linux"},
            "__salt__": {},
        }
    }

def test_function():
    result = mymodule.my_function("test")
    assert result == "expected"
```

### Running Tests
```bash
# Nox
nox -e test-3 -- tests/pytests/unit/test_loader.py
nox -e test-3 -- --lf  # Last failed

# Direct (faster)
./venv312/bin/pytest tests/pytests/unit/test_foo.py -v
```

**See [agents/docs/testing.md](agents/docs/testing.md) for complete guide.**

---

## Common Patterns

### Platform Detection
```python
salt.utils.platform.is_windows()
salt.utils.platform.is_linux()
__grains__.get("os_family")  # "Debian", "RedHat", etc.
```

### Run Commands
```python
output = __salt__["cmd.run"]("ls -la")
result = __salt__["cmd.run_all"]("cmd")  # {"retcode": 0, "stdout": "...", "stderr": "..."}
```

### File Operations
```python
content = __salt__["file.read"](path)
__salt__["file.write"](path, content)
__salt__["file.file_exists"](path)
```

---

## Checklists

### Execution Module
- [ ] `log = logging.getLogger(__name__)`
- [ ] Docstrings with CLI examples
- [ ] `__virtual__()` if platform-specific
- [ ] Input validation (`SaltInvocationError`)
- [ ] Error handling (`CommandExecutionError`)
- [ ] Context caching for expensive ops
- [ ] Unit tests

### State Module
- [ ] Returns: name, result (True/False/None), changes, comment
- [ ] result=None for test mode
- [ ] Check current state before modifying
- [ ] Populate changes dict with old/new

---

## Documentation

**Essential guides in `agents/docs/`:**

- **[agents/docs/development-setup.md](agents/docs/development-setup.md)** - venv310/venv312 setup, dependencies
- **[agents/docs/architecture.md](agents/docs/architecture.md)** - Complete architecture, module types, loader
- **[agents/docs/module-templates.md](agents/docs/module-templates.md)** - Complete templates, all patterns
- **[agents/docs/testing.md](agents/docs/testing.md)** - Test templates, mocking, running tests
- **[agents/docs/git-and-ci.md](agents/docs/git-and-ci.md)** - Commit guidelines, PR workflow, CI reproduction
- **[agents/docs/troubleshooting.md](agents/docs/troubleshooting.md)** - Common issues and solutions

**Key example files:** `salt/modules/test.py`, `salt/modules/file.py`, `salt/states/pkg.py`

---

## Key Principles

- **Idempotency**: Safe to run multiple times
- **Testing**: Every function needs tests
- **Documentation**: Docstrings with CLI examples
- **Error Handling**: Use Salt exception classes
- **Performance**: Cache in `__context__`
- **Security**: Validate inputs, never log secrets
