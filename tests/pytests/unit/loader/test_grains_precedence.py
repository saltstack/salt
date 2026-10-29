"""
Precedence tests for salt.loader.grains(): custom (ext) grain modules must
override built-in (int) grain modules of the same name, matching the documented
precedence (issue #54694).
"""

import salt.loader
from tests.support.mock import patch


def _grain(retval, module):
    """Build a grain function whose namespaced ``__module__`` marks it int/ext."""

    def _func(**kwargs):
        return retval

    _func.__module__ = module
    return _func


class _StubGrainLoader:
    """Minimal stand-in for the grain_funcs LazyLoader."""

    loaded_base_name = "salt.loaded"

    def __init__(self, funcs, order):
        self._funcs = funcs
        self._order = order

    def __iter__(self):
        return iter(self._order)

    def __getitem__(self, key):
        return self._funcs[key]

    def clear(self):
        pass

    def clean_modules(self):
        pass


def _run_grains(stub, tmp_path):
    opts = {"cachedir": str(tmp_path), "grains_cache": False}
    with patch("salt.loader.grain_funcs", return_value=stub):
        return salt.loader.grains(opts)


def test_custom_grain_overrides_builtin(tmp_path):
    # A built-in (int) grain and a custom (ext) grain both emit "interfaces".
    # The loader iterates the custom one first, so before the fix the built-in
    # ran last and won; the custom value must win regardless of order (#54694).
    builtin = _grain({"interfaces": ["Loopback"]}, "salt.loaded.int.grains.napalm")
    custom = _grain({"interfaces": "from_custom_grain"}, "salt.loaded.ext.grains.issue")
    stub = _StubGrainLoader(
        {"napalm.interfaces": builtin, "issue.interfaces": custom},
        order=["issue.interfaces", "napalm.interfaces"],
    )
    result = _run_grains(stub, tmp_path)
    assert result["interfaces"] == "from_custom_grain"


def test_builtin_relative_order_preserved(tmp_path):
    # Two built-in grains colliding: the later-iterated one still wins, i.e. the
    # partition must not reorder within the built-in group.
    first = _grain({"role": "first"}, "salt.loaded.int.grains.a")
    second = _grain({"role": "second"}, "salt.loaded.int.grains.b")
    stub = _StubGrainLoader(
        {"a.role": first, "b.role": second}, order=["a.role", "b.role"]
    )
    result = _run_grains(stub, tmp_path)
    assert result["role"] == "second"


def test_custom_relative_order_preserved(tmp_path):
    # Two custom grains colliding: later-iterated still wins (order preserved
    # within the custom group).
    first = _grain({"site": "first"}, "salt.loaded.ext.grains.a")
    second = _grain({"site": "second"}, "salt.loaded.ext.grains.b")
    stub = _StubGrainLoader(
        {"a.site": first, "b.site": second}, order=["a.site", "b.site"]
    )
    result = _run_grains(stub, tmp_path)
    assert result["site"] == "second"


def test_noncolliding_builtin_and_custom_both_present(tmp_path):
    # Non-colliding grains from both origins are all present.
    builtin = _grain({"kernel": "Linux"}, "salt.loaded.int.grains.kernelinfo")
    custom = _grain({"datacenter": "dc1"}, "salt.loaded.ext.grains.location")
    stub = _StubGrainLoader(
        {"kernelinfo.kernel": builtin, "location.datacenter": custom},
        order=["location.datacenter", "kernelinfo.kernel"],
    )
    result = _run_grains(stub, tmp_path)
    assert result["kernel"] == "Linux"
    assert result["datacenter"] == "dc1"


def test_core_grain_overridable_by_custom(tmp_path):
    # core.* grains run first; a custom grain of the same name overrides them.
    core = _grain({"osrelease": "9.9"}, "salt.loaded.int.grains.core")
    custom = _grain({"osrelease": "custom"}, "salt.loaded.ext.grains.override")
    stub = _StubGrainLoader(
        {"core.osrelease": core, "override.osrelease": custom},
        order=["core.osrelease", "override.osrelease"],
    )
    result = _run_grains(stub, tmp_path)
    assert result["osrelease"] == "custom"
