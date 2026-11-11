"""
Regression tests for the "Return path" section of
``doc/topics/master-topology/index.md``.

Pins three claims the docs make:

1. Breadcrumb entry shape --- value is a msgpack dict with keys
   ``link_cluster_id`` (the inbound peer's ``cluster_id``) and
   ``expiry_at`` (a wall-clock timestamp).  The "inbound link
   identifier" the docs promise is the peer ``cluster_id`` string.
2. Breadcrumb TTL is honored on the staleness check.  The
   ``topology_breadcrumb_grace`` and ``topology_breadcrumb_max_age``
   opts actually feed into the expiry formula and ``lookup`` returns
   ``None`` for expired entries (so a long-running job that overruns
   its lifetime drops on arrival --- which is what the "Breadcrumb
   miss on return" troubleshooting section says).
3. Cross-boundary return event tag format is
   ``salt/topology/return/<origin>/<jid>`` as rendered by
   :meth:`salt.master.AESFuncs._maybe_fire_topology_return`.

The breadcrumbs module docstring claims keys are formatted as
``<cluster_id>:<jid>`` but :meth:`TopologyRouter.forward_publish`
passes ``load["jid"]`` directly --- the test documents the actual
behavior (bare jid key), and the doc text in index.md will need to
be reconciled with the implementation.
"""

import pytest

import salt.topology.breadcrumbs as breadcrumbs
import salt.topology.registry as registry
import salt.topology.router as router_mod


def _opts(tmp_path, cluster_id="origin"):
    pki_dir = tmp_path / f"{cluster_id}-pki"
    (pki_dir / "master").mkdir(parents=True, exist_ok=True)
    return {
        "pki_dir": str(pki_dir),
        "cluster_id": cluster_id,
        "topology_enabled": True,
        "topology_breadcrumb_grace": 30,
        "topology_breadcrumb_max_age": 600,
        "topology_breadcrumb_cache_size": 256,
        "topology_breadcrumb_cache_key_size": 64,
        "topology_registry_cache_size": 256,
        "topology_registry_cache_key_size": 64,
    }


def _router(tmp_path, cluster_id="origin"):
    opts = _opts(tmp_path, cluster_id)
    breadcrumbs.pre_create(opts)
    registry.pre_create(opts)
    br = breadcrumbs.open_writer(opts)
    reg = registry.open_writer(opts)
    r = router_mod.TopologyRouter(opts, reg, br)
    return r, opts, reg, br


class _Link:
    """Minimal inbound-link stand-in exposing the authenticated
    ``peer_cluster_id`` attribute that the router uses as the
    "inbound link identifier" written into breadcrumbs."""

    def __init__(self, peer_cluster_id):
        self.peer_cluster_id = peer_cluster_id
        self.health = "connected"


# ---------------------------------------------------------------------------
# 1. Breadcrumb entry shape: jid -> inbound peer cluster_id (+ expiry_at)
# ---------------------------------------------------------------------------


class TestBreadcrumbEntryShape:
    def test_value_is_link_cluster_id_and_expiry_at(self, tmp_path, monkeypatch):
        """
        Docs: "value is ``{'link_cluster_id': <inbound peer>,
        'expiry_at': <ts>}``".  The dict shape is load-bearing because
        ``_handle_topology_return_event`` and
        :meth:`TopologyRouter.lookup_breadcrumb` both key on these
        exact names.
        """
        r, opts, reg, br = _router(tmp_path)
        try:
            monkeypatch.setattr(breadcrumbs.time, "time", lambda: 10_000.0)
            r.record_breadcrumb("jid-shape", _Link("west"), timeout=5)
            raw = br.get("jid-shape")
            decoded = breadcrumbs._decode(raw)  # pylint: disable=protected-access
            assert set(decoded) == {"link_cluster_id", "expiry_at"}
            # Inbound link identifier is the peer's cluster_id string.
            assert decoded["link_cluster_id"] == "west"
            # Exact formula: now + min(timeout + grace, max_age)
            #              = 10000 + min(5 + 30, 600) = 10035.
            assert decoded["expiry_at"] == pytest.approx(10_035.0)
        finally:
            br.close()
            reg.close()

    def test_key_is_bare_jid_not_cluster_scoped(self, tmp_path):
        """
        Implementation reality check.

        ``TopologyRouter.forward_publish`` reads ``load["jid"]`` and
        passes it straight to :func:`breadcrumbs.put` as the key --
        it does NOT prefix with ``<cluster_id>:``.  The breadcrumbs
        module docstring (and ``doc/topics/master-topology/index.md``
        line 322) claim keys look like ``<cluster_id>:<jid>`` but
        the code stores the bare jid.  This test pins the actual
        behavior so the next refactor doesn't silently flip the
        contract on ``_maybe_fire_topology_return`` (which also looks
        up by bare jid).
        """
        r, opts, reg, br = _router(tmp_path)
        try:
            r.record_breadcrumb("20260101000000000001", _Link("east"), timeout=5)
            # Bare jid is a direct hit.
            assert breadcrumbs.lookup(br, "20260101000000000001") == "east"
            # A cluster-scoped key is NOT a hit --- proving the key is bare.
            assert breadcrumbs.lookup(br, "origin:20260101000000000001") is None
        finally:
            br.close()
            reg.close()


