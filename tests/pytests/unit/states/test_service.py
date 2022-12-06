"""
    :codeauthor: Gareth J. Greenaway <ggreenaway@vmware.com>
"""

import logging

import pytest

import salt.modules.beacons as beaconmod
import salt.states.beacon as beaconstate
import salt.states.service as service
import salt.utils.platform
from salt.utils.event import SaltEvent
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


def func(name):
    """
    Mock func method
    """
    return name


@pytest.fixture
def configure_loader_modules():
    return {
        service: {
            "__env__": "base",
            "__salt__": {},
            "__opts__": {"test": False, "cachedir": ""},
            "__instance_id__": "",
            "__low__": {},
            "__utils__": {},
            "__context__": {},
        },
        beaconstate: {"__salt__": {}, "__opts__": {}},
        beaconmod: {"__salt__": {}, "__opts__": {}},
    }


def test_get_systemd_only():
    """
    Test the _get_system_only function
    """

    def test_func(cats, dogs, no_block):
        pass

    with patch.object(service._get_systemd_only, "HAS_SYSTEMD", True, create=True):
        ret, warnings = service._get_systemd_only(
            test_func, {"cats": 1, "no_block": 2, "unmask": 3}
        )
        assert len(warnings) == 0
        assert ret == {"no_block": 2}

        ret, warnings = service._get_systemd_only(test_func, {"cats": 1, "unmask": 3})

        assert len(warnings) == 0
        assert ret == {}


def test_get_systemd_only_platform():
    """
    Test the _get_system_only function on unsupported platforms
    """

    def test_func(cats, dogs, no_block):
        pass

    with patch.object(service._get_systemd_only, "HAS_SYSTEMD", False, create=True):
        ret, warnings = service._get_systemd_only(
            test_func, {"cats": 1, "no_block": 2, "unmask": 3}
        )

        assert warnings == ["The 'no_block' argument is not supported by this platform"]
        assert ret == {}

        ret, warnings = service._get_systemd_only(test_func, {"cats": 1, "unmask": 3})

        assert len(warnings) == 0
        assert ret == {}


def test_get_systemd_only_no_mock():
    """
    Test the _get_system_only without mocking
    """

    def test_func(cats, dogs, no_block):
        pass

    ret, warnings = service._get_systemd_only(
        test_func, {"cats": 1, "no_block": 2, "unmask": 3}
    )

    assert isinstance(ret, dict)
    assert isinstance(warnings, list)


