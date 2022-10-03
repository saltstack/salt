import pytest

import salt.config
import salt.runners.saltutil as saltutil
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    opts = salt.config.DEFAULT_MASTER_OPTS.copy()

    return {saltutil: {"opts": opts}}


def test_sync_all():
    sync_out = MagicMock(return_value=[[], True])
    roster_keys = [
        "clouds",
        "modules",
        "states",
        "grains",
        "renderers",
        "returners",
        "output",
        "proxymodules",
        "runners",
        "wheel",
        "engines",
        "thorium",
        "queues",
        "pillar",
        "utils",
        "sdb",
        "cache",
        "fileserver",
        "tops",
        "tokens",
        "serializers",
        "executors",
        "roster",
    ]
    with patch("salt.utils.extmods.sync", sync_out):
        ret = saltutil.sync_all()
        for key in roster_keys:
            assert key in ret


def test_sync_modules():
    sync_out = MagicMock(return_value=[[], True])
    with patch("salt.utils.extmods.sync", sync_out) as extmods_sync:
        ret = saltutil.sync_modules()
        assert ret == []

        extmods_sync.assert_called_with(
            {}, "modules", extmod_blacklist=None, extmod_whitelist=None, saltenv="base"
        )


def test_sync_states():
    sync_out = MagicMock(return_value=[[], True])
    with patch("salt.utils.extmods.sync", sync_out) as extmods_sync:
        ret = saltutil.sync_states()
        assert ret == []

        extmods_sync.assert_called_with(
            {}, "states", extmod_blacklist=None, extmod_whitelist=None, saltenv="base"
        )


def test_sync_grains():
    sync_out = MagicMock(return_value=[[], True])
    with patch("salt.utils.extmods.sync", sync_out) as extmods_sync:
        ret = saltutil.sync_grains()
        assert ret == []

        extmods_sync.assert_called_with(
            {}, "grains", extmod_blacklist=None, extmod_whitelist=None, saltenv="base"
        )


def test_sync_renderers():
    sync_out = MagicMock(return_value=[[], True])
    with patch("salt.utils.extmods.sync", sync_out) as extmods_sync:
        ret = saltutil.sync_renderers()
        assert ret == []

        extmods_sync.assert_called_with(
            {},
            "renderers",
            extmod_blacklist=None,
            extmod_whitelist=None,
            saltenv="base",
        )


def test_sync_returners():
    sync_out = MagicMock(return_value=[[], True])
    with patch("salt.utils.extmods.sync", sync_out) as extmods_sync:
        ret = saltutil.sync_returners()
        assert ret == []

        extmods_sync.assert_called_with(
            {},
            "returners",
            extmod_blacklist=None,
            extmod_whitelist=None,
            saltenv="base",
        )


def test_sync_output():
    sync_out = MagicMock(return_value=[[], True])
    with patch("salt.utils.extmods.sync", sync_out) as extmods_sync:
        ret = saltutil.sync_output()
        assert ret == []

        extmods_sync.assert_called_with(
            {}, "output", extmod_blacklist=None, extmod_whitelist=None, saltenv="base"
        )


def test_sync_proxymodules():
    sync_out = MagicMock(return_value=[[], True])
    with patch("salt.utils.extmods.sync", sync_out) as extmods_sync:
        ret = saltutil.sync_proxymodules()
        assert ret == []

        extmods_sync.assert_called_with(
            {}, "proxy", extmod_blacklist=None, extmod_whitelist=None, saltenv="base"
        )


def test_sync_runners():
    sync_out = MagicMock(return_value=[[], True])
    with patch("salt.utils.extmods.sync", sync_out) as extmods_sync:
        ret = saltutil.sync_runners()
        assert ret == []

        extmods_sync.assert_called_with(
            {}, "runners", extmod_blacklist=None, extmod_whitelist=None, saltenv="base"
        )


def test_sync_wheel():
    sync_out = MagicMock(return_value=[[], True])
    with patch("salt.utils.extmods.sync", sync_out) as extmods_sync:
        ret = saltutil.sync_wheel()
        assert ret == []

        extmods_sync.assert_called_with(
            {}, "wheel", extmod_blacklist=None, extmod_whitelist=None, saltenv="base"
        )


def test_sync_engines():
    sync_out = MagicMock(return_value=[[], True])
    with patch("salt.utils.extmods.sync", sync_out) as extmods_sync:
        ret = saltutil.sync_engines()
        assert ret == []

        extmods_sync.assert_called_with(
            {}, "engines", extmod_blacklist=None, extmod_whitelist=None, saltenv="base"
        )


