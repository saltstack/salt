"""
Unit tests for the docker module
"""

import logging

import pytest

import salt.loader
import salt.modules.dockermod as docker_mod
import salt.utils.platform
from salt.exceptions import CommandExecutionError, SaltInvocationError
from tests.support.mock import MagicMock, Mock, call, patch

log = logging.getLogger(__name__)

pytest.importorskip(
    "docker", reason="The python 'docker' package must be installed to run these tests"
)


@pytest.fixture
def configure_loader_modules(minion_opts):
    utils = salt.loader.utils(
        minion_opts,
        whitelist=[
            "args",
            "docker",
            "json",
            "state",
            "thin",
            "systemd",
            "path",
            "platform",
        ],
    )
    return {
        docker_mod: {
            "__context__": {"docker.docker_version": ""},
            "__utils__": utils,
        }
    }


def test_failed_login():
    """
    Check that when docker.login failed a retcode other then 0
    is part of the return.
    """
    client = Mock()
    get_client_mock = MagicMock(return_value=client)
    ref_out = {"stdout": "", "stderr": "login failed", "retcode": 1}
    with patch.dict(
        docker_mod.__pillar__,
        {
            "docker-registries": {
                "portus.example.com:5000": {
                    "username": "admin",
                    "password": "linux12345",
                    "email": "tux@example.com",
                }
            }
        },
    ):
        with patch.object(docker_mod, "_get_client", get_client_mock):
            dunder_salt = {
                "cmd.run_all": MagicMock(return_value=ref_out),
                "config.get": MagicMock(return_value={}),
                "config.option": MagicMock(return_value={}),
            }
            with patch.dict(docker_mod.__salt__, dunder_salt):
                ret = docker_mod.login("portus.example.com:5000")
                assert "retcode" in ret
                assert ret["retcode"] != 0


def test_logout_calls_docker_cli_logout_single():
    client = Mock()
    get_client_mock = MagicMock(return_value=client)
    ref_out = {"stdout": "", "stderr": "", "retcode": 0}
    registry_auth_data = {
        "portus.example.com:5000": {
            "username": "admin",
            "password": "linux12345",
            "email": "tux@example.com",
        }
    }
    docker_mock = MagicMock(return_value=ref_out)
    with patch.object(docker_mod, "_get_client", get_client_mock):
        dunder_salt = {
            "config.get": MagicMock(return_value=registry_auth_data),
            "cmd.run_all": docker_mock,
            "config.option": MagicMock(return_value={}),
        }
        with patch.dict(docker_mod.__salt__, dunder_salt):
            ret = docker_mod.logout("portus.example.com:5000")
            assert "retcode" in ret
            assert ret["retcode"] == 0
            docker_mock.assert_called_with(
                ["docker", "logout", "portus.example.com:5000"],
                python_shell=False,
                output_loglevel="quiet",
            )


def test_logout_calls_docker_cli_logout_all():
    client = Mock()
    get_client_mock = MagicMock(return_value=client)
    ref_out = {"stdout": "", "stderr": "", "retcode": 0}
    registry_auth_data = {
        "portus.example.com:5000": {
            "username": "admin",
            "password": "linux12345",
            "email": "tux@example.com",
        },
        "portus2.example.com:5000": {
            "username": "admin",
            "password": "linux12345",
            "email": "tux@example.com",
        },
    }

    docker_mock = MagicMock(return_value=ref_out)
    with patch.object(docker_mod, "_get_client", get_client_mock):
        dunder_salt = {
            "config.get": MagicMock(return_value=registry_auth_data),
            "cmd.run_all": docker_mock,
            "config.option": MagicMock(return_value={}),
        }
        with patch.dict(docker_mod.__salt__, dunder_salt):
            ret = docker_mod.logout()
            assert "retcode" in ret
            assert ret["retcode"] == 0
            assert docker_mock.call_count == 2


def test_ps_with_host_true():
    """
    Check that docker.ps called with host is ``True``,
    include resutlt of ``network.interfaces`` command in returned result.
    """
    client = Mock()
    client.containers = MagicMock(return_value=[])
    get_client_mock = MagicMock(return_value=client)
    network_interfaces = Mock(return_value={"mocked": None})

    with patch.dict(docker_mod.__salt__, {"network.interfaces": network_interfaces}):
        with patch.object(docker_mod, "_get_client", get_client_mock):
            ret = docker_mod.ps_(host=True)
            assert ret == {"host": {"interfaces": {"mocked": None}}}


def test_ps_with_filters():
    """
    Check that docker.ps accept filters parameter.
    """
    client = Mock()
    client.containers = MagicMock(return_value=[])
    get_client_mock = MagicMock(return_value=client)

    with patch.object(docker_mod, "_get_client", get_client_mock):
        docker_mod.ps_(filters={"label": "KEY"})
        client.containers.assert_called_once_with(all=True, filters={"label": "KEY"})


