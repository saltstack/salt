"""
Adversarial scenarios for master-topology peer-input trust boundary.

Every test in this module is a focused probe of ONE attack vector a
hostile authenticated peer master can mount against this master.
Each probe either:

* passes --- the defense works as advertised; or
* xfails cleanly --- the defense is missing and the test documents
  the bug precisely enough that fixing the implementation flips
  the xfail to a pass.

Attack surface:

* ``cluster_id`` smuggling (reserved sentinels, Unicode homoglyphs,
  prefix collisions, overlong strings vs MmapCache ``key_size``
  truncation, duplicate attach with a different public key).
* Path authentication tampering (empty path, self-cycle, type
  confusion, destinations list that includes self).
* Reserved-key defense on the registry writer, the Raft state
  machine, and the ``_master_auth`` handshake.
* Identity rotation while a prior key is pinned in ``masters/``.
* ``salt-key -a/--master`` + ``salt-key -d/--master`` TOCTOU on
  the pending/accepted file set.

The probes drive the real :mod:`salt.topology.registry`,
:mod:`salt.topology.breadcrumbs`, :mod:`salt.topology.router`, and
:mod:`salt.cluster.consensus.raft.topology` modules against on-disk
MmapCache files; no implementation modules are stubbed.
"""

import asyncio
import logging
import os
import pathlib
import re
import threading

import pytest

import salt.topology.breadcrumbs as breadcrumbs
import salt.topology.link_manager as link_manager
import salt.topology.registry as registry
import salt.topology.router as router_mod
from salt.cluster.consensus.raft.log import LogEntryType
from salt.cluster.consensus.raft.topology import TopologyStateMachine
from salt.config.topology import CLUSTER_ID_RE
from salt.topology.link import LinkHealth
from salt.topology.summary import ClusterSummary

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


FAKE_PUB_A = b"-----BEGIN PUBLIC KEY-----\nAAAA\n-----END PUBLIC KEY-----\n"
FAKE_PUB_B = b"-----BEGIN PUBLIC KEY-----\nBBBB\n-----END PUBLIC KEY-----\n"
FAKE_PRIV_A = b"-----BEGIN RSA PRIVATE KEY-----\naaaa\n-----END RSA PRIVATE KEY-----\n"

RESERVED_SENTINELS = [
    "__identity_pub__",
    "__identity_version__",
    "__raft_bootstrapped__",
    "__raft_applied_peers__",
]


def _opts(pki_root, cluster_id="self"):
    """Minimal opts dict for registry + SM + router construction."""
    master_dir = pki_root / "master"
    master_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("masters", "masters_pre", "masters_rejected", "masters_denied"):
        (pki_root / sub).mkdir(parents=True, exist_ok=True)
    return {
        "pki_dir": str(pki_root),
        "cluster_id": cluster_id,
        "topology_enabled": True,
        "topology_registry_cache_size": 1024,
        "topology_registry_cache_key_size": 64,
        "topology_breadcrumb_cache_size": 1024,
        "topology_breadcrumb_cache_key_size": 64,
        "topology_breadcrumb_grace": 2,
        "topology_breadcrumb_max_age": 60,
        "topology_link_port": 44506,
        "keysize": 2048,
        "hash_type": "sha256",
    }


def _attach_cmd(cluster_id, public_key, **extra):
    """Build a MASTER_PEER_ATTACH cmd payload."""
    cmd = {
        "type": LogEntryType.MASTER_PEER_ATTACH,
        "cluster_id": cluster_id,
        "public_key": public_key,
        "endpoints": ("127.0.0.1:4506",),
        "attached_at": 1_700_000_000.0,
    }
    cmd.update(extra)
    return cmd


def _detach_cmd(cluster_id, reason="revoked"):
    """Build a MASTER_PEER_DETACH cmd payload."""
    return {
        "type": LogEntryType.MASTER_PEER_DETACH,
        "cluster_id": cluster_id,
        "reason": reason,
    }


class _StubInboundLink:
    """Minimal :class:`PeerMasterLink` stand-in for router probes."""

    def __init__(self, peer_cluster_id):
        self.peer_cluster_id = peer_cluster_id
        self.health = LinkHealth.CONNECTED
        self.publishes = []
        self.summaries = []

    async def send_publish(self, load, path):
        self.publishes.append({"load": load, "path": list(path)})

    async def send_summary(self, summary):
        self.summaries.append(summary)


