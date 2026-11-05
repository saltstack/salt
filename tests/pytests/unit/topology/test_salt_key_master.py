"""
Unit tests for the ``--master`` scope added to salt-key.

Covers:

* Each new :class:`salt.key.Key` method's happy path on a solo
  master (no raft_service): ``list_master``, ``accept_master``,
  ``reject_master``, ``delete_master``, ``finger_master``.
* Rejection of invalid / reserved cluster_ids (regex +
  ``_RESERVED_CLUSTER_IDS``).
* :class:`KeyCLI` parser dispatch: ``--master -a east`` routes to
  :meth:`Key.accept_master` via ``CLI_KEY_MASTER_MAP``.

Keeps the heavy test harness out: no :class:`TopologyStateMachine`,
no :class:`MmapCache`, no event bus.  The ``Key`` is constructed
with a hand-rolled opts dict and the ``event`` descriptor shadowed
by a recorder so :meth:`__exit__` is a no-op.
"""

import pytest

import salt.key
import salt.utils.crypt
import salt.utils.files

FAKE_PUB = (
    b"-----BEGIN PUBLIC KEY-----\n"
    b"test-cluster-identity-key\n"
    b"-----END PUBLIC KEY-----\n"
)


class _RecordingEvent:
    def __init__(self):
        self.fired = []

    def fire_event(self, data, tag):
        self.fired.append((data, tag))

    def destroy(self):
        pass


def _write_pub(path, body=FAKE_PUB):
    with salt.utils.files.fopen(str(path), "wb") as fh:
        fh.write(body)


def _make_opts(pki_dir, sock_dir, cache_dir):
    """Minimal opts for an unclustered master."""
    return {
        "pki_dir": str(pki_dir),
        "cachedir": str(cache_dir),
        "sock_dir": str(sock_dir),
        "transport": "zeromq",
        "keys.cache_driver": "localfs_key",
        "key_cache": "",
        "preserve_minions": False,
        "rotate_aes_key": False,
        "hash_type": "sha256",
        "keysize": 2048,
        "__role": "master",
        "id": "test-master",
        "user": "root",
        "signing_key_pass": None,
    }


@pytest.fixture
def pki_dir(tmp_path):
    d = tmp_path / "pki"
    d.mkdir()
    for sub in ("masters", "masters_pre", "masters_rejected", "masters_denied"):
        (d / sub).mkdir()
    return d


@pytest.fixture
def key(tmp_path, pki_dir):
    cache = tmp_path / "cache"
    cache.mkdir()
    sock = tmp_path / "sock"
    sock.mkdir()
    opts = _make_opts(pki_dir, sock, cache)
    k = salt.key.MasterKey(opts)
    # Shadow the cached_property with a non-side-effecting stand-in so
    # ``fire_event`` / ``destroy`` work without a running salt-master.
    k.__dict__["event"] = _RecordingEvent()
    try:
        yield k
    finally:
        try:
            k.event.destroy()
        except Exception:  # pylint: disable=broad-except
            pass


# ---------------------------------------------------------------------------
# list_master
# ---------------------------------------------------------------------------


def test_list_master_sorts_each_bucket(key, pki_dir):
    _write_pub(pki_dir / "masters" / "zeta.pub")
    _write_pub(pki_dir / "masters" / "alpha.pub")
    _write_pub(pki_dir / "masters_pre" / "pending-b.pub")
    _write_pub(pki_dir / "masters_pre" / "pending-a.pub")
    _write_pub(pki_dir / "masters_rejected" / "rej.pub")
    _write_pub(pki_dir / "masters_denied" / "den.pub")

    ret = key.list_keys()
    assert ret == {
        "accepted": ["alpha", "zeta"],
        "pending": ["pending-a", "pending-b"],
        "rejected": ["rej"],
        "denied": ["den"],
    }


def test_list_master_ignores_non_pub_files(key, pki_dir):
    """Only ``.pub`` entries show up in the listing."""
    _write_pub(pki_dir / "masters" / "real.pub")
    (pki_dir / "masters" / "scratch.tmp").write_bytes(b"junk")
    (pki_dir / "masters" / "notes.txt").write_bytes(b"notes")

    ret = key.list_keys()
    assert ret["accepted"] == ["real"]


# ---------------------------------------------------------------------------
# accept_master (solo)
# ---------------------------------------------------------------------------


def test_accept_master_solo_renames_file(key, pki_dir):
    pending = pki_dir / "masters_pre" / "east.pub"
    _write_pub(pending)

    ret = key.accept("east")
    accepted = pki_dir / "masters" / "east.pub"
    assert accepted.exists()
    assert not pending.exists()
    assert ret == {"accepted": ["east"]}


