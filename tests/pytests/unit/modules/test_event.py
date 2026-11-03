"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>

    Test cases for salt.modules.event
"""

import gc
import warnings

import pytest

import salt.modules.event as event
import salt.utils.event
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules(minion_opts):
    return {event: {"__opts__": minion_opts}}


def test_fire_master():
    """
    Test for Fire an event off up to the master server
    """
    with patch("salt.crypt.SAuth") as salt_crypt_sauth, patch(
        "salt.channel.client.ReqChannel.factory"
    ) as salt_transport_channel_factory:

        preload = {
            "id": "id",
            "tag": "tag",
            "data": "data",
            "tok": "salt",
            "cmd": "_minion_event",
        }

        with patch.dict(
            event.__opts__,
            {"transport": "A", "master_uri": "localhost", "local": False},
        ):
            with patch.object(salt_crypt_sauth, "gen_token", return_value="tok"):
                with patch.object(
                    salt_transport_channel_factory, "send", return_value=None
                ):
                    assert event.fire_master("data", "tag", preload)

        with patch.dict(event.__opts__, {"transport": "A", "local": False}):
            with patch.object(
                salt.utils.event.MinionEvent,
                "fire_event",
                side_effect=Exception("foo"),
            ):
                assert not event.fire_master("data", "tag")


def test_fire():
    """
    Test to fire an event on the local minion event bus.
    Data must be formed as a dict.
    """
    with patch("salt.utils.event") as salt_utils_event:
        with patch.object(salt_utils_event, "get_event") as mock:
            mock.fire_event = MagicMock(return_value=True)
            assert event.fire("data", "tag")


def test_send():
    """
    Test for Send an event to the Salt Master
    """
    with patch.object(event, "fire_master", return_value="B"):
        assert event.send("tag") == "B"


def test_send_use_master_when_local_false():
    """
    Test for Send an event when opts has use_master_when_local and its False
    """
    patch_master_opts = patch.dict(event.__opts__, {"use_master_when_local": False})
    patch_file_client = patch.dict(event.__opts__, {"file_client": "local"})
    with patch.object(event, "fire", return_value="B") as patch_send:
        with patch_master_opts, patch_file_client, patch_send:
            assert event.send("tag") == "B"
            patch_send.assert_called_once()


def test_send_use_master_when_local_true():
    """
    Test for Send an event when opts has use_master_when_local and its True
    """
    patch_master_opts = patch.dict(event.__opts__, {"use_master_when_local": True})
    patch_file_client = patch.dict(event.__opts__, {"file_client": "local"})
    with patch.object(event, "fire_master", return_value="B") as patch_send:
        with patch_master_opts, patch_file_client, patch_send:
            assert event.send("tag") == "B"
            patch_send.assert_called_once()


def test_fire_master_context_managed_no_unclosed_warnings(tmp_path):
    """
    Regression test for issue #70175.

    ``salt.modules.event.fire_master`` used to construct a temporary
    ``MinionEvent`` in an expression, call ``.fire_event()`` on it, and
    return the result -- e.g.::

        return salt.utils.event.MinionEvent(__opts__, listen=False).fire_event(...)

    That fire-and-forget form left the ``MinionEvent`` unreferenced and
    reliant on GC to invoke ``__del__`` (see ``SaltEvent.__del__`` in
    ``salt/utils/event.py``).  Each per-job call therefore emitted one
    three-warning triad from the underlying transport chain when the
    finalizer eventually ran:

        - ``unclosed publish server <PublishServer ...>``
        - ``unclosed publisher client <_TCPPubServerPublisher ...>``
        - ``unclosed SyncWrapper for cls=<class '..._TCPPubServerPublisher'>``

    On a 3008.x minion under mixed-job load this surfaced as ~3 warnings
    per job (issue #70175 reports 646 warnings across ~200 jobs -- the
    file descriptors backing each unclosed publisher pinned an
    ``PublishServer`` graph until GC ran).

    The fix wraps the ``MinionEvent`` in a ``with`` block so
    ``__exit__`` -> ``destroy()`` -> ``close_pub()`` / ``close_pull()``
    tears down the ``SyncWrapper`` -> ``_TCPPubServerPublisher`` chain
    synchronously.

    Pre-patch failure mode against N=50 iterations::

        AssertionError: fire_master leaked 143 unclosed-resource warnings
        across 50 iterations (expected 0).  Sample warnings:
          - unclosed publisher client <_TCPPubServerPublisher ...>
          - unclosed publish server <PublishServer ...>
          - unclosed SyncWrapper for cls=<class '..._TCPPubServerPublisher'>

    Post-patch: 0 warnings.
    """
    tmp_sock = tmp_path / "sock"
    tmp_sock.mkdir()
    opts = {
        "id": "test-minion",
        "sock_dir": str(tmp_sock),
        "transport": "tcp",
        "ipc_mode": "ipc",
        "hash_type": "sha256",
        "acceptance_wait_time": 0,
        "acceptance_wait_time_max": 0,
        "loop_interval": 60,
        "local": False,
        "use_master_when_local": False,
        "max_event_size": 1048576,
    }

    triad_markers = (
        "unclosed publish server",
        "unclosed publisher client",
        "unclosed SyncWrapper",
    )
    n_iterations = 50
    with patch.dict(event.__opts__, opts):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ResourceWarning)
            warnings.simplefilter("always")
            for i in range(n_iterations):
                event.fire_master({"i": i}, f"test/tag/{i}")
            # Force any deferred ``__del__`` runs.
            gc.collect()
            gc.collect()

        leaked = [
            str(record.message)
            for record in caught
            if any(marker in str(record.message) for marker in triad_markers)
        ]

    assert not leaked, (
        f"fire_master leaked {len(leaked)} unclosed-resource warnings "
        f"across {n_iterations} iterations (expected 0).  Sample warnings:\n"
        + "\n".join(f"  - {msg[:160]}" for msg in leaked[:6])
    )