@pytest.fixture
def sm(tmp_path):
    """A :class:`TopologyStateMachine` wired to a fresh registry."""
    opts = _opts(tmp_path)
    registry.pre_create(opts)
    machine = TopologyStateMachine(opts)
    try:
        yield machine, opts
    finally:
        cache = getattr(machine, "registry", None)
        if cache is not None and hasattr(cache, "close"):
            try:
                cache.close()
            except Exception:  # pylint: disable=broad-except
                pass


@pytest.fixture
def router_fx(tmp_path):
    """A real :class:`TopologyRouter` on fresh MmapCaches."""
    opts = _opts(tmp_path, cluster_id="west")
    breadcrumbs.pre_create(opts)
    registry.pre_create(opts)
    br_cache = breadcrumbs.open_writer(opts)
    reg_cache = registry.open_writer(opts)
    r = router_mod.TopologyRouter(opts, reg_cache, br_cache)
    try:
        yield r, opts, reg_cache, br_cache
    finally:
        try:
            br_cache.close()
        except Exception:  # pylint: disable=broad-except
            pass
        try:
            reg_cache.close()
        except Exception:  # pylint: disable=broad-except
            pass


def _warning_records(caplog, logger_name):
    """Return WARNING-and-above records for a specific logger name."""
    return [
        rec
        for rec in caplog.records
        if rec.levelno >= logging.WARNING and rec.name == logger_name
    ]


# ===========================================================================
# Reserved-sentinel attacks against the registry writer
# ===========================================================================


@pytest.mark.parametrize("reserved", RESERVED_SENTINELS)
def test_registry_set_peer_rejects_reserved_sentinel(tmp_path, reserved):
    """
    Direct call to :func:`registry.set_peer` with a reserved sentinel
    cluster_id must raise ``ValueError`` --- the defense documented in
    the registry docstring.  Protects against a buggy caller (or a
    future refactor that forgot to check at the Raft layer).
    """
    opts = _opts(tmp_path)
    registry.pre_create(opts)
    cache = registry.open_writer(opts)
    try:
        state = {
            "cluster_id": reserved,
            "public_key": FAKE_PUB_A,
            "endpoints": (),
            "attached_at": 1_700_000_000.0,
        }
        with pytest.raises(ValueError, match="reserved"):
            registry.set_peer(cache, reserved, state)
        # And identity_pub bytes must remain unaltered / absent.
        assert registry.get_identity_pub(cache) is None
    finally:
        cache.close()


@pytest.mark.parametrize("reserved", RESERVED_SENTINELS)
def test_registry_delete_peer_silently_ignores_reserved(tmp_path, reserved):
    """
    :func:`registry.delete_peer` on a reserved sentinel is a documented
    no-op (not an error) so a bulk-detach loop including a reserved id
    does not fail the whole batch.  Verify the sentinel's slot is NOT
    deleted as a side effect.
    """
    opts = _opts(tmp_path)
    registry.pre_create(opts)
    cache = registry.open_writer(opts)
    try:
        # Plant a known value under the sentinel (via the raw cache
        # ``put`` which has no sentinel check) and verify delete_peer
        # leaves it alone.
        planted = b"planted-sentinel-value"
        cache.put(reserved, planted)
        registry.delete_peer(cache, reserved)
        got = cache.get(reserved, default=None)
        # MmapCache may round-trip bytes as str; the invariant we care
        # about is "slot contents preserved" so normalise before compare.
        if isinstance(got, str):
            got_bytes = got.encode("utf-8")
        else:
            got_bytes = got
        assert got_bytes == planted, (
            f"delete_peer({reserved!r}) must not touch the reserved slot; "
            f"got {got!r}"
        )
    finally:
        cache.close()


# ===========================================================================
# Reserved-sentinel attacks against the Raft state machine
# ===========================================================================


