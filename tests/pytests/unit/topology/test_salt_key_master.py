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
    k = salt.key.Key(opts)
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

    ret = key.list_master()
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

    ret = key.list_master()
    assert ret["accepted"] == ["real"]


# ---------------------------------------------------------------------------
# accept_master (solo)
# ---------------------------------------------------------------------------


def test_accept_master_solo_renames_file(key, pki_dir):
    pending = pki_dir / "masters_pre" / "east.pub"
    _write_pub(pending)

    ret = key.accept_master("east")
    accepted = pki_dir / "masters" / "east.pub"
    assert accepted.exists()
    assert not pending.exists()
    assert ret == {"accepted": ["east"]}


def test_accept_master_solo_fires_event(key, pki_dir):
    _write_pub(pki_dir / "masters_pre" / "east.pub")
    key.accept_master("east")
    assert key.event.fired
    data, tag = key.event.fired[-1]
    assert data["act"] == "accept"
    assert data["id"] == "east"
    assert data["scope"] == "master"
    assert tag.startswith("salt/key")


def test_accept_master_solo_missing_pending_noop(key):
    ret = key.accept_master("east")
    assert ret == {"accepted": []}


# ---------------------------------------------------------------------------
# reject_master (solo)
# ---------------------------------------------------------------------------


def test_reject_master_solo_renames_file(key, pki_dir):
    pending = pki_dir / "masters_pre" / "east.pub"
    _write_pub(pending)

    ret = key.reject_master("east")
    rejected = pki_dir / "masters_rejected" / "east.pub"
    assert rejected.exists()
    assert not pending.exists()
    assert ret == {"rejected": ["east"]}


def test_reject_master_missing_pending_noop(key):
    ret = key.reject_master("east")
    assert ret == {"rejected": []}


# ---------------------------------------------------------------------------
# delete_master (solo)
# ---------------------------------------------------------------------------


def test_delete_master_solo_removes_file(key, pki_dir):
    accepted = pki_dir / "masters" / "east.pub"
    _write_pub(accepted)

    ret = key.delete_master("east")
    assert not accepted.exists()
    assert ret == {"deleted": ["east"]}


def test_delete_master_solo_missing_still_returns_ok(key):
    """
    Deleting a non-existent key is a no-op on disk but still
    reports success so the operator does not get spurious errors
    on cleanup.
    """
    ret = key.delete_master("east")
    assert ret == {"deleted": ["east"]}


# ---------------------------------------------------------------------------
# finger_master
# ---------------------------------------------------------------------------


def test_finger_master_computes_expected_sha256(key, pki_dir):
    _write_pub(pki_dir / "masters" / "east.pub")
    expected = salt.utils.crypt.pem_finger(key=FAKE_PUB, sum_type="sha256")

    assert key.finger_master("east") == expected


def test_finger_master_honours_opts_hash_type(key, pki_dir):
    """
    When no hash_type is passed, ``finger_master`` falls back to
    ``opts["hash_type"]``.
    """
    _write_pub(pki_dir / "masters" / "east.pub")
    key.opts["hash_type"] = "sha512"
    expected = salt.utils.crypt.pem_finger(key=FAKE_PUB, sum_type="sha512")
    assert key.finger_master("east") == expected


def test_finger_master_missing_returns_empty_string(key):
    assert key.finger_master("east") == ""


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
        key.accept_master(bad)


@pytest.mark.parametrize("bad", ["", "BAD", "__identity_pub__"])
def test_reject_master_rejects_invalid_cluster_id(key, bad):
    with pytest.raises(ValueError):
        key.reject_master(bad)


@pytest.mark.parametrize("bad", ["", "BAD", "__peer_index__"])
def test_delete_master_rejects_invalid_cluster_id(key, bad):
    with pytest.raises(ValueError):
        key.delete_master(bad)


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
        "eauth": "",
        "cachedir": "/tmp",
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
        "include_all": False,
        "include_rejected": False,
        "include_accepted": False,
        "include_denied": False,
    }
    opts[cmd] = match if not cmd.endswith("_all") else True
    # ``KeyCLI.__init__`` imports ``salt.wheel`` and builds a
    # WheelClient --- substitute a dummy to keep the unit test cheap.
    # It also calls :func:`salt.key.get_key` which tries to open the
    # cache; stub both.
    import salt.wheel

    recorder = _DummyKey()
    monkeypatch.setattr(salt.wheel, "WheelClient", lambda *a, **kw: _DummyWheelClient())
    monkeypatch.setattr(salt.key, "get_key", lambda _opts: recorder)
    cli = salt.key.KeyCLI(opts)
    cli.key = recorder
    return cli


def test_master_scope_accept_dispatches_to_accept_master(monkeypatch):
    cli = _make_keycli(
        master_scope=True, cmd="accept", match="east", monkeypatch=monkeypatch
    )
    cli._update_opts()
    cli._run_cmd("accept", args=["east"])
    assert ("accept_master", "east") in cli.key.calls


def test_master_scope_delete_dispatches_to_delete_master(monkeypatch):
    cli = _make_keycli(
        master_scope=True, cmd="delete", match="east", monkeypatch=monkeypatch
    )
    cli._update_opts()
    cli._run_cmd("delete", args=["east"])
    assert ("delete_master", "east") in cli.key.calls


def test_master_scope_list_dispatches_to_list_master(monkeypatch):
    cli = _make_keycli(
        master_scope=True, cmd="list_all", match=True, monkeypatch=monkeypatch
    )
    cli._update_opts()
    cli._run_cmd("list", args=[])
    assert ("list_master",) in cli.key.calls


def test_master_scope_finger_dispatches_to_finger_master(monkeypatch):
    cli = _make_keycli(
        master_scope=True, cmd="finger", match="east", monkeypatch=monkeypatch
    )
    cli._update_opts()
    cli._run_cmd("finger", args=["east"])
    assert ("finger_master", "east") in cli.key.calls


def test_default_scope_uses_minion_methods(monkeypatch):
    """Without ``master_scope``, the dispatch still lands on the
    legacy minion-scope method."""
    cli = _make_keycli(
        master_scope=False, cmd="accept", match="east", monkeypatch=monkeypatch
    )
    cli._update_opts()
    cli._run_cmd("accept", args=["east"])
    # The default accept path goes through CLI_KEY_MAP ("accept"
    # -> "accept"), so we expect our dummy's ``accept`` to be the
    # one that got called, not ``accept_master``.
    names = [call[0] for call in cli.key.calls]
    assert "accept" in names
    assert "accept_master" not in names


def test_cli_key_master_map_covers_main_actions():
    """Sanity: the master-scope map includes list/accept/reject/
    delete/finger so ``--master`` works for all of them."""
    for action in ("list", "accept", "reject", "delete", "finger"):
        assert action in salt.key.KeyCLI.CLI_KEY_MASTER_MAP, (
            f"CLI_KEY_MASTER_MAP missing {action!r}; --master {action} "
            f"would silently fall back to the minion-scope method"
        )
