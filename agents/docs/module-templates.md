# Salt Module Templates

This document provides comprehensive templates for writing Salt modules.

## Execution Module Template

All execution modules follow this basic structure:

```python
"""
Module docstring explaining purpose
"""

import logging

import salt.exceptions
import salt.utils.args
import salt.utils.data
import salt.utils.files
import salt.utils.path
import salt.utils.platform

# Set up logging
log = logging.getLogger(__name__)

# Module metadata
__virtualname__ = "mymodule"  # Optional: override module name
__proxyenabled__ = ["*"]  # Optional: enable for proxy minions
__func_alias__ = {
    "list_": "list"  # Optional: map function names to avoid Python keywords
}


def __virtual__():
    """
    Only load this module if requirements are met
    Returns True, False, or (False, reason)
    """
    if not salt.utils.path.which("mycommand"):
        return False, "mycommand binary not found"
    return True


def my_function(name, param=None):
    """
    Function description

    name
        Description of name parameter

    param
        Description of param parameter

    CLI Example:

    .. code-block:: bash

        salt '*' mymodule.my_function foo param=bar
    """
    log.debug("Running my_function with name=%s", name)

    # Implementation
    result = do_something(name, param)

    return result
```

## State Module Template

State modules provide idempotent, declarative configuration. They call execution modules to do the actual work.

### State Return Structure

Every state function MUST return this exact structure:

```python
ret = {
    "name": name,        # The name parameter passed to the state
    "result": result,    # True (success), False (failure), or None (test mode)
    "changes": {},       # Dictionary of changes made
    "comment": comment   # String or list describing what happened
}
```

### Complete State Template

```python
"""
State module docstring
"""

import logging

import salt.exceptions

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load if the corresponding execution module is available
    """
    if "mymod.do_thing" in __salt__:
        return True
    return (False, "mymod execution module not available")


def managed(name, value=None, **kwargs):
    """
    Ensure something is in the desired state

    name
        The resource identifier

    value
        The desired value

    Example:

    .. code-block:: yaml

        /etc/myconfig:
          mymod.managed:
            - value: foo
    """
    # Initialize return dict
    ret = {
        "name": name,
        "result": False,
        "changes": {},
        "comment": ""
    }

    # 1. Validate input
    if not name:
        ret["comment"] = "Name is required"
        return ret

    # 2. Check current state
    current = __salt__["mymod.get_current"](name)

    # 3. Compare with desired state
    if current == value:
        ret["result"] = True
        ret["comment"] = f"{name} is already in the desired state"
        return ret

    # 4. Handle test mode
    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"{name} would be updated"
        ret["changes"] = {"old": current, "new": value}
        return ret

    # 5. Make changes
    try:
        result = __salt__["mymod.set_value"](name, value)
    except Exception as exc:
        ret["comment"] = f"Failed to update {name}: {exc}"
        return ret

    # 6. Verify changes
    new_value = __salt__["mymod.get_current"](name)

    # 7. Set result and changes
    if new_value == value:
        ret["result"] = True
        ret["changes"] = {"old": current, "new": new_value}
        ret["comment"] = f"{name} was updated"
    else:
        ret["result"] = False
        ret["comment"] = f"Failed to update {name}"

    return ret
```

### State Flow Diagram

```
1. Validate Input → Invalid? Return with result=False
                  ↓
2. Check Current State
                  ↓
3. Already Correct? → Yes: Return with result=True, no changes
                  ↓ No
4. Test Mode? → Yes: Return with result=None, proposed changes
                  ↓ No
5. Make Changes
                  ↓
6. Verify Changes
                  ↓
7. Return Result (True/False) with changes dict
```

### State Result Values

- **`result=True`**: State succeeded, system is in desired state
- **`result=False`**: State failed, system is NOT in desired state
- **`result=None`**: Test mode, changes would be made but weren't

### Changes Dictionary

The `changes` dictionary should show what changed:

```python
# Simple change
ret["changes"] = {"old": "foo", "new": "bar"}

# Multiple changes
ret["changes"] = {
    "user": {"old": "root", "new": "apache"},
    "mode": {"old": "0644", "new": "0755"},
}

# New resource created
ret["changes"] = {"created": name}

# Resource removed
ret["changes"] = {"removed": name}
```

## The __virtual__ Function Patterns

The `__virtual__()` function determines whether a module should load on a particular system. It runs before any other module code and should be fast.

### Return Values

1. **`True`**: Load module with filename as name
2. **`False`**: Don't load module
3. **`(False, reason)`**: Don't load, with explanation
4. **`"string"`**: Load module with this name (virtualname)
5. **`("string", reason)`**: Load with name, with explanation

### Pattern 1: Simple Platform Check

```python
def __virtual__():
    """
    Only work on POSIX-like systems
    """
    if salt.utils.platform.is_windows():
        return (
            False,
            "The file execution module cannot be loaded: only available on "
            "non-Windows systems - use win_file instead.",
        )
    return True
```

### Pattern 2: Virtual Name with OS Check

Used when multiple modules implement the same interface (e.g., `pkg` for different package managers).

```python
__virtualname__ = "pkg"

def __virtual__():
    """
    Confirm this module is on a Debian-based system
    """
    if __grains__.get("os_family") == "Debian":
        return __virtualname__
    return False, "The pkg module could not be loaded: unsupported OS family"
```

### Pattern 3: Binary Availability Check

```python
def __virtual__():
    """
    Only load if systemctl is available
    """
    if not salt.utils.path.which("systemctl"):
        return False, "The systemd module could not be loaded: systemctl not found"
    return True
```

### Pattern 4: Complex Multi-Condition Check

```python
__virtualname__ = "service"

def __virtual__():
    """
    Only work on systems that have been booted with systemd
    """
    is_linux = __grains__.get("kernel") == "Linux"
    is_booted = salt.utils.systemd.booted(__context__)
    is_offline = salt.utils.systemd.offline(__context__)

    if is_linux and (is_booted or is_offline):
        return __virtualname__

    return (
        False,
        "The systemd execution module failed to load: only available on Linux "
        "systems which have been booted with systemd.",
    )
```

### Pattern 5: Check for Execution Module Availability

Used in state modules to verify required execution modules exist.

```python
def __virtual__():
    """
    Only make these states available if a pkg provider has been detected
    """
    if "pkg.install" in __salt__:
        return True
    return (False, "pkg module could not be loaded")
```

### Best Practices for __virtual__

- Keep `__virtual__()` fast - it runs on every module scan
- Provide clear error messages explaining why the module didn't load
- Use `salt.utils.platform` for platform detection
- Check grains for OS-specific logic
- Cache expensive checks in `__context__` if needed

## Common Module Patterns

### Decorators

Salt provides decorators for common tasks:

```python
from salt.utils.decorators import depends, memoize
from salt.utils.decorators.path import which

# Ensure binary exists
@which("systemctl")
def restart_service(name):
    """Only available if systemctl is found"""
    pass

# Ensure Python module exists
@depends("docker")
def list_containers():
    """Only available if docker module is installed"""
    pass

# Memoize expensive operations
@memoize
def get_system_info():
    """Cache result for lifetime of process"""
    pass
```

### Function Aliases

Map function names to avoid Python keywords:

```python
__func_alias__ = {
    "list_": "list",      # my_module.list() → my_module.list_()
    "exec_": "exec",      # my_module.exec() → my_module.exec_()
}
```

### Cross-Calling Modules

```python
def my_function():
    """Call other execution modules"""
    # Get file contents
    content = __salt__["file.read"]("/etc/hosts")

    # Run a command
    output = __salt__["cmd.run"]("ls -la")

    # Install a package
    result = __salt__["pkg.install"]("nginx")

    return result
```

### Argument Handling

```python
import salt.utils.args

def my_function(*args, **kwargs):
    """Handle various argument formats"""
    # Clean extra kwargs from state data
    kwargs = salt.utils.args.clean_kwargs(**kwargs)

    # Parse key=value arguments
    kwargs.update(salt.utils.args.parse_input(args))

    return kwargs
```

