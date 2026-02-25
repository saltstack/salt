# Salt Development Troubleshooting

Common gotchas and solutions when developing Salt.

## Import Order Issues

Salt enforces strict import order via `isort` (profile 3, trailing commas). Configuration is in `pyproject.toml`.

### Required Order

```python
# 1. Standard library imports
import logging
import os
import sys

# 2. Salt imports
import salt.exceptions
import salt.utils.args
import salt.utils.platform

# 3. Third-party imports
import requests
```

### Fixing Import Order

```bash
# Auto-fix import order
isort .

# Check without modifying
isort --check .
```

## Module Discovery Issues

### Missing __init__.py

Module directories need `__init__.py` files for Python to recognize them as packages.

```bash
# Check for missing __init__.py
find salt/modules -type d ! -exec test -e {}/__init__.py \; -print
```

### Filename Becomes Namespace

The filename determines the module namespace:
- `salt/modules/pkg.py` → accessible as `pkg.*`
- Use `__virtualname__` to override the name

### Performance Tip

Filename should match virtualname when possible to avoid loader overhead.

**Good:**
```python
# File: salt/modules/systemd_service.py
__virtualname__ = "service"  # Will be service.* on systemd systems
```

**Less efficient:**
```python
# File: salt/modules/my_totally_different_name.py
__virtualname__ = "service"  # Loader has to scan more files
```

## Loader Changes Impact Everything

Changes to `salt/loader/` affect all plugin types (modules, states, grains, pillars, etc.).

### Test Thoroughly

```bash
# Run loader unit tests
nox -e test-3 -- tests/pytests/unit/test_loader.py

# Run integration tests
nox -e test-3 -- tests/pytests/integration/
```

### Common Loader Issues

1. **Cache invalidation** - Clear `__context__` properly on reload
2. **Dunder injection** - Ensure all required dunders are injected
3. **Virtual module loading** - Check `__virtual__()` is called correctly
4. **Lazy loading** - Modules only load on first access

## ZeroMQ Issues

### Tests Hang or Timeout

If tests hang indefinitely:

```bash
# Kill stale Salt processes
pkill -9 -f salt

# Check for port conflicts
lsof -i :4505  # Publisher port
lsof -i :4506  # Request port
```

### Verify ZeroMQ Installation

```bash
python -c "import zmq; print(zmq.zmq_version())"
```

If this fails, reinstall ZeroMQ:

```bash
pip uninstall pyzmq
pip install pyzmq
```

### Port Conflicts

Salt uses:
- **4505**: Publish port (master publishes commands)
- **4506**: Request port (minions send requests)

If these ports are in use, tests will fail or hang.

## Container Filesystem Behavior

When running tests in containers:

### Source Changes

Changes to `salt/` source code are visible immediately (mounted volume):

```bash
# Edit on host
vim salt/modules/pkg.py

# Immediately visible in container
docker exec mycontainer cat /salt/salt/modules/pkg.py
```

### Library Changes

Changes to installed Salt library may need manual sync:

```bash
# After editing source, copy to installed location
docker exec <NAME> cp /salt/salt/modules/foo.py \
    /salt/artifacts/salt/lib/python3.11/site-packages/salt/modules/
```

## Python 3.11+ Compatibility

### Known Issues

1. **IPv6 timeout** - Python 3.11+ prefers IPv6, waits before IPv4 fallback
2. **Relenv toolchain path** - Expects `/root/.local/relenv/toolchain/`, but relenv uses `/root/.cache/relenv/toolchains/`
3. **"backports" module** - Conditionally included in Python < 3.13

### Solutions

#### IPv6 Timeout

Use ULA IPv6 addresses with NAT:

```yaml
# In container config
networks:
  default:
    enable_ipv6: true
    ipam:
      config:
        - subnet: fd00:db8::/64
```

#### Relenv Toolchain Path

Create symlink in container:

```bash
docker exec <NAME> bash -c "mkdir -p /root/.local/relenv && ln -sf /root/.cache/relenv/toolchains /root/.local/relenv/toolchain"
```

This is required for all Python 3.11+ container tests.

#### Backports Module

Update test mocks to handle conditional import:

```python
# Old (fails on 3.11+)
import backports.ssl

# New (handles both)
try:
    import backports.ssl
except ImportError:
    import ssl as backports_ssl
```