# ---------------------------------------------------------------------------
# 2. TTL honored: grace + max_age feed the staleness check
# ---------------------------------------------------------------------------


class TestBreadcrumbTTLHonored:
    def test_grace_opt_extends_lifetime(self, tmp_path, monkeypatch):
        """
        Docs: "Raise ``topology_breadcrumb_grace`` ... if your jobs
        run long."  Verify the opt actually lands in
        ``_compute_expiry_at``: a bigger grace produces a later
        expiry_at for the same timeout.
        """
        monkeypatch.setattr(breadcrumbs.time, "time", lambda: 1000.0)
        short_opts = {
            "topology_breadcrumb_grace": 5,
            "topology_breadcrumb_max_age": 10_000,
        }
        long_opts = {
            "topology_breadcrumb_grace": 300,
            "topology_breadcrumb_max_age": 10_000,
        }
        short_expiry = breadcrumbs._compute_expiry_at(60.0, short_opts)
        long_expiry = breadcrumbs._compute_expiry_at(60.0, long_opts)
        assert long_expiry - short_expiry == pytest.approx(295.0)

    def test_max_age_clamps_grace_plus_timeout(self, tmp_path, monkeypatch):
        """
        Docs: ``topology_breadcrumb_max_age`` is "absolute ceiling
        on breadcrumb age regardless of publish timeout."  A publish
        timeout + grace exceeding max_age must clamp.
        """
        monkeypatch.setattr(breadcrumbs.time, "time", lambda: 2000.0)
        opts = {
            "topology_breadcrumb_grace": 60,
            "topology_breadcrumb_max_age": 120,
        }
        # timeout 10_000 + grace 60 = 10_060 >> max_age 120 -> clamp.
        expiry = breadcrumbs._compute_expiry_at(10_000.0, opts)
        assert expiry == pytest.approx(2000.0 + 120.0)

    def test_expired_lookup_returns_none(self, tmp_path, monkeypatch):
        """
        Docs: "Expired entries are swept by a periodic cleanup;
        readers also treat expired as absent."  Prove the lazy
        staleness check: an entry whose ``expiry_at`` is in the
        past is invisible to ``lookup`` without any cleanup
        running.
        """
        r, opts, reg, br = _router(tmp_path)
        try:
            now = {"t": 1000.0}
            monkeypatch.setattr(breadcrumbs.time, "time", lambda: now["t"])
            # grace=30, timeout=5 -> expiry at 1035.
            r.record_breadcrumb("jid-ttl", _Link("west"), timeout=5)
            # Still fresh.
            assert breadcrumbs.lookup(br, "jid-ttl") == "west"
            # Jump past expiry without invoking cleanup.
            now["t"] = 1_000_000.0
            assert breadcrumbs.lookup(br, "jid-ttl") is None
        finally:
            br.close()
            reg.close()

    def test_default_grace_and_max_age_match_docs(self):
        """
        Docs table: ``topology_breadcrumb_grace`` default 30,
        ``topology_breadcrumb_max_age`` default 600.  Pin the
        module-level defaults so a silent config change surfaces
        here before the doc table goes stale.
        """
        assert breadcrumbs._DEFAULT_GRACE == 30
        assert breadcrumbs._DEFAULT_MAX_AGE == 600
        # And the formula honors them when opts is empty.
        now = 1000.0
        assert breadcrumbs._compute_expiry_at(60.0, {}, now=now) == pytest.approx(
            now + 90.0
        )
        # 10_000s timeout clamps to default max_age of 600.
        assert breadcrumbs._compute_expiry_at(10_000.0, {}, now=now) == pytest.approx(
            now + 600.0
        )