def test_sync_thorium():
    sync_out = MagicMock(return_value=[[], True])
    with patch("salt.utils.extmods.sync", sync_out) as extmods_sync:
        ret = saltutil.sync_thorium()
        assert ret == []

        extmods_sync.assert_called_with(
            {}, "thorium", extmod_blacklist=None, extmod_whitelist=None, saltenv="base"
        )


def test_sync_queues():
    sync_out = MagicMock(return_value=[[], True])
    with patch("salt.utils.extmods.sync", sync_out) as extmods_sync:
        ret = saltutil.sync_queues()
        assert ret == []

        extmods_sync.assert_called_with(
            {}, "queues", extmod_blacklist=None, extmod_whitelist=None, saltenv="base"
        )


def test_sync_pillar():
    sync_out = MagicMock(return_value=[[], True])
    with patch("salt.utils.extmods.sync", sync_out) as extmods_sync:
        ret = saltutil.sync_pillar()
        assert ret == []

        extmods_sync.assert_called_with(
            {}, "pillar", extmod_blacklist=None, extmod_whitelist=None, saltenv="base"
        )


def test_sync_utils():
    sync_out = MagicMock(return_value=[[], True])
    with patch("salt.utils.extmods.sync", sync_out) as extmods_sync:
        ret = saltutil.sync_utils()
        assert ret == []

        extmods_sync.assert_called_with(
            {}, "utils", extmod_blacklist=None, extmod_whitelist=None, saltenv="base"
        )


def test_sync_sdb():
    sync_out = MagicMock(return_value=[[], True])
    with patch("salt.utils.extmods.sync", sync_out) as extmods_sync:
        ret = saltutil.sync_sdb()
        assert ret == []

        extmods_sync.assert_called_with(
            {}, "sdb", extmod_blacklist=None, extmod_whitelist=None, saltenv="base"
        )


def test_sync_tops():
    sync_out = MagicMock(return_value=[[], True])
    with patch("salt.utils.extmods.sync", sync_out) as extmods_sync:
        ret = saltutil.sync_tops()
        assert ret == []

        extmods_sync.assert_called_with(
            {}, "tops", extmod_blacklist=None, extmod_whitelist=None, saltenv="base"
        )


def test_sync_cache():
    sync_out = MagicMock(return_value=[[], True])
    with patch("salt.utils.extmods.sync", sync_out) as extmods_sync:
        ret = saltutil.sync_cache()
        assert ret == []

        extmods_sync.assert_called_with(
            {}, "cache", extmod_blacklist=None, extmod_whitelist=None, saltenv="base"
        )


def test_sync_fileserver():
    sync_out = MagicMock(return_value=[[], True])
    with patch("salt.utils.extmods.sync", sync_out) as extmods_sync:
        ret = saltutil.sync_fileserver()
        assert ret == []

        extmods_sync.assert_called_with(
            {},
            "fileserver",
            extmod_blacklist=None,
            extmod_whitelist=None,
            saltenv="base",
        )


def test_sync_clouds():
    sync_out = MagicMock(return_value=[[], True])
    with patch("salt.utils.extmods.sync", sync_out) as extmods_sync:
        ret = saltutil.sync_clouds()
        assert ret == []

        extmods_sync.assert_called_with(
            {}, "clouds", extmod_blacklist=None, extmod_whitelist=None, saltenv="base"
        )


def test_sync_roster():
    sync_out = MagicMock(return_value=[[], True])
    with patch("salt.utils.extmods.sync", sync_out) as extmods_sync:
        ret = saltutil.sync_roster()
        assert ret == []

        extmods_sync.assert_called_with(
            {}, "roster", extmod_blacklist=None, extmod_whitelist=None, saltenv="base"
        )


def test_sync_eauth_tokens():
    sync_out = MagicMock(return_value=[[], True])
    with patch("salt.utils.extmods.sync", sync_out) as extmods_sync:
        ret = saltutil.sync_eauth_tokens()
        assert ret == []

        extmods_sync.assert_called_with(
            {}, "tokens", extmod_blacklist=None, extmod_whitelist=None, saltenv="base"
        )


def test_sync_serializers():
    sync_out = MagicMock(return_value=[[], True])
    with patch("salt.utils.extmods.sync", sync_out) as extmods_sync:
        ret = saltutil.sync_serializers()
        assert ret == []

        extmods_sync.assert_called_with(
            {},
            "serializers",
            extmod_blacklist=None,
            extmod_whitelist=None,
            saltenv="base",
        )


def test_sync_executors():
    sync_out = MagicMock(return_value=[[], True])
    with patch("salt.utils.extmods.sync", sync_out) as extmods_sync:
        ret = saltutil.sync_executors()
        assert ret == []

        extmods_sync.assert_called_with(
            {},
            "executors",
            extmod_blacklist=None,
            extmod_whitelist=None,
            saltenv="base",
        )
