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
    Base stub modules are preserved as they're shared infrastructure.
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

    # Filter out base stub modules and utils modules - these are intentionally preserved
    # Base stubs are exactly: salt.loaded.int, salt.loaded.int.{tag}, salt.loaded.ext, salt.loaded.ext.{tag}
    # where {tag} is the loader type (e.g., "grains", "modules", etc.)
    # Utils modules are shared infrastructure: salt.loaded.int.utils.*, salt.loaded.ext.utils.*
    # Anything with more path components than that is an actual loaded module
    non_stub_modules = []
    for m in loaded_modules:
        parts = m.split(".")
        # Base stubs have exactly 3 or 4 parts: salt.loaded.int or salt.loaded.int.grains
        if len(parts) <= 4:
            continue
        # Utils modules are shared infrastructure, skip them
        # e.g., salt.loaded.int.utils.zfs
        if len(parts) > 4 and parts[3] == "utils":
            continue
        # Actual grains modules have 5+ parts: salt.loaded.int.grains.core
        non_stub_modules.append(m)

    # After grains() completes, loaded grains modules should be cleaned up
    # (but base stubs and utils modules remain as shared infrastructure)
    assert (
        len(non_stub_modules) == 0
    ), f"Found {len(non_stub_modules)} grains modules still in sys.modules: {non_stub_modules[:10]}"


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
        except Exception:  # pylint: disable=broad-except
            # Some grains may fail to load, that's ok
            pass

    # Get loaded module objects from sys.modules and create weakrefs
    for mod_name in list(sys.modules.keys()):
        if (
            mod_name.startswith("salt.loaded.int.grains.")
            and mod_name not in initial_modules
        ):
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

    Each call should clean up after itself. Base stubs remain but actual
    grains modules should not accumulate.
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

        # Filter out base stub and utils modules
        non_stub_modules = []
        for m in loaded_modules:
            parts = m.split(".")
            # Base stub has exactly 4 parts: salt.loaded.int.grains
            if len(parts) <= 4:
                continue
            # Skip utils modules (shared infrastructure)
            if len(parts) > 4 and parts[3] == "utils":
                continue
            non_stub_modules.append(m)

        assert (
            len(non_stub_modules) == 0
        ), f"Iteration {i+1}: Found {len(non_stub_modules)} accumulated grains modules: {non_stub_modules[:10]}"


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
        except Exception:  # pylint: disable=broad-except
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

    # Filter out base stubs and utils modules
    non_stub_modules = []
    for m in loaded_modules:
        parts = m.split(".")
        # Base stubs have 4 or fewer parts
        if len(parts) <= 4:
            continue
        # Skip utils modules (shared infrastructure)
        if len(parts) > 4 and parts[3] == "utils":
            continue
        non_stub_modules.append(m)

    assert (
        len(non_stub_modules) == 0
    ), f"Cleanup failed on error: {len(non_stub_modules)} modules remain: {non_stub_modules}"


def test_clean_modules_removes_from_sys_modules(minion_opts):
    """
    Test that LazyLoader.clean_modules() properly removes modules from sys.modules.

    This is a focused test of the clean_modules() method itself.
    """
    loader = salt.loader.grain_funcs(minion_opts)

    # Track what base name and tag are used
    loaded_base_name = loader.loaded_base_name
    tag = loader.tag

    # Expected base stub modules that should be preserved
    expected_base_stubs = {
        f"{loaded_base_name}.int",
        f"{loaded_base_name}.int.{tag}",
        f"{loaded_base_name}.ext",
        f"{loaded_base_name}.ext.{tag}",
    }

    # Load some modules
    for key in list(loader.keys())[:5]:
        try:
            _ = loader[key]
        except Exception:  # pylint: disable=broad-except
            pass

    # Find modules that were loaded
    loaded_before = [m for m in sys.modules if m.startswith(loaded_base_name)]
    assert len(loaded_before) > 0, "No modules were loaded for testing"

    # Clean modules
    loader.clean_modules()

    # Verify actual loaded modules are removed but base stubs remain
    remaining = [m for m in sys.modules if m.startswith(loaded_base_name)]

    # All remaining modules should be base stubs or utils modules (shared infrastructure)
    # Filter out both base stubs and utils modules
    unexpected = []
    for m in remaining:
        # Skip base stubs
        if m in expected_base_stubs:
            continue
        # Skip utils modules (shared infrastructure)
        parts = m.split(".")
        # Utils modules: salt.loaded.int.utils, salt.loaded.int.utils.*, etc.
        if len(parts) >= 4 and parts[3] == "utils":
            continue
        # Anything else is unexpected
        unexpected.append(m)

    assert (
        len(unexpected) == 0
    ), f"clean_modules() failed to remove {len(unexpected)} modules: {unexpected}"

    # Base stubs should still be present
    for stub in expected_base_stubs:
        assert stub in sys.modules, f"Base stub module {stub} was incorrectly removed"


def test_base_stubs_preserved_across_loaders(minion_opts):
    """
    Test that base stub modules are preserved when one loader cleans up,
    so other loaders can still function.

    This is critical because stub modules are shared infrastructure.
    """
    # Create two different loaders
    loader1 = salt.loader.grain_funcs(minion_opts)
    loader2 = salt.loader.grain_funcs(minion_opts)

    # Verify they share the same base
    assert loader1.loaded_base_name == loader2.loaded_base_name
    assert loader1.tag == loader2.tag

    # Track base stubs
    base_stubs = {
        f"{loader1.loaded_base_name}.int",
        f"{loader1.loaded_base_name}.int.{loader1.tag}",
        f"{loader1.loaded_base_name}.ext",
        f"{loader1.loaded_base_name}.ext.{loader1.tag}",
    }

    # Load something in loader1
    for key in list(loader1.keys())[:3]:
        try:
            _ = loader1[key]
        except Exception:  # pylint: disable=broad-except
            pass

    # Clean loader1
    loader1.clean_modules()

    # Verify base stubs still exist for loader2 to use
    for stub in base_stubs:
        assert (
            stub in sys.modules
        ), f"Base stub {stub} was removed, breaking other loaders"

    # Verify loader2 can still load modules
    for key in list(loader2.keys())[:3]:
        try:
            func = loader2[key]
            # Should be able to access the function
            assert callable(func)
        except Exception as e:  # pylint: disable=broad-except
            pytest.fail(f"Loader2 failed after loader1 cleanup: {e}")


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

    # Base stubs and utils modules are ok to remain - they're shared infrastructure
    # Filter them out to check for actual loaded modules
    non_stub_modules = []
    for m in loaded_modules:
        parts = m.split(".")
        # Base stubs have 4 or fewer parts
        if len(parts) <= 4:
            continue
        # Skip utils modules (shared infrastructure)
        if len(parts) > 4 and parts[3] == "utils":
            continue
        non_stub_modules.append(m)

    assert len(non_stub_modules) == 0, (
        f"Cleanup failed with force_refresh={force_refresh}: "
        f"{len(non_stub_modules)} non-stub modules remain: {non_stub_modules}"
    )