def test_running():
    """
    Test to verify that the service is running
    """
    ret = [
        {"comment": "", "changes": {}, "name": "salt", "result": True},
        {
            "changes": {},
            "comment": "The service salt is already running",
            "name": "salt",
            "result": True,
        },
        {
            "changes": "saltstack",
            "comment": "The service salt is already running",
            "name": "salt",
            "result": True,
        },
        {
            "changes": {},
            "comment": "Service salt is set to start",
            "name": "salt",
            "result": None,
        },
        {
            "changes": "saltstack",
            "comment": "Started service salt",
            "name": "salt",
            "result": True,
        },
        {
            "changes": {},
            "comment": "The service salt is already running",
            "name": "salt",
            "result": True,
        },
        {
            "changes": "saltstack",
            "comment": "Service salt failed to start",
            "name": "salt",
            "result": False,
        },
        {
            "changes": "saltstack",
            "comment": (
                "Started service salt\nService masking not available on this minion"
            ),
            "name": "salt",
            "result": True,
        },
        {
            "changes": "saltstack",
            "comment": (
                "Started service salt\nService masking not available on this minion"
            ),
            "name": "salt",
            "result": True,
        },
        {
            "changes": {},
            "comment": (
                "The service salt is disabled but enable is not True. Set enable to"
                " True to successfully start the service."
            ),
            "name": "salt",
            "result": False,
        },
        {
            "changes": {},
            "comment": "The service salt is set to restart",
            "name": "salt",
            "result": None,
        },
    ]

    tmock = MagicMock(return_value=True)
    fmock = MagicMock(return_value=False)
    vmock = MagicMock(return_value="salt")
    with patch.object(service, "_enabled_used_error", vmock):
        assert service.running("salt", enabled=1) == "salt"

    with patch.object(service, "_available", fmock):
        assert service.running("salt") == ret[0]

    with patch.object(service, "_available", tmock):
        with patch.dict(service.__opts__, {"test": False}):
            with patch.dict(
                service.__salt__,
                {"service.enabled": tmock, "service.status": tmock},
            ):
                assert service.running("salt") == ret[1]

            mock = MagicMock(return_value={"changes": "saltstack"})
            with patch.dict(
                service.__salt__,
                {
                    "service.enabled": MagicMock(side_effect=[False, True]),
                    "service.status": tmock,
                },
            ):
                with patch.object(service, "_enable", mock):
                    assert service.running("salt", True) == ret[2]

            with patch.dict(
                service.__salt__,
                {
                    "service.enabled": MagicMock(side_effect=[True, False]),
                    "service.status": tmock,
                },
            ):
                with patch.object(service, "_disable", mock):
                    assert service.running("salt", False) == ret[2]

            with patch.dict(
                service.__salt__,
                {
                    "service.status": MagicMock(side_effect=[False, True]),
                    "service.enabled": MagicMock(side_effect=[False, True]),
                    "service.start": MagicMock(return_value="stack"),
                },
            ):
                with patch.object(
                    service,
                    "_enable",
                    MagicMock(return_value={"changes": "saltstack"}),
                ):
                    assert service.running("salt", True) == ret[4]

            with patch.dict(
                service.__salt__,
                {
                    "service.status": MagicMock(side_effect=[False, True]),
                    "service.enabled": MagicMock(side_effect=[False, True]),
                    "service.unmask": MagicMock(side_effect=[False, True]),
                    "service.start": MagicMock(return_value="stack"),
                },
            ):
                with patch.object(
                    service,
                    "_enable",
                    MagicMock(return_value={"changes": "saltstack"}),
                ):
                    assert service.running("salt", True, unmask=True) == ret[7]

        with patch.dict(service.__opts__, {"test": True}):
            with patch.dict(service.__salt__, {"service.status": tmock}):
                assert service.running("salt") == ret[5]

            with patch.dict(service.__salt__, {"service.status": fmock}):
                assert service.running("salt") == ret[3]

        with patch.dict(service.__opts__, {"test": False}):
            with patch.dict(
                service.__salt__,
                {
                    "service.status": MagicMock(side_effect=[False, False]),
                    "service.enabled": MagicMock(side_effect=[True, True]),
                    "service.start": MagicMock(return_value="stack"),
                },
            ):
                with patch.object(
                    service,
                    "_enable",
                    MagicMock(return_value={"changes": "saltstack"}),
                ):
                    assert service.running("salt", True) == ret[6]
            # test some unique cases simulating Windows
            with patch.object(salt.utils.platform, "is_windows", tmock):
                # We should fail if a service is disabled on Windows and enable
                # isn't set.
                with patch.dict(
                    service.__salt__,
                    {
                        "service.status": fmock,
                        "service.enabled": fmock,
                        "service.start": tmock,
                    },
                ):
                    assert service.running("salt", None) == ret[9]
                    assert service.__context__ == {"service.state": "running"}
            # test some unique cases simulating macOS
            with patch.object(salt.utils.platform, "is_darwin", tmock):
                # We should fail if a service is disabled on macOS and enable
                # isn't set.
                with patch.dict(
                    service.__salt__,
                    {
                        "service.status": fmock,
                        "service.enabled": fmock,
                        "service.start": tmock,
                    },
                ):
                    assert service.running("salt", None) == ret[9]
                    assert service.__context__ == {"service.state": "running"}
                # test enabling a service prior starting it on macOS
                with patch.dict(
                    service.__salt__,
                    {
                        "service.status": MagicMock(side_effect=[False, "loaded"]),
                        "service.enabled": MagicMock(side_effect=[False, True]),
                        "service.start": tmock,
                    },
                ):
                    with patch.object(
                        service,
                        "_enable",
                        MagicMock(return_value={"changes": "saltstack"}),
                    ):
                        assert service.running("salt", True) == ret[4]
                        assert service.__context__ == {"service.state": "running"}
                # if an enable attempt fails on macOS or windows then a
                # disabled service will always fail to start.
                with patch.dict(
                    service.__salt__,
                    {
                        "service.status": fmock,
                        "service.enabled": fmock,
                        "service.start": fmock,
                    },
                ):
                    with patch.object(
                        service,
                        "_enable",
                        MagicMock(
                            return_value={"changes": "saltstack", "result": False}
                        ),
                    ):
                        assert service.running("salt", True) == ret[6]
                        assert service.__context__ == {"service.state": "running"}