@pytest.mark.slow_test
@pytest.mark.parametrize(
    "command_name, args",
    (
        ("create", ()),
        ("rm_", ()),
        ("kill", ()),
        ("pause", ()),
        ("signal_", ("KILL",)),
        ("start_", ()),
        ("stop", ()),
        ("unpause", ()),
        ("_run", ("command",)),
        ("_script", ("command",)),
    ),
)
def test_check_mine_cache_is_refreshed_on_container_change_event(command_name, args):
    """
    Every command that might modify docker containers state.
    Should trig an update on ``mine.send``
    """
    if salt.utils.platform.is_windows() and command_name == "_script":
        pytest.skip(
            "Skipping test since `dockermod._script` will create a temporary file in /tmp "
            "which does not exist on windows"
        )
    with patch.object(docker_mod, "_get_exec_driver"):
        client_args_mock = MagicMock(
            return_value={
                "create_container": [
                    "image",
                    "command",
                    "hostname",
                    "user",
                    "detach",
                    "stdin_open",
                    "tty",
                    "ports",
                    "environment",
                    "volumes",
                    "network_disabled",
                    "name",
                    "entrypoint",
                    "working_dir",
                    "domainname",
                    "cpuset",
                    "host_config",
                    "mac_address",
                    "labels",
                    "volume_driver",
                    "stop_signal",
                    "networking_config",
                    "healthcheck",
                    "stop_timeout",
                ],
                "host_config": [
                    "binds",
                    "port_bindings",
                    "lxc_conf",
                    "publish_all_ports",
                    "links",
                    "privileged",
                    "dns",
                    "dns_search",
                    "volumes_from",
                    "network_mode",
                    "restart_policy",
                    "cap_add",
                    "cap_drop",
                    "devices",
                    "extra_hosts",
                    "read_only",
                    "pid_mode",
                    "ipc_mode",
                    "security_opt",
                    "ulimits",
                    "log_config",
                    "mem_limit",
                    "memswap_limit",
                    "mem_reservation",
                    "kernel_memory",
                    "mem_swappiness",
                    "cgroup_parent",
                    "group_add",
                    "cpu_quota",
                    "cpu_period",
                    "blkio_weight",
                    "blkio_weight_device",
                    "device_read_bps",
                    "device_write_bps",
                    "device_read_iops",
                    "device_write_iops",
                    "oom_kill_disable",
                    "shm_size",
                    "sysctls",
                    "tmpfs",
                    "oom_score_adj",
                    "dns_opt",
                    "cpu_shares",
                    "cpuset_cpus",
                    "userns_mode",
                    "pids_limit",
                    "isolation",
                    "auto_remove",
                    "storage_opt",
                ],
                "networking_config": [
                    "aliases",
                    "links",
                    "ipv4_address",
                    "ipv6_address",
                    "link_local_ips",
                ],
            }
        )

        mine_send = Mock()
        command = getattr(docker_mod, command_name)
        client = MagicMock()
        client.api_version = "1.12"
        with patch.dict(
            docker_mod.__salt__,
            {
                "mine.send": mine_send,
                "container_resource.run": MagicMock(),
                "config.get": MagicMock(return_value=True),
                "config.option": MagicMock(return_value=True),
                "cp.cache_file": MagicMock(return_value=False),
            },
        ):
            with patch.dict(
                docker_mod.__utils__,
                {"docker.get_client_args": client_args_mock},
            ):
                with patch.object(docker_mod, "_get_client", client):
                    command("container", *args)
        try:
            mine_send.assert_called_with("docker.ps", verbose=True, all=True, host=True)
        except AssertionError as exc:
            raise Exception(
                "command '{}' did not call docker.ps with expected "
                "arguments: {}".format(command_name, exc)
            )


def test_update_mine():
    """
    Test the docker.update_mine config option
    """

    def config_get_disabled(val, default):
        return {
            "base_url": docker_mod.NOTSET,
            "version": docker_mod.NOTSET,
            "docker.url": docker_mod.NOTSET,
            "docker.version": docker_mod.NOTSET,
            "docker.machine": docker_mod.NOTSET,
            "docker.update_mine": False,
        }[val]

    def config_get_enabled(val, default):
        return {
            "base_url": docker_mod.NOTSET,
            "version": docker_mod.NOTSET,
            "docker.url": docker_mod.NOTSET,
            "docker.version": docker_mod.NOTSET,
            "docker.machine": docker_mod.NOTSET,
            "docker.update_mine": True,
        }[val]

    mine_mock = Mock()
    dunder_salt = {
        "config.get": MagicMock(side_effect=config_get_disabled),
        "config.option": MagicMock(return_value=False),
        "mine.send": mine_mock,
    }
    with patch.dict(docker_mod.__salt__, dunder_salt), patch.dict(
        docker_mod.__context__, {"docker.client": Mock()}
    ), patch.object(docker_mod, "state", MagicMock(return_value="stopped")):
        docker_mod.stop("foo", timeout=1)
        mine_mock.assert_not_called()

    with patch.dict(docker_mod.__salt__, dunder_salt), patch.dict(
        docker_mod.__context__, {"docker.client": Mock()}
    ), patch.object(docker_mod, "state", MagicMock(return_value="stopped")):
        dunder_salt["config.get"].side_effect = config_get_enabled
        dunder_salt["config.option"].return_value = True
        docker_mod.stop("foo", timeout=1)
        mine_mock.assert_called_once()


@pytest.mark.skipif(
    docker_mod.docker.version_info < (1, 5, 0),
    reason="docker module must be installed to run this test or is too old. >=1.5.0",
)
def test_list_networks():
    """
    test list networks.
    """
    __salt__ = {
        "config.get": Mock(),
        "mine.send": Mock(),
    }
    client = Mock()
    client.api_version = "1.21"
    client.networks = Mock(
        return_value=[{"Name": "foo", "Id": "01234", "Containers": {}}]
    )
    get_client_mock = MagicMock(return_value=client)
    with patch.dict(docker_mod.__dict__, {"__salt__": __salt__}):
        with patch.object(docker_mod, "_get_client", get_client_mock):
            docker_mod.networks(names=["foo"], ids=["01234"])
    client.networks.assert_called_once_with(names=["foo"], ids=["01234"])