def test_accept_master_solo_fires_event(key, pki_dir):
    _write_pub(pki_dir / "masters_pre" / "east.pub")
    key.accept("east")
    assert key.event.fired
    data, tag = key.event.fired[-1]
    assert data["act"] == "accept"
    assert data["id"] == "east"
    assert data["scope"] == "master"
    assert tag.startswith("salt/key")


def test_accept_master_solo_missing_pending_noop(key):
    ret = key.accept("east")
    assert ret == {"accepted": []}


# ---------------------------------------------------------------------------
# reject_master (solo)
# ---------------------------------------------------------------------------


def test_reject_master_solo_renames_file(key, pki_dir):
    pending = pki_dir / "masters_pre" / "east.pub"
    _write_pub(pending)

    ret = key.reject("east")
    rejected = pki_dir / "masters_rejected" / "east.pub"
    assert rejected.exists()
    assert not pending.exists()
    assert ret == {"rejected": ["east"]}


def test_reject_master_missing_pending_noop(key):
    ret = key.reject("east")
    assert ret == {"rejected": []}


# ---------------------------------------------------------------------------
# delete_master (solo)
# ---------------------------------------------------------------------------


def test_delete_master_solo_removes_file(key, pki_dir):
    accepted = pki_dir / "masters" / "east.pub"
    _write_pub(accepted)

    ret = key.delete_key("east")
    assert not accepted.exists()
    assert ret == {"deleted": ["east"]}


def test_delete_master_solo_missing_still_returns_ok(key):
    """
    Deleting a non-existent key is a no-op on disk but still
    reports success so the operator does not get spurious errors
    on cleanup.
    """
    ret = key.delete_key("east")
    assert ret == {"deleted": ["east"]}


# ---------------------------------------------------------------------------
# finger_master
# ---------------------------------------------------------------------------


def test_finger_master_computes_expected_sha256(key, pki_dir):
    _write_pub(pki_dir / "masters" / "east.pub")
    expected = salt.utils.crypt.pem_finger(key=FAKE_PUB, sum_type="sha256")

    assert key.finger("east") == expected


def test_finger_master_honours_opts_hash_type(key, pki_dir):
    """
    When no hash_type is passed, ``finger_master`` falls back to
    ``opts["hash_type"]``.
    """
    _write_pub(pki_dir / "masters" / "east.pub")
    key.opts["hash_type"] = "sha512"
    expected = salt.utils.crypt.pem_finger(key=FAKE_PUB, sum_type="sha512")
    assert key.finger("east") == expected


def test_finger_master_missing_returns_empty_string(key):
    assert key.finger("east") == ""


# ---------------------------------------------------------------------------
# cluster_id validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "UPPER",
        "spaces here",
        "has/slash",
        "has.dot",
        "__identity_pub__",
        "__peer_index__",
        "__cluster_meta__",
    ],
)
def test_accept_master_rejects_invalid_cluster_id(key, bad):
    with pytest.raises(ValueError):
        key.accept(bad)


@pytest.mark.parametrize("bad", ["", "BAD", "__identity_pub__"])
def test_reject_master_rejects_invalid_cluster_id(key, bad):
    with pytest.raises(ValueError):
        key.reject(bad)


@pytest.mark.parametrize("bad", ["", "BAD", "__peer_index__"])
def test_delete_master_rejects_invalid_cluster_id(key, bad):
    with pytest.raises(ValueError):
        key.delete_key(bad)


# ---------------------------------------------------------------------------
# KeyCLI parser dispatch: --master routes to the master-scope method
# ---------------------------------------------------------------------------


class _DummyWheelClient:
    """Replaces :class:`salt.wheel.WheelClient` so ``KeyCLI`` ctor
    doesn't try to stand up a real one in a unit test."""

    def destroy(self):
        pass