def test_running_in_offline_mode():
    """
    Tests the case in which a service.running state is executed on an offline environemnt

    """
    name = "thisisnotarealservice"
    with patch.object(service, "_offline", MagicMock(return_value=True)):
        ret = service.running(name=name)
        assert ret == {
            "changes": {},
            "comment": "Running in OFFLINE mode. Nothing to do",
            "result": True,
            "name": name,
        }


def test_dead():
    """
    Test to ensure that the named service is dead
    """
    ret = [
        {"changes": {}, "comment": "", "name": "salt", "result": True},
        {
            "changes": "saltstack",
            "comment": "The service salt is already dead",
            "name": "salt",
            "result": True,
        },
        {
            "changes": {},
            "comment": "Service salt is set to be killed",
            "name": "salt",
            "result": None,
        },
        {
            "changes": "saltstack",
            "comment": "Service salt was killed",
            "name": "salt",
            "result": True,
        },
        {
            "changes": {},
            "comment": "Service salt failed to die",
            "name": "salt",
            "result": False,
        },
        {
            "changes": "saltstack",
            "comment": "The service salt is already dead",
            "name": "salt",
            "result": True,
        },
    ]
    info_mock = MagicMock(return_value={"StartType": ""})

    mock = MagicMock(return_value="salt")
    with patch.object(service, "_enabled_used_error", mock):
        assert service.dead("salt", enabled=1) == "salt"

    tmock = MagicMock(return_value=True)
    fmock = MagicMock(return_value=False)
    with patch.object(service, "_available", fmock):
        assert service.dead("salt") == ret[0]

    with patch.object(service, "_available", tmock):
        mock = MagicMock(return_value={"changes": "saltstack"})
        with patch.dict(service.__opts__, {"test": True}):
            with patch.dict(
                service.__salt__,
                {
                    "service.enabled": fmock,
                    "service.stop": tmock,
                    "service.status": fmock,
                    "service.info": info_mock,
                },
            ):
                with patch.object(service, "_enable", mock):
                    assert service.dead("salt", True) == ret[5]

            with patch.dict(
                service.__salt__,
                {
                    "service.enabled": tmock,
                    "service.status": tmock,
                    "service.info": info_mock,
                },
            ):
                assert service.dead("salt") == ret[2]

        with patch.dict(service.__opts__, {"test": False}):
            with patch.dict(
                service.__salt__,
                {
                    "service.enabled": fmock,
                    "service.stop": tmock,
                    "service.status": fmock,
                    "service.info": info_mock,
                },
            ):
                with patch.object(service, "_enable", mock):
                    assert service.dead("salt", True) == ret[1]

            with patch.dict(
                service.__salt__,
                {
                    "service.enabled": MagicMock(side_effect=[True, True, False]),
                    "service.status": MagicMock(side_effect=[True, False, False]),
                    "service.stop": MagicMock(return_value="stack"),
                    "service.info": info_mock,
                },
            ):
                with patch.object(
                    service,
                    "_enable",
                    MagicMock(return_value={"changes": "saltstack"}),
                ):
                    assert service.dead("salt", True) == ret[3]

            # test an initd which a wrong status (True even if dead)
            with patch.dict(
                service.__salt__,
                {
                    "service.enabled": MagicMock(side_effect=[False, False, False]),
                    "service.status": MagicMock(side_effect=[True, True, True]),
                    "service.stop": MagicMock(return_value="stack"),
                    "service.info": info_mock,
                },
            ):
                with patch.object(service, "_disable", MagicMock(return_value={})):
                    assert service.dead("salt", False) == ret[4]

        assert service.__context__ == {"service.state": "dead"}


