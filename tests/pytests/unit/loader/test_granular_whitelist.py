"""
Unit tests for the function-level (``module.func``) syntax in
``whitelist_modules`` / ``whitelist_state_modules``.

The classic coarse-grained syntax -- bare module names -- is preserved.
Operators may additionally pin a specific function:

    whitelist_modules:
      - test               # whole module allowed
      - cmd.run            # only cmd.run; cmd.shell / cmd.retcode / ... blocked

Enforcement lives in :class:`salt.loader.lazy.LazyLoader` and therefore
applies identically to every loader subsystem that uses it (execution
modules, state modules, ...).
"""

import pytest

import salt.loader
import salt.loader.lazy
from salt.loader.lazy import LazyLoader, _parse_whitelist

# --------------------------------------------------------------------------- #
# _parse_whitelist
# --------------------------------------------------------------------------- #


def test_parse_whitelist_none_for_empty():
    assert _parse_whitelist(None) is None
    assert _parse_whitelist([]) is None


def test_parse_whitelist_bare_entry_is_none_value():
    """
    Bare module name -> ``None`` -- the "all functions allowed" marker.
    """
    parsed = _parse_whitelist(["test"])
    assert parsed == {"test": None}


def test_parse_whitelist_dotted_entry_is_frozenset():
    """
    ``module.func`` -> frozenset of allowed function names.
    """
    parsed = _parse_whitelist(["cmd.run"])
    assert parsed == {"cmd": frozenset({"run"})}


def test_parse_whitelist_multiple_dotted_entries_merge():
    """
    Multiple ``module.func`` entries for the same module collapse to a
    single frozenset -- order-independent.
    """
    parsed = _parse_whitelist(["cmd.run", "cmd.retcode"])
    assert parsed == {"cmd": frozenset({"run", "retcode"})}


def test_parse_whitelist_dotted_wins_over_bare():
    """
    Mixing ``[cmd, cmd.run]`` or ``[cmd.run, cmd]`` narrows to just the
    dotted entries -- the stricter rule wins, so an operator who adds
    a ``module.func`` tightening doesn't have to also remove any
    existing bare ``module`` entry.
    """
    assert _parse_whitelist(["cmd", "cmd.run"]) == {"cmd": frozenset({"run"})}
    assert _parse_whitelist(["cmd.run", "cmd"]) == {"cmd": frozenset({"run"})}
    # Bare + multiple dotted entries -> all listed functions, no more.
    assert _parse_whitelist(["cmd", "cmd.run", "cmd.retcode"]) == {
        "cmd": frozenset({"run", "retcode"})
    }


def test_parse_whitelist_distinct_modules_kept_separate():
    parsed = _parse_whitelist(["test", "cmd.run", "file"])
    assert parsed == {
        "test": None,
        "cmd": frozenset({"run"}),
        "file": None,
    }


# --------------------------------------------------------------------------- #
# LazyLoader._whitelist_allows_* helpers
# --------------------------------------------------------------------------- #


def _loader(whitelist):
    """
    Build a minimal LazyLoader; we only need the whitelist-related
    state for these tests so no module_dirs are required.
    """
    return LazyLoader([], opts={}, whitelist=whitelist)


def test_module_gate_no_whitelist_allows_everything():
    loader = _loader(None)
    assert loader._whitelist_allows_module("cmd") is True
    assert loader._whitelist_allows_key("cmd.run") is True


def test_module_gate_bare_entry_allows_any_func():
    loader = _loader(["cmd"])
    assert loader._whitelist_allows_module("cmd") is True
    assert loader._whitelist_allows_key("cmd.run") is True
    assert loader._whitelist_allows_key("cmd.anything") is True
    assert loader._whitelist_allows_module("pkg") is False
    assert loader._whitelist_allows_key("pkg.install") is False


def test_module_gate_dotted_entry_is_function_scoped():
    """
    A ``module.func`` entry implies the module may load (so the gated
    function can be served) but only that one function is reachable.
    """
    loader = _loader(["cmd.run"])
    assert loader._whitelist_allows_module("cmd") is True
    assert loader._whitelist_allows_key("cmd.run") is True
    assert loader._whitelist_allows_key("cmd.retcode") is False


def test_module_gate_dotted_narrows_bare():
    """
    Mixing a bare module entry with a dotted entry -- the dotted entry
    narrows the bare one so only the listed function is reachable.
    """
    loader = _loader(["cmd", "cmd.run"])
    assert loader._whitelist_allows_module("cmd") is True
    assert loader._whitelist_allows_key("cmd.run") is True
    assert loader._whitelist_allows_key("cmd.retcode") is False


def test_whitelist_allows_key_rejects_undotted():
    loader = _loader(["cmd"])
    assert loader._whitelist_allows_key("cmd") is False


# --------------------------------------------------------------------------- #
# End-to-end via a filesystem-backed loader
# --------------------------------------------------------------------------- #


@pytest.fixture
def loader_dir(tmp_path):
    """
    Two-function module so we can test "allow func1, block func2".
    """
    mod_contents = """
        def __virtual__():
            return True

        def func1():
            return "func1"

        def func2():
            return "func2"
    """
    with pytest.helpers.temp_file(
        "mod_a.py", directory=tmp_path, contents=mod_contents
    ), pytest.helpers.temp_file("mod_b.py", directory=tmp_path, contents=mod_contents):
        yield str(tmp_path)


