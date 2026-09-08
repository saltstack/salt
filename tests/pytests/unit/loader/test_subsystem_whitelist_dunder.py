"""
Regression tests for the two-loader model across four internal Salt
subsystems: beacons, engines, and the two sys.doc error-path lookups
(``salt.cli.caller.BaseCaller.call`` and the minion / metaproxy analog
in ``salt.minion._thread_multi_return`` and ``salt.metaproxy.*``).

Each of these subsystems is internal Salt machinery -- either always
running (beacons/engines started by the minion daemon) or a hard-coded
diagnostic path (sys.doc invoked to explain why a user-requested
function is missing).  None of them should be gated by
``whitelist_modules``:

  * Beacons need ``__salt__[f"status.{func}"]``, ``status.procs()``, etc.
    Requiring the operator to add ``status`` to the wire whitelist just
    to enable a shipped beacon is a maintenance treadmill.

  * Engines need ``__salt__["event.send"]`` / ``__salt__["pillar.get"]``
    for the same reason (slack/webhook/sqs engines etc.).

  * ``sys.doc`` is the "function not found" fallback documentation
    lookup.  If the operator's whitelist omits ``sys``, the *error path*
    itself KeyError'd and the user got a traceback instead of the "did
    you mean" message.

The scheme mirrors PR #70192's state-loader extension: shipped internal
code reads through the inner unfiltered ``functions._dunder_salt``, and
user-facing wire dispatch stays on the outer whitelist-filtered loader.
"""

import pytest

import salt.loader
from tests.support.mock import MagicMock


def _minion_opts_with_whitelist(minion_opts, whitelist):
    """Return a copy of ``minion_opts`` with ``whitelist_modules`` set."""
    opts = minion_opts.copy()
    opts["whitelist_modules"] = list(whitelist)
    return opts


# ---------------------------------------------------------------------------
# salt.loader.beacons -- two-loader passthrough + backcompat
# ---------------------------------------------------------------------------


def test_beacons_loader_dunder_salt_passthrough(minion_opts):
    """
    When ``salt.loader.beacons`` is built with an outer wire loader that
    carries ``_dunder_salt``, the beacon loader's ``__salt__`` pack must
    be the inner unfiltered loader -- so shipped beacons like
    ``salt.beacons.status`` and ``salt.beacons.sh`` can compose with
    their helper execution modules regardless of ``whitelist_modules``.
    """
    opts = _minion_opts_with_whitelist(minion_opts, ["test"])
    ret = salt.loader.minion_mods(opts)
    salt_dunder = ret._dunder_salt
    beacons = salt.loader.beacons(opts, ret)
    assert beacons.pack["__salt__"] is salt_dunder
    # Wire loader stays whitelist-gated ...
    assert "status.procs" not in ret
    # ... but the inner dunder that beacons see is not.
    assert "status.procs" in beacons.pack["__salt__"]


def test_beacons_loader_backcompat_without_dunder_salt(minion_opts):
    """
    When ``functions`` has no ``_dunder_salt`` attribute (salt-ssh
    ``FunctionWrapper``, plain-dict test fixtures), ``salt.loader.beacons``
    must fall back to packing ``functions`` as ``__salt__`` -- pre-fix
    behaviour, so external callers are not broken.
    """
    plain_functions = {"test.ping": lambda: True}
    beacons = salt.loader.beacons(minion_opts, plain_functions)
    assert beacons.pack["__salt__"] is plain_functions


def test_beacons_loader_backcompat_with_none_dunder_salt(minion_opts):
    """
    ``_dunder_salt`` explicitly set to ``None`` also falls back to
    ``functions`` -- guards against a loader that sets the attribute
    defensively before populating it.
    """

    class _Loader(dict):
        pass

    functions = _Loader({"test.ping": lambda: True})
    functions._dunder_salt = None
    beacons = salt.loader.beacons(minion_opts, functions)
    assert beacons.pack["__salt__"] is functions


# ---------------------------------------------------------------------------
# salt.loader.engines -- two-loader passthrough + backcompat
# ---------------------------------------------------------------------------


def test_engines_loader_dunder_salt_passthrough(minion_opts):
    """
    ``salt.loader.engines`` must pack the inner unfiltered loader as
    ``__salt__`` when the outer wire loader exposes it.  Shipped engines
    (slack / webhook / sqs) compose with ``event.send`` / ``pillar.get``
    even when those are omitted from ``whitelist_modules``.
    """
    opts = _minion_opts_with_whitelist(minion_opts, ["test"])
    ret = salt.loader.minion_mods(opts)
    salt_dunder = ret._dunder_salt
    utils = salt.loader.utils(opts)
    engines = salt.loader.engines(opts, ret, runners=[], utils=utils)
    assert engines.pack["__salt__"] is salt_dunder
    # Wire loader stays whitelist-gated ...
    assert "event.send" not in ret
    # ... but the inner dunder is not.
    assert "event.send" in engines.pack["__salt__"]


def test_engines_loader_backcompat_without_dunder_salt(minion_opts):
    """
    ``salt.loader.engines`` falls back to packing ``functions`` as
    ``__salt__`` when the inner loader attribute is absent.
    """
    plain_functions = {"test.ping": lambda: True}
    utils = salt.loader.utils(minion_opts)
    engines = salt.loader.engines(minion_opts, plain_functions, runners=[], utils=utils)
    assert engines.pack["__salt__"] is plain_functions