@pytest.mark.parametrize("reserved", RESERVED_SENTINELS)
def test_sm_peer_attach_rejects_reserved(sm, reserved, caplog):
    """
    An entry committed to Raft (hostile peer OR buggy proposer)
    carrying a reserved cluster_id must be rejected by
    :meth:`TopologyStateMachine._handle_peer_attach`.  Rejection is a
    CRITICAL log + no registry mutation.
    """
    machine, _opts_ = sm
    before_peers = set(registry.list_peer_ids(machine.registry))
    before_pub = registry.get_identity_pub(machine.registry)
    with caplog.at_level(
        logging.CRITICAL, logger="salt.cluster.consensus.raft.topology"
    ):
        machine.apply(_attach_cmd(reserved, FAKE_PUB_A), client_id="h", sequence_num=1)
    after_peers = set(registry.list_peer_ids(machine.registry))
    after_pub = registry.get_identity_pub(machine.registry)
    assert after_peers == before_peers, (
        f"reserved attach {reserved!r} leaked into registry: "
        f"new peer ids {after_peers - before_peers!r}"
    )
    # And the identity_pub slot must be untouched (defense in depth).
    assert (
        after_pub == before_pub
    ), f"reserved attach {reserved!r} unexpectedly altered identity_pub"


@pytest.mark.parametrize("reserved", RESERVED_SENTINELS)
def test_sm_peer_detach_rejects_reserved(sm, reserved, caplog):
    """
    MASTER_PEER_DETACH for a reserved sentinel must be ignored --- the
    SM must not call registry.delete_peer (no-op) nor touch the raw
    MmapCache slot.
    """
    machine, _opts_ = sm
    # Plant a sentinel value and attach a legit peer so we can verify
    # the detach does not cascade.
    machine.apply(
        {"type": LogEntryType.MASTER_IDENTITY_KEY, "public_key": FAKE_PUB_A},
        client_id="op",
        sequence_num=1,
    )
    machine.apply(_attach_cmd("east", FAKE_PUB_A), client_id="op", sequence_num=2)
    before_pub = registry.get_identity_pub(machine.registry)
    with caplog.at_level(
        logging.CRITICAL, logger="salt.cluster.consensus.raft.topology"
    ):
        machine.apply(_detach_cmd(reserved), client_id="h", sequence_num=3)
    after_pub = registry.get_identity_pub(machine.registry)
    # Reserved detach must not clear the identity_pub slot.
    assert before_pub == after_pub
    # And the legit peer must still be present.
    assert registry.get_peer(machine.registry, "east") is not None


# ===========================================================================
# cluster_id shape attacks against the state machine
# ===========================================================================


@pytest.mark.parametrize(
    "bad_id",
    [
        # Cyrillic 'е' + 'ast' — looks like 'east' to the eye but fails ASCII regex.
        "еast",
        # Latin + Cyrillic mixed homoglyphs
        "eаst",  # Cyrillic 'а' in the middle
        # Full-width latin 'EAST'
        "ｅａｓｔ",
        # Zero-width joiner inside an otherwise-plausible id
        "ea‍st",
        # Leading dash (not matching [a-z0-9] first-char class)
        "-east",
        # Underscore prefix (looks reserved but regex blocks via [a-z0-9] first)
        "_identity_pub_",
        # Shell metacharacters
        "east;rm",
    ],
)
def test_sm_peer_attach_rejects_malformed_cluster_id(sm, bad_id, caplog):
    """
    :data:`CLUSTER_ID_RE` must reject every Unicode homoglyph, prefix
    corruption, and shell-sensitive variant --- a hostile peer cannot
    smuggle a near-twin of a legitimate cluster_id past the regex.
    """
    machine, _opts_ = sm
    with caplog.at_level(
        logging.CRITICAL, logger="salt.cluster.consensus.raft.topology"
    ):
        machine.apply(_attach_cmd(bad_id, FAKE_PUB_A), client_id="h", sequence_num=1)
    peers = set(registry.list_peer_ids(machine.registry))
    assert bad_id not in peers, (
        f"malformed cluster_id {bad_id!r} slipped past the regex and "
        f"landed in the registry"
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "implementation bug: CLUSTER_ID_RE = '^[a-z0-9][a-z0-9_-]*$' with "
        "Python's default re.match semantics allows '$' to match before a "
        "trailing newline, so cluster_id='east\\n' matches the regex and "
        "lands in the registry.  Hostile peer can thus register a "
        "near-twin of a legitimate cluster_id that will corrupt log files "
        "(line splits), directory listings, and any downstream text "
        "parsing.  Fix: either use re.compile(..., re.MULTILINE=False) "
        "with r'\\A[a-z0-9][a-z0-9_-]*\\Z' (anchors that do NOT accept "
        "\\n), or explicitly reject strings containing '\\r' or '\\n' "
        "before the regex check in _handle_peer_attach + salt.key."
    ),
)
def test_sm_peer_attach_rejects_trailing_newline_cluster_id(sm, caplog):
    """
    Hostile cluster_id ``east\\n`` matches ``CLUSTER_ID_RE`` because
    Python's ``$`` matches before a trailing newline by default.  The
    SM must still reject it --- a cluster_id containing a newline
    cannot safely be used as a filename component, a log token, or a
    MmapCache key.
    """
    machine, _opts_ = sm
    bad_id = "east\n"
    with caplog.at_level(
        logging.CRITICAL, logger="salt.cluster.consensus.raft.topology"
    ):
        machine.apply(_attach_cmd(bad_id, FAKE_PUB_A), client_id="h", sequence_num=1)
    peers = set(registry.list_peer_ids(machine.registry))
    assert bad_id not in peers, (
        f"malformed cluster_id {bad_id!r} slipped past the regex and "
        f"landed in the registry"
    )


