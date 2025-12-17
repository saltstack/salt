# Testing Guide for archive.compressed Function

## Quick Start

### 1. Copy Tests to Test File

The template is in `test_compressed_template.py`. Copy the test functions into:

```
tests/pytests/unit/states/test_archive.py
```

Add them at the end of the file (after line 486).

### 2. Run Tests in WSL

```bash
# Navigate to project root
cd /mnt/c/Users/ironm/Documents/development/salt-dev/salt

# Run a single test
nox -e 'pytest-zeromq-3.11(coverage=False)' -- tests/pytests/unit/states/test_archive.py::test_compressed_zip_success -v

# Run all compressed tests
nox -e 'pytest-zeromq-3.11(coverage=False)' -- tests/pytests/unit/states/test_archive.py -k compressed -v

# Run all archive state tests
nox -e 'pytest-zeromq-3.11(coverage=False)' -- tests/pytests/unit/states/test_archive.py -v
```

## Understanding the Test Structure

### Basic Test Pattern

```python
def test_compressed_<scenario>():
    """
    Test description
    """
    # 1. Create mocks for execution modules
    zip_mock = MagicMock(return_value=True)

    # 2. Patch Salt's __salt__ dict with mocks
    with patch.dict(
        archive.__salt__,
        {"archive.zip": zip_mock},
    ), patch.dict(archive.__opts__, {"test": False}):

        # 3. Call the function
        ret = archive.compressed(
            name="/tmp/test.zip",
            sources=["/tmp/file.txt"],
        )

        # 4. Assert the results
        assert ret["result"] is True
        assert ret["changes"] == {"created": "/tmp/test.zip"}
        zip_mock.assert_called_once()
```

### Key Components

1. **Mocks**: Simulate Salt execution modules without actually running them
2. **patch.dict**: Temporarily replace `__salt__` and `__opts__` for testing
3. **Assertions**: Verify the function returns correct results and calls modules correctly

## Minimum Tests for PR Acceptance

Based on Salt's CONTRIBUTING.rst, you need:

1. ✅ **ZIP format test** - Verify ZIP creation works
2. ✅ **TAR format test** - Verify TAR creation with compression
3. ✅ **Test mode** - Verify no changes in test mode
4. ✅ **Error handling** - Verify failures are handled correctly

## Recommended Test Coverage

### Format Tests

- `test_compressed_zip_success` - ZIP creation
- `test_compressed_tar_gz_success` - TAR with gzip
- `test_compressed_tar_bz2` - TAR with bzip2
- `test_compressed_tar_xz` - TAR with xz
- `test_compressed_tar_no_compression` - Plain TAR

### Behavior Tests

- `test_compressed_test_mode` - Test mode (no changes)
- `test_compressed_file_exists_no_overwrite` - Don't overwrite by default
- `test_compressed_file_exists_with_overwrite` - Overwrite when requested

### Error Tests

- `test_compressed_missing_sources` - Handle empty sources
- `test_compressed_invalid_format` - Handle unsupported formats
- `test_compressed_execution_module_fails` - Handle module failures

### Feature Tests

- `test_compressed_tar_with_ownership` - User/group/mode for tar
- `test_compressed_zip_with_options` - Custom options

## Adjusting Tests to Your Implementation

### 1. Check Your Return Structure

Look at your `compressed` function to see what it returns:

```python
# Your function probably returns something like:
return {
    "name": name,
    "result": True,  # or False, or None
    "changes": {"created": name},  # or {}
    "comment": "Successfully created archive"
}
```

### 2. Check Parameter Names

Make sure test calls match your function signature:

```python
def compressed(name, sources, archive_format="zip", compression=None,
               options=None, user=None, group=None, mode=None, overwrite=True):
```

### 3. Check Execution Module Calls

See what your function calls in `__salt__`:

```python
# For ZIP:
__salt__["archive.zip"](name, sources=sources, ...)

# For TAR:
__salt__["archive.tar"](options, name, sources=sources, ...)
```

### 4. Check Error Messages

Update test assertions to match your actual error messages:

```python
# If your function returns:
"comment": "No sources provided"

# Update test assertion:
assert "No sources" in ret["comment"]
```

## Running Tests Efficiently

### During Development

```bash
# Run just the test you're working on
nox -e 'pytest-zeromq-3.11(coverage=False)' -- tests/pytests/unit/states/test_archive.py::test_compressed_zip_success -v
```

### Before Committing

```bash
# Run all compressed tests
nox -e 'pytest-zeromq-3.11(coverage=False)' -- tests/pytests/unit/states/test_archive.py -k compressed -v

# Run all archive tests to ensure nothing broke
nox -e 'pytest-zeromq-3.11(coverage=False)' -- tests/pytests/unit/states/test_archive.py -v
```

## Interpreting Test Results

### Success

```
tests/pytests/unit/states/test_archive.py::test_compressed_zip_success PASSED
```

### Failure

```
tests/pytests/unit/states/test_archive.py::test_compressed_zip_success FAILED
...
AssertionError: assert False is True
```

This means your function returned `result: False` when the test expected `True`.

### Mock Not Called

```
AssertionError: Expected 'archive.zip' to be called once. Called 0 times.
```

This means your function didn't call the execution module when it should have.

## Common Issues

### 1. Import Error

If you get: `NameError: name 'archive' is not defined`

The tests use the module imported at the top of test_archive.py:

```python
import salt.states.archive as archive
```

### 2. Mock Not Working

If execution modules are actually being called (not mocked):

```python
# Make sure you're using patch.dict correctly:
with patch.dict(archive.__salt__, {"archive.zip": zip_mock}):
    # Your test here
```

### 3. Test Passes But Shouldn't

Your mock might be too permissive. Add specific assertions:

```python
zip_mock.assert_called_once_with(
    "/tmp/test.zip",
    sources=["/tmp/file.txt"],
    cwd=None,
)
```

## Next Steps

1. **Copy tests** from template to test_archive.py
2. **Adjust tests** to match your implementation
3. **Run one test** to verify it works
4. **Fix any issues** revealed by the test
5. **Run all tests** to ensure complete coverage
6. **Commit** when all tests pass

## PR Requirements

When submitting your PR, Salt maintainers look for:

- ✅ Tests exist for new functionality
- ✅ Tests pass in CI/CD pipeline
- ✅ Tests cover normal operation
- ✅ Tests cover error cases
- ✅ Tests cover test mode (dry run)
- ✅ Tests don't break existing functionality

Your tests will run automatically when you submit the PR on GitHub.