### Path Handling

```python
import salt.utils.path

def my_function():
    """Handle paths safely"""
    # Find binary in PATH
    binary = salt.utils.path.which("nginx")
    if not binary:
        return False

    # Join paths correctly for OS
    config_path = salt.utils.path.join("/etc", "nginx", "nginx.conf")

    return config_path
```

### Platform Detection

```python
import salt.utils.platform

def my_function():
    """Handle platform differences"""
    if salt.utils.platform.is_windows():
        return "C:\\Windows"
    elif salt.utils.platform.is_linux():
        return "/etc"
    elif salt.utils.platform.is_darwin():
        return "/Library"

    # Check specific OS family
    if __grains__.get("os_family") == "Debian":
        return "apt"
    elif __grains__.get("os_family") == "RedHat":
        return "yum"
```

### Context Caching Pattern

```python
def _get_cached_value():
    """Safe context usage for standalone calls"""
    try:
        context = __context__
    except NameError:
        context = {}

    if "my_key" not in context:
        context["my_key"] = expensive_operation()
    return context.get("my_key")
```

## Error Handling

Use Salt's exception classes for consistent error handling:

```python
from salt.exceptions import (
    CommandExecutionError,    # Command/operation failed
    SaltInvocationError,      # Bad function arguments
    MinionError,              # General minion error
    CommandNotFoundError,     # Binary not found
)

def my_function(path, required_param):
    """
    Example with proper error handling
    """
    # Validate required parameters
    if not required_param:
        raise SaltInvocationError("required_param is mandatory")

    # Validate parameter values
    if not os.path.exists(path):
        raise SaltInvocationError(f"Path does not exist: {path}")

    # Check for required binary
    binary = salt.utils.path.which("mytool")
    if not binary:
        raise CommandNotFoundError("mytool binary not found in PATH")

    # Execute operation with error handling
    try:
        result = __salt__["cmd.run_all"](f"{binary} {path}")
    except Exception as exc:
        raise CommandExecutionError(
            f"Failed to run mytool on {path}: {exc}"
        )

    # Check command result
    if result["retcode"] != 0:
        raise CommandExecutionError(
            f"mytool failed: {result['stderr']}"
        )

    return result["stdout"]
```

### When to Use Each Exception

- **`SaltInvocationError`**: Invalid function arguments, missing required parameters
- **`CommandExecutionError`**: Operation failed (file not found, command failed, etc.)
- **`CommandNotFoundError`**: Required binary not in PATH
- **`MinionError`**: General minion-side errors
- **Standard exceptions**: Use Python's built-in exceptions when appropriate

## Module Checklists

### Execution Module Checklist

- [ ] Proper imports (logging, salt.exceptions, salt.utils.*)
- [ ] Logger configured: `log = logging.getLogger(__name__)`
- [ ] `__virtual__()` function if platform/dependency specific
- [ ] Docstrings on all functions with CLI examples
- [ ] Input validation with proper exceptions
- [ ] Error handling with CommandExecutionError/SaltInvocationError
- [ ] Use `__context__` for caching expensive operations
- [ ] Unit tests covering success and error cases

### State Module Checklist

- [ ] Returns correct dict structure (name, result, changes, comment)
- [ ] Validates input parameters
- [ ] Checks current state before making changes
- [ ] Handles test mode (`__opts__["test"]`)
- [ ] Verifies changes after applying
- [ ] Sets `result` correctly (True/False/None)
- [ ] Populates `changes` dict with before/after
- [ ] Provides clear `comment` explaining what happened

## Reference Files

- Simple example: `salt/modules/test.py`
- Complex example: `salt/modules/file.py`
- Platform-specific: `salt/modules/aptpkg.py`, `salt/modules/systemd_service.py`
- State examples: `salt/states/file.py`, `salt/states/pkg.py`
- Documentation: `doc/topics/development/modules/developing.rst`, `doc/ref/states/writing.rst`
