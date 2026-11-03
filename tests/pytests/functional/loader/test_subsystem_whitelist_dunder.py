"""
Functional tests for the two-loader model propagation into the beacons
loader, the engines loader, and the four ``sys.doc`` error-path
lookups (``salt/cli/caller.py``, ``salt/minion.py``,
``salt/metaproxy/proxy.py``, ``salt/metaproxy/deltaproxy.py``).

Companion to
:mod:`tests.pytests.unit.loader.test_subsystem_whitelist_dunder`.

Where the unit tests fabricate the two-loader shape with mocks / plain
dicts, these functional tests wire up real ``salt.loader.minion_mods``,
real ``salt.loader.beacons``, and real ``salt.loader.engines`` on an
opts dict configured with a strict ``whitelist_modules``, and prove
end-to-end that shipped beacons / engines / diagnostic code can still
compose with non-whitelisted execution modules.
"""

import copy
import logging

import pytest

import salt.loader
from tests.support.mock import MagicMock

log = logging.getLogger(__name__)


@pytest.fixture
def whitelist_opts(minion_opts, tmp_path):
    """
    Minion opts with a narrow ``whitelist_modules`` -- everything the
    shipped subsystems compose with internally (``status``, ``config``,
    ``event``, ``pillar``, ``sys``) is deliberately omitted, so the
    fix has to route those through the inner loader for the tests to
    pass.
    """
    opts = copy.deepcopy(minion_opts)
    opts["whitelist_modules"] = ["test", "grains"]
    opts.setdefault("grains", {})
    opts["grains"]["os_family"] = "Linux"
    root_dir = tmp_path / "subsystem-whitelist-functional"
    opts["conf_dir"] = str(root_dir)
    opts["root_dir"] = str(root_dir)
    opts["sock_dir"] = str(root_dir / "test-socks")
    opts["pki_dir"] = str(root_dir / "pki")
    opts["cachedir"] = str(root_dir / "cache")
    return opts


@pytest.fixture
def two_loader_functions(whitelist_opts):
    """
    Real outer wire-filtered loader carrying ``_dunder_salt`` per
    PR #69983.  Asserts the substrate is present so any downstream
    test failure is attributable to the subsystem fix under test, not
    to a missing prerequisite.
    """
    functions = salt.loader.minion_mods(whitelist_opts)
    assert hasattr(functions, "_dunder_salt"), (
        "PR #69983 two-loader model not present on this branch; "
        "subsystem fixes have nothing to hang off of"
    )
    return functions


# ---------------------------------------------------------------------------
# salt.loader.beacons -- two-loader propagation end-to-end
# ---------------------------------------------------------------------------


def test_beacons_loader_packs_unfiltered_salt(whitelist_opts, two_loader_functions):
    """
    Every beacon module's packed ``__salt__`` must be the unfiltered
    inner loader.  Precondition: the wire loader lacks ``status.procs``
    (a helper the shipped ``salt.beacons.status`` / ``salt.beacons.sh``
    modules dispatch through ``__salt__``).  Postcondition: the beacon
    loader's ``__salt__`` pack still has it.
    """
    assert "status.procs" not in two_loader_functions
    beacons = salt.loader.beacons(whitelist_opts, two_loader_functions)
    packed_salt = beacons.pack["__salt__"]
    assert packed_salt is two_loader_functions._dunder_salt
    assert "status.procs" in packed_salt


def test_beacon_module_can_reach_non_whitelisted_exec(
    whitelist_opts, two_loader_functions
):
    """
    Load ``salt.beacons.status`` (a shipped beacon whose ``beacon()``
    dispatches through ``__salt__["status.<func>"]``) and confirm the
    NamedLoaderContext-resolved ``__salt__`` inside its module globals
    reaches the non-whitelisted ``status.procs``.

    We use ``status`` rather than ``sh`` because ``salt.beacons.sh``
    has a ``__virtual__`` gate requiring ``strace`` on PATH -- CI
    images (unlike dev workstations) don't ship strace, so ``sh``
    silently fails to load and the ``__globals__`` lookup below KeyErrors
    on ``sh.beacon``.  ``salt.beacons.status`` has no external
    prereqs (its ``__virtual__`` unconditionally returns the
    virtualname) so it loads on every supported Linux/BSD/Windows
    runner while exercising the same ``__salt__`` dispatch pattern.
    """
    import salt.loader.context

    beacons = salt.loader.beacons(whitelist_opts, two_loader_functions)
    # Force-load the beacon so its module-globals get populated.
    beacons._load_module("status")
    status_globals = beacons._dict["status.beacon"].__globals__
    packed_salt = status_globals["__salt__"]
    token = salt.loader.context.loader_ctxvar.set(beacons)
    try:
        # status.procs is on salt/modules/status.py which is NOT
        # on the whitelist -- but the beacon's __salt__ is the
        # unfiltered dunder, so the lookup succeeds.
        assert "status.procs" in packed_salt
    finally:
        salt.loader.context.loader_ctxvar.reset(token)