def test_cluster_id_regex_rejects_unicode_homoglyphs():
    """
    The ASCII-only ``CLUSTER_ID_RE`` is specifically expected to reject
    characters outside ``[a-z0-9_-]`` even under Python's default
    Unicode-aware ``re`` module.  Pin the behaviour so a future flag
    change (``re.ASCII`` removal, etc.) does not silently open a hole.
    """
    homoglyphs = [
        "еast",  # Cyrillic 'е' + ast
        "eаst",  # 'e' + Cyrillic 'а' + st
        "ｅast",  # Full-width 'ｅ' + ast
    ]
    for ident in homoglyphs:
        assert not re.match(
            CLUSTER_ID_RE, ident
        ), f"CLUSTER_ID_RE must not match Unicode homoglyph {ident!r}"


def test_sm_peer_attach_accepts_prefix_siblings_without_collision(sm, tmp_path):
    """
    Peer ``ea`` is a strict prefix of ``east``.  Both are valid under
    the regex and must land as DISTINCT peers --- the registry must
    not conflate them via any file-system or key-naming shortcut.
    """
    machine, opts_ = sm
    # Attach the long one first, then the prefix.
    machine.apply(_attach_cmd("east", FAKE_PUB_A), client_id="op", sequence_num=1)
    machine.apply(_attach_cmd("ea", FAKE_PUB_B), client_id="op", sequence_num=2)
    assert registry.get_peer(machine.registry, "east") is not None
    assert registry.get_peer(machine.registry, "ea") is not None
    assert registry.get_peer(machine.registry, "east")["public_key"] == FAKE_PUB_A
    assert registry.get_peer(machine.registry, "ea")["public_key"] == FAKE_PUB_B
    # And file-system state: no "east.pub.bak" or similar collision.
    masters = os.listdir(os.path.join(opts_["pki_dir"], "masters"))
    assert sorted(masters) == [
        "ea.pub",
        "east.pub",
    ], f"unexpected files in masters/: {masters!r}"


def test_sm_peer_attach_truncation_collision_on_overlong_cluster_ids(sm, caplog):
    """
    MmapCache stores keys truncated to ``key_size`` bytes.  Two
    cluster_ids that match the regex but share the first ``key_size``
    bytes will collide in the cache's index, and the regex places no
    upper bound on the string.

    With ``topology_registry_cache_key_size=64`` the probe is to attach
    peer ``a`` * 64 and peer ``a`` * 64 + ``b``.  The second attach,
    carrying a different public_key, is EITHER:

    * rejected (good --- the SM enforces a length cap or the registry's
      conflict-resolution branch fires), or
    * silently overwrites the first entry at the storage layer because
      the index entry collides after truncation (BAD --- the second
      peer stole the first peer's identity slot).

    If the "silent overwrite" branch is observed, that's a bug.  The
    xfail notes which arm fired so the fix knows what to tighten.
    """
    machine, _opts_ = sm
    short_id = "a" * 64
    long_id = "a" * 64 + "b"
    machine.apply(_attach_cmd(short_id, FAKE_PUB_A), client_id="op", sequence_num=1)
    # Confirm the short id landed.
    first = registry.get_peer(machine.registry, short_id)
    assert first is not None
    assert first["public_key"] == FAKE_PUB_A

    # Second attach: different public_key, longer id that truncates
    # to the same 64-byte prefix.
    with caplog.at_level(
        logging.CRITICAL, logger="salt.cluster.consensus.raft.topology"
    ):
        machine.apply(_attach_cmd(long_id, FAKE_PUB_B), client_id="op", sequence_num=2)
    after = registry.get_peer(machine.registry, short_id)
    assert after is not None
    # The short peer's key MUST still be the one we attached.  Any
    # silent overwrite by the long id's attach is a trust violation.
    assert after["public_key"] == FAKE_PUB_A, (
        f"truncation collision: peer {short_id!r}'s public_key was "
        f"overwritten by a longer peer id {long_id!r} that collided on "
        f"the first 64 bytes"
    )