@pytest.mark.skipif(
    docker_mod.docker.version_info < (1, 5, 0),
    reason="docker module must be installed to run this test or is too old. >=1.5.0",
)
def test_create_network():
    """
    test create network.
    """
    __salt__ = {
        "config.get": Mock(),
        "mine.send": Mock(),
    }
    client = Mock()
    client.api_version = "1.21"
    get_client_mock = MagicMock(return_value=client)

    with patch.dict(docker_mod.__dict__, {"__salt__": __salt__}):
        with patch.object(docker_mod, "_get_client", get_client_mock):
            docker_mod.create_network(
                "foo",
                driver="bridge",
                driver_opts={},
                gateway="192.168.0.1",
                ip_range="192.168.0.128/25",
                subnet="192.168.0.0/24",
            )
    client.create_network.assert_called_once_with(
        "foo",
        driver="bridge",
        options={},
        ipam={
            "Config": [
                {
                    "Gateway": "192.168.0.1",
                    "IPRange": "192.168.0.128/25",
                    "Subnet": "192.168.0.0/24",
                }
            ],
            "Driver": "default",
        },
        check_duplicate=True,
    )


@pytest.mark.skipif(
    docker_mod.docker.version_info < (1, 5, 0),
    reason="docker module must be installed to run this test or is too old. >=1.5.0",
)
def test_remove_network():
    """
    test remove network.
    """
    __salt__ = {
        "config.get": Mock(),
        "mine.send": Mock(),
    }
    client = Mock()
    client.api_version = "1.21"
    get_client_mock = MagicMock(return_value=client)

    with patch.dict(docker_mod.__dict__, {"__salt__": __salt__}):
        with patch.object(docker_mod, "_get_client", get_client_mock):
            docker_mod.remove_network("foo")
    client.remove_network.assert_called_once_with("foo")


@pytest.mark.skipif(
    docker_mod.docker.version_info < (1, 5, 0),
    reason="docker module must be installed to run this test or is too old. >=1.5.0",
)
def test_inspect_network():
    """
    test inspect network.
    """
    __salt__ = {
        "config.get": Mock(),
        "mine.send": Mock(),
    }
    client = Mock()
    client.api_version = "1.21"
    get_client_mock = MagicMock(return_value=client)

    with patch.dict(docker_mod.__dict__, {"__salt__": __salt__}):
        with patch.object(docker_mod, "_get_client", get_client_mock):
            docker_mod.inspect_network("foo")
    client.inspect_network.assert_called_once_with("foo")


@pytest.mark.skipif(
    docker_mod.docker.version_info < (1, 5, 0),
    reason="docker module must be installed to run this test or is too old. >=1.5.0",
)
def test_connect_container_to_network():
    """
    test connect_container_to_network
    """
    __salt__ = {
        "config.get": Mock(),
        "mine.send": Mock(),
    }
    client = Mock()
    client.api_version = "1.21"
    get_client_mock = MagicMock(return_value=client)

    context = {"docker.exec_driver": "docker-exec"}

    with patch.dict(docker_mod.__dict__, {"__salt__": __salt__}):
        with patch.dict(docker_mod.__context__, context):
            with patch.object(docker_mod, "_get_client", get_client_mock):
                docker_mod.connect_container_to_network("container", "foo")
    client.connect_container_to_network.assert_called_once_with("container", "foo")


@pytest.mark.skipif(
    docker_mod.docker.version_info < (1, 5, 0),
    reason="docker module must be installed to run this test or is too old. >=1.5.0",
)
def test_disconnect_container_from_network():
    """
    test disconnect_container_from_network
    """
    __salt__ = {
        "config.get": Mock(),
        "mine.send": Mock(),
    }
    client = Mock()
    client.api_version = "1.21"
    get_client_mock = MagicMock(return_value=client)

    with patch.dict(docker_mod.__dict__, {"__salt__": __salt__}):
        with patch.object(docker_mod, "_get_client", get_client_mock):
            docker_mod.disconnect_container_from_network("container", "foo")
    client.disconnect_container_from_network.assert_called_once_with("container", "foo")


@pytest.mark.skipif(
    docker_mod.docker.version_info < (1, 5, 0),
    reason="docker module must be installed to run this test or is too old. >=1.5.0",
)
def test_list_volumes():
    """
    test list volumes.
    """
    __salt__ = {
        "config.get": Mock(),
        "mine.send": Mock(),
    }
    client = Mock()
    client.api_version = "1.21"
    get_client_mock = MagicMock(return_value=client)

    with patch.dict(docker_mod.__dict__, {"__salt__": __salt__}):
        with patch.object(docker_mod, "_get_client", get_client_mock):
            docker_mod.volumes(
                filters={"dangling": [True]},
            )
    client.volumes.assert_called_once_with(
        filters={"dangling": [True]},
    )


@pytest.mark.skipif(
    docker_mod.docker.version_info < (1, 5, 0),
    reason="docker module must be installed to run this test or is too old. >=1.5.0",
)
def test_create_volume():
    """
    test create volume.
    """
    __salt__ = {
        "config.get": Mock(),
        "mine.send": Mock(),
    }
    client = Mock()
    client.api_version = "1.21"
    get_client_mock = MagicMock(return_value=client)

    with patch.dict(docker_mod.__dict__, {"__salt__": __salt__}):
        with patch.object(docker_mod, "_get_client", get_client_mock):
            docker_mod.create_volume(
                "foo",
                driver="bridge",
                driver_opts={},
            )
    client.create_volume.assert_called_once_with(
        "foo",
        driver="bridge",
        driver_opts={},
    )


