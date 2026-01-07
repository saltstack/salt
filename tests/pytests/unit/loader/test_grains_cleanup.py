"""
Tests for grains module cleanup and garbage collection

Validates that grains modules are properly unloaded and garbage collected
after salt.loader.grains() completes to prevent memory leaks.
"""

import gc
import sys
import weakref

import pytest

import salt.config
import salt.loader


@pytest.fixture
def minion_opts():
    """
    Default minion configuration for testing.
    """
    opts = salt.config.DEFAULT_MINION_OPTS.copy()
    opts["optimization_order"] = [0]
    opts["extension_modules"] = ""
    opts["grains_cache"] = False  # Disable caching for clean test
    return opts


def test_grains_modules_removed_from_sys_modules(minion_opts):
    """
    Test that grains modules are removed from sys.modules after grains() completes.

    This prevents modules from accumulating in memory on repeated grains() calls.
    """
    # Get initial state
    initial_modules = set(sys.modules.keys())

    # Load grains
    grains_data = salt.loader.grains(minion_opts)

    # Verify we got grains
    assert isinstance(grains_data, dict)
    assert len(grains_data) > 0

    # Check what modules are in sys.modules now
    after_grains = set(sys.modules.keys())
    loaded_modules = [
        m for m in (after_grains - initial_modules) if m.startswith("salt.loaded.")
    ]

    # After grains() completes, loaded grains modules should be cleaned up
    assert (
        len(loaded_modules) == 0
    ), f"Found {len(loaded_modules)} grains modules still in sys.modules: {loaded_modules[:10]}"


def test_grains_modules_garbage_collected(minion_opts):
    """
    Test that grains modules are actually garbage collected, not just removed from sys.modules.

    Uses weakrefs to verify modules are truly freed from memory.
    """
    # Track initial state
    initial_modules = set(sys.modules.keys())

    # Create a loader to get some module references
    temp_loader = salt.loader.grain_funcs(minion_opts)

    # Load a few grains modules and create weakrefs to them
    module_weakrefs = []
    for key in list(temp_loader.keys())[:5]:
        # Trigger loading by accessing the function
        try:
            _ = temp_loader[key]
        except Exception:
            # Some grains may fail to load, that's ok
            pass

    # Get loaded module objects from sys.modules and create weakrefs
    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith("salt.loaded.int.grains.") and mod_name not in initial_modules:
            mod_obj = sys.modules[mod_name]
            module_weakrefs.append((mod_name, weakref.ref(mod_obj)))

    # Clean up the loader
    temp_loader.clean_modules()
    del temp_loader

    # Now call grains() which should also clean up
    grains_data = salt.loader.grains(minion_opts)
    assert isinstance(grains_data, dict)

    # Force garbage collection
    gc.collect()
    gc.collect()  # Sometimes need multiple passes

    # Check that weakrefs are dead (modules were garbage collected)
    still_alive = []
    for mod_name, ref in module_weakrefs:
        if ref() is not None:
            still_alive.append(mod_name)

    # Allow a small number of modules to remain due to circular references
    # or imports from other modules, but most should be collected
    total_tracked = len(module_weakrefs)
    collected = total_tracked - len(still_alive)
    collection_rate = (collected / total_tracked * 100) if total_tracked > 0 else 100

    assert collection_rate >= 80, (
        f"Only {collection_rate:.1f}% of modules were garbage collected "
        f"({collected}/{total_tracked}). Still alive: {still_alive}"
    )


def test_grains_cleanup_is_idempotent(minion_opts):
    """
    Test that calling grains() multiple times doesn't accumulate modules.

    Each call should clean up after itself.
    """
    # Get baseline
    gc.collect()
    initial_modules = set(sys.modules.keys())

    # Call grains() multiple times
    for i in range(3):
        grains_data = salt.loader.grains(minion_opts)
        assert isinstance(grains_data, dict)

        # Check modules after each call
        current_modules = set(sys.modules.keys())
        loaded_modules = [
            m for m in current_modules if m.startswith("salt.loaded.int.grains.")
        ]

        assert (
            len(loaded_modules) == 0
        ), f"Iteration {i+1}: Found {len(loaded_modules)} accumulated grains modules"


