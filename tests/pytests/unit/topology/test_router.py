"""
Unit tests for :mod:`salt.topology.router`.

Pure-logic coverage that doesn't need the functional harness:

* grammar fuzz on :func:`strip_cluster_scope`: for every random
  compound expression that embeds ``C@`` tokens, either the strip
  residual re-parses cleanly OR the function took the ``not`` skip-
  strip path (which returns the original string unchanged for the
  minion-side matcher to evaluate).
* breadcrumb TTL formula edge cases via
  :func:`salt.topology.breadcrumbs._compute_expiry_at`, exercised
  through :class:`TopologyRouter.record_breadcrumb`.
* envelope builder on a load with and without a pre-existing
  ``load["topology"]`` key.
* :meth:`TopologyRouter.route_event` tag-pattern subscription
  matching including globs.
"""

import random

import pytest

import salt.topology.breadcrumbs as breadcrumbs
import salt.topology.registry as registry
import salt.topology.router as router

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _opts(tmp_path, cluster_id="unit"):
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


def _router(tmp_path, cluster_id="unit"):
    opts = _opts(tmp_path, cluster_id)
    breadcrumbs.pre_create(opts)
    registry.pre_create(opts)
    br = breadcrumbs.open_writer(opts)
    reg = registry.open_writer(opts)
    r = router.TopologyRouter(opts, reg, br)
    return r, opts, reg, br


class _Link:
    def __init__(self, peer_cluster_id):
        self.peer_cluster_id = peer_cluster_id
        self.health = "connected"


# ===========================================================================
# strip_cluster_scope grammar fuzz
# ===========================================================================


_C_TOKENS = ["C@east", "C@west", "C@east,west", "C@north,south,east"]
_PLAIN_TOKENS = ["web-*", "G@os:ubuntu", "*", "db-*", "L@a,b"]
_OPERATORS = ["and", "or"]


def _random_expression(rng, size=4, allow_not=False, allow_parens=True):
    """Generate a random compound expression that includes >=1 C@ token."""
    parts = []
    include_not = allow_not and rng.random() < 0.3
    for i in range(size):
        if i > 0:
            parts.append(rng.choice(_OPERATORS))
        if include_not and i == 0:
            parts.append("not")
        wrap = allow_parens and rng.random() < 0.3
        if rng.random() < 0.5:
            tok = rng.choice(_C_TOKENS)
        else:
            tok = rng.choice(_PLAIN_TOKENS)
        if wrap:
            tok = "(" + tok + ")"
        parts.append(tok)
    expr = " ".join(parts)
    if "C@" not in expr:
        # Force at least one C@ term so the test exercises the
        # strip-path.
        expr = expr + " and " + rng.choice(_C_TOKENS)
    return expr


def _residual_parses(expr):
    """
    Rough grammar check for a stripped residual.

    Returns False when the residual contains obvious compound-syntax
    errors (empty parens, double operators, dangling leading/trailing
    operator).  This mirrors the hand-rolled grammar in
    :meth:`salt.utils.minions.CkMinions._check_compound_minions`.
    """
    if expr is None:
        return False
    tokens = router._tokenize(expr)  # pylint: disable=protected-access
    if not tokens:
        return False
    if tokens[0] in {"and", "or"}:
        return False
    if tokens[-1] in {"and", "or", "not"}:
        return False
    prev = None
    depth = 0
    for tok in tokens:
        if tok == "(":
            depth += 1
            if prev not in (None, "and", "or", "not", "("):
                return False
        elif tok == ")":
            depth -= 1
            if depth < 0:
                return False
            if prev in ("and", "or", "not", "("):
                return False
        elif tok in {"and", "or"}:
            if prev in (None, "and", "or", "not", "("):
                return False
        prev = tok
    return depth == 0


