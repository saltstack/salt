import copy

import pytest

import salt.config
from salt.cloud import Cloud
from tests.support.mock import MagicMock, patch


@pytest.fixture
def master_config():
    opts = copy.deepcopy(salt.config.DEFAULT_MASTER_OPTS)
    opts["parallel"] = False
    opts["providers"] = {
        "test": {},
    }
    return opts


@pytest.fixture
def vm_config():
    return {
        "driver": "test",
        "name": "test",
        "provider": "test:test",
    }


@pytest.mark.parametrize(
    "sync, expected_func",
    (
        ("all", "saltutil.sync_all"),
        ("beacons", "saltutil.sync_beacons"),
        ("clouds", "saltutil.sync_clouds"),
        ("engines", "saltutil.sync_engines"),
        ("executors", "saltutil.sync_executors"),
        ("grains", "saltutil.sync_grains"),
        ("log", "saltutil.sync_log"),
        ("matchers", "saltutil.sync_matchers"),
        ("modules", "saltutil.sync_modules"),
        ("output", "saltutil.sync_output"),
        ("pillar", "saltutil.sync_pillar"),
        ("proxymodules", "saltutil.sync_proxymodules"),
        ("renderers", "saltutil.sync_renderers"),
        ("returners", "saltutil.sync_returners"),
        ("sdb", "saltutil.sync_sdb"),
        ("serializers", "saltutil.sync_serializers"),
        ("states", "saltutil.sync_states"),
        ("thorium", "saltutil.sync_thorium"),
        ("utils", "saltutil.sync_utils"),
        (
            "lol this is a bad sync option",
            "saltutil.sync_all",
        ),  # With a bad option it should default to all
    ),
)
def test_cloud_create_attempt_sync_after_install(
    master_config, vm_config, sync, expected_func
):
    master_config["sync_after_install"] = sync
    cloud = Cloud(master_config)
    cloud.clouds["test.create"] = lambda x: True

    fake_context_manager = MagicMock()
    fake_client = MagicMock(return_value=MagicMock(return_value=True))
    fake_context_manager.__enter__.return_value = fake_client
    with patch(
        "salt.client.get_local_client",
        autospec=True,
        return_value=fake_context_manager,
    ):
        ret = cloud.create(vm_config, sync_sleep=0)
    assert ret
    fake_client.cmd.assert_called_with("test", expected_func, timeout=5)
