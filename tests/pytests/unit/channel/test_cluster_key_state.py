"""
Unit tests for the unified cluster-key propagation state machine
(``salt/channel/_cluster_key_state.py``).

Four axes are exercised:

* Fingerprint helpers (``fingerprint_bytes``, ``read_sentinel_fingerprint``,
  ``write_sentinel_fingerprint``) -- atomic + round-trip semantics.
* Startup state reconciliation (``verify_committed_state_on_startup``)
  -- the T-2 stale-fingerprint-reverts-to-BOOTSTRAP hole.
* Receiver state machine decision table (``ClusterKeyStateMachine.decide``)
  -- BOOTSTRAP accept, COMMITTED noop, COMMITTED mismatch WARN, and the
  T-1 founder-wait defer.
* ``bootstrap_reset`` -- re-opens the commit window for operator-driven
  rotation.

These tests are pure-logic, no timing dependency outside the
founder-wait window (which is driven by a monkey-patched clock to
avoid real ``sleep`` calls).
"""

import pytest

from salt.channel._cluster_key_state import (
    DEFAULT_FOUNDER_WAIT_S,
    OPT_FOUNDER_WAIT,
    STATE_BOOTSTRAP,
    STATE_COMMITTED,
    ClusterKeyStateMachine,
    cluster_key_sentinel_path,
    fingerprint_bytes,
    install_cluster_key,
    read_sentinel_fingerprint,
    verify_committed_state_on_startup,
    write_sentinel_fingerprint,
)

# ---------------------------------------------------------------------------
# Fingerprint helpers
# ---------------------------------------------------------------------------


def test_fingerprint_bytes_format():
    """
    Fingerprint is ``sha256:<64-hex>`` of the input bytes.
    """
    fp = fingerprint_bytes(b"hello")
    assert fp.startswith("sha256:")
    assert len(fp) == len("sha256:") + 64


def test_fingerprint_bytes_deterministic_and_input_independent():
    """
    Identical bytes map to identical fingerprints; one-byte changes
    flip the fingerprint.
    """
    a = fingerprint_bytes(b"cluster_aes_bytes")
    b = fingerprint_bytes(b"cluster_aes_bytes")
    c = fingerprint_bytes(b"cluster_aes_byteS")
    assert a == b
    assert a != c


def test_fingerprint_bytes_accepts_str():
    """
    ``str`` input is encoded as UTF-8 before hashing so PEM strings
    round-trip with their bytes equivalents.
    """
    assert fingerprint_bytes("x") == fingerprint_bytes(b"x")


def test_fingerprint_bytes_rejects_non_bytes():
    with pytest.raises(TypeError):
        fingerprint_bytes(1234)  # type: ignore[arg-type]


def test_sentinel_path_only_accepts_known_keys(tmp_path):
    cluster_key_sentinel_path(tmp_path, "cluster_aes")
    cluster_key_sentinel_path(tmp_path, "cluster_pem")
    with pytest.raises(ValueError):
        cluster_key_sentinel_path(tmp_path, "cluster_pub")


def test_write_and_read_sentinel_roundtrip(tmp_path):
    sentinel = tmp_path / ".cluster_aes.committed"
    fp = fingerprint_bytes(b"example")
    write_sentinel_fingerprint(sentinel, fp)
    assert read_sentinel_fingerprint(sentinel) == fp


def test_write_sentinel_rejects_malformed_fingerprint(tmp_path):
    with pytest.raises(ValueError):
        write_sentinel_fingerprint(tmp_path / ".x.committed", "not-a-sha")


def test_read_sentinel_returns_none_when_absent(tmp_path):
    assert read_sentinel_fingerprint(tmp_path / ".missing") is None


def test_read_sentinel_rejects_unknown_format(tmp_path, caplog):
    import logging as _logging

    bogus = tmp_path / ".cluster_aes.committed"
    bogus.write_text("plain text\n", encoding="utf-8")
    caplog.set_level(_logging.WARNING, logger="salt.channel._cluster_key_state")
    assert read_sentinel_fingerprint(bogus) is None
    assert any("unrecognised format" in rec.getMessage() for rec in caplog.records)


