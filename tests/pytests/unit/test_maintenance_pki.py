import pytest

import salt.master
import salt.utils.pki
from tests.support.mock import MagicMock, patch


@pytest.fixture
def opts(tmp_path):
    pki_dir = tmp_path / "pki"
    pki_dir.mkdir()
    return {
        "pki_index_enabled": True,
        "pki_dir": str(pki_dir),
        "pki_index_size": 100,
        "pki_index_slot_size": 64,
        "sock_dir": str(tmp_path / "sock"),
        "loop_interval": 1,
        "maintenance_interval": 1,
        "transport": "zeromq",
    }


def test_handle_pki_index_events(opts):
    maint = salt.master.Maintenance(opts)
    maint.event = MagicMock()
    maint.ckminions = MagicMock()

    # 1. Simulate an 'accepted' event
    maint.event.get_event.side_effect = [
        {"tag": "salt/key/accepted", "data": {"act": "accepted", "id": "minion1"}},
        None,  # Break the while True loop
    ]

    with patch("salt.utils.pki.PkiIndex.rebuild"):
        maint.handle_pki_index()
        assert maint.pki_index.contains("minion1") is True

    # 2. Simulate a 'delete' event
    maint.event.get_event.side_effect = [
        {"tag": "salt/key/delete", "data": {"act": "delete", "id": "minion1"}},
        None,
    ]
    maint.handle_pki_index()
    assert maint.pki_index.contains("minion1") is False


def test_handle_pki_index_rebuild_event(opts):
    maint = salt.master.Maintenance(opts)
    maint.event = MagicMock()
    maint.ckminions = MagicMock()
    maint.ckminions._pki_minions.return_value = {"minion_a", "minion_b"}

    # Simulate a manual rebuild trigger
    maint.event.get_event.side_effect = [
        {"tag": "salt/pki/index/rebuild", "data": {}},
        None,
    ]

    maint.handle_pki_index()

    assert maint.pki_index.contains("minion_a") is True
    assert maint.pki_index.contains("minion_b") is True
    maint.event.fire_event.assert_any_call(
        {"result": True}, "salt/pki/index/rebuild/complete"
    )