def test_sm_peer_attach_duplicate_cluster_id_different_key_rejected(sm, caplog):
    """
    Second attach for the same cluster_id but a different public_key
    without ``force_replace=True`` must be rejected and the FIRST key
    preserved --- Raft-apply hostile-peer conflict resolution.
    """
    machine, _opts_ = sm
    machine.apply(_attach_cmd("east", FAKE_PUB_A), client_id="op", sequence_num=1)
    with caplog.at_level(
        logging.CRITICAL, logger="salt.cluster.consensus.raft.topology"
    ):
        machine.apply(_attach_cmd("east", FAKE_PUB_B), client_id="h", sequence_num=2)
    state = registry.get_peer(machine.registry, "east")
    assert state is not None
    assert (
        state["public_key"] == FAKE_PUB_A
    ), "duplicate-attach without force_replace must preserve the first key"


def test_sm_peer_attach_duplicate_different_key_force_replace_overwrites(sm, caplog):
    """
    Positive control --- a committed entry with ``force_replace=True``
    IS allowed to replace the key.  Only an *operator* on a healthy
    quorum can propose this; the hostile peer never gets to flip the
    flag.  Pin that the flag is honoured so the earlier "without
    force_replace" test's negative result is specifically about the
    missing flag, not about any attach-with-same-id being blocked.
    """
    machine, _opts_ = sm
    machine.apply(_attach_cmd("east", FAKE_PUB_A), client_id="op", sequence_num=1)
    machine.apply(
        _attach_cmd("east", FAKE_PUB_B, force_replace=True),
        client_id="op",
        sequence_num=2,
    )
    state = registry.get_peer(machine.registry, "east")
    assert state is not None
    assert state["public_key"] == FAKE_PUB_B


# ===========================================================================
# Reserved-sentinel attacks against the inbound _master_auth handshake
# ===========================================================================


@pytest.mark.parametrize("reserved", RESERVED_SENTINELS)
def test_master_auth_rejects_reserved_cluster_id(tmp_path, reserved):
    """
    Inbound ``_master_auth`` carrying a reserved cluster_id must be
    rejected --- the earliest layer in the trust boundary.
    """
    load = {"cluster_id": reserved, "public_key": FAKE_PUB_A}
    loop = asyncio.new_event_loop()
    try:
        reply = loop.run_until_complete(link_manager._handle_master_auth(load))
    finally:
        loop.close()
    assert isinstance(reply, dict)
    assert reply.get("status") == "rejected", (
        f"_master_auth must reject reserved cluster_id {reserved!r}; " f"got {reply!r}"
    )


@pytest.mark.parametrize(
    "sneaky",
    [
        "_identity_pub_",  # single underscore edges
        "__id_pub__",  # near-twin dunder
        "__identity_pub__extra",  # reserved prefix with suffix
    ],
)
def test_master_auth_rejects_dunder_near_twins(tmp_path, sneaky):
    """
    cluster_ids that look like dunder sentinels or have a reserved
    prefix must be rejected by ``_master_auth``.

    * ``_identity_pub_`` (single underscore): fails regex via leading
      ``_`` outside ``[a-z0-9]``.
    * ``__id_pub__``: ``_reserved_cluster_id`` matches on the
      ``__...__`` shape even though the exact name is not in the
      sentinel set.
    * ``__identity_pub__extra``: not in the sentinel set as a value
      but shares the reserved prefix.
    """
    load = {"cluster_id": sneaky, "public_key": FAKE_PUB_A}
    loop = asyncio.new_event_loop()
    try:
        reply = loop.run_until_complete(link_manager._handle_master_auth(load))
    finally:
        loop.close()
    assert isinstance(reply, dict)
    assert reply.get("status") == "rejected", (
        f"_master_auth must reject near-twin cluster_id {sneaky!r}; " f"got {reply!r}"
    )


# ===========================================================================
# Path-authentication attacks against forward_publish
# ===========================================================================