def test_write_sentinel_is_atomic_via_rename(tmp_path):
    """
    ``write_sentinel_fingerprint`` must use a temp-file + rename so a
    concurrent reader never sees a torn write.  Easiest proof: the
    rename replaces, so the final file's contents equal the new
    fingerprint even when a previous sentinel exists.
    """
    sentinel = tmp_path / ".cluster_aes.committed"
    write_sentinel_fingerprint(sentinel, fingerprint_bytes(b"first"))
    write_sentinel_fingerprint(sentinel, fingerprint_bytes(b"second"))
    assert read_sentinel_fingerprint(sentinel) == fingerprint_bytes(b"second")
    # No stale tmp files left in the directory.
    stale_tmps = list(tmp_path.glob(".cluster_aes.committed.*.tmp"))
    assert stale_tmps == []


# ---------------------------------------------------------------------------
# Startup reconciliation
# ---------------------------------------------------------------------------


def test_verify_state_bootstrap_when_sentinel_absent(tmp_path):
    state, fp = verify_committed_state_on_startup(
        tmp_path, "cluster_aes", b"bootstrap-bytes"
    )
    assert state == STATE_BOOTSTRAP
    assert fp is None


def test_verify_state_committed_when_fingerprint_matches(tmp_path):
    key_bytes = b"on-disk-key"
    sentinel = cluster_key_sentinel_path(tmp_path, "cluster_aes")
    write_sentinel_fingerprint(sentinel, fingerprint_bytes(key_bytes))
    state, fp = verify_committed_state_on_startup(tmp_path, "cluster_aes", key_bytes)
    assert state == STATE_COMMITTED
    assert fp == fingerprint_bytes(key_bytes)


def test_verify_state_reverts_when_fingerprint_mismatches(tmp_path, caplog):
    """
    Reviewer T-2: sentinel present but on-disk bytes have changed
    (operator rm .aes, or offline rotation) -> delete sentinel, revert
    to BOOTSTRAP.
    """
    import logging as _logging

    sentinel = cluster_key_sentinel_path(tmp_path, "cluster_aes")
    write_sentinel_fingerprint(sentinel, fingerprint_bytes(b"old"))
    caplog.set_level(_logging.WARNING, logger="salt.channel._cluster_key_state")
    state, fp = verify_committed_state_on_startup(tmp_path, "cluster_aes", b"new")
    assert state == STATE_BOOTSTRAP
    assert fp is None
    assert not sentinel.exists(), "stale sentinel should be deleted"
    assert any("does not match on-disk" in r.getMessage() for r in caplog.records)


def test_verify_state_reverts_when_sentinel_present_but_disk_missing(tmp_path):
    """
    Sentinel on disk but no key bytes (crash between writes).  Revert
    to BOOTSTRAP so the next arriving install can reseat both.
    """
    sentinel = cluster_key_sentinel_path(tmp_path, "cluster_pem")
    write_sentinel_fingerprint(sentinel, fingerprint_bytes(b"gone"))
    state, fp = verify_committed_state_on_startup(tmp_path, "cluster_pem", None)
    assert state == STATE_BOOTSTRAP
    assert fp is None
    assert not sentinel.exists()


# ---------------------------------------------------------------------------
# State-machine decide
# ---------------------------------------------------------------------------


def _make_sm(tmp_path, wait_s=DEFAULT_FOUNDER_WAIT_S):
    opts = {OPT_FOUNDER_WAIT: wait_s}
    sm = ClusterKeyStateMachine(opts, tmp_path)
    return sm


def test_decide_bootstrap_installs_from_founder(tmp_path):
    sm = _make_sm(tmp_path)
    assert (
        sm.decide("cluster_aes", b"xyz", sender_peer_id="m1", is_founder=True)
        == "install"
    )


def test_decide_bootstrap_defers_non_founder_within_window(tmp_path):
    sm = _make_sm(tmp_path, wait_s=5.0)
    assert (
        sm.decide("cluster_aes", b"xyz", sender_peer_id="m2", is_founder=False)
        == "defer"
    )


def test_decide_bootstrap_accepts_non_founder_after_window(tmp_path, monkeypatch):
    """
    After the founder-wait window elapses, the next non-founder
    install is accepted (with WARN).  Simulated by monkeypatching
    ``time.monotonic`` in the state-machine module.
    """
    import salt.channel._cluster_key_state as mod

    sm = _make_sm(tmp_path, wait_s=2.0)
    tick = [100.0]
    monkeypatch.setattr(mod.time, "monotonic", lambda: tick[0])
    # First arrival starts the window.
    assert (
        sm.decide("cluster_aes", b"xyz", sender_peer_id="m2", is_founder=False)
        == "defer"
    )
    # Advance past the window.
    tick[0] = 103.0
    assert (
        sm.decide("cluster_aes", b"xyz", sender_peer_id="m2", is_founder=False)
        == "install"
    )