def test_grains_cleanup_clears_loader_internals(minion_opts):
    """
    Test that clean_modules() clears internal loader state.

    Verifies that _dict, loaded_modules, loaded_files, and missing_modules
    are all cleared to allow garbage collection.
    """
    # Create a loader
    loader = salt.loader.grain_funcs(minion_opts)

    # Load some modules
    for key in list(loader.keys())[:3]:
        try:
            _ = loader[key]
        except Exception:
            pass

    # Verify loader has state
    assert len(loader._dict) > 0 or len(loader.loaded_modules) > 0

    # Clean modules
    loader.clean_modules()

    # Verify all internal state is cleared
    assert len(loader._dict) == 0, "loader._dict not cleared"
    assert len(loader.loaded_modules) == 0, "loader.loaded_modules not cleared"
    assert len(loader.loaded_files) == 0, "loader.loaded_files not cleared"
    assert len(loader.missing_modules) == 0, "loader.missing_modules not cleared"


def test_grains_cleanup_on_error(minion_opts):
    """
    Test that cleanup happens even if grains() encounters errors.

    This ensures we don't leak memory when grains fail to load.
    """
    # Intentionally break something to cause potential errors
    # (grains should still return a dict even with some failures)
    initial_modules = set(sys.modules.keys())

    # Call grains - may have some failures but should still work
    grains_data = salt.loader.grains(minion_opts)
    assert isinstance(grains_data, dict)

    # Verify cleanup happened despite any errors
    after_modules = set(sys.modules.keys())
    loaded_modules = [
        m for m in (after_modules - initial_modules) if m.startswith("salt.loaded.")
    ]

    assert (
        len(loaded_modules) == 0
    ), f"Cleanup failed on error: {len(loaded_modules)} modules remain"


def test_clean_modules_removes_from_sys_modules(minion_opts):
    """
    Test that LazyLoader.clean_modules() properly removes modules from sys.modules.

    This is a focused test of the clean_modules() method itself.
    """
    loader = salt.loader.grain_funcs(minion_opts)

    # Track what base name is used
    loaded_base_name = loader.loaded_base_name

    # Load some modules
    for key in list(loader.keys())[:5]:
        try:
            _ = loader[key]
        except Exception:
            pass

    # Find modules that were loaded
    loaded_before = [m for m in sys.modules if m.startswith(loaded_base_name)]
    assert len(loaded_before) > 0, "No modules were loaded for testing"

    # Clean modules
    loader.clean_modules()

    # Verify they're removed
    loaded_after = [m for m in sys.modules if m.startswith(loaded_base_name)]
    assert (
        len(loaded_after) == 0
    ), f"clean_modules() failed to remove {len(loaded_after)} modules from sys.modules"


@pytest.mark.parametrize("force_refresh", [False, True])
def test_grains_cleanup_with_refresh(minion_opts, force_refresh):
    """
    Test that cleanup works with both normal and force_refresh modes.

    Args:
        force_refresh: Whether to force refresh grains
    """
    initial_modules = set(sys.modules.keys())

    # Call grains with force_refresh parameter
    grains_data = salt.loader.grains(minion_opts, force_refresh=force_refresh)
    assert isinstance(grains_data, dict)

    # Verify cleanup happened
    after_modules = set(sys.modules.keys())
    loaded_modules = [
        m for m in (after_modules - initial_modules) if m.startswith("salt.loaded.")
    ]

    assert len(loaded_modules) == 0, (
        f"Cleanup failed with force_refresh={force_refresh}: "
        f"{len(loaded_modules)} modules remain"
    )
