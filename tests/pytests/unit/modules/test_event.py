"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>

    Test cases for salt.modules.event
"""

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