class _DummyKey:
    """
    Minimal stand-in for :class:`salt.key.Key` that records which
    method the CLI dispatched to.
    """

    PEND = "minions_pre"
    ACC = "minions"
    REJ = "minions_rejected"
    DEN = "minions_denied"

    def __init__(self):
        self.calls = []

    def accept_master(self, cluster_id):
        self.calls.append(("accept_master", cluster_id))
        return {"accepted": [cluster_id]}

    def accept(self, *args, **kwargs):
        self.calls.append(("accept", args, kwargs))
        return {self.PEND: []}

    def delete_master(self, cluster_id):
        self.calls.append(("delete_master", cluster_id))
        return {"deleted": [cluster_id]}

    def delete_key(self, *args, **kwargs):
        self.calls.append(("delete_key", args, kwargs))
        return {self.PEND: []}

    def list_master(self):
        self.calls.append(("list_master",))
        return {"accepted": [], "pending": [], "rejected": [], "denied": []}

    def list_status(self, match):
        self.calls.append(("list_status", match))
        return {}

    def finger_master(self, cluster_id):
        self.calls.append(("finger_master", cluster_id))
        return "deadbeef"

    def finger(self, *args, **kwargs):
        self.calls.append(("finger", args, kwargs))
        return {}


def _make_keycli(master_scope, cmd, match="east", monkeypatch=None):
    """
    Build a :class:`KeyCLI` whose ``self.key`` is a recorder.

    Both the real :class:`salt.wheel.WheelClient` and the real
    :class:`salt.key.Key` constructor are substituted out so this
    unit test does not stand up any filesystem state.
    """
    opts = {
        "master_scope": master_scope,
        "client_auth": False,
        "eauth": "",
        "cachedir": "/tmp",
        "keys.cache_driver": "localfs_key",
        "gen_keys": "",
        "gen_signature": False,
        "list": "",
        "list_all": False,
        "print": "",
        "print_all": False,
        "accept": "",
        "accept_all": False,
        "reject": "",
        "reject_all": False,
        "delete": "",
        "delete_all": False,
        "finger": "",
        "finger_all": False,
        # Client-scope opts added by upstream PR #70656 remote-CLI.
        # Not used by master-scope tests, but ``_update_opts`` iterates
        # over them so they must be present.
        "list_clients": "",
        "accept_client": "",
        "reject_client": "",
        "print_client": "",
        "delete_client": "",
        "finger_client": "",
        "include_all": False,
        "include_rejected": False,
        "include_accepted": False,
        "include_denied": False,
    }
    opts[cmd] = match if not cmd.endswith("_all") else True
    # ``KeyCLI.__init__`` imports ``salt.wheel`` and builds a
    # WheelClient --- substitute a dummy to keep the unit test cheap.
    # It also calls :func:`salt.key.get_key` which tries to open the
    # cache; stub both.  Upstream PR #70656 added ``ClientKey`` --
    # stub it too so the test does not open the keys cache.
    import salt.wheel

    recorder = _DummyKey()
    master_recorder = _DummyKey()
    monkeypatch.setattr(salt.wheel, "WheelClient", lambda *a, **kw: _DummyWheelClient())
    monkeypatch.setattr(salt.key, "get_key", lambda _opts: recorder)
    monkeypatch.setattr(salt.key, "MasterKey", lambda *a, **kw: master_recorder)
    monkeypatch.setattr(salt.key, "ClientKey", lambda *a, **kw: _DummyKey())
    cli = salt.key.KeyCLI(opts)
    cli.key = recorder
    cli.master_key = master_recorder
    return cli


def test_master_scope_accept_dispatches_to_master_key_accept(monkeypatch):
    """``--master accept east`` -> ``MasterKey.accept("east")``.

    Post-unification, master-scope dispatches to the
    :class:`MasterKey` subclass via ``cli.master_key`` using the
    base-class public method name ``accept``, not the old
    ``accept_master`` legacy name on ``cli.key``.
    """
    cli = _make_keycli(
        master_scope=True, cmd="accept", match="east", monkeypatch=monkeypatch
    )
    cli._update_opts()
    cli._run_cmd("accept", args=["east"])
    assert ("accept", ("east",), {}) in cli.master_key.calls
    assert not cli.key.calls, "master-scope must not touch the minion Key"


def test_master_scope_delete_dispatches_to_master_key_delete_key(monkeypatch):
    cli = _make_keycli(
        master_scope=True, cmd="delete", match="east", monkeypatch=monkeypatch
    )
    cli._update_opts()
    cli._run_cmd("delete", args=["east"])
    # CLI_KEY_MAP maps "delete" -> "delete_key".
    assert ("delete_key", ("east",), {}) in cli.master_key.calls
    assert not cli.key.calls