def test_decide_committed_equal_is_noop(tmp_path):
    sm = _make_sm(tmp_path)
    sm.mark_committed("cluster_aes", b"same-bytes")
    assert (
        sm.decide(
            "cluster_aes",
            b"same-bytes",
            sender_peer_id="peer",
            is_founder=True,
        )
        == "noop"
    )


def test_decide_committed_mismatch_rejects_and_warns(tmp_path, caplog):
    import logging as _logging

    sm = _make_sm(tmp_path)
    sm.mark_committed("cluster_aes", b"committed-bytes")
    caplog.set_level(_logging.WARNING, logger="salt.channel._cluster_key_state")
    assert (
        sm.decide(
            "cluster_aes",
            b"divergent-bytes",
            sender_peer_id="attacker",
            is_founder=True,
        )
        == "reject"
    )
    assert any(
        "refusing install" in r.getMessage() for r in caplog.records
    ), f"expected refusing-install WARN, got {[r.getMessage() for r in caplog.records]}"


def test_decide_rejects_none_bytes(tmp_path):
    sm = _make_sm(tmp_path)
    assert (
        sm.decide("cluster_aes", None, sender_peer_id="m1", is_founder=True) == "reject"
    )


def test_decide_unsupported_key_name_raises(tmp_path):
    sm = _make_sm(tmp_path)
    with pytest.raises(ValueError):
        sm.decide("cluster_pub", b"x", sender_peer_id="m1", is_founder=True)


# ---------------------------------------------------------------------------
# mark_committed / bootstrap_reset
# ---------------------------------------------------------------------------


def test_mark_committed_writes_sentinel_and_flips_state(tmp_path):
    sm = _make_sm(tmp_path)
    assert sm.state_of("cluster_aes") == STATE_BOOTSTRAP
    transition = sm.mark_committed("cluster_aes", b"xx")
    assert transition is True
    assert sm.state_of("cluster_aes") == STATE_COMMITTED
    assert sm.fingerprint_of("cluster_aes") == fingerprint_bytes(b"xx")
    # Sentinel is on disk with the matching fingerprint.
    sentinel = cluster_key_sentinel_path(tmp_path, "cluster_aes")
    assert read_sentinel_fingerprint(sentinel) == fingerprint_bytes(b"xx")


def test_mark_committed_idempotent_recommit(tmp_path):
    """
    Recommitting the same bytes returns ``transition=False`` so the
    caller can skip ``drop_all_pending`` fan-out for cluster_aes.
    """
    sm = _make_sm(tmp_path)
    sm.mark_committed("cluster_aes", b"xx")
    transition = sm.mark_committed("cluster_aes", b"xx")
    assert transition is False


def test_bootstrap_reset_reopens_commit_window(tmp_path):
    sm = _make_sm(tmp_path)
    sm.mark_committed("cluster_aes", b"xx")
    assert sm.state_of("cluster_aes") == STATE_COMMITTED
    sm.bootstrap_reset("cluster_aes")
    assert sm.state_of("cluster_aes") == STATE_BOOTSTRAP
    assert sm.fingerprint_of("cluster_aes") is None
    sentinel = cluster_key_sentinel_path(tmp_path, "cluster_aes")
    assert not sentinel.exists()


def test_load_from_disk_commits_when_fingerprint_matches(tmp_path):
    sentinel = cluster_key_sentinel_path(tmp_path, "cluster_aes")
    write_sentinel_fingerprint(sentinel, fingerprint_bytes(b"persisted"))
    sm = _make_sm(tmp_path)
    sm.load_from_disk("cluster_aes", b"persisted")
    assert sm.state_of("cluster_aes") == STATE_COMMITTED


def test_load_from_disk_stays_bootstrap_on_mismatch(tmp_path):
    sentinel = cluster_key_sentinel_path(tmp_path, "cluster_pem")
    write_sentinel_fingerprint(sentinel, fingerprint_bytes(b"old"))
    sm = _make_sm(tmp_path)
    sm.load_from_disk("cluster_pem", b"new")
    assert sm.state_of("cluster_pem") == STATE_BOOTSTRAP
    assert not sentinel.exists()


# ---------------------------------------------------------------------------
# install_cluster_key high-level helper
# ---------------------------------------------------------------------------


