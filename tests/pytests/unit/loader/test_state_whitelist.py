"""
Unit tests for the ``whitelist_state_modules`` minion option.

``salt.loader.states`` gains a state-loader counterpart to
``whitelist_modules`` (which gates execution modules).  When set on the
minion opts it is passed through to the underlying :class:`LazyLoader`
as ``whitelist``, so state modules whose name is not on the list are not
loadable and an SLS that references them fails compile with
``State '<mod>.<fun>' was not found in SLS ...``.
"""

import pytest

import salt.loader


@pytest.fixture
def _wired_deps(minion_opts):
    """
    Materialise the LazyLoaders that ``states()`` needs.  ``functions``
    is a real ``minion_mods()`` result; ``utils`` / ``serializers`` are
    plain factory outputs.
    """
    minion_mods = salt.loader.minion_mods(minion_opts)
    utils = salt.loader.utils(minion_opts)
    serializers = salt.loader.serializers(minion_opts)
    return minion_mods, utils, serializers


def test_opt_flows_to_lazyloader_whitelist(minion_opts, _wired_deps):
    """
    When ``whitelist_state_modules`` is set in opts and ``whitelist`` is
    not passed explicitly, ``states()`` forwards the opt value to the
    LazyLoader as ``self.whitelist``.
    """
    minion_mods, utils, serializers = _wired_deps
    opts = minion_opts.copy()
    opts["whitelist_state_modules"] = ["test", "file"]
    loader = salt.loader.states(opts, minion_mods, utils, serializers)
    assert loader.whitelist == ["test", "file"]


def test_explicit_kwarg_wins_over_opt(minion_opts, _wired_deps):
    """
    An explicit ``whitelist=`` kwarg must override the opt (mirroring
    ``salt.loader.minion_mods`` behaviour so callers can pin the loader
    scope independently of minion config).
    """
    minion_mods, utils, serializers = _wired_deps
    opts = minion_opts.copy()
    opts["whitelist_state_modules"] = ["test"]
    loader = salt.loader.states(
        opts, minion_mods, utils, serializers, whitelist=["file", "pkg"]
    )
    assert loader.whitelist == ["file", "pkg"]


def test_unset_opt_means_no_filtering(minion_opts, _wired_deps):
    """
    ``whitelist_state_modules`` unset -- or set to the falsy default
    ``[]`` from ``DEFAULT_MINION_OPTS`` -- results in a LazyLoader whose
    whitelist is falsy, i.e. no filtering (``LazyLoader._load`` checks
    ``if self.whitelist and mod_name not in self.whitelist``).
    """
    minion_mods, utils, serializers = _wired_deps
    opts = minion_opts.copy()
    opts.pop("whitelist_state_modules", None)
    loader = salt.loader.states(opts, minion_mods, utils, serializers)
    assert not loader.whitelist

    # Explicit empty list -- same semantics.
    opts["whitelist_state_modules"] = []
    loader = salt.loader.states(opts, minion_mods, utils, serializers)
    assert not loader.whitelist


def test_whitelist_modules_is_orthogonal(minion_opts, _wired_deps):
    """
    Setting the *execution*-loader whitelist must not affect the state
    loader's whitelist -- the two options are independent gates.
    """
    minion_mods, utils, serializers = _wired_deps
    opts = minion_opts.copy()
    opts["whitelist_modules"] = ["test"]
    # Only ``whitelist_state_modules`` gates the state loader.
    loader = salt.loader.states(opts, minion_mods, utils, serializers)
    assert not loader.whitelist
    opts["whitelist_state_modules"] = ["file"]
    loader = salt.loader.states(opts, minion_mods, utils, serializers)
    assert loader.whitelist == ["file"]
