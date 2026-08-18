# Salt Development Instructions for Gemini

You are assisting with development of Salt, a powerful infrastructure automation and configuration management system written in Python. This guide provides essential quick reference and links to detailed documentation.

## Coding Philosophy

**CRITICAL**: Write code as a CPython core developer:
- Understand Python internals, memory management, GC
- Know performance implications
- Be aware of implementation details

**Zen of Python**: Readability counts. Explicit > implicit. Simple > complex. Errors never pass silently.

**TDD for Bug Fixes**:
1. Write failing test first → 2. Verify it fails → 3. Fix bug (minimal changes) → 4. Verify test passes → 5. Run related tests

---

## Architecture Quick Reference

Salt is a Python-based configuration management system:
- **Master-Minion Architecture**: Central master controls distributed minions
- **Event-Driven**: Real-time communication via event bus
- **Plugin-Based**: Extensible through loader system

**Key Module Types:**
- **Execution Modules** (`salt/modules/`): CLI commands on minions (264+)
- **State Modules** (`salt/states/`): Declarative configuration (126+)
- **Utils** (`salt/utils/`): Shared utility functions (170+)

**See [agents/docs/architecture.md](agents/docs/architecture.md) for complete architecture.**

---

## Dunder Dictionaries

Salt injects special variables into module scope:

**Always Available:**
- `__opts__` - Config options: `__opts__.get("id")`, `__opts__["test"]`
- `__grains__` - System data: `__grains__.get("os_family")`
- `__pillar__` - Secure data: `__pillar__.get("password")`
- `__context__` - Per-run cache for expensive operations

**Module-Specific:**
- `__salt__` - Other execution modules: `__salt__["pkg.install"]("nginx")`
- `__utils__` - Utility functions: `__utils__["files.is_text"](path)`
- `__states__` - State modules (in state modules only)

**Context Caching Pattern:**
```python
if "pkg_list" not in __context__:
    __context__["pkg_list"] = expensive_fetch()  # Once per run
return __context__["pkg_list"]
```

**See [agents/docs/architecture.md](agents/docs/architecture.md) for loader system details.**

---

## Execution Module Structure

```python
import logging
import salt.exceptions
import salt.utils.platform

log = logging.getLogger(__name__)

def __virtual__():
    """Returns True to load, False or (False, reason) to skip"""
    if not salt.utils.path.which("required_binary"):
        return False, "required_binary not found"
    return True

def my_function(name, param=None):
    """
    CLI Example:
        salt '*' mymodule.my_function foo param=bar
    """
    if not name:
        raise salt.exceptions.SaltInvocationError("name required")
    return __salt__["cmd.run"](f"command {name}")
```

**See [agents/docs/module-templates.md](agents/docs/module-templates.md) for complete templates.**

---

## State Module Structure

**Required Return:**
```python
{
    "name": name,              # Resource identifier
    "result": True/False/None, # Success/Failure/Test mode
    "changes": {},             # {"old": ..., "new": ...}
    "comment": ""              # What happened
}
```

**State Flow:**
1. Validate input → 2. Check current state → 3. If correct: return success → 4. If test mode: return `result=None` with proposed changes → 5. Make changes → 6. Return result

**See [agents/docs/module-templates.md](agents/docs/module-templates.md) for complete state templates.**

---

## Common Patterns

### Logging
```python
log = logging.getLogger(__name__)
# Use lazy formatting (NOT f-strings)
log.debug("Processing: %s", filename)  # Good
log.debug(f"Processing: {filename}")   # Bad
```
**Never log sensitive data.**

### Error Handling
```python
from salt.exceptions import (
    CommandExecutionError,   # Operation failed
    SaltInvocationError,     # Invalid arguments
    CommandNotFoundError,    # Binary not found
)
```

### Platform Detection
```python
import salt.utils.platform
if salt.utils.platform.is_windows():
    # Windows-specific
if __grains__.get("os_family") == "Debian":
    # Debian-based
```

---

## Git Workflow

### CRITICAL RULES

1. **NO attribution lines** - **NEVER** add "Generated with Claude Code", "Co-Authored-By: Claude", or any AI attribution
2. **Imperative mood** - "Fix bug", not "Fixed bug"
3. **Reference issues** - Use `#NNNN`
4. **Small commits** - One logical change per commit
5. **Rebase before push** - Linear history

**Good Commit:**
```
Fix loader cache invalidation on module reload

Clear cache dict on reload to ensure fresh module imports.

Fixes #12345
```

**Bad (NEVER):**
```
Fixed bugs
Co-Authored-By: Claude <noreply@anthropic.com>
```

**See [agents/docs/git-and-ci.md](agents/docs/git-and-ci.md) for complete workflow.**

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
- [ ] Returns: name, result, changes, comment
- [ ] `result=None` for test mode
- [ ] Check current state first
- [ ] Populate changes dict
- [ ] Clear comments

---

## Detailed Documentation

**Essential guides in `agents/docs/`:**

- **[agents/docs/development-setup.md](agents/docs/development-setup.md)** - venv310/venv311 setup, dependencies, verification
- **[agents/docs/architecture.md](agents/docs/architecture.md)** - Complete architecture, module types, loader, event bus
- **[agents/docs/module-templates.md](agents/docs/module-templates.md)** - Complete templates, `__virtual__()` patterns, decorators
- **[agents/docs/testing.md](agents/docs/testing.md)** - Test structure, templates, mocking, running tests
- **[agents/docs/git-and-ci.md](agents/docs/git-and-ci.md)** - Commit guidelines, PR workflow, CI reproduction
- **[agents/docs/troubleshooting.md](agents/docs/troubleshooting.md)** - Import issues, ZeroMQ, Python 3.11+, lazy loading

---

## Key Example Files

- Simple: `salt/modules/test.py`
- Complex: `salt/modules/file.py`
- Package: `salt/modules/aptpkg.py`
- Service: `salt/modules/systemd_service.py`
- States: `salt/states/file.py`, `salt/states/pkg.py`

---

## Summary

1. **Follow patterns** - Use existing modules as templates
2. **Use dunders** - `__salt__`, `__opts__`, `__grains__`, `__context__`
3. **Implement `__virtual__()`** - Declare dependencies
4. **Handle errors** - Use Salt exception classes
5. **Write tests** - Every function needs tests
6. **Document** - Docstrings with CLI examples required
7. **Think idempotent** - Safe to repeat
8. **Cache wisely** - Use `__context__`

**When in doubt, check existing modules and refer to detailed docs.**

**Remember: NEVER add AI attribution lines to commits!**