def test_dead_with_missing_service():
    """
    Tests the case in which a service.dead state is executed on a state
    which does not exist.

    See https://github.com/saltstack/salt/issues/37511
    """
    name = "thisisnotarealservice"
    with patch.dict(
        service.__salt__, {"service.available": MagicMock(return_value=False)}
    ):
        ret = service.dead(name=name)
        assert ret == {
            "changes": {},
            "comment": "The named service {} is not available".format(name),
            "result": True,
            "name": name,
        }


def test_dead_in_offline_mode():
    """
    Tests the case in which a service.dead state is executed on an offline environemnt

    """
    name = "thisisnotarealservice"
    with patch.object(service, "_offline", MagicMock(return_value=True)):
        ret = service.dead(name=name)
        assert ret == {
            "changes": {},
            "comment": "Running in OFFLINE mode. Nothing to do",
            "result": True,
            "name": name,
        }


def test_enabled():
    """
    Test to verify that the service is enabled
    """
    ret = {"changes": "saltstack", "comment": "", "name": "salt", "result": True}
    mock = MagicMock(return_value={"changes": "saltstack"})
    with patch.object(service, "_enable", mock):
        assert service.enabled("salt") == ret
        assert service.__context__ == {"service.state": "enabled"}


def test_enabled_in_test_mode():
    ret = {
        "changes": {},
        "comment": "Service salt not present; if created in this state run, it would have been enabled",
        "name": "salt",
        "result": None,
    }
    mock = MagicMock(
        return_value={
            "result": "False",
            "comment": "The named service salt is not available",
        }
    )
    with patch.object(service, "_enable", mock), patch.dict(
        service.__opts__, {"test": True}
    ):
        assert service.enabled("salt") == ret
        assert service.__context__ == {"service.state": "enabled"}


def test_disabled():
    """
    Test to verify that the service is disabled
    """
    ret = {"changes": "saltstack", "comment": "", "name": "salt", "result": True}
    mock = MagicMock(return_value={"changes": "saltstack"})
    with patch.object(service, "_disable", mock):
        assert service.disabled("salt") == ret
        assert service.__context__ == {"service.state": "disabled"}


def test_mod_watch():
    """
    Test to the service watcher, called to invoke the watch command.
    """
    ret = [
        {
            "changes": {},
            "comment": "Service is already stopped",
            "name": "salt",
            "result": True,
        },
        {
            "changes": {},
            "comment": "Unable to trigger watch for service.stack",
            "name": "salt",
            "result": False,
        },
        {
            "changes": {},
            "comment": "Service is set to be started",
            "name": "salt",
            "result": None,
        },
        {
            "changes": {"salt": "salt"},
            "comment": "Service started",
            "name": "salt",
            "result": "salt",
        },
    ]

    mock = MagicMock(return_value=False)
    with patch.dict(service.__salt__, {"service.status": mock}):
        assert service.mod_watch("salt", "dead") == ret[0]

        with patch.dict(service.__salt__, {"service.start": func}):
            with patch.dict(service.__opts__, {"test": True}):
                assert service.mod_watch("salt", "running") == ret[2]

            with patch.dict(service.__opts__, {"test": False}):
                assert service.mod_watch("salt", "running") == ret[3]

        assert service.mod_watch("salt", "stack") == ret[1]