class TestStripGrammarFuzz:
    """
    Property-based: for 100 random C@-bearing expressions, either
    the residual re-parses OR the function fell through to the
    ``not`` skip-strip path.
    """

    def test_random_expressions_either_parse_or_skip_strip(self):
        rng = random.Random(0xC0FFEE)
        for _ in range(100):
            expr = _random_expression(rng, size=rng.randint(2, 6), allow_not=True)
            residual = router.strip_cluster_scope(expr)
            if residual == expr:
                # Skip-strip path (``not`` present) --- correct behavior,
                # the receiver evaluates the full compound.
                continue
            assert _residual_parses(residual), (
                "Residual failed to parse:\n"
                f"  input:    {expr!r}\n"
                f"  residual: {residual!r}"
            )

    def test_no_C_passthrough(self):
        """Expressions without a C@ token are returned unchanged."""
        rng = random.Random(42)
        for _ in range(20):
            parts = [rng.choice(_PLAIN_TOKENS)]
            for _ in range(rng.randint(0, 3)):
                parts.append(rng.choice(_OPERATORS))
                parts.append(rng.choice(_PLAIN_TOKENS))
            expr = " ".join(parts)
            assert router.strip_cluster_scope(expr) == expr


# ===========================================================================
# breadcrumb TTL formula edge cases
# ===========================================================================


class TestBreadcrumbTTL:
    def test_timeout_plus_grace_wins_when_below_max(self, tmp_path, monkeypatch):
        """``put_time + timeout + grace`` wins while below ``max_age``."""
        r, opts, reg, br = _router(tmp_path)
        try:
            monkeypatch.setattr(breadcrumbs.time, "time", lambda: 1000.0)
            r.record_breadcrumb("jid-1", _Link("west"), timeout=10)
            # grace=30 -> expiry at 1000 + 10 + 30 = 1040.
            raw = br.get("jid-1")
            # Decode via breadcrumbs._decode helper to inspect expiry_at.
            decoded = breadcrumbs._decode(raw)  # pylint: disable=protected-access
            assert decoded["link_cluster_id"] == "west"
            assert decoded["expiry_at"] == pytest.approx(1040.0)
        finally:
            br.close()
            reg.close()

    def test_max_age_clamps_long_timeout(self, tmp_path, monkeypatch):
        """``max_age`` clamps a long declared timeout."""
        r, opts, reg, br = _router(tmp_path)
        try:
            monkeypatch.setattr(breadcrumbs.time, "time", lambda: 2000.0)
            # timeout+grace=1000+30=1030 which exceeds max_age=600.
            r.record_breadcrumb("jid-2", _Link("west"), timeout=1000)
            decoded = breadcrumbs._decode(  # pylint: disable=protected-access
                br.get("jid-2")
            )
            assert decoded["expiry_at"] == pytest.approx(2000.0 + 600.0)
        finally:
            br.close()
            reg.close()

    def test_zero_timeout_still_has_grace(self, tmp_path, monkeypatch):
        """A zero timeout still gets at least ``grace`` seconds."""
        r, opts, reg, br = _router(tmp_path)
        try:
            monkeypatch.setattr(breadcrumbs.time, "time", lambda: 3000.0)
            r.record_breadcrumb("jid-3", _Link("west"), timeout=0)
            decoded = breadcrumbs._decode(  # pylint: disable=protected-access
                br.get("jid-3")
            )
            assert decoded["expiry_at"] == pytest.approx(3030.0)
        finally:
            br.close()
            reg.close()

    def test_lookup_breadcrumb_returns_link(self, tmp_path):
        r, opts, reg, br = _router(tmp_path)
        try:
            west = _Link("west")
            r._links = {"west": west}  # pylint: disable=protected-access
            r.record_breadcrumb("jid-link", west, timeout=5)
            got = r.lookup_breadcrumb("jid-link")
            assert got is west
        finally:
            br.close()
            reg.close()

    def test_lookup_expired_returns_none(self, tmp_path, monkeypatch):
        r, opts, reg, br = _router(tmp_path)
        try:
            west = _Link("west")
            r._links = {"west": west}  # pylint: disable=protected-access
            # Pin ``time.time`` to a known base BEFORE the write so the
            # breadcrumb's stored ``expiry_at`` is relative to it.
            now = {"t": 1000.0}
            monkeypatch.setattr(breadcrumbs.time, "time", lambda: now["t"])
            r.record_breadcrumb("jid-exp", west, timeout=5)
            # Advance the clock past the breadcrumb's expiry window.
            now["t"] = 1000.0 + 10_000.0
            assert r.lookup_breadcrumb("jid-exp") is None
        finally:
            br.close()
            reg.close()


