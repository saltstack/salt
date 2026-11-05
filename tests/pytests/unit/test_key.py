"""
Unit tests for ``salt.key.Key``.

Guards the sender/receiver contract between
``salt.key.Key.change_state`` -> ``salt/key`` event ->
``salt.master.EventMonitor._apply_peer_key_change``.  Peer masters in a
cluster drop any event whose ``act`` isn't in
``EventMonitor._PEER_KEY_STATE`` (plus the hard-coded ``deny``/``delete``
branches); a typo in ``ACT_MAP`` can silently break salt-key replication
on an isolated-filesystem cluster.  See discussion on PR #70428 and
issue #70401.
"""

import pytest

import salt.key
import salt.master
from tests.support.mock import MagicMock, patch

RECEIVER_ACTS = set(salt.master.EventMonitor._PEER_KEY_STATE) | {"deny", "delete"}


@pytest.fixture
def key_instance():
    """
    A ``salt.key.Key`` with its network/filesystem/event dependencies
    stubbed so ``change_state`` can be exercised in isolation.
    """
    opts = {
        "__role": "master",
        "keys.cache_driver": "localfs_key",
        "pki_dir": "/tmp/does-not-exist",
        "cluster_id": None,
        "cluster_pki_dir": "",
        "signing_key_pass": None,
        "sock_dir": "/tmp/does-not-exist",
    }
    with patch("salt.cache.Cache", autospec=True) as cache_cls, patch(
        "salt.utils.sdb.sdb_get", return_value=None
    ), patch("salt.crypt.PublicKey.from_str"):
        key = salt.key.Key(opts)
        # Prime the cached_property so change_state uses our mock.
        event_mock = MagicMock()
        key.__dict__["event"] = event_mock
        # ``cache_cls`` is the ``Cache`` constructor; the instance Key
        # built in __init__ is its return_value.
        key.cache = cache_cls.return_value
        yield key


@pytest.mark.parametrize(
    "to_state",
    [salt.key.Key.ACC, salt.key.Key.REJ, salt.key.Key.PEND],
)
def test_change_state_fires_act_the_receiver_handles(key_instance, to_state):
    """
    For each ``to_state`` the sender exposes via ``change_state``, the
    fired ``salt/key`` event must carry (a) an ``act`` the cluster peer
    actually dispatches on and (b) a ``pub`` payload the receiver can
    store verbatim as a str.
    """
    keyname = "testminion"
    key_instance.cache.fetch.return_value = {
        "pub": "-----BEGIN PUBLIC KEY-----\nFAKEBODY\n-----END PUBLIC KEY-----",
        "state": "pending",
    }
    match_dict = {salt.key.Key.PEND: [keyname]}

    key_instance.change_state(salt.key.Key.PEND, to_state, match_dict=match_dict)

    assert key_instance.event.fire_event.call_count == 1
    eload, _tag = key_instance.event.fire_event.call_args.args
    assert eload["id"] == keyname
    assert eload["act"] in RECEIVER_ACTS, (
        f"change_state fired act={eload['act']!r} which "
        f"EventMonitor._apply_peer_key_change will silently drop; "
        f"receiver handles only {sorted(RECEIVER_ACTS)}"
    )
    assert isinstance(eload["pub"], str), (
        f"change_state fired pub of type {type(eload['pub']).__name__}; "
        f"receiver stores pub verbatim and expects a str"
    )


def test_act_map_covers_every_state():
    """
    Every state constant on ``Key`` must have a corresponding entry in
    ``ACT_MAP``, otherwise ``change_state`` would KeyError on a
    hypothetical caller passing that state.
    """
    for state in (
        salt.key.Key.ACC,
        salt.key.Key.REJ,
        salt.key.Key.PEND,
        salt.key.Key.DEN,
    ):
        assert state in salt.key.Key.ACT_MAP


def test_key_destroy_is_idempotent():
    key = object.__new__(salt.key.Key)
    event = MagicMock()
    key.__dict__["event"] = event

    key.destroy()
    key.destroy()

    event.destroy.assert_called_once_with()
    assert "event" not in key.__dict__


def test_key_cli_context_destroys_local_key():
    key_cli = object.__new__(salt.key.KeyCLI)
    key_cli.opts = {"eauth": ""}
    key_cli.key = MagicMock()

    with key_cli:
        pass

    key_cli.key.destroy.assert_called_once_with()


def test_key_cli_context_does_not_destroy_key_class_for_eauth():
    key_cli = object.__new__(salt.key.KeyCLI)
    key_cli.opts = {"eauth": "pam"}
    key_cli.key = salt.key.Key

    with key_cli:
        pass
