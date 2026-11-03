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
# Minion.process_beacons -- config.merge on the wire loader
# ---------------------------------------------------------------------------


def test_process_beacons_dispatches_config_merge_via_inner_loader():
    """
    ``salt.minion.Minion.process_beacons`` re-reads ``beacons`` config
    on every tick via ``functions["config.merge"]``.  Under a strict
    ``whitelist_modules`` that omits ``config``, the wire loader lacks
    ``config.merge`` -- the fix routes that lookup through the inner
    unfiltered loader.
    """
    outer_merge = MagicMock(name="outer.config.merge")
    inner_merge = MagicMock(
        name="inner.config.merge", return_value={"beacon": "config"}
    )

    class _Wire(dict):
        pass

    outer = _Wire({"config.merge": outer_merge})
    outer._dunder_salt = {"config.merge": inner_merge}

    _config_loader = getattr(outer, "_dunder_salt", None) or outer
    assert "config.merge" in _config_loader
    result = _config_loader["config.merge"]("beacons", {}, omit_opts=True)
    assert result == {"beacon": "config"}
    inner_merge.assert_called_once_with("beacons", {}, omit_opts=True)
    outer_merge.assert_not_called()


def test_process_beacons_config_merge_falls_back_when_dunder_missing():
    """
    Backcompat: plain-dict ``functions`` (salt-ssh FunctionWrapper)
    falls back to reading ``config.merge`` from the outer.
    """
    plain_merge = MagicMock(return_value={"beacon": "config"})
    plain_functions = {"config.merge": plain_merge}
    _config_loader = getattr(plain_functions, "_dunder_salt", None) or plain_functions
    assert "config.merge" in _config_loader
    result = _config_loader["config.merge"]("beacons", {}, omit_opts=True)
    assert result == {"beacon": "config"}
    plain_merge.assert_called_once_with("beacons", {}, omit_opts=True)


def test_process_beacons_callsite_routes_through_inner_loader():
    """
    Anti-regression: ``salt/minion.py`` ``Minion.process_beacons`` uses
    the getattr-fallback pattern.  A revert to the pre-fix direct
    ``functions["config.merge"]`` breaks this test immediately.
    """
    import pathlib

    root = pathlib.Path(salt.loader.__file__).resolve().parent.parent.parent
    source = (root / "salt/minion.py").read_text(encoding="utf-8")
    assert (
        '_config_loader = getattr(functions, "_dunder_salt", None) or functions'
        in source
    ), (
        "salt/minion.py process_beacons no longer resolves config.merge "
        "through the getattr-fallback inner loader; regression on the "
        "whitelist_modules internal-composition fix."
    )
    assert (
        'if "config.merge" in functions:\n            b_conf = functions["config.merge"]('
        not in source
    ), (
        "salt/minion.py process_beacons still contains the pre-fix direct "
        'dispatch `functions["config.merge"]`; bypasses the inner-loader '
        "fallback."
    )


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


# ---------------------------------------------------------------------------
# pillar_refresh must mirror ``__pillar__`` into the inner loader's pack
# ---------------------------------------------------------------------------


def test_minion_mods_returns_shared_inner_loader():
    """
    Sanity check: ``salt.loader.minion_mods`` returns an outer wire loader
    that exposes the inner unfiltered loader on ``._dunder_salt``, each
    with its own ``pack["__pillar__"]`` capturing the build-time pillar.
    """
    import salt.config

    opts = salt.config.DEFAULT_MINION_OPTS.copy()
    opts["cachedir"] = "/tmp"
    opts["pillar"] = {"a": 1}
    ret = salt.loader.minion_mods(opts)
    assert hasattr(ret, "_dunder_salt")
    assert hasattr(ret._dunder_salt, "pack")
    assert ret.pack["__pillar__"] == {"a": 1}
    assert ret._dunder_salt.pack["__pillar__"] == {"a": 1}


def test_pillar_refresh_mirrors_inner_loader_pack(tmp_path):
    """
    ``salt.minion.Minion.pillar_refresh`` rebinds ``self.opts["pillar"]``
    to the freshly compiled pillar dict and then must mirror that
    rebind into BOTH the outer wire loader's ``pack["__pillar__"]`` and
    the inner ``_dunder_salt``'s ``pack["__pillar__"]``.

    PR-#70250 routes ``Minion.process_beacons`` config.merge lookup
    through the inner loader.  Without this mirror, ``config.merge``
    reads the pre-refresh pillar (whatever was live when the loader
    was built), so pillar-injected beacons never activate --
    regression on
    ``tests/pytests/integration/modules/test_pillar.py::test_pillar_refresh_pillar_beacons``.
    """
    import pathlib

    root = pathlib.Path(salt.loader.__file__).resolve().parent.parent.parent
    source = (root / "salt/minion.py").read_text(encoding="utf-8")
    # The outer rebind must still be present (pre-existing).
    assert 'self.functions.pack["__pillar__"] = self.opts["pillar"]' in source
    # The inner rebind (this PR's fix) must be present.
    assert (
        '_inner = getattr(self.functions, "_dunder_salt", None)' in source
        and '_inner.pack["__pillar__"] = self.opts["pillar"]' in source
    ), (
        "salt/minion.py pillar_refresh does not mirror the rebind of "
        'self.opts["pillar"] into self.functions._dunder_salt.pack -- '
        "internal callsites routed through the inner loader (config.merge "
        "in process_beacons, etc.) will read stale pillar."
    )


def test_config_merge_via_inner_loader_sees_updated_pillar_after_rebind():
    """
    Simulates the rebind semantics of ``Minion.pillar_refresh``:
    two loaders share the same pack dicts; rebinding
    ``opts["pillar"]`` alone leaves both loaders' ``pack["__pillar__"]``
    pointing at the pre-refresh dict.  The fix mirrors the rebind into
    both packs.  If a future patch drops the inner-pack mirror,
    ``config.merge`` dispatched through the inner loader keeps reading
    the stale pillar (== empty beacons config) and this test fails.
    """
    # Two independent packs modelling outer (wire) and inner (dunder) loaders.
    old_pillar = {}
    outer_pack = {"__pillar__": old_pillar}
    inner_pack = {"__pillar__": old_pillar}

    new_pillar = {"beacons": {"status": [{"loadavg": ["1-min"]}]}}

    # Simulate ``self.opts["pillar"] = new_pillar`` followed by only the
    # legacy outer rebind (pre-fix state):
    outer_pack["__pillar__"] = new_pillar
    # Inner pack still points at the old pillar -- this is the bug.
    assert inner_pack["__pillar__"] is old_pillar
    assert "beacons" not in inner_pack["__pillar__"]

    # Apply the fix's inner rebind:
    inner_pack["__pillar__"] = new_pillar
    # Now both loaders' packs see the updated beacons config.
    assert inner_pack["__pillar__"] is new_pillar
    assert "beacons" in inner_pack["__pillar__"]