def test_master_scope_list_dispatches_to_master_key(monkeypatch):
    cli = _make_keycli(
        master_scope=True, cmd="list_all", match=True, monkeypatch=monkeypatch
    )
    cli._update_opts()
    # ``args=None`` routes through ``_get_args_kwargs`` which fills
    # positional args from opts, matching the real salt-key flow.
    cli._run_cmd("list")
    # CLI_KEY_MAP maps ``list`` -> ``list_status``.  MasterKey's
    # ``list_status`` is an alias for ``list_keys`` (the four
    # bucket inventory).  The important invariant here is that
    # dispatch hits the MasterKey instance, not the minion Key.
    names = [call[0] for call in cli.master_key.calls]
    assert "list_status" in names, (
        f"master-scope list should route to MasterKey.list_status, "
        f"got {cli.master_key.calls!r}"
    )
    assert not cli.key.calls


def test_master_scope_finger_dispatches_to_master_key_finger(monkeypatch):
    cli = _make_keycli(
        master_scope=True, cmd="finger", match="east", monkeypatch=monkeypatch
    )
    cli._update_opts()
    cli._run_cmd("finger", args=["east"])
    assert ("finger", ("east",), {}) in cli.master_key.calls
    assert not cli.key.calls


def test_default_scope_uses_minion_methods(monkeypatch):
    """Without ``master_scope``, the dispatch still lands on the
    legacy minion-scope method."""
    cli = _make_keycli(
        master_scope=False, cmd="accept", match="east", monkeypatch=monkeypatch
    )
    cli._update_opts()
    cli._run_cmd("accept", args=["east"])
    names = [call[0] for call in cli.key.calls]
    assert "accept" in names
    assert not cli.master_key.calls, "default scope must not touch MasterKey"


# ---------------------------------------------------------------------------
# ``--kind`` unifying flag
#
# Unit coverage for the post-rebase operator-UX unification: a single
# ``--kind {minion|master|client}`` flag that maps to the legacy
# ``--master`` boolean / ``--list-clients`` family.  Every test builds
# a KeyCLI with a specific ``kind`` opt, drives ``_update_opts()``,
# and asserts the resulting opts dict shape matches what the legacy
# flag sets.
# ---------------------------------------------------------------------------


def _make_kind_cli(kind, cmd, match, monkeypatch):
    """Like :func:`_make_keycli` but parametrised on ``kind`` only."""
    cli = _make_keycli(
        master_scope=False, cmd=cmd, match=match, monkeypatch=monkeypatch
    )
    cli.opts["kind"] = kind
    return cli


def test_kind_master_sets_master_scope(monkeypatch):
    """``--kind master`` must set ``master_scope`` so _run_cmd
    dispatches to MasterKey -- equivalent to the legacy ``--master``
    boolean flag."""
    cli = _make_kind_cli(
        kind="master", cmd="accept", match="east", monkeypatch=monkeypatch
    )
    assert cli.opts.get("master_scope") is False
    cli._update_opts()
    assert cli.opts["master_scope"] is True


def test_kind_client_rewrites_action_to_client_suffix(monkeypatch):
    """``--kind client accept east`` must become ``accept_client=east``
    so the legacy dispatch picks ClientKey.  The non-client ``accept``
    is cleared so the dispatch loop stops on the client variant."""
    cli = _make_kind_cli(
        kind="client", cmd="accept", match="alice", monkeypatch=monkeypatch
    )
    assert cli.opts["accept"] == "alice"
    assert cli.opts["accept_client"] == ""
    cli._update_opts()
    assert cli.opts["accept"] == ""
    assert cli.opts["accept_client"] == "alice"
    assert cli.opts["fun"] == "accept_client"


def test_kind_minion_is_default_no_op(monkeypatch):
    """``--kind minion`` (or no ``--kind``) leaves opts untouched."""
    cli = _make_kind_cli(
        kind="minion", cmd="accept", match="webmnn", monkeypatch=monkeypatch
    )
    cli._update_opts()
    assert cli.opts["accept"] == "webmnn"
    assert cli.opts.get("master_scope") is False
    assert cli.opts.get("accept_client", "") == ""
    assert cli.opts["fun"] == "accept"


def test_kind_client_does_not_override_explicit_client_opt(monkeypatch):
    """When the operator passes BOTH ``--kind client`` AND an explicit
    ``--accept-client=alice``, the explicit value wins; we do NOT
    overwrite it with the ``accept`` opt."""
    cli = _make_kind_cli(
        kind="client", cmd="accept_client", match="alice", monkeypatch=monkeypatch
    )
    # The legacy ``--accept-client=alice`` already populated accept_client.
    # ``--kind client`` alone (with empty accept) must not clear it.
    cli._update_opts()
    assert cli.opts["accept_client"] == "alice"
    assert cli.opts["fun"] == "accept_client"