def test_install_cluster_key_runs_install_fn_on_bootstrap(tmp_path):
    sm = _make_sm(tmp_path)
    called = []

    def install_fn():
        called.append("yes")
        return b"installed-bytes"

    outcome = install_cluster_key(
        sm,
        "cluster_aes",
        b"arriving",
        sender_peer_id="m1",
        is_founder=True,
        install_fn=install_fn,
    )
    assert outcome["decision"] == "install"
    assert outcome["committed"] is True
    assert outcome["transition"] is True
    assert called == ["yes"]
    assert sm.state_of("cluster_aes") == STATE_COMMITTED


def test_install_cluster_key_skips_install_fn_on_committed_equal(tmp_path):
    sm = _make_sm(tmp_path)
    sm.mark_committed("cluster_aes", b"same")
    called = []

    def install_fn():
        called.append("boom")
        return b"same"

    outcome = install_cluster_key(
        sm,
        "cluster_aes",
        b"same",
        sender_peer_id="m1",
        is_founder=True,
        install_fn=install_fn,
    )
    assert outcome["decision"] == "noop"
    assert outcome["committed"] is False
    assert called == []


def test_install_cluster_key_skips_install_fn_on_committed_mismatch(tmp_path):
    sm = _make_sm(tmp_path)
    sm.mark_committed("cluster_aes", b"old")
    called = []

    def install_fn():
        called.append("nope")
        return b"new"

    outcome = install_cluster_key(
        sm,
        "cluster_aes",
        b"different",
        sender_peer_id="m2",
        is_founder=True,
        install_fn=install_fn,
    )
    assert outcome["decision"] == "reject"
    assert called == []


def test_install_cluster_key_handles_failed_install(tmp_path):
    """
    ``install_fn`` returning ``None`` represents a decrypt failure
    (or similar).  The state machine must stay in BOOTSTRAP so a
    subsequent arrival can succeed.
    """
    sm = _make_sm(tmp_path)

    def install_fn():
        return None

    outcome = install_cluster_key(
        sm,
        "cluster_aes",
        b"x",
        sender_peer_id="m1",
        is_founder=True,
        install_fn=install_fn,
    )
    assert outcome["decision"] == "install_failed"
    assert sm.state_of("cluster_aes") == STATE_BOOTSTRAP


# ---------------------------------------------------------------------------
# Integration: 3-master bootstrap determinism
# ---------------------------------------------------------------------------


def test_three_master_bootstrap_converges_deterministically(tmp_path, monkeypatch):
    """
    Simulate the three-master bootstrap: founder m1 and non-founders
    m2, m3 each send their locally-generated bootstrap bytes to m-receiver.
    With the founder-wait window in place, m-receiver commits to m1's
    bytes regardless of arrival order within the window.
    """
    import salt.channel._cluster_key_state as mod

    rounds = []
    for arrival_order in [
        ("m1", "m2", "m3"),
        ("m2", "m1", "m3"),
        ("m3", "m2", "m1"),
        ("m2", "m3", "m1"),
    ]:
        # Fresh SM per round.
        sm_dir = tmp_path / f"round-{'-'.join(arrival_order)}"
        sm_dir.mkdir()
        sm = ClusterKeyStateMachine({OPT_FOUNDER_WAIT: 2.0}, sm_dir)
        tick = [100.0]
        monkeypatch.setattr(mod.time, "monotonic", lambda t=tick: t[0])
        founder_bytes = b"founder-authoritative"
        bytes_for = {"m1": founder_bytes, "m2": b"m2-bootstrap", "m3": b"m3-bootstrap"}
        committed = None
        for peer in arrival_order:
            is_founder = peer == "m1"
            # Each arrival is 100ms apart.
            tick[0] += 0.1
            decision = sm.decide(
                "cluster_aes",
                bytes_for[peer],
                sender_peer_id=peer,
                is_founder=is_founder,
            )
            if decision == "install":
                sm.mark_committed("cluster_aes", bytes_for[peer])
                committed = bytes_for[peer]
        rounds.append((arrival_order, committed))
    # In every arrival order, the founder's bytes win because the
    # defer window keeps non-founder arrivals out until the founder
    # lands (all within 300ms << 2.0s window).
    for order, winner in rounds:
        assert winner == b"founder-authoritative", (
            f"arrival order {order} committed {winner!r} instead of "
            "founder-authoritative bytes"
        )