@pytest.mark.skipif(
    docker_mod.docker.version_info < (1, 5, 0),
    reason="docker module must be installed to run this test or is too old. >=1.5.0",
)
def test_remove_volume():
    """
    test remove volume.
    """
    __salt__ = {
        "config.get": Mock(),
        "mine.send": Mock(),
    }
    client = Mock()
    client.api_version = "1.21"
    get_client_mock = MagicMock(return_value=client)

    with patch.dict(docker_mod.__dict__, {"__salt__": __salt__}):
        with patch.object(docker_mod, "_get_client", get_client_mock):
            docker_mod.remove_volume("foo")
    client.remove_volume.assert_called_once_with("foo")


@pytest.mark.skipif(
    docker_mod.docker.version_info < (1, 5, 0),
    reason="docker module must be installed to run this test or is too old. >=1.5.0",
)
def test_inspect_volume():
    """
    test inspect volume.
    """
    __salt__ = {
        "config.get": Mock(),
        "mine.send": Mock(),
    }
    client = Mock()
    client.api_version = "1.21"
    get_client_mock = MagicMock(return_value=client)

    with patch.dict(docker_mod.__dict__, {"__salt__": __salt__}):
        with patch.object(docker_mod, "_get_client", get_client_mock):
            docker_mod.inspect_volume("foo")
    client.inspect_volume.assert_called_once_with("foo")


def test_wait_success():
    client = Mock()
    client.api_version = "1.21"
    client.wait = Mock(return_value=0)
    get_client_mock = MagicMock(return_value=client)

    docker_inspect_container = Mock(
        side_effect=[{"State": {"Running": True}}, {"State": {"Stopped": True}}]
    )
    with patch.object(docker_mod, "inspect_container", docker_inspect_container):
        with patch.object(docker_mod, "_get_client", get_client_mock):
            docker_mod._clear_context()
            result = docker_mod.wait("foo")
    assert result == {
        "result": True,
        "exit_status": 0,
        "state": {"new": "stopped", "old": "running"},
    }


def test_wait_fails_already_stopped():
    client = Mock()
    client.api_version = "1.21"
    client.wait = Mock(return_value=0)
    get_client_mock = MagicMock(return_value=client)

    docker_inspect_container = Mock(
        side_effect=[{"State": {"Stopped": True}}, {"State": {"Stopped": True}}]
    )
    with patch.object(docker_mod, "inspect_container", docker_inspect_container):
        with patch.object(docker_mod, "_get_client", get_client_mock):
            docker_mod._clear_context()
            result = docker_mod.wait("foo")
    assert result == {
        "result": False,
        "comment": "Container 'foo' already stopped",
        "exit_status": 0,
        "state": {"new": "stopped", "old": "stopped"},
    }


def test_wait_success_already_stopped():
    client = Mock()
    client.api_version = "1.21"
    client.wait = Mock(return_value=0)
    get_client_mock = MagicMock(return_value=client)

    docker_inspect_container = Mock(
        side_effect=[{"State": {"Stopped": True}}, {"State": {"Stopped": True}}]
    )
    with patch.object(docker_mod, "inspect_container", docker_inspect_container):
        with patch.object(docker_mod, "_get_client", get_client_mock):
            docker_mod._clear_context()
            result = docker_mod.wait("foo", ignore_already_stopped=True)
    assert result == {
        "result": True,
        "comment": "Container 'foo' already stopped",
        "exit_status": 0,
        "state": {"new": "stopped", "old": "stopped"},
    }


def test_wait_success_absent_container():
    client = Mock()
    client.api_version = "1.21"
    get_client_mock = MagicMock(return_value=client)

    docker_inspect_container = Mock(side_effect=CommandExecutionError)
    with patch.object(docker_mod, "inspect_container", docker_inspect_container):
        with patch.object(docker_mod, "_get_client", get_client_mock):
            docker_mod._clear_context()
            result = docker_mod.wait("foo", ignore_already_stopped=True)
    assert result == {"result": True, "comment": "Container 'foo' absent"}


def test_wait_fails_on_exit_status():
    client = Mock()
    client.api_version = "1.21"
    client.wait = Mock(return_value=1)
    get_client_mock = MagicMock(return_value=client)

    docker_inspect_container = Mock(
        side_effect=[{"State": {"Running": True}}, {"State": {"Stopped": True}}]
    )
    with patch.object(docker_mod, "inspect_container", docker_inspect_container):
        with patch.object(docker_mod, "_get_client", get_client_mock):
            docker_mod._clear_context()
            result = docker_mod.wait("foo", fail_on_exit_status=True)
    assert result == {
        "result": False,
        "exit_status": 1,
        "state": {"new": "stopped", "old": "running"},
    }


def test_wait_fails_on_exit_status_and_already_stopped():
    client = Mock()
    client.api_version = "1.21"
    client.wait = Mock(return_value=1)
    get_client_mock = MagicMock(return_value=client)

    docker_inspect_container = Mock(
        side_effect=[{"State": {"Stopped": True}}, {"State": {"Stopped": True}}]
    )
    with patch.object(docker_mod, "inspect_container", docker_inspect_container):
        with patch.object(docker_mod, "_get_client", get_client_mock):
            docker_mod._clear_context()
            result = docker_mod.wait(
                "foo", ignore_already_stopped=True, fail_on_exit_status=True
            )
    assert result == {
        "result": False,
        "comment": "Container 'foo' already stopped",
        "exit_status": 1,
        "state": {"new": "stopped", "old": "stopped"},
    }


