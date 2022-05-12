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


def test_cloud_create_attempt_sync_after_install(master_config, vm_config):
    master_config["sync_after_install"] = "all"
    cloud = Cloud(master_config)
    cloud.clouds["test.create"] = lambda x: True

    with patch(
        "salt.client.get_local_client",
        MagicMock(return_value=MagicMock(return_value=True)),
    ):
        ret = cloud.create(vm_config)
    assert ret