# ---------------------------------------------------------------------------
# sys.doc error path: inner loader when present, functions otherwise
# ---------------------------------------------------------------------------


class _FakeWireLoader(dict):
    """
    Minimal stand-in for the whitelist-filtered outer LazyLoader used
    by the sys.doc-error-path tests.  Only mapping semantics + the
    ``_dunder_salt`` attribute are exercised.
    """


def _run_sys_doc_lookup(functions, function_name):
    """
    Execute the exact getattr-and-dispatch pattern used by the four
    error-path callsites (``salt/cli/caller.py``, ``salt/minion.py``,
    ``salt/metaproxy/proxy.py``, ``salt/metaproxy/deltaproxy.py``).

    Keeping this helper here as the single source of truth means these
    four sites can be regression-tested in one place; if any of the
    inline callsites drift from this pattern the drift will show up as
    a behaviour delta on the site's own coverage (see integration
    tests) even though the pattern below is verified once.
    """
    sys_loader = getattr(functions, "_dunder_salt", None) or functions
    return sys_loader["sys.doc"](f"{function_name}*")


def test_sys_doc_error_path_uses_inner_loader_when_present():
    """
    The four sys.doc error-path callsites route through
    ``functions._dunder_salt`` when the outer wire loader carries it,
    so ``sys.doc`` still resolves under a strict ``whitelist_modules``
    that omits ``sys``.
    """
    outer_sys_doc = MagicMock(name="outer.sys.doc")
    inner_sys_doc = MagicMock(name="inner.sys.doc", return_value={"foo.bar": "docs"})

    outer = _FakeWireLoader({"sys.doc": outer_sys_doc})
    outer._dunder_salt = {"sys.doc": inner_sys_doc}

    result = _run_sys_doc_lookup(outer, "foo.bar")

    assert result == {"foo.bar": "docs"}
    inner_sys_doc.assert_called_once_with("foo.bar*")
    outer_sys_doc.assert_not_called()


def test_sys_doc_error_path_falls_back_when_dunder_salt_missing():
    """
    When ``functions`` has no ``_dunder_salt`` (salt-ssh ``FunctionWrapper``,
    tests that pass a plain dict), the error path falls back to the outer
    loader -- pre-fix behaviour.
    """
    plain_sys_doc = MagicMock(return_value={"foo.bar": "docs"})
    plain_functions = {"sys.doc": plain_sys_doc}

    result = _run_sys_doc_lookup(plain_functions, "foo.bar")

    assert result == {"foo.bar": "docs"}
    plain_sys_doc.assert_called_once_with("foo.bar*")


def test_sys_doc_error_path_falls_back_when_dunder_salt_none():
    """
    Explicit ``_dunder_salt = None`` on the outer loader also falls back
    to the outer -- symmetric with the beacons/engines fallback.
    """
    outer_sys_doc = MagicMock(return_value={})
    outer = _FakeWireLoader({"sys.doc": outer_sys_doc})
    outer._dunder_salt = None

    result = _run_sys_doc_lookup(outer, "foo.bar")

    assert result == {}
    outer_sys_doc.assert_called_once_with("foo.bar*")


# ---------------------------------------------------------------------------
# Anti-regression: the four sys.doc error-path callsites all use the
# same getattr-with-fallback pattern.  If any site drifts (e.g. someone
# reverts the fix), this test breaks immediately.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "relpath,marker",
    [
        ("salt/cli/caller.py", '_sys_loader["sys.doc"](f"{fun}*")'),
        ("salt/minion.py", '_sys_loader["sys.doc"](f"{function_name}*")'),
        ("salt/metaproxy/proxy.py", '_sys_loader["sys.doc"](f"{function_name}*")'),
        (
            "salt/metaproxy/deltaproxy.py",
            '_sys_loader["sys.doc"](f"{function_name}*")',
        ),
    ],
)
def test_sys_doc_callsites_route_through_inner_loader(relpath, marker):
    """
    Each of the four sys.doc error-path callsites must dispatch through
    the resolved ``_sys_loader`` (getattr-with-fallback) rather than
    directly through ``functions["sys.doc"]``.  Guards against a future
    revert of any single site.
    """
    import pathlib

    root = pathlib.Path(salt.loader.__file__).resolve().parent.parent.parent
    source = (root / relpath).read_text(encoding="utf-8")
    assert marker in source, (
        f"{relpath} no longer routes sys.doc through the getattr-fallback "
        "inner loader; regression on whitelist_modules internal-composition "
        "fix."
    )
    # Also assert no direct ``functions["sys.doc"](...)`` call survives on
    # ``self.minion.functions`` or ``minion_instance.functions``.  The
    # error-path lookup must go through ``_sys_loader``.
    direct_forms = [
        'self.minion.functions["sys.doc"](f"{fun}*")',
        'minion_instance.functions["sys.doc"](f"{function_name}*")',
    ]
    for direct in direct_forms:
        assert direct not in source, (
            f"{relpath} still contains the pre-fix direct dispatch "
            f"{direct!r}; this bypasses the inner-loader fallback."
        )