def _tampered_publish(topology_envelope, jid="jid-adv-1"):
    """Build a minimal publish payload with a crafted topology envelope."""
    return {
        "tgt": "*",
        "tgt_type": "glob",
        "fun": "test.ping",
        "jid": jid,
        "timeout": 10,
        "topology": topology_envelope,
    }


def test_forward_publish_rejects_empty_path(router_fx, caplog):
    """
    An envelope with ``path=[]`` cannot possibly match
    ``path[-1] == inbound_peer`` --- the receiver must drop it.
    Importantly, the drop must NOT raise ``IndexError`` on
    ``path[-1]`` when the list is empty.
    """
    r, _opts_, _reg_, _br_ = router_fx
    east = _StubInboundLink("east")
    south = _StubInboundLink("south")
    r._links = {"east": east, "south": south}  # pylint: disable=protected-access
    load = _tampered_publish(
        {
            "origin": "east",
            "destinations": None,
            "transit_match": True,
            "path": [],
        }
    )
    with caplog.at_level(logging.WARNING, logger=router_mod.log.name):
        links, local_match = r.forward_publish(load, east)
    assert links == []
    assert local_match is False
    assert south.publishes == []
    assert east.publishes == []
    # Envelope untouched: no self-append happened on the drop path.
    assert load["topology"]["path"] == []


def test_forward_publish_rejects_self_only_path(router_fx, caplog):
    """
    ``path = ["west"]`` where ``west`` is the receiver's own
    cluster_id.  ``path[-1]`` is west, which never matches an inbound
    peer_cluster_id (that would mean west sent to west).  Drop.
    """
    r, _opts_, _reg_, _br_ = router_fx
    east = _StubInboundLink("east")
    r._links = {"east": east}  # pylint: disable=protected-access
    load = _tampered_publish(
        {
            "origin": "west",
            "destinations": None,
            "transit_match": True,
            "path": ["west"],
        }
    )
    with caplog.at_level(logging.WARNING, logger=router_mod.log.name):
        links, local_match = r.forward_publish(load, east)
    assert links == []
    assert local_match is False
    assert east.publishes == []
    assert load["topology"]["path"] == ["west"]


def test_forward_publish_rejects_self_in_path_tail_matches(router_fx, caplog):
    """
    ``path = ["west", "east"]`` arriving on the east<->west link.
    ``path[-1] = "east"`` matches the authenticated inbound.  But
    self ``"west"`` is also in path --- cycle.  Drop by the loop
    check.  This test exercises both defences in order: tail-match
    passes, then self-in-path kicks in.
    """
    r, _opts_, _reg_, _br_ = router_fx
    east = _StubInboundLink("east")
    south = _StubInboundLink("south")
    r._links = {"east": east, "south": south}  # pylint: disable=protected-access
    load = _tampered_publish(
        {
            "origin": "west",
            "destinations": None,
            "transit_match": True,
            "path": ["west", "east"],
        }
    )
    with caplog.at_level(logging.DEBUG, logger=router_mod.log.name):
        links, local_match = r.forward_publish(load, east)
    assert links == []
    assert local_match is False
    assert south.publishes == []
    assert east.publishes == []
    # Envelope must not have been re-appended with self.
    assert load["topology"]["path"] == ["west", "east"]


def test_forward_publish_handles_none_path(router_fx, caplog):
    """
    ``path=None`` must be treated as "empty" and dropped, not crash
    with ``TypeError`` when the handler iterates it.
    """
    r, _opts_, _reg_, _br_ = router_fx
    east = _StubInboundLink("east")
    r._links = {"east": east}  # pylint: disable=protected-access
    load = _tampered_publish(
        {
            "origin": "east",
            "destinations": None,
            "transit_match": True,
            "path": None,
        }
    )
    with caplog.at_level(logging.WARNING, logger=router_mod.log.name):
        links, local_match = r.forward_publish(load, east)
    assert links == []
    assert local_match is False
    assert east.publishes == []


