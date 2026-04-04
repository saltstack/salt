import pytest

import salt.runners.pki
from tests.support.mock import MagicMock, patch


@pytest.fixture
def opts(tmp_path):
    return {
        "pki_index_enabled": True,
        "sock_dir": str(tmp_path / "sock"),
    }


def test_rebuild_index_success(opts):
    if not hasattr(salt.runners.pki, "__opts__"):
        salt.runners.pki.__opts__ = {}
    with patch("salt.utils.event.get_master_event") as mock_event_get:
        mock_event = MagicMock()
        mock_event_get.return_value.__enter__.return_value = mock_event

        # Simulate success event
        mock_event.get_event.return_value = {
            "tag": "salt/pki/index/rebuild/complete",
            "data": {"result": True},
        }

        with patch.dict(salt.runners.pki.__opts__, opts):
            res = salt.runners.pki.rebuild_index()
            assert res == "PKI index rebuild successful."
            mock_event.fire_event.assert_called_with({}, "salt/pki/index/rebuild")


def test_rebuild_index_timeout(opts):
    if not hasattr(salt.runners.pki, "__opts__"):
        salt.runners.pki.__opts__ = {}
    with patch("salt.utils.event.get_master_event") as mock_event_get:
        mock_event = MagicMock()
        mock_event_get.return_value.__enter__.return_value = mock_event

        # Simulate timeout
        mock_event.get_event.return_value = None

        with patch.dict(salt.runners.pki.__opts__, opts):
            res = salt.runners.pki.rebuild_index()
            assert res == "PKI index rebuild failed or timed out."


def test_rebuild_index_disabled(opts):
    if not hasattr(salt.runners.pki, "__opts__"):
        salt.runners.pki.__opts__ = {}
    opts["pki_index_enabled"] = False
    with patch.dict(salt.runners.pki.__opts__, opts):
        res = salt.runners.pki.rebuild_index()
        assert res == "PKI index is not enabled in configuration."
