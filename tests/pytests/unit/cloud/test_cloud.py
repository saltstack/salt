import pytest

from salt.cloud import Cloud
from salt.exceptions import SaltCloudSystemExit
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.timeout_unless_on_windows(120),
]


@pytest.fixture
def master_config(master_opts):
    master_opts["parallel"] = False
    master_opts["providers"] = {
        "test": {},
    }
    return master_opts


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


@pytest.mark.slow_test
def test_vm_config_merger():
    """
    Validate the vm's config is generated correctly.

    https://github.com/saltstack/salt/issues/49226
    """
    main = {
        "minion": {"master": "172.31.39.213"},
        "log_file": "var/log/salt/cloud.log",
        "pool_size": 10,
    }
    provider = {
        "private_key": "dwoz.pem",
        "grains": {"foo1": "bar", "foo2": "bang"},
        "availability_zone": "us-west-2b",
        "driver": "ec2",
        "ssh_interface": "private_ips",
        "ssh_username": "admin",
        "location": "us-west-2",
    }
    profile = {
        "profile": "default",
        "grains": {"meh2": "bar", "meh1": "foo"},
        "provider": "ec2-default:ec2",
        "ssh_username": "admin",
        "image": "ami-0a1fbca0e5b419fd1",
        "size": "t2.micro",
    }
    expected = {
        "minion": {"master": "172.31.39.213"},
        "log_file": "var/log/salt/cloud.log",
        "pool_size": 10,
        "private_key": "dwoz.pem",
        "grains": {
            "foo1": "bar",
            "foo2": "bang",
            "meh2": "bar",
            "meh1": "foo",
        },
        "availability_zone": "us-west-2b",
        "driver": "ec2",
        "ssh_interface": "private_ips",
        "ssh_username": "admin",
        "location": "us-west-2",
        "profile": "default",
        "provider": "ec2-default:ec2",
        "image": "ami-0a1fbca0e5b419fd1",
        "size": "t2.micro",
        "name": "test_vm",
    }
    vm = Cloud.vm_config("test_vm", main, provider, profile, {})
    assert expected == vm


@pytest.mark.skip_on_fips_enabled_platform
def test_cloud_run_profile_create_returns_boolean(master_config):

    master_config["profiles"] = {"test_profile": {"provider": "test_provider:saltify"}}
    master_config["providers"] = {
        "test_provider": {
            "saltify": {"profiles": {"provider": "test_provider:saltify"}}
        }
    }
    master_config["show_deploy_args"] = False

    cloud = Cloud(master_config)
    with patch.object(cloud, "create", return_value=True):
        ret = cloud.run_profile("test_profile", ["test_vm"])
        assert ret == {"test_vm": True}

    cloud = Cloud(master_config)
    with patch.object(cloud, "create", return_value=False):
        with pytest.raises(SaltCloudSystemExit):
            ret = cloud.run_profile("test_profile", ["test_vm"])
            assert ret == {"test_vm": False}