def test_sls_build():
    """
    test build sls image.
    """
    docker_start_mock = MagicMock(return_value={})
    docker_create_mock = MagicMock(return_value={"Id": "ID", "Name": "NAME"})
    docker_stop_mock = MagicMock(
        return_value={"state": {"old": "running", "new": "stopped"}, "result": True}
    )
    docker_rm_mock = MagicMock(return_value={})
    docker_commit_mock = MagicMock(
        return_value={"Id": "ID2", "Image": "foo", "Time_Elapsed": 42}
    )

    docker_sls_mock = MagicMock(
        return_value={
            "file_|-/etc/test.sh_|-/etc/test.sh_|-managed": {
                "comment": "File /etc/test.sh is in the correct state",
                "name": "/etc/test.sh",
                "start_time": "07:04:26.834792",
                "result": True,
                "duration": 13.492,
                "__run_num__": 0,
                "changes": {},
            },
            "test_|-always-passes_|-foo_|-succeed_without_changes": {
                "comment": "Success!",
                "name": "foo",
                "start_time": "07:04:26.848915",
                "result": True,
                "duration": 0.363,
                "__run_num__": 1,
                "changes": {},
            },
        }
    )

    ret = None
    with patch.object(docker_mod, "start_", docker_start_mock), patch.object(
        docker_mod, "create", docker_create_mock
    ), patch.object(docker_mod, "stop", docker_stop_mock), patch.object(
        docker_mod, "commit", docker_commit_mock
    ), patch.object(
        docker_mod, "sls", docker_sls_mock
    ), patch.object(
        docker_mod, "rm_", docker_rm_mock
    ):
        ret = docker_mod.sls_build("foo", mods="foo")
    docker_create_mock.assert_called_once_with(
        cmd="sleep infinity", image="opensuse/python", interactive=True, tty=True
    )
    docker_start_mock.assert_called_once_with("ID")
    docker_sls_mock.assert_called_once_with("ID", "foo")
    docker_stop_mock.assert_called_once_with("ID")
    docker_rm_mock.assert_called_once_with("ID")
    docker_commit_mock.assert_called_once_with("ID", "foo", tag="latest")
    assert {"Id": "ID2", "Image": "foo", "Time_Elapsed": 42} == ret


def test_sls_build_dryrun():
    """
    test build sls image in dryrun mode.
    """
    docker_start_mock = MagicMock(return_value={})
    docker_create_mock = MagicMock(return_value={"Id": "ID", "Name": "NAME"})
    docker_stop_mock = MagicMock(
        return_value={"state": {"old": "running", "new": "stopped"}, "result": True}
    )
    docker_rm_mock = MagicMock(return_value={})

    docker_sls_mock = MagicMock(
        return_value={
            "file_|-/etc/test.sh_|-/etc/test.sh_|-managed": {
                "comment": "File /etc/test.sh is in the correct state",
                "name": "/etc/test.sh",
                "start_time": "07:04:26.834792",
                "result": True,
                "duration": 13.492,
                "__run_num__": 0,
                "changes": {},
            },
            "test_|-always-passes_|-foo_|-succeed_without_changes": {
                "comment": "Success!",
                "name": "foo",
                "start_time": "07:04:26.848915",
                "result": True,
                "duration": 0.363,
                "__run_num__": 1,
                "changes": {},
            },
        }
    )

    ret = None
    with patch.object(docker_mod, "start_", docker_start_mock), patch.object(
        docker_mod, "create", docker_create_mock
    ), patch.object(docker_mod, "stop", docker_stop_mock), patch.object(
        docker_mod, "rm_", docker_rm_mock
    ), patch.object(
        docker_mod, "sls", docker_sls_mock
    ):
        ret = docker_mod.sls_build("foo", mods="foo", dryrun=True)
    docker_create_mock.assert_called_once_with(
        cmd="sleep infinity", image="opensuse/python", interactive=True, tty=True
    )
    docker_start_mock.assert_called_once_with("ID")
    docker_sls_mock.assert_called_once_with("ID", "foo")
    docker_stop_mock.assert_called_once_with("ID")
    docker_rm_mock.assert_called_once_with("ID")
    assert {
        "file_|-/etc/test.sh_|-/etc/test.sh_|-managed": {
            "comment": "File /etc/test.sh is in the correct state",
            "name": "/etc/test.sh",
            "start_time": "07:04:26.834792",
            "result": True,
            "duration": 13.492,
            "__run_num__": 0,
            "changes": {},
        },
        "test_|-always-passes_|-foo_|-succeed_without_changes": {
            "comment": "Success!",
            "name": "foo",
            "start_time": "07:04:26.848915",
            "result": True,
            "duration": 0.363,
            "__run_num__": 1,
            "changes": {},
        },
    } == ret