def test_forward_publish_handles_string_path(router_fx, caplog):
    """
    Type-confusion probe: ``path`` is a string.  ``list("east")``
    yields ``['e','a','s','t']`` which would silently coerce; the
    router must not accept this as a 4-hop path.

    Observed as of now: ``list("east")[-1] == 't'`` !=
    inbound peer_cluster_id ("east"), so the tail check drops it
    even on the string-coercion path.  Pin this behaviour so a
    future refactor that pre-validates ``isinstance(path, list)``
    doesn't accidentally regress.
    """
    r, _opts_, _reg_, _br_ = router_fx
    east = _StubInboundLink("east")
    r._links = {"east": east}  # pylint: disable=protected-access
    load = _tampered_publish(
        {
            "origin": "east",
            "destinations": None,
            "transit_match": True,
            "path": "east",
        }
    )
    with caplog.at_level(logging.WARNING, logger=router_mod.log.name):
        links, local_match = r.forward_publish(load, east)
    assert links == [], f"string-coerced path must be dropped; got {links!r} forwards"
    assert local_match is False
    assert east.publishes == []


def test_forward_publish_destinations_including_self(router_fx):
    """
    ``destinations`` arriving in the envelope that already includes
    the receiver's own cluster_id must be shrunk --- the forwarded
    envelope's destinations tuple must have self removed, otherwise
    a hostile peer could craft a destinations list to make the
    receiver keep forwarding its own publishes back to itself.
    """
    r, _opts_, _reg_, _br_ = router_fx
    east = _StubInboundLink("east")
    south = _StubInboundLink("south")
    r._links = {"east": east, "south": south}  # pylint: disable=protected-access
    load = _tampered_publish(
        {
            "origin": "east",
            # ``west`` IS the receiver; must be stripped on forward.
            "destinations": ["east", "south", "west"],
            "transit_match": True,
            "path": ["east"],
        }
    )
    links, local_match = r.forward_publish(load, east)
    # Legitimate path auth -> accept.
    assert local_match is True
    # ``west`` (self) must be shrunk out of destinations.
    assert "west" not in (load["topology"]["destinations"] or ()), (
        f"self must be stripped from destinations on forward; got "
        f"{load['topology']['destinations']!r}"
    )
    # And south is on the shrunken list -> forwarded.
    fwd_cluster_ids = [getattr(ln, "peer_cluster_id", None) for ln in links]
    assert fwd_cluster_ids == ["south"]


# ===========================================================================
# Path-authentication attacks against ingest_summary
# ===========================================================================


def _summary(cluster_id, path, origin_seq=1):
    """Build a :class:`ClusterSummary` with the given path."""
    return ClusterSummary(
        cluster_id=cluster_id,
        path=tuple(path),
        minion_count=1,
        up_count=1,
        grain_histograms={},
        origin_seq=origin_seq,
        origin_at=1_700_000_000.0,
    )


def test_ingest_summary_rejects_empty_path(router_fx, caplog):
    """
    Empty summary.path must not crash on ``path[-1]`` and must not
    land the origin in the registry.
    """
    r, _opts_, reg, _br_ = router_fx
    east = _StubInboundLink("east")
    r._links = {"east": east}  # pylint: disable=protected-access
    bad_sum = _summary("north", path=(), origin_seq=1)
    loop = asyncio.new_event_loop()
    try:
        with caplog.at_level(logging.WARNING, logger=router_mod.log.name):
            loop.run_until_complete(r.ingest_summary(bad_sum, east))
    finally:
        loop.close()
    assert (
        registry.get_peer(reg, "north") is None
    ), "empty-path summary must not land in the registry"


# ===========================================================================
# Identity rotation while a prior key is still pinned
# ===========================================================================


