"""
tests.pytests.unit.utils.templates.test_aliased_loader
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

VCOPS-90587: attribute-style access on the Jinja ``salt`` binding
(``{{ salt.cmd.run('...') }}``) must be gated by ``whitelist_modules``
just like dict-style access (``{{ salt['cmd.run']('...') }}``).
"""

import pytest

import salt.config
import salt.loader
from salt.utils.templates import AliasedLoader


@pytest.fixture
def whitelisted_minion_mods(minion_opts):
    """Build a real ``minion_mods`` loader with ``whitelist_modules`` set."""
    opts = minion_opts.copy()
    opts["whitelist_modules"] = ["test", "grains"]
    return salt.loader.minion_mods(opts), opts


def test_dict_style_whitelisted_still_works(whitelisted_minion_mods):
    """Sanity: ``salt['test.ping']`` must resolve for whitelisted modules."""
    mods, _ = whitelisted_minion_mods
    al = AliasedLoader(mods)
    assert callable(al["test.ping"])


def test_dict_style_non_whitelisted_raises(whitelisted_minion_mods):
    """Non-whitelisted dict-style access must KeyError (existing gate)."""
    mods, _ = whitelisted_minion_mods
    al = AliasedLoader(mods)
    with pytest.raises(KeyError):
        _unused = al["cmd.run"]


def test_attr_style_whitelisted_still_works(whitelisted_minion_mods):
    """``salt.grains`` for a whitelisted module returns a LoadedMod proxy."""
    mods, _ = whitelisted_minion_mods
    al = AliasedLoader(mods)
    grains_mod = al.grains
    # LoadedMod proxy: has a `.get` function attribute
    assert callable(grains_mod.get)


def test_attr_style_non_whitelisted_raises_attribute_error(
    whitelisted_minion_mods,
):
    """
    ``salt.cmd`` for a non-whitelisted module must raise ``AttributeError``,
    not silently return a LoadedMod that would then let ``salt.cmd.run(...)``
    escape the wire filter.  This closes the pre-existing Jinja escape hatch
    on attribute-style access.
    """
    mods, _ = whitelisted_minion_mods
    al = AliasedLoader(mods)
    with pytest.raises(AttributeError):
        _unused = al.cmd
    # ``hasattr`` contract: must return False for blocked modules so
    # Jinja's ``undefined`` fallthrough behaves.
    assert not hasattr(al, "cmd")
    assert hasattr(al, "test")


def test_lazyloader_attr_gate_direct(whitelisted_minion_mods):
    """
    ``LazyLoader.__getattr__`` itself must reject non-whitelisted names -
    the AliasedLoader is only one consumer; anything using the loader
    directly (e.g. pyobjects, sdb renderers) benefits from the same gate.
    """
    mods, _ = whitelisted_minion_mods
    with pytest.raises(AttributeError):
        _unused = mods.cmd
    assert not hasattr(mods, "cmd")
    # And a whitelisted one still resolves.
    assert hasattr(mods, "test")


def test_no_whitelist_no_gate(minion_opts):
    """
    When ``whitelist_modules`` isn't set, attribute-style access still works
    for every discoverable module - no regression for the un-hardened case.
    """
    opts = minion_opts.copy()
    opts.pop("whitelist_modules", None)
    mods = salt.loader.minion_mods(opts)
    al = AliasedLoader(mods)
    # Both should resolve (cmd is discoverable on all platforms Salt ships).
    assert hasattr(al, "test")
    assert hasattr(al, "cmd")
