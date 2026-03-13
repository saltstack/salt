# Salt Development Instructions for Claude

You are assisting with development of Salt, a powerful infrastructure automation and configuration management system. This document provides essential quick reference information and links to detailed documentation.

## Table of Contents

1. [Coding Philosophy](#coding-philosophy)
2. [Architecture Quick Reference](#architecture-quick-reference)
3. [Dunder Dictionaries](#dunder-dictionaries)
4. [Module Basics](#module-basics)
5. [State Basics](#state-basics)
6. [Git Workflow](#git-workflow)
7. [Checklists](#checklists)
8. [Detailed Documentation](#detailed-documentation)

---

## Coding Philosophy

**CRITICAL**: Approach Salt development as a CPython core developer:
- Know memory management and garbage collection implications
- Understand performance trade-offs between implementations
- Be aware of CPython implementation details and GIL impact

**TDD for Bug Fixes**: Always write a failing test first, verify it fails, fix the bug, verify it passes, then run related tests.

**Zen of Python**: Readability counts. Explicit is better than implicit. Simple is better than complex. Errors should never pass silently.

---

## Architecture Quick Reference

Salt is a Python-based configuration management system using master-minion architecture with an event-driven plugin system.

**Key Module Types:**
- **Execution Modules** (`salt/modules/`) - CLI commands on minions (264+)
- **State Modules** (`salt/states/`) - Declarative configuration (126+)
- **Utils** (`salt/utils/`) - Shared utility functions (170+)

**See [agents/docs/architecture.md](agents/docs/architecture.md) for complete architecture details.**

---

## Dunder Dictionaries

Salt injects special dictionaries into module scope via the loader:

**Always Available:**
- `__opts__` - Configuration options (test mode, minion ID, etc.)
- `__grains__` - System information (OS, platform, custom data)
- `__pillar__` - Secure data for this minion
- `__context__` - Per-run cache (persists during Salt execution)

**Module-Specific:**
- `__salt__` - Access other execution modules
- `__utils__` - Utility functions
- `__states__` - Call other states (in state modules only)

**Example: Context Caching**
```python
if "cache_key" not in __context__:
    __context__["cache_key"] = expensive_operation()  # Only once per run
return __context__["cache_key"]
```

**See [agents/docs/architecture.md](agents/docs/architecture.md) for detailed loader system documentation.**

---

## Module Basics

**Execution Module Structure:**
```python
import logging
import salt.exceptions
import salt.utils.platform

log = logging.getLogger(__name__)

def __virtual__():
    """Return True to load, False or (False, reason) to skip"""
    if salt.utils.platform.is_windows():
        return False, "Not available on Windows"
    return True

def my_function(name, param=None):
    """
    CLI Example::
        salt '*' mymodule.my_function foo param=bar
    """
    if not name:
        raise salt.exceptions.SaltInvocationError("name is required")
    return __salt__["cmd.run"](f"command {name}")
```

**See [agents/docs/module-templates.md](agents/docs/module-templates.md) for complete templates and patterns.**

---

## State Basics

**State Return Structure (REQUIRED):**
```python
ret = {
    "name": name,        # Name parameter
    "result": False,     # True (success), False (fail), None (test mode)
    "changes": {},       # Dict of changes: {"old": ..., "new": ...}
    "comment": ""        # What happened
}
```

**State Flow:**
1. Validate input
2. Check current state
3. If already correct: return success
4. If test mode (`__opts__["test"]`): return `result=None` with proposed changes
5. Make changes and return result

**See [agents/docs/module-templates.md](agents/docs/module-templates.md) for complete state templates.**

---

## Git Workflow

### CRITICAL RULES

1. **NO attribution lines** - **NEVER** add "Generated with Claude Code", "Co-Authored-By: Claude", or any AI attribution
2. **Use imperative mood** - "Fix bug", not "Fixed bug" or "Fixes bug"
3. **Reference issues** - Use `#NNNN` to reference GitHub issues
4. **Small, focused commits** - One logical change per commit
5. **Rebase before push** - Keep history linear and clean

**Good Commit:**
```
Fix loader cache invalidation on module reload

When modules are reloaded, the loader cache was not properly
invalidated, causing stale references. Clear the cache dict
on reload to ensure fresh module imports.

Fixes #12345
```

**Bad Commit (NEVER DO THIS):**
```
Fixed some bugs

Co-Authored-By: Claude <noreply@anthropic.com>
```

**See [agents/docs/git-and-ci.md](agents/docs/git-and-ci.md) for complete git workflow and CI reproduction.**

---

## Checklists

### Execution Module Checklist
- [ ] `log = logging.getLogger(__name__)`
- [ ] Docstrings with CLI examples
- [ ] `__virtual__()` if platform/dependency specific
- [ ] Input validation with `SaltInvocationError`
- [ ] Error handling with `CommandExecutionError`
- [ ] Context caching for expensive operations
- [ ] Unit tests

### State Module Checklist
- [ ] Returns dict with: name, result, changes, comment
- [ ] `result=None` for test mode (`__opts__["test"]`)
- [ ] Check current state before changing
- [ ] Populate changes dict with old/new values
- [ ] Clear comment explaining outcome

### Common Imports
```python
import logging
import salt.exceptions
import salt.utils.args
import salt.utils.platform
import salt.utils.path

log = logging.getLogger(__name__)
```

### Logging
```python
# Use lazy formatting (NOT f-strings)
log.debug("Processing file: %s", filename)  # Good
log.debug(f"Processing file: {filename}")   # Bad
```

**Never log sensitive data** (passwords, tokens, keys).

### Error Handling
```python
from salt.exceptions import (
    CommandExecutionError,    # Operation failed
    SaltInvocationError,      # Invalid arguments
    CommandNotFoundError,     # Binary not found
)
```

---

## Detailed Documentation

**Essential guides in `agents/docs/`:**

- **[agents/docs/development-setup.md](agents/docs/development-setup.md)** - Virtual environment setup (venv310 and venv311), platform-specific dependencies, installation verification
- **[agents/docs/architecture.md](agents/docs/architecture.md)** - Complete Salt architecture, all module types, loader system, event bus
- **[agents/docs/module-templates.md](agents/docs/module-templates.md)** - Complete templates for execution and state modules, `__virtual__()` patterns, decorators
- **[agents/docs/testing.md](agents/docs/testing.md)** - Test structure, unit test templates, mocking patterns, running tests
- **[agents/docs/git-and-ci.md](agents/docs/git-and-ci.md)** - Commit guidelines, PR workflow, CI failure reproduction, container testing
- **[agents/docs/troubleshooting.md](agents/docs/troubleshooting.md)** - Import issues, module discovery, ZeroMQ, Python 3.11+ compatibility, lazy loading

---

## Key Example Files

- Simple module: `salt/modules/test.py`
- Complex module: `salt/modules/file.py`
- Package manager: `salt/modules/aptpkg.py`
- Service: `salt/modules/systemd_service.py`
- State examples: `salt/states/file.py`, `salt/states/pkg.py`

---

## Summary

When writing Salt code:

1. **Follow the patterns** - Use existing modules as templates
2. **Use dunders correctly** - `__salt__`, `__opts__`, `__grains__`, `__context__`
3. **Implement `__virtual__()`** - Declare platform and dependency requirements
4. **Handle errors properly** - Use Salt's exception classes
5. **Write tests** - Every new function needs unit tests
6. **Document thoroughly** - Docstrings with CLI examples are required
7. **Think idempotent** - Operations should be safe to repeat
8. **Cache wisely** - Use `__context__` for expensive operations

**When in doubt, look at existing modules for patterns and refer to the detailed documentation.**

**Remember: NEVER add AI attribution lines to commits!**