def test_dotted_whitelist_blocks_sibling_function_via_getitem(loader_dir):
    """
    ``whitelist=["mod_a.func1"]`` -- ``mod_a.func1`` is callable,
    ``mod_a.func2`` raises ``KeyError`` even though it exists in the
    module file.
    """
    loader = LazyLoader(
        [loader_dir], opts={"optimization_order": [0]}, whitelist=["mod_a.func1"]
    )
    assert loader["mod_a.func1"]() == "func1"
    with pytest.raises(KeyError):
        loader["mod_a.func2"]()


def test_dotted_whitelist_blocks_sibling_after_module_loaded(loader_dir):
    """
    Loading ``mod_a.func1`` populates ``mod_a.func2`` into ``_dict``
    too (LazyLoader loads the whole module on first access).  The
    function-level gate must still reject ``mod_a.func2`` on the second
    lookup -- i.e. the check cannot live only in ``_load`` since
    LazyDict.__getitem__ skips ``_load`` once the key is cached.
    """
    loader = LazyLoader(
        [loader_dir], opts={"optimization_order": [0]}, whitelist=["mod_a.func1"]
    )
    # Trigger module load.
    assert loader["mod_a.func1"]() == "func1"
    # mod_a.func2 is in _dict now; the gate must still reject it.
    assert "mod_a.func2" in loader._dict
    with pytest.raises(KeyError):
        loader["mod_a.func2"]()


def test_dotted_whitelist_blocks_other_modules(loader_dir):
    """
    ``whitelist=["mod_a.func1"]`` -- unrelated module ``mod_b`` must
    still be blocked at module granularity.
    """
    loader = LazyLoader(
        [loader_dir], opts={"optimization_order": [0]}, whitelist=["mod_a.func1"]
    )
    with pytest.raises(KeyError):
        loader["mod_b.func1"]()


def test_bare_plus_dotted_narrows_in_loader(loader_dir):
    """
    End-to-end check that ``[mod_a, mod_a.func1]`` narrows to ``func1``
    only -- verifies the dotted-wins rule travels through the real
    ``__getitem__`` gate, not just the normalized map.
    """
    loader = LazyLoader(
        [loader_dir],
        opts={"optimization_order": [0]},
        whitelist=["mod_a", "mod_a.func1"],
    )
    assert loader["mod_a.func1"]() == "func1"
    with pytest.raises(KeyError):
        loader["mod_a.func2"]()


def test_bare_whitelist_still_allows_any_function(loader_dir):
    """
    Backward compat: ``whitelist=["mod_a"]`` behaves as before -- every
    function of ``mod_a`` is reachable.
    """
    loader = LazyLoader(
        [loader_dir], opts={"optimization_order": [0]}, whitelist=["mod_a"]
    )
    assert loader["mod_a.func1"]() == "func1"
    assert loader["mod_a.func2"]() == "func2"


def test_jinja_attr_access_honors_function_gate(loader_dir):
    """
    Jinja's ``salt.mod_a.func1(...)`` syntax resolves via
    ``LoadedMod.__getattr__`` which routes through
    ``loader["mod_a.func1"]``, so the function-level gate must apply.
    """
    loader = LazyLoader(
        [loader_dir], opts={"optimization_order": [0]}, whitelist=["mod_a.func1"]
    )
    mod = loader.mod_a
    assert isinstance(mod, salt.loader.lazy.LoadedMod)
    assert mod.func1() == "func1"
    with pytest.raises(AttributeError):
        getattr(mod, "func2")


def test_jinja_attr_access_rejects_blocked_module(loader_dir):
    """
    Blocked module -> ``AttributeError`` on attribute-style access, so
    ``hasattr(salt, 'mod_b')`` / Jinja's ``undefined`` fallthrough
    behave correctly.
    """
    loader = LazyLoader(
        [loader_dir], opts={"optimization_order": [0]}, whitelist=["mod_a.func1"]
    )
    with pytest.raises(AttributeError):
        getattr(loader, "mod_b")


# --------------------------------------------------------------------------- #
# whitelist_state_modules shares the same semantics
# --------------------------------------------------------------------------- #


def test_state_whitelist_accepts_dotted_entries(minion_opts):
    """
    ``whitelist_state_modules`` is forwarded into the same
    ``LazyLoader`` wiring as ``whitelist_modules``, so function-level
    entries work identically for state modules.
    """
    minion_mods = salt.loader.minion_mods(minion_opts)
    utils = salt.loader.utils(minion_opts)
    serializers = salt.loader.serializers(minion_opts)
    opts = minion_opts.copy()
    opts["whitelist_state_modules"] = ["file.managed", "test"]
    loader = salt.loader.states(opts, minion_mods, utils, serializers)
    # Original list preserved on the loader for introspection.
    assert loader.whitelist == ["file.managed", "test"]
    # Normalized map reflects the granular shape.
    assert loader._whitelist_funcs == {
        "file": frozenset({"managed"}),
        "test": None,
    }
    # Helper gates agree.
    assert loader._whitelist_allows_key("file.managed") is True
    assert loader._whitelist_allows_key("file.absent") is False
    assert loader._whitelist_allows_key("test.succeed_without_changes") is True