@pytest.mark.slow_test
def test_call_success():
    """
    test module calling inside containers
    """
    ret = None
    docker_run_all_mock = MagicMock(
        return_value={
            "retcode": 0,
            "stdout": '{"retcode": 0, "comment": "container cmd"}',
            "stderr": "err",
        }
    )
    docker_copy_to_mock = MagicMock(return_value={"retcode": 0})
    docker_config_mock = MagicMock(return_value="")
    client = Mock()
    client.put_archive = Mock()
    get_client_mock = MagicMock(return_value=client)

    context = {"docker.exec_driver": "docker-exec"}
    salt_dunder = {"config.option": docker_config_mock}

    with patch.object(docker_mod, "run_all", docker_run_all_mock), patch.object(
        docker_mod, "copy_to", docker_copy_to_mock
    ), patch.object(docker_mod, "_get_client", get_client_mock), patch.dict(
        docker_mod.__opts__, {"cachedir": "/tmp"}
    ), patch.dict(
        docker_mod.__salt__, salt_dunder
    ), patch.dict(
        docker_mod.__context__, context
    ):
        # call twice to verify tmp path later
        for i in range(2):
            ret = docker_mod.call("ID", "test.arg", 1, 2, arg1="val1")

    # Check that the directory is different each time
    # [ call(name, [args]), ...
    assert "mkdir" in docker_run_all_mock.mock_calls[0][1][1]
    assert "mkdir" in docker_run_all_mock.mock_calls[5][1][1]
    assert (
        docker_run_all_mock.mock_calls[0][1][1]
        != docker_run_all_mock.mock_calls[5][1][1]
    )

    assert "python3 --version" == docker_run_all_mock.mock_calls[1][1][1]

    assert "salt-call" in docker_run_all_mock.mock_calls[3][1][1]
    assert "salt-call" in docker_run_all_mock.mock_calls[8][1][1]
    assert (
        docker_run_all_mock.mock_calls[3][1][1]
        != docker_run_all_mock.mock_calls[8][1][1]
    )

    # check thin untar
    assert "tarfile" in docker_run_all_mock.mock_calls[2][1][1]
    assert "tarfile" in docker_run_all_mock.mock_calls[7][1][1]
    assert (
        docker_run_all_mock.mock_calls[2][1][1]
        != docker_run_all_mock.mock_calls[7][1][1]
    )

    # check directory cleanup
    assert "rm -rf" in docker_run_all_mock.mock_calls[4][1][1]
    assert "rm -rf" in docker_run_all_mock.mock_calls[9][1][1]
    assert (
        docker_run_all_mock.mock_calls[4][1][1]
        != docker_run_all_mock.mock_calls[9][1][1]
    )

    assert {"retcode": 0, "comment": "container cmd"} == ret


def test_images_with_empty_tags():
    """
    docker 1.12 reports also images without tags with `null`.
    """
    client = Mock()
    client.api_version = "1.24"
    client.images = Mock(
        return_value=[
            {"Id": "sha256:abcde", "RepoTags": None},
            {"Id": "sha256:abcdef"},
            {"Id": "sha256:abcdefg", "RepoTags": ["image:latest"]},
        ]
    )
    get_client_mock = MagicMock(return_value=client)

    with patch.object(docker_mod, "_get_client", get_client_mock):
        docker_mod._clear_context()
        result = docker_mod.images()
    assert result == {"sha256:abcdefg": {"RepoTags": ["image:latest"]}}


def test_compare_container_image_id_resolution():
    """
    Test comparing two containers when one's inspect output is an ID and
    not formatted in image:tag notation.
    """

    def _inspect_container_effect(id_):
        return {
            "container1": {
                "Config": {"Image": "realimage:latest"},
                "HostConfig": {},
            },
            "container2": {"Config": {"Image": "image_id"}, "HostConfig": {}},
        }[id_]

    def _inspect_image_effect(id_):
        return {
            "realimage:latest": {"Id": "image_id"},
            "image_id": {"Id": "image_id"},
        }[id_]

    inspect_container_mock = MagicMock(side_effect=_inspect_container_effect)
    inspect_image_mock = MagicMock(side_effect=_inspect_image_effect)

    with patch.object(docker_mod, "inspect_container", inspect_container_mock):
        with patch.object(docker_mod, "inspect_image", inspect_image_mock):
            ret = docker_mod.compare_containers("container1", "container2")
            assert ret == {}


def test_compare_container_ulimits_order():
    """
    Test comparing two containers when the order of the Ulimits HostConfig
    values are different, but the values are the same.
    """

    def _inspect_container_effect(id_):
        return {
            "container1": {
                "Config": {},
                "HostConfig": {
                    "Ulimits": [
                        {"Hard": -1, "Soft": -1, "Name": "core"},
                        {"Hard": 65536, "Soft": 65536, "Name": "nofile"},
                    ]
                },
            },
            "container2": {
                "Config": {},
                "HostConfig": {
                    "Ulimits": [
                        {"Hard": 65536, "Soft": 65536, "Name": "nofile"},
                        {"Hard": -1, "Soft": -1, "Name": "core"},
                    ]
                },
            },
        }[id_]

    inspect_container_mock = MagicMock(side_effect=_inspect_container_effect)

    with patch.object(docker_mod, "inspect_container", inspect_container_mock):
        # pylint: disable=not-callable
        ret = docker_mod.compare_container("container1", "container2")
        # pylint: enable=not-callable
        assert ret == {}


def test_compare_container_env_order():
    """
    Test comparing two containers when the order of the Env HostConfig
    values are different, but the values are the same.
    """

    def _inspect_container_effect(id_):
        return {
            "container1": {
                "Config": {},
                "HostConfig": {"Env": ["FOO=bar", "HELLO=world"]},
            },
            "container2": {
                "Config": {},
                "HostConfig": {"Env": ["HELLO=world", "FOO=bar"]},
            },
        }[id_]

    inspect_container_mock = MagicMock(side_effect=_inspect_container_effect)

    with patch.object(docker_mod, "inspect_container", inspect_container_mock):
        # pylint: disable=not-callable
        ret = docker_mod.compare_container("container1", "container2")
        # pylint: enable=not-callable
        assert ret == {}