def test_mod_beacon(tmp_path):
    """
    Test to create a beacon based on a service
    """
    name = "sshd"

    with patch.dict(service.__salt__, {"beacons.list": MagicMock(return_value={})}):
        with patch.dict(service.__states__, {"beacon.present": beaconstate.present}):
            ret = service.mod_beacon(name, sfun="copy")
            expected = {
                "name": name,
                "changes": {},
                "result": False,
                "comment": "service.copy does not work with the beacon state function",
            }

            assert ret == expected

    event_returns = [
        {
            "complete": True,
            "tag": "/salt/minion/minion_beacons_list_complete",
            "beacons": {},
        },
        {
            "complete": True,
            "tag": "/salt/minion/minion_beacons_list_complete",
            "beacons": {},
        },
        {
            "complete": True,
            "tag": "/salt/minion/minion_beacons_list_available_complete",
            "beacons": ["service"],
        },
        {
            "valid": True,
            "tag": "/salt/minion/minion_beacon_validation_complete",
            "vcomment": "Valid beacon configuration",
        },
        {
            "complete": True,
            "tag": "/salt/minion/minion_beacon_add_complete",
            "beacons": {
                "beacon_service_sshd": [
                    {
                        "services": {
                            "sshd": {
                                "onchangeonly": True,
                                "delay": 0,
                                "uncleanshutdown": None,
                                "emitatstartup": False,
                            },
                        }
                    },
                    {"interval": 60},
                    {"beacon_module": "service"},
                ]
            },
        },
    ]
    mock = MagicMock(return_value=True)
    beacon_state_mocks = {
        "beacons.list": beaconmod.list_,
        "beacons.add": beaconmod.add,
        "beacons.list_available": beaconmod.list_available,
        "event.fire": mock,
    }

    beacon_mod_mocks = {"event.fire": mock}

    sock_dir = str(tmp_path / "test-socks")
    with patch.dict(service.__states__, {"beacon.present": beaconstate.present}):
        with patch.dict(beaconstate.__salt__, beacon_state_mocks):
            with patch.dict(beaconmod.__salt__, beacon_mod_mocks):
                with patch.dict(
                    beaconmod.__opts__, {"beacons": {}, "sock_dir": sock_dir}
                ):
                    with patch.object(
                        SaltEvent, "get_event", side_effect=event_returns
                    ):
                        ret = service.mod_beacon(name, sfun="running", beacon="True")
                        expected = {
                            "name": "beacon_service_sshd",
                            "changes": {},
                            "result": True,
                            "comment": "Adding beacon_service_sshd to beacons",
                        }

                        assert ret == expected


@pytest.mark.skip_on_darwin(reason="service.running is currently failing on OSX")
@pytest.mark.skip_if_not_root
@pytest.mark.destructive_test
@pytest.mark.slow_test
def test_running_with_reload(minion_opts):
    """
    Test that a running service is properly reloaded
    """
    # TODO: This is not a unit test, it interacts with the system. Move to functional.
    minion_opts["grains"] = salt.loader.grains(minion_opts)
    utils = salt.loader.utils(minion_opts)
    modules = salt.loader.minion_mods(minion_opts, utils=utils)

    service_name = "cron"
    cmd_name = "crontab"
    os_family = minion_opts["grains"]["os_family"]
    os_release = minion_opts["grains"]["osrelease"]
    if os_family == "RedHat":
        service_name = "crond"
    elif os_family == "Arch":
        service_name = "sshd"
        cmd_name = "systemctl"
    elif os_family == "MacOS":
        service_name = "org.ntp.ntpd"
        if int(os_release.split(".")[1]) >= 13:
            service_name = "com.openssh.sshd"
    elif os_family == "Windows":
        service_name = "Spooler"

    if os_family != "Windows" and salt.utils.path.which(cmd_name) is None:
        pytest.skip("{} is not installed".format(cmd_name))

    pre_srv_enabled = (
        True if service_name in modules["service.get_enabled"]() else False
    )
    post_srv_disable = False
    if not pre_srv_enabled:
        modules["service.enable"](service_name)
        post_srv_disable = True

    try:
        with patch.dict(service.__grains__, minion_opts["grains"]), patch.dict(
            service.__opts__, minion_opts
        ), patch.dict(service.__salt__, modules), patch.dict(
            service.__utils__, utils
        ), patch.dict(
            service.__opts__, {"test": False}
        ), patch(
            "salt.utils.systemd.offline", MagicMock(return_value=False)
        ):
            service.dead(service_name, enable=False)
            result = service.running(name=service_name, enable=True, reload=False)

        if salt.utils.platform.is_windows():
            comment = "Started service {}".format(service_name)
        else:
            comment = "Service {} has been enabled, and is running".format(service_name)
        expected = {
            "changes": {service_name: True},
            "comment": comment,
            "name": service_name,
            "result": True,
        }
        assert result == expected
    finally:
        if post_srv_disable:
            modules["service.disable"](service_name)
