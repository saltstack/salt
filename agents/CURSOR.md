# Salt Development Rules for Cursor

You are working on Salt, a Python-based configuration management and remote execution system. Follow these rules when writing or modifying Salt code.

## Critical Rules

**CODING PHILOSOPHY:**
- Write as a CPython core developer - know internals, memory management, GC, performance
- Zen of Python: Readability counts. Explicit > implicit. Simple > complex
- TDD for bugs: Write failing test → verify fail → fix → verify pass → run related tests

**GIT WORKFLOW:**
- **NEVER** add "Generated with Claude Code" or "Co-Authored-By: Claude" to commits
- Use imperative mood: "Fix bug" not "Fixed bug"
- Reference issues: `#NNNN`
- Small, focused commits
- Rebase before push

**LINTING:**
- Black: 88 char lines (`black .`)
- isort: Profile 3, trailing commas (`isort .`)
- Lint: `nox -e lint-salt`

---

## Architecture Quick Reference

**Salt Components:**
- Master-Minion architecture for distributed configuration management
- Event-driven communication via event bus
- Execution modules: CLI commands (`salt/modules/`) - 264+
- State modules: Declarative config (`salt/states/`) - 126+
- Utils: Shared functions (`salt/utils/`) - 170+

**See [agents/docs/architecture.md](agents/docs/architecture.md) for complete architecture.**

---

## Module Structure

### Execution Module Skeleton
```python
import logging
import salt.exceptions
import salt.utils.platform

log = logging.getLogger(__name__)

def __virtual__():
    """Returns True/False/(False, reason)"""
    if not salt.utils.path.which("required_cmd"):
        return False, "required_cmd not found"
    return True

def my_function(name, param=None):
    """
    CLI Example::
        salt '*' mymodule.my_function foo param=bar
    """
    if not name:
        raise salt.exceptions.SaltInvocationError("name required")
    return __salt__["cmd.run"](f"command {name}")
```

### State Module Return Structure
```python
ret = {
    "name": name,        # Resource name
    "result": False,     # True/False/None (test mode)
    "changes": {},       # {"old": ..., "new": ...}
    "comment": ""        # What happened
}
```

**State flow:** Validate → Check current → If correct return → If test mode return None → Make changes → Return result

**Complete templates: [agents/docs/module-templates.md](agents/docs/module-templates.md)**

---

## Dunder Dictionaries

- `__opts__`: Config (`__opts__["test"]`, `__opts__.get("id")`)
- `__grains__`: System info (`__grains__.get("os_family")`)
- `__pillar__`: Secure data (`__pillar__.get("password")`)
- `__context__`: Per-run cache - use for expensive operations
- `__salt__`: Execution modules (`__salt__["pkg.install"]("nginx")`)
- `__utils__`: Utilities (`__utils__["files.is_text"](path)`)
- `__states__`: State modules (states only)

**Context cache pattern:**
```python
if "cache_key" not in __context__:
    __context__["cache_key"] = expensive_operation()
return __context__["cache_key"]
```

---

## Common Patterns

### Error Handling
```python
from salt.exceptions import (
    CommandExecutionError,    # Operation failed
    SaltInvocationError,      # Bad arguments
    CommandNotFoundError,     # Binary not found
)
```

### Logging
```python
log = logging.getLogger(__name__)
log.debug("Processing %s", filename)  # Good - lazy formatting
log.debug(f"Processing {filename}")   # Bad - f-strings evaluated early
```
**Never log secrets.**

### Platform Detection
```python
salt.utils.platform.is_windows()
salt.utils.platform.is_linux()
__grains__.get("os_family")  # "Debian", "RedHat", etc.
```

### Decorators
```python
from salt.utils.decorators.path import which
from salt.utils.decorators import depends, memoize

@which("systemctl")  # Require binary
@depends("docker")   # Require Python module
@memoize            # Cache forever
```

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

**Always use full paths:** `./venv312/bin/python`, `./venv312/bin/pytest` (master); `./venv310/...` for 3006.x/3007.x

**Complete setup: [agents/docs/development-setup.md](agents/docs/development-setup.md)**

---

## Testing

### Pytest Structure
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

**Complete guide: [agents/docs/testing.md](agents/docs/testing.md)**

---

## Code Checklist

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

## Quick Reference

### Common Imports
```python
import logging
import salt.exceptions
import salt.utils.args
import salt.utils.platform
import salt.utils.path

log = logging.getLogger(__name__)
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
exists = __salt__["file.file_exists"](path)
```

---

## Documentation Links

- **[agents/docs/development-setup.md](agents/docs/development-setup.md)** - venv setup, verification
- **[agents/docs/architecture.md](agents/docs/architecture.md)** - Complete architecture, all module types
- **[agents/docs/module-templates.md](agents/docs/module-templates.md)** - Complete templates, patterns
- **[agents/docs/testing.md](agents/docs/testing.md)** - Test templates, mocking, container testing
- **[agents/docs/git-and-ci.md](agents/docs/git-and-ci.md)** - Commit rules, PR workflow, CI reproduction
- **[agents/docs/troubleshooting.md](agents/docs/troubleshooting.md)** - Common issues and solutions

**Key example files:** `salt/modules/test.py`, `salt/modules/file.py`, `salt/states/pkg.py`

---

## Key Principles

- **Idempotency**: Safe to run multiple times
- **Testing**: Every function needs tests
- **Documentation**: Docstrings with CLI examples
- **Error Handling**: Use Salt exceptions
- **Performance**: Cache in `__context__`
- **Security**: Validate inputs, never log secrets