def test_resolve_tag():
    """
    Test the resolve_tag function. It runs docker.insect_image on the image
    name passed and then looks for the RepoTags key in the result
    """
    id_ = "sha256:6ad733544a6317992a6fac4eb19fe1df577d4dec7529efec28a5bd0edad0fd30"
    tags = ["foo:latest", "foo:bar"]
    mock_tagged = MagicMock(return_value={"Id": id_, "RepoTags": tags})
    mock_untagged = MagicMock(return_value={"Id": id_, "RepoTags": []})
    mock_unexpected = MagicMock(return_value={"Id": id_})
    mock_not_found = MagicMock(side_effect=CommandExecutionError())

    with patch.object(docker_mod, "inspect_image", mock_tagged):
        assert docker_mod.resolve_tag("foo") == tags[0]
        assert docker_mod.resolve_tag("foo", all=True) == tags

    with patch.object(docker_mod, "inspect_image", mock_untagged):
        assert docker_mod.resolve_tag("foo") == id_
        assert docker_mod.resolve_tag("foo", all=True) == [id_]

    with patch.object(docker_mod, "inspect_image", mock_unexpected):
        assert docker_mod.resolve_tag("foo") == id_
        assert docker_mod.resolve_tag("foo", all=True) == [id_]

    with patch.object(docker_mod, "inspect_image", mock_not_found):
        assert docker_mod.resolve_tag("foo") is False
        assert docker_mod.resolve_tag("foo", all=True) is False


def test_prune():
    """
    Test the prune function
    """

    def _run(**kwargs):
        side_effect = kwargs.pop("side_effect", None)
        # No arguments passed, we should be pruning everything but volumes
        client = Mock()
        if side_effect is not None:
            client.side_effect = side_effect
        with patch.object(docker_mod, "_client_wrapper", client):
            docker_mod.prune(**kwargs)
        return client

    # Containers only, no filters
    client = _run(containers=True)
    client.assert_called_once_with("prune_containers", filters={})

    # Containers only, with filters
    client = _run(containers=True, until="24h", label="foo,bar=baz")
    client.assert_called_once_with(
        "prune_containers", filters={"until": ["24h"], "label": ["foo", "bar=baz"]}
    )

    # Images only, no filters
    client = _run(images=True)
    client.assert_called_once_with("prune_images", filters={})

    # Images only, with filters
    client = _run(images=True, dangling=True, until="24h", label="foo,bar=baz")
    client.assert_called_once_with(
        "prune_images",
        filters={"dangling": True, "until": ["24h"], "label": ["foo", "bar=baz"]},
    )

    # Networks only, no filters
    client = _run(networks=True)
    client.assert_called_once_with("prune_networks", filters={})

    # Networks only, with filters
    client = _run(networks=True, until="24h", label="foo,bar=baz")
    client.assert_called_once_with(
        "prune_networks", filters={"until": ["24h"], "label": ["foo", "bar=baz"]}
    )

    # Volumes only, no filters
    client = _run(system=False, volumes=True)
    client.assert_called_once_with("prune_volumes", filters={})

    # Volumes only, with filters
    client = _run(system=False, volumes=True, label="foo,bar=baz")
    client.assert_called_once_with(
        "prune_volumes", filters={"label": ["foo", "bar=baz"]}
    )

    # Containers and images, no filters
    client = _run(containers=True, images=True)
    assert client.call_args_list == [
        call("prune_containers", filters={}),
        call("prune_images", filters={}),
    ]

    # Containers and images, with filters
    client = _run(containers=True, images=True, until="24h", label="foo,bar=baz")
    assert client.call_args_list == [
        call(
            "prune_containers",
            filters={"until": ["24h"], "label": ["foo", "bar=baz"]},
        ),
        call(
            "prune_images",
            filters={"until": ["24h"], "label": ["foo", "bar=baz"]},
        ),
    ]

    # System, no volumes, no filters, assuming prune_build in docker-py
    client = _run(system=True)
    assert client.call_args_list == [
        call("prune_containers", filters={}),
        call("prune_images", filters={}),
        call("prune_networks", filters={}),
        call("prune_build", filters={}),
    ]

    # System, no volumes, no filters, assuming prune_build not in docker-py
    client = _run(
        system=True,
        side_effect=[None, None, None, SaltInvocationError(), None, None, None],
    )
    assert client.call_args_list == [
        call("prune_containers", filters={}),
        call("prune_images", filters={}),
        call("prune_networks", filters={}),
        call("prune_build", filters={}),
        call("_url", "/build/prune"),
        call("_post", None),
        call("_result", None, True),
    ]

    # System, no volumes, with filters, assuming prune_build in docker-py
    client = _run(system=True, label="foo,bar=baz")
    assert client.call_args_list == [
        call("prune_containers", filters={"label": ["foo", "bar=baz"]}),
        call("prune_images", filters={"label": ["foo", "bar=baz"]}),
        call("prune_networks", filters={"label": ["foo", "bar=baz"]}),
        call("prune_build", filters={"label": ["foo", "bar=baz"]}),
    ]

    # System, no volumes, with filters, assuming prune_build not in docker-py
    client = _run(
        system=True,
        label="foo,bar=baz",
        side_effect=[None, None, None, SaltInvocationError(), None, None, None],
    )
    assert client.call_args_list == [
        call("prune_containers", filters={"label": ["foo", "bar=baz"]}),
        call("prune_images", filters={"label": ["foo", "bar=baz"]}),
        call("prune_networks", filters={"label": ["foo", "bar=baz"]}),
        call("prune_build", filters={"label": ["foo", "bar=baz"]}),
        call("_url", "/build/prune"),
        call("_post", None),
        call("_result", None, True),
    ]

    # System and volumes, no filters, assuming prune_build in docker-py
    client = _run(system=True, volumes=True)
    assert client.call_args_list == [
        call("prune_containers", filters={}),
        call("prune_images", filters={}),
        call("prune_networks", filters={}),
        call("prune_build", filters={}),
        call("prune_volumes", filters={}),
    ]

    # System and volumes, no filters, assuming prune_build not in docker-py
    client = _run(
        system=True,
        volumes=True,
        side_effect=[
            None,
            None,
            None,
            SaltInvocationError(),
            None,
            None,
            None,
            None,
        ],
    )
    assert client.call_args_list == [
        call("prune_containers", filters={}),
        call("prune_images", filters={}),
        call("prune_networks", filters={}),
        call("prune_build", filters={}),
        call("_url", "/build/prune"),
        call("_post", None),
        call("_result", None, True),
        call("prune_volumes", filters={}),
    ]

    # System and volumes with filters, assuming prune_build in docker-py
    client = _run(system=True, volumes=True, label="foo,bar=baz")
    assert client.call_args_list == [
        call("prune_containers", filters={"label": ["foo", "bar=baz"]}),
        call("prune_images", filters={"label": ["foo", "bar=baz"]}),
        call("prune_networks", filters={"label": ["foo", "bar=baz"]}),
        call("prune_build", filters={"label": ["foo", "bar=baz"]}),
        call("prune_volumes", filters={"label": ["foo", "bar=baz"]}),
    ]

    # System and volumes, with filters, assuming prune_build not in docker-py
    client = _run(
        system=True,
        volumes=True,
        label="foo,bar=baz",
        side_effect=[
            None,
            None,
            None,
            SaltInvocationError(),
            None,
            None,
            None,
            None,
        ],
    )
    assert client.call_args_list == [
        call("prune_containers", filters={"label": ["foo", "bar=baz"]}),
        call("prune_images", filters={"label": ["foo", "bar=baz"]}),
        call("prune_networks", filters={"label": ["foo", "bar=baz"]}),
        call("prune_build", filters={"label": ["foo", "bar=baz"]}),
        call("_url", "/build/prune"),
        call("_post", None),
        call("_result", None, True),
        call("prune_volumes", filters={"label": ["foo", "bar=baz"]}),
    ]