# ===========================================================================
# envelope builder --- with / without pre-existing topology key
# ===========================================================================


class TestEnvelopeBuilder:
    def test_envelope_added_on_fresh_load(self, tmp_path):
        r, opts, reg, br = _router(tmp_path, cluster_id="east")
        try:
            load = {"tgt": "C@west and web-*", "jid": "j1"}
            r.route_publish(load)
            env = load["topology"]
            assert env["origin"] == "east"
            assert env["path"] == []
            assert set(env["destinations"]) == {"west"}
        finally:
            br.close()
            reg.close()

    def test_envelope_overwrites_preexisting(self, tmp_path):
        """A load with a stale ``topology`` key is overwritten at origin."""
        r, opts, reg, br = _router(tmp_path, cluster_id="east")
        try:
            load = {
                "tgt": "*",
                "jid": "j2",
                "topology": {
                    "origin": "SPOOFED",
                    "destinations": ["spoof"],
                    "transit_match": False,
                    "path": ["spoofed"],
                },
            }
            r.route_publish(load)
            env = load["topology"]
            assert env["origin"] == "east"
            assert env["path"] == []
            assert env["destinations"] is None  # flood
            assert env["transit_match"] is True
        finally:
            br.close()
            reg.close()

    def test_envelope_scoped_without_self_marks_transit_false(self, tmp_path):
        r, opts, reg, br = _router(tmp_path, cluster_id="east")
        try:
            load = {"tgt": "C@west", "jid": "j3"}
            r.route_publish(load)
            env = load["topology"]
            assert env["transit_match"] is False
            assert set(env["destinations"]) == {"west"}
        finally:
            br.close()
            reg.close()


# ===========================================================================
# route_event --- tag pattern matching
# ===========================================================================


class TestRouteEvent:
    def test_exact_tag_matches(self, tmp_path):
        r, opts, reg, br = _router(tmp_path)
        try:
            west = _Link("west")
            r._links = {"west": west}  # pylint: disable=protected-access
            r._event_subscriptions = {  # pylint: disable=protected-access
                "salt/job/*/new": ["west"],
            }
            got = r.route_event({"tag": "salt/job/12345/new", "data": {}})
            assert got == [west]
        finally:
            br.close()
            reg.close()

    def test_no_subscription_returns_empty(self, tmp_path):
        r, opts, reg, br = _router(tmp_path)
        try:
            r._event_subscriptions = {  # pylint: disable=protected-access
                "salt/job/*/new": ["west"],
            }
            assert r.route_event({"tag": "unrelated"}) == []
        finally:
            br.close()
            reg.close()

    def test_multiple_subscribers_dedup(self, tmp_path):
        r, opts, reg, br = _router(tmp_path)
        try:
            west = _Link("west")
            north = _Link("north")
            r._links = {
                "west": west,
                "north": north,
            }  # pylint: disable=protected-access
            r._event_subscriptions = {  # pylint: disable=protected-access
                "salt/job/*/new": ["west", "north"],
                "salt/*": ["west"],  # ``west`` already matched; must not duplicate.
            }
            got = r.route_event({"tag": "salt/job/1/new"})
            assert west in got
            assert north in got
            # ``west`` appears once even though two patterns match.
            assert got.count(west) == 1
        finally:
            br.close()
            reg.close()

    def test_tag_matches_helper_glob(self):
        _m = router._tag_matches  # pylint: disable=protected-access
        assert _m("salt/job/42/new", "salt/job/*/new")
        assert not _m("salt/other/42", "salt/job/*")
        assert _m("salt/anything/at/all", "salt/*")


# ===========================================================================
# get_router default
# ===========================================================================


class TestGetRouterUnit:
    def test_default_none(self, monkeypatch):
        monkeypatch.setattr(router, "_router", None, raising=False)
        assert router.get_router() is None