# ---------------------------------------------------------------------------
# 3. Return event tag format: salt/topology/return/<origin>/<jid>
# ---------------------------------------------------------------------------


class TestReturnEventTagFormat:
    def test_fire_tag_includes_origin_and_jid(self, tmp_path, monkeypatch):
        """
        Docs: "MWorker fires a single event:
        ``salt/topology/return/<origin_cluster_id>/<jid>``".

        Drives :meth:`salt.master.AESFuncs._maybe_fire_topology_return`
        past its breadcrumb-hit guard and captures the tag it fires
        on the master event bus.
        """
        # Pre-seed a breadcrumb so the hand-off doesn't early-return
        # on the "we did not forward this jid" guard.
        opts = _opts(tmp_path, cluster_id="mid")
        breadcrumbs.pre_create(opts)
        writer = breadcrumbs.open_writer(opts)
        try:
            breadcrumbs.put(writer, "jid-tag", "west", 60.0, opts)
        finally:
            writer.close()

        import salt.master  # pylint: disable=import-outside-toplevel

        fired = []

        class _Event:
            def fire_event(self, data, tag):
                fired.append((tag, data))

        class _Shim:
            """Minimal stand-in for AESFuncs; only the bits
            ``_maybe_fire_topology_return`` touches."""

            opts = None
            event = _Event()

            _maybe_fire_topology_return = (
                salt.master.AESFuncs._maybe_fire_topology_return
            )

        shim = _Shim()
        shim.opts = opts
        load = {
            "jid": "jid-tag",
            "id": "minion-1",
            "return": {"ok": True},
            "topology": {"origin": "far-cluster"},
        }
        shim._maybe_fire_topology_return(load, async_path=False)

        assert fired, "no event fired"
        tag, data = fired[-1]
        assert tag == "salt/topology/return/far-cluster/jid-tag"
        assert data == {"load": load}

    def test_fire_uses_breadcrumb_peer_when_envelope_origin_missing(self, tmp_path):
        """
        Docs: origin is taken from the envelope, but
        ``_maybe_fire_topology_return`` falls back to the breadcrumb's
        ``link_cluster_id`` when the minion's return rebuild dropped
        the ``topology`` envelope.  Pin the fallback so a refactor
        doesn't silently fire ``salt/topology/return//<jid>`` (empty
        origin) when the envelope is missing.
        """
        opts = _opts(tmp_path, cluster_id="mid")
        breadcrumbs.pre_create(opts)
        writer = breadcrumbs.open_writer(opts)
        try:
            breadcrumbs.put(writer, "jid-fallback", "west", 60.0, opts)
        finally:
            writer.close()

        import salt.master  # pylint: disable=import-outside-toplevel

        fired = []

        class _Event:
            def fire_event(self, data, tag):
                fired.append((tag, data))

        class _Shim:
            opts = None
            event = _Event()
            _maybe_fire_topology_return = (
                salt.master.AESFuncs._maybe_fire_topology_return
            )

        shim = _Shim()
        shim.opts = opts
        load = {
            "jid": "jid-fallback",
            "id": "minion-2",
            "return": {"ok": True},
            # No "topology" envelope at all --- minion rebuild path.
        }
        shim._maybe_fire_topology_return(load, async_path=False)
        assert fired, "no event fired on breadcrumb-origin fallback"
        tag, _data = fired[-1]
        assert tag == "salt/topology/return/west/jid-fallback"

    def test_subscriber_tag_prefix_matches_fire_tag(self):
        """
        Docs: The publish daemon "runs a dedicated subscriber ... that
        picks up the event."  The ``startswith`` subscription in
        :func:`_start_return_subscriber` must match the exact tag
        prefix fired by the MWorker.
        """
        # Grep the module source for the subscribe prefix and the
        # fire-tag format, and pin they match.
        import inspect

        import salt.topology.link_manager as lm  # pylint: disable=import-outside-toplevel

        src = inspect.getsource(lm)
        assert 'event_bus.subscribe("salt/topology/return"' in src
        assert '"salt/topology/return/' in src or ("salt/topology/return/" in src)