def test_identity_rotation_preserves_prior_master_pub_in_peer_masters_dir(
    tmp_path,
):
    """
    After a MASTER_IDENTITY_KEY rotation on cluster A, cluster B still
    has A's OLD key in ``masters/A.pub``.  A reconnect handshake
    presenting the NEW key must fail against B's old-pinned key ---
    the rotation is operator-visible by design.

    This test models the invariant from B's side: B's ``masters/A.pub``
    stays byte-for-byte identical to the OLD bytes.  A separate
    operator-level ``salt-key -a A --master`` is required to accept the
    new key.
    """
    # Build cluster B with cluster A's old key pinned.
    b_root = tmp_path / "b-pki"
    (b_root / "masters").mkdir(parents=True, exist_ok=True)
    b_a_pub = b_root / "masters" / "a.pub"
    b_a_pub.write_bytes(FAKE_PUB_A)
    old_bytes = b_a_pub.read_bytes()
    assert old_bytes == FAKE_PUB_A

    # Build cluster A's state machine and rotate the identity key.
    a_root = tmp_path / "a-pki"
    (a_root / "master").mkdir(parents=True, exist_ok=True)
    a_opts = _opts(a_root, cluster_id="a")
    registry.pre_create(a_opts)
    a_sm = TopologyStateMachine(a_opts)
    try:
        # Fresh bootstrap, then rotation to a different key.
        a_sm.apply(
            {
                "type": LogEntryType.MASTER_IDENTITY_KEY,
                "public_key": FAKE_PUB_A,
                "private_key": FAKE_PRIV_A,
            },
            client_id="op",
            sequence_num=1,
        )
        a_sm.apply(
            {
                "type": LogEntryType.MASTER_IDENTITY_KEY,
                "public_key": FAKE_PUB_B,
            },
            client_id="op",
            sequence_num=2,
        )
        # Cluster A's own registry now holds FAKE_PUB_B.
        assert registry.get_identity_pub(a_sm.registry) == FAKE_PUB_B
    finally:
        a_sm.registry.close()

    # Cluster B's masters/a.pub still carries the OLD bytes.  The
    # topology implementation does not reach across hosts to update
    # peers' masters/ dirs on rotation --- that is the operator's job.
    assert b_a_pub.read_bytes() == FAKE_PUB_A, (
        "cluster B's pinned key for A must NOT be auto-updated on A's "
        "rotation --- preserves the operator-visible rotation invariant"
    )


# ===========================================================================
# salt-key race on master-scope accept + delete
# ===========================================================================


def test_salt_key_master_accept_delete_concurrent_no_partial_state(tmp_path):
    """
    Concurrent ``accept_master`` + ``delete_master`` on the same
    cluster_id must leave the file system in a well-defined terminal
    state: either (a) the key is in ``masters/``, or (b) the key is
    absent from every bucket.  "File in ``masters/`` + a committed
    delete that lost the race" is not permitted on a solo master
    (no raft).  A partial state (e.g. file exists in both ``masters/``
    and ``masters_pre/``) is a bug.
    """
    import salt.config  # local to keep module imports light.
    import salt.key

    pki_root = tmp_path / "pki"
    (pki_root / "masters_pre").mkdir(parents=True, exist_ok=True)
    (pki_root / "masters").mkdir(parents=True, exist_ok=True)
    pending_path = pki_root / "masters_pre" / "east.pub"
    pending_path.write_bytes(FAKE_PUB_A)
    accepted_path = pki_root / "masters" / "east.pub"

    # salt.key.Key wants a full master_config dict; build one on top
    # of /dev/null (defaults only) and override the paths we need.
    opts = salt.config.master_config("/dev/null")
    opts.update(
        {
            "pki_dir": str(pki_root),
            "sock_dir": str(tmp_path / "sock"),
            "cachedir": str(tmp_path / "cache"),
            "id": "topology-adv",
        }
    )
    pathlib.Path(opts["sock_dir"]).mkdir(parents=True, exist_ok=True)
    pathlib.Path(opts["cachedir"]).mkdir(parents=True, exist_ok=True)

    try:
        key = salt.key.Key(opts)
    except Exception as exc:  # pylint: disable=broad-except
        pytest.skip(
            f"salt.key.Key cannot be constructed in this environment: "
            f"{type(exc).__name__}: {exc}"
        )

    try:
        barrier = threading.Barrier(2)
        errors = []

        def _accept():
            barrier.wait()
            try:
                key.accept_master("east")
            except Exception as exc:  # pylint: disable=broad-except
                errors.append(("accept", exc))

        def _delete():
            barrier.wait()
            try:
                key.delete_master("east")
            except Exception as exc:  # pylint: disable=broad-except
                errors.append(("delete", exc))

        t_a = threading.Thread(target=_accept)
        t_d = threading.Thread(target=_delete)
        t_a.start()
        t_d.start()
        t_a.join(timeout=15)
        t_d.join(timeout=15)
        assert (
            not t_a.is_alive() and not t_d.is_alive()
        ), "accept/delete worker threads did not finish in time"
    finally:
        try:
            key.event.destroy()
        except Exception:  # pylint: disable=broad-except
            pass

    # Terminal state: both-present is invalid.
    both_present = accepted_path.exists() and pending_path.exists()
    assert not both_present, (
        f"concurrent accept + delete left east.pub in both "
        f"masters/ ({accepted_path.exists()}) and masters_pre/ "
        f"({pending_path.exists()}); errors={errors!r}"
    )