def test_beacons_loader_backcompat_with_plain_dict(whitelist_opts):
    """
    Backcompat: when ``functions`` is a plain dict (salt-ssh
    ``FunctionWrapper``), no ``_dunder_salt`` attribute is present and
    the beacon loader falls back to packing ``functions`` as
    ``__salt__``.
    """
    plain = {"test.ping": lambda: True}
    beacons = salt.loader.beacons(whitelist_opts, plain)
    assert beacons.pack["__salt__"] is plain


# ---------------------------------------------------------------------------
# salt.loader.engines -- two-loader propagation end-to-end
# ---------------------------------------------------------------------------


def test_engines_loader_packs_unfiltered_salt(whitelist_opts, two_loader_functions):
    """
    Every engine module's packed ``__salt__`` must be the unfiltered
    inner loader.  Precondition: the wire loader lacks ``event.send``.
    Postcondition: the engine loader's ``__salt__`` pack still has it.
    """
    assert "event.send" not in two_loader_functions
    utils = salt.loader.utils(whitelist_opts)
    engines = salt.loader.engines(
        whitelist_opts, two_loader_functions, runners=[], utils=utils
    )
    packed_salt = engines.pack["__salt__"]
    assert packed_salt is two_loader_functions._dunder_salt
    assert "event.send" in packed_salt


def test_engine_module_can_reach_non_whitelisted_exec(
    whitelist_opts, two_loader_functions
):
    """
    Load ``salt.engines.script`` (a shipped engine that composes with
    ``__salt__["cmd.run_bg"]``) and confirm the NamedLoaderContext-
    resolved ``__salt__`` reaches the non-whitelisted ``cmd.run_bg``.
    """
    import salt.loader.context

    utils = salt.loader.utils(whitelist_opts)
    engines = salt.loader.engines(
        whitelist_opts, two_loader_functions, runners=[], utils=utils
    )
    # Force-load the engine so its module-globals get populated.
    engines._load_module("script")
    script_globals = engines._dict["script.start"].__globals__
    packed_salt = script_globals["__salt__"]
    token = salt.loader.context.loader_ctxvar.set(engines)
    try:
        assert "cmd.run_bg" in packed_salt
    finally:
        salt.loader.context.loader_ctxvar.reset(token)


def test_engines_loader_backcompat_with_plain_dict(whitelist_opts):
    """
    Backcompat: plain-dict ``functions`` falls back to packing itself as
    ``__salt__`` in the engine loader.
    """
    plain = {"test.ping": lambda: True}
    utils = salt.loader.utils(whitelist_opts)
    engines = salt.loader.engines(whitelist_opts, plain, runners=[], utils=utils)
    assert engines.pack["__salt__"] is plain


# ---------------------------------------------------------------------------
# sys.doc error path -- end-to-end lookup through the inner loader
# ---------------------------------------------------------------------------


def test_wire_loader_omits_sys_but_inner_has_it(two_loader_functions):
    """
    Precondition: the narrow whitelist really does strip ``sys.doc``
    from the wire loader.  Sanity check that the inner unfiltered
    loader still ships it -- otherwise the four sys.doc callsites
    have nothing to fall back to.
    """
    assert "sys.doc" not in two_loader_functions
    assert "sys.doc" in two_loader_functions._dunder_salt


def test_sys_doc_error_path_resolves_via_inner_loader(two_loader_functions):
    """
    End-to-end: execute the exact getattr-and-dispatch pattern used by
    all four callsites (``salt/cli/caller.py:135``,
    ``salt/minion.py:3276``, and the two metaproxy files) against a
    real wire loader that has ``_dunder_salt`` set.  The lookup must
    resolve through the inner loader and return a real docs dict,
    proving the "function not found" fallback message won't itself
    crash with ``KeyError`` on ``sys.doc`` under a strict whitelist.
    """
    _sys_loader = (
        getattr(two_loader_functions, "_dunder_salt", None) or two_loader_functions
    )
    docs = _sys_loader["sys.doc"]("test.ping")
    # ``sys.doc`` returns a dict keyed by function name.  test.ping is
    # on the whitelist so it's discoverable via the inner loader too;
    # we don't assert exact keys (SDK loaders can differ across
    # branches), only that the return shape is a mapping.
    assert isinstance(docs, dict)


def test_sys_doc_error_path_falls_back_when_dunder_missing():
    """
    Backcompat: with a plain-dict ``functions`` (no ``_dunder_salt``),
    the pattern falls back to the outer loader -- salt-ssh
    ``FunctionWrapper`` / plain-dict test callers keep working.
    """
    plain_sys_doc = MagicMock(return_value={"foo.bar": "docs"})
    plain_functions = {"sys.doc": plain_sys_doc}
    _sys_loader = getattr(plain_functions, "_dunder_salt", None) or plain_functions
    docs = _sys_loader["sys.doc"]("foo.bar*")
    assert docs == {"foo.bar": "docs"}
    plain_sys_doc.assert_called_once_with("foo.bar*")