## Stale Artifacts

### Symptom

Tests fail with confusing errors like "module not found" or "wrong version".

### Solution

Always clean before downloading new CI artifacts:

```bash
rm -rf artifacts/ nox-*.zip nox.*.tar.*
```

### Why This Happens

Artifacts are cached locally. If you download artifacts from a different run, old files may conflict.

## Lazy Loading Behavior

### Issue

Modules only load on first access. Import-time side effects may not occur until first use of a module function.

### Example

```python
# Module import doesn't execute __virtual__()
import salt.modules.systemd_service

# __virtual__() executes on first function call
salt.modules.systemd_service.restart("nginx")
```

### Impact

- Unit tests must trigger module loading explicitly
- Side effects at module level may not happen when expected
- `__virtual__()` failures only visible on first use

## Pre-commit Hook Issues

### Hooks Not Running

If pre-commit hooks don't run on commit:

```bash
# Ensure you're in venv311
source venv311/bin/activate

# Install hooks
pre-commit install

# Test manually
pre-commit run --all-files
```

### Hook Failures

If hooks fail:

```bash
# Run specific hook
pre-commit run black --all-files
pre-commit run isort --all-files

# Auto-fix issues
black .
isort .
```

### Skipping Hooks (Not Recommended)

Only skip hooks if absolutely necessary:

```bash
git commit --no-verify
```

## Module Import Errors

### Salt Exceptions Not Found

If you get `ImportError: cannot import name 'SaltInvocationError'`:

```python
# Wrong
from salt.exceptions import SaltInvocationError

# Check spelling and case
from salt.exceptions import (
    CommandExecutionError,
    SaltInvocationError,  # Note: capital I
)
```

### Circular Import Issues

Salt's loader system can sometimes create circular imports. Solutions:

1. **Lazy import** - Import inside function instead of module level
2. **Use __salt__** - Call other modules via `__salt__` instead of direct import
3. **Utility functions** - Move shared code to `salt/utils/`

## Test Failures

### Tests Pass Individually But Fail Together

This often indicates:
1. **Shared state** - Tests modifying global state
2. **Resource conflicts** - Tests using same ports/files
3. **Order dependency** - Tests depending on execution order

Solution: Use proper teardown and isolation.

### Mocking Doesn't Work

Common issues:

```python
# Wrong - mocking after import
import salt.modules.mymodule as mymodule
with patch("some.function"):  # Too late!
    mymodule.my_function()

# Right - mock before use
with patch("salt.modules.mymodule.some_function"):
    import salt.modules.mymodule as mymodule
    mymodule.my_function()

# Better - use patch.dict for dunders
with patch.dict(mymodule.__salt__, {"cmd.run": MagicMock()}):
    mymodule.my_function()
```

## Performance Issues

### Slow Tests

If tests are slow:

1. **Check mocking** - Ensure external calls are mocked
2. **Avoid network** - Mock all network operations
3. **Mock subprocess** - Don't run real commands in unit tests
4. **Use __context__** - Cache expensive operations

### Slow __virtual__

Keep `__virtual__()` fast:

```python
# Bad - expensive operation
def __virtual__():
    packages = fetch_all_packages()  # Slow!
    if "mypackage" in packages:
        return True
    return False

# Good - quick check
def __virtual__():
    if salt.utils.path.which("mycommand"):
        return True
    return False
```

## Common Error Messages

### "Transport ZMQ exception"

- Kill stale processes: `pkill -9 -f salt`
- Check ZeroMQ install: `python -c "import zmq"`
- Check port availability: `lsof -i :4505 :4506`

### "Module 'X' could not be loaded"

- Check `__virtual__()` return value
- Verify dependencies are installed
- Check platform compatibility

### "KeyError: '__salt__'"

- Dunder not injected - check test fixture
- Module not loaded via loader - use proper test setup

### "SaltInvocationError"

- Check function arguments
- Validate required parameters are provided
- Ensure parameter types are correct

## Getting Help

If you're still stuck:

1. **Check existing modules** - Look for similar patterns
2. **Read test files** - See how others test similar code
3. **Git history** - Look at how issues were fixed before
4. **Documentation** - Check `doc/` directory
5. **Contributing guide** - Read `CONTRIBUTING.rst`
