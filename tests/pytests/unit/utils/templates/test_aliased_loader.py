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


def test_attr_style_with_funcwrapper_like_wrapped():
    """
    Regression: when the wrapped loader synthesises a module lookup for
    every attribute access (as salt-ssh's ``FunctionWrapper`` does via
    :class:`salt.client.ssh.wrapper.LoadedMod`), ``getattr(wrapped,
    "whitelist", None)`` returns a proxy object rather than ``None`` or a
    list.  The whitelist gate in :meth:`AliasedLoader.__getattr__` must
    treat that non-container value as "no whitelist" and fall through to
    the wrapper -- attempting ``name in <proxy>`` used to raise
    ``TypeError`` (``argument of type 'LoadedMod' is not a container or
    iterable``) and blow up
    ``funcwrapper_attr_exewrap_test`` / ``{{ salt.exewrap.run() }}``
    style Jinja templates on salt-ssh.
    """

    class _LoadedModSentinel:
        # Deliberately no ``__contains__`` and no ``__iter__`` - matches
        # ``salt.client.ssh.wrapper.LoadedMod``.
        __slots__ = ("mod",)

        def __init__(self, mod):
            self.mod = mod

        def __repr__(self):
            return f"<_LoadedModSentinel mod={self.mod!r}>"

    class _FunctionWrapperLike:
        """
        Minimal stand-in for salt-ssh's ``FunctionWrapper``: every
        non-dunder attribute name resolves to a ``_LoadedModSentinel``,
        including ``whitelist``.
        """

        def __getattr__(self, name):
            if name.startswith("__") and name.endswith("__"):
                raise AttributeError(name)
            return _LoadedModSentinel(name)

    wrapped = _FunctionWrapperLike()
    # Precondition: the buggy pre-fix code path we're guarding against.
    assert isinstance(getattr(wrapped, "whitelist", None), _LoadedModSentinel)

    al = AliasedLoader(wrapped)

    # The critical assertion: attribute-style access must not raise
    # TypeError.  Under the fix, it returns the underlying proxy
    # (which the caller then uses as a module namespace).
    try:
        result = al.exewrap
    except TypeError as exc:  # pragma: no cover - guarded by the fix
        pytest.fail(
            f"AliasedLoader.__getattr__ raised TypeError on a FunctionWrapper-like "
            f"wrapped loader: {exc}"
        )
    assert isinstance(result, _LoadedModSentinel)
    assert result.mod == "exewrap"