def test_port():
    """
    Test docker.port function. Note that this test case does not test what
    happens when a specific container name is passed and that container
    does not exist. When that happens, the Docker API will just raise a 404
    error. Since we're using as side_effect to mock
    docker.inspect_container, it would be meaningless to code raising an
    exception into it and then test that we raised that exception.
    """
    ports = {
        "foo": {
            "5555/tcp": [{"HostIp": "0.0.0.0", "HostPort": "32768"}],
            "6666/tcp": [{"HostIp": "0.0.0.0", "HostPort": "32769"}],
        },
        "bar": {
            "4444/udp": [{"HostIp": "0.0.0.0", "HostPort": "32767"}],
            "5555/tcp": [{"HostIp": "0.0.0.0", "HostPort": "32768"}],
            "6666/tcp": [{"HostIp": "0.0.0.0", "HostPort": "32769"}],
        },
        "baz": {
            "5555/tcp": [{"HostIp": "0.0.0.0", "HostPort": "32768"}],
            "6666/udp": [{"HostIp": "0.0.0.0", "HostPort": "32769"}],
        },
    }
    list_mock = MagicMock(return_value=["bar", "baz", "foo"])
    inspect_mock = MagicMock(
        side_effect=lambda x: {"NetworkSettings": {"Ports": ports.get(x)}}
    )
    with patch.object(docker_mod, "list_containers", list_mock), patch.object(
        docker_mod, "inspect_container", inspect_mock
    ):

        # Test with specific container name
        ret = docker_mod.port("foo")
        assert ret == ports["foo"]

        # Test with specific container name and filtering on port
        ret = docker_mod.port("foo", private_port="5555/tcp")
        assert ret == {"5555/tcp": ports["foo"]["5555/tcp"]}

        # Test using pattern expression
        ret = docker_mod.port("ba*")
        assert ret == {"bar": ports["bar"], "baz": ports["baz"]}
        ret = docker_mod.port("ba?")
        assert ret == {"bar": ports["bar"], "baz": ports["baz"]}
        ret = docker_mod.port("ba[rz]")
        assert ret == {"bar": ports["bar"], "baz": ports["baz"]}

        # Test using pattern expression and port filtering
        ret = docker_mod.port("ba*", private_port="6666/tcp")
        assert ret == {"bar": {"6666/tcp": ports["bar"]["6666/tcp"]}, "baz": {}}
        ret = docker_mod.port("ba?", private_port="6666/tcp")
        assert ret == {"bar": {"6666/tcp": ports["bar"]["6666/tcp"]}, "baz": {}}
        ret = docker_mod.port("ba[rz]", private_port="6666/tcp")
        assert ret == {"bar": {"6666/tcp": ports["bar"]["6666/tcp"]}, "baz": {}}
        ret = docker_mod.port("*")
        assert ret == ports
        ret = docker_mod.port("*", private_port="5555/tcp")
        assert ret == {
            "foo": {"5555/tcp": ports["foo"]["5555/tcp"]},
            "bar": {"5555/tcp": ports["bar"]["5555/tcp"]},
            "baz": {"5555/tcp": ports["baz"]["5555/tcp"]},
        }
        ret = docker_mod.port("*", private_port=6666)
        assert ret == {
            "foo": {"6666/tcp": ports["foo"]["6666/tcp"]},
            "bar": {"6666/tcp": ports["bar"]["6666/tcp"]},
            "baz": {"6666/udp": ports["baz"]["6666/udp"]},
        }
        ret = docker_mod.port("*", private_port="6666/tcp")
        assert ret == {
            "foo": {"6666/tcp": ports["foo"]["6666/tcp"]},
            "bar": {"6666/tcp": ports["bar"]["6666/tcp"]},
            "baz": {},
        }
