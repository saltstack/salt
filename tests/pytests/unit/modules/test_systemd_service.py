import os

import pytest

import salt.modules.systemd_service as systemd
import salt.utils.systemd
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch


@pytest.fixture()
def systemctl_status():
    return {
        "sshd.service": {
            "stdout": """\
* sshd.service - OpenSSH Daemon
   Loaded: loaded (/usr/lib/systemd/system/sshd.service; disabled; vendor preset: disabled)
   Active: inactive (dead)""",
            "stderr": "",
            "retcode": 3,
            "pid": 12345,
        },
        "foo.service": {
            "stdout": """\
* foo.service
   Loaded: not-found (Reason: No such file or directory)
   Active: inactive (dead)""",
            "stderr": "",
            "retcode": 3,
            "pid": 12345,
        },
    }


# This reflects systemd >= 231 behavior
@pytest.fixture()
def systemctl_status_gte_231():
    return {
        "bar.service": {
            "stdout": "Unit bar.service could not be found.",
            "stderr": "",
            "retcode": 4,
            "pid": 12345,
        },
    }


@pytest.fixture()
def list_unit_files():
    return """\
service1.service                           enabled              -
service2.service                           disabled             -
service3.service                           static               -
timer1.timer                               enabled              -
timer2.timer                               disabled             -
timer3.timer                               static               -
service4.service                           enabled              enabled
service5.service                           disabled             enabled
service6.service                           static               enabled
timer4.timer                               enabled              enabled
timer5.timer                               disabled             enabled
timer6.timer                               static               enabled
service7.service                           enabled              disabled
service8.service                           disabled             disabled
service9.service                           static               disabled
timer7.timer                               enabled              disabled
timer8.timer                               disabled             disabled
timer9.timer                               static               disabled
service10.service                          enabled
service11.service                          disabled
service12.service                          static
timer10.timer                              enabled
timer11.timer                              disabled
timer12.timer                              static"""


@pytest.fixture()
def configure_loader_modules():
    return {systemd: {}}


def test_systemctl_reload():
    """
    Test to Reloads systemctl
    """
    mock = MagicMock(
        side_effect=[
            {"stdout": "Who knows why?", "stderr": "", "retcode": 1, "pid": 12345},
            {"stdout": "", "stderr": "", "retcode": 0, "pid": 54321},
        ]
    )
    with patch.dict(systemd.__salt__, {"cmd.run_all": mock}):
        with pytest.raises(
            CommandExecutionError,
            match="Problem performing systemctl daemon-reload: Who knows why?",
        ):
            systemd.systemctl_reload()
        assert systemd.systemctl_reload() is True


def test_get_enabled(list_unit_files, systemctl_status):
    """
    Test to return a list of all enabled services
    """
    cmd_mock = MagicMock(return_value=list_unit_files)
    listdir_mock = MagicMock(return_value=["foo", "bar", "baz", "README"])
    sd_mock = MagicMock(
        return_value={x.replace(".service", "") for x in systemctl_status}
    )
    access_mock = MagicMock(
        side_effect=lambda x, y: x != os.path.join(systemd.INITSCRIPT_PATH, "README")
    )
    sysv_enabled_mock = MagicMock(side_effect=lambda x, _: x == "baz")

    with patch.dict(systemd.__salt__, {"cmd.run": cmd_mock}):
        with patch.object(os, "listdir", listdir_mock):
            with patch.object(systemd, "_get_systemd_services", sd_mock):
                with patch.object(os, "access", side_effect=access_mock):
                    with patch.object(systemd, "_sysv_enabled", sysv_enabled_mock):
                        assert systemd.get_enabled() == [
                            "baz",
                            "service1",
                            "service10",
                            "service4",
                            "service7",
                            "timer1.timer",
                            "timer10.timer",
                            "timer4.timer",
                            "timer7.timer",
                        ]


def test_get_disabled(list_unit_files, systemctl_status):
    """
    Test to return a list of all disabled services
    """
    cmd_mock = MagicMock(return_value=list_unit_files)
    # 'foo' should collide with the systemd services (as returned by
    # sd_mock) and thus not be returned by _get_sysv_services(). It doesn't
    # matter that it's not part of the _LIST_UNIT_FILES output, we just
    # want to ensure that 'foo' isn't identified as a disabled initscript
    # even though below we are mocking it to show as not enabled (since
    # only 'baz' will be considered an enabled sysv service).
    listdir_mock = MagicMock(return_value=["foo", "bar", "baz", "README"])
    sd_mock = MagicMock(
        return_value={x.replace(".service", "") for x in systemctl_status}
    )
    access_mock = MagicMock(
        side_effect=lambda x, y: x != os.path.join(systemd.INITSCRIPT_PATH, "README")
    )
    sysv_enabled_mock = MagicMock(side_effect=lambda x, _: x == "baz")

    with patch.dict(systemd.__salt__, {"cmd.run": cmd_mock}):
        with patch.object(os, "listdir", listdir_mock):
            with patch.object(systemd, "_get_systemd_services", sd_mock):
                with patch.object(os, "access", side_effect=access_mock):
                    with patch.object(systemd, "_sysv_enabled", sysv_enabled_mock):
                        assert systemd.get_disabled() == [
                            "bar",
                            "service11",
                            "service2",
                            "service5",
                            "service8",
                            "timer11.timer",
                            "timer2.timer",
                            "timer5.timer",
                            "timer8.timer",
                        ]


def test_get_static(list_unit_files, systemctl_status):
    """
    Test to return a list of all disabled services
    """
    cmd_mock = MagicMock(return_value=list_unit_files)
    # 'foo' should collide with the systemd services (as returned by
    # sd_mock) and thus not be returned by _get_sysv_services(). It doesn't
    # matter that it's not part of the _LIST_UNIT_FILES output, we just
    # want to ensure that 'foo' isn't identified as a disabled initscript
    # even though below we are mocking it to show as not enabled (since
    # only 'baz' will be considered an enabled sysv service).
    listdir_mock = MagicMock(return_value=["foo", "bar", "baz", "README"])
    sd_mock = MagicMock(
        return_value={x.replace(".service", "") for x in systemctl_status}
    )
    access_mock = MagicMock(
        side_effect=lambda x, y: x != os.path.join(systemd.INITSCRIPT_PATH, "README")
    )
    sysv_enabled_mock = MagicMock(side_effect=lambda x, _: x == "baz")

    with patch.dict(systemd.__salt__, {"cmd.run": cmd_mock}):
        with patch.object(os, "listdir", listdir_mock):
            with patch.object(systemd, "_get_systemd_services", sd_mock):
                with patch.object(os, "access", side_effect=access_mock):
                    with patch.object(systemd, "_sysv_enabled", sysv_enabled_mock):
                        assert systemd.get_static() == [
                            "service12",
                            "service3",
                            "service6",
                            "service9",
                            "timer12.timer",
                            "timer3.timer",
                            "timer6.timer",
                            "timer9.timer",
                        ]


def test_get_all():
    """
    Test to return a list of all available services
    """
    listdir_mock = MagicMock(
        side_effect=[
            ["foo.service", "multi-user.target.wants", "mytimer.timer"],
            [],
            ["foo.service", "multi-user.target.wants", "bar.service"],
            ["mysql", "nginx", "README"],
        ]
    )
    access_mock = MagicMock(
        side_effect=lambda x, y: x != os.path.join(systemd.INITSCRIPT_PATH, "README")
    )
    with patch.object(os, "listdir", listdir_mock):
        with patch.object(os, "access", side_effect=access_mock):
            assert systemd.get_all() == [
                "bar",
                "foo",
                "mysql",
                "mytimer.timer",
                "nginx",
            ]


def test_available(systemctl_status, systemctl_status_gte_231):
    """
    Test to check that the given service is available
    """
    mock = MagicMock(side_effect=lambda x: systemctl_status[x])

    # systemd < 231
    with patch.dict(systemd.__context__, {"salt.utils.systemd.version": 230}):
        with patch.object(systemd, "_systemctl_status", mock), patch.object(
            systemd, "offline", MagicMock(return_value=False)
        ):
            assert systemd.available("sshd.service") is True
            assert systemd.available("foo.service") is False

    # systemd >= 231
    with patch.dict(systemd.__context__, {"salt.utils.systemd.version": 231}):
        with patch.dict(systemctl_status, systemctl_status_gte_231):
            with patch.object(systemd, "_systemctl_status", mock), patch.object(
                systemd, "offline", MagicMock(return_value=False)
            ):
                assert systemd.available("sshd.service") is True
                assert systemd.available("bar.service") is False

    # systemd < 231 with retcode/output changes backported (e.g. RHEL 7.3)
    with patch.dict(systemd.__context__, {"salt.utils.systemd.version": 219}):
        with patch.dict(systemctl_status, systemctl_status_gte_231):
            with patch.object(systemd, "_systemctl_status", mock), patch.object(
                systemd, "offline", MagicMock(return_value=False)
            ):
                assert systemd.available("sshd.service") is True
                assert systemd.available("bar.service") is False


def test_missing(systemctl_status, systemctl_status_gte_231):
    """
    Test to the inverse of service.available.
    """
    mock = MagicMock(side_effect=lambda x: systemctl_status[x])

    # systemd < 231
    with patch.dict(systemd.__context__, {"salt.utils.systemd.version": 230}):
        with patch.object(systemd, "_systemctl_status", mock), patch.object(
            systemd, "offline", MagicMock(return_value=False)
        ):
            assert systemd.missing("sshd.service") is False
            assert systemd.missing("foo.service") is True

    # systemd >= 231
    with patch.dict(systemd.__context__, {"salt.utils.systemd.version": 231}):
        with patch.dict(systemctl_status, systemctl_status_gte_231):
            with patch.object(systemd, "_systemctl_status", mock), patch.object(
                systemd, "offline", MagicMock(return_value=False)
            ):
                assert systemd.missing("sshd.service") is False
                assert systemd.missing("bar.service") is True

    # systemd < 231 with retcode/output changes backported (e.g. RHEL 7.3)
    with patch.dict(systemd.__context__, {"salt.utils.systemd.version": 219}):
        with patch.dict(systemctl_status, systemctl_status_gte_231):
            with patch.object(systemd, "_systemctl_status", mock), patch.object(
                systemd, "offline", MagicMock(return_value=False)
            ):
                assert systemd.missing("sshd.service") is False
                assert systemd.missing("bar.service") is True


def test_show():
    """
    Test to show properties of one or more units/jobs or the manager
    """
    show_output = "a=b\nc=d\ne={ f=g ; h=i }\nWants=foo.service bar.service\n"
    mock = MagicMock(return_value=show_output)
    with patch.dict(systemd.__salt__, {"cmd.run": mock}):
        assert systemd.show("sshd") == {
            "a": "b",
            "c": "d",
            "e": {"f": "g", "h": "i"},
            "Wants": ["foo.service", "bar.service"],
        }


def test_execs():
    """
    Test to return a list of all files specified as ``ExecStart`` for all
    services
    """
    mock = MagicMock(return_value=["a", "b"])
    with patch.object(systemd, "get_all", mock):
        mock = MagicMock(return_value={"ExecStart": {"path": "c"}})
        with patch.object(systemd, "show", mock):
            assert systemd.execs() == {"a": "c", "b": "c"}


@pytest.fixture()
def unit_name():
    return "foo"


@pytest.fixture()
def mock_none():
    return MagicMock(return_value=None)


@pytest.fixture()
def mock_success():
    return MagicMock(return_value=0)


@pytest.fixture()
def mock_failure():
    return MagicMock(return_value=1)


@pytest.fixture()
def mock_true():
    return MagicMock(return_value=True)


@pytest.fixture()
def mock_false():
    return MagicMock(return_value=False)


@pytest.fixture()
def mock_empty_list():
    return MagicMock(return_value=[])


@pytest.fixture()
def mock_run_all_success():
    return MagicMock(
        return_value={"retcode": 0, "stdout": "", "stderr": "", "pid": 12345}
    )


@pytest.fixture()
def mock_run_all_failure():
    return MagicMock(
        return_value={"retcode": 1, "stdout": "", "stderr": "", "pid": 12345}
    )


@pytest.mark.parametrize(
    "action,no_block",
    [
        ["start", False],
        ["start", True],
        ["stop", False],
        ["stop", True],
        ["restart", False],
        ["restart", True],
        ["reload_", False],
        ["reload_", True],
        ["force_reload", False],
        ["force_reload", True],
        ["enable", False],
        ["enable", True],
        ["disable", False],
        ["disable", True],
    ],
)
def test_change_state(
    unit_name,
    mock_none,
    mock_empty_list,
    mock_true,
    mock_false,
    mock_run_all_success,
    mock_run_all_failure,
    action,
    no_block,
):
    """
    Common code for start/stop/restart/reload/force_reload tests
    """
    # We want the traceback if the function name can't be found in the
    # systemd execution module.
    func = getattr(systemd, action)
    # Remove trailing _ in "reload_"
    action = action.rstrip("_").replace("_", "-")
    systemctl_command = ["/bin/systemctl"]
    if no_block:
        systemctl_command.append("--no-block")
    systemctl_command.extend([action, unit_name + ".service"])
    scope_prefix = ["/bin/systemd-run", "--scope"]

    assert_kwargs = {"python_shell": False}
    if action in ("enable", "disable"):
        assert_kwargs["ignore_retcode"] = True

    with patch("salt.utils.path.which", lambda x: "/bin/" + x):
        with patch.object(systemd, "_check_for_unit_changes", mock_none):
            with patch.object(systemd, "_unit_file_changed", mock_none):
                with patch.object(systemd, "_check_unmask", mock_none):
                    with patch.object(systemd, "_get_sysv_services", mock_empty_list):

                        # Has scopes available
                        with patch.object(salt.utils.systemd, "has_scope", mock_true):

                            # Scope enabled, successful
                            with patch.dict(
                                systemd.__salt__,
                                {
                                    "config.get": mock_true,
                                    "cmd.run_all": mock_run_all_success,
                                },
                            ):
                                ret = func(unit_name, no_block=no_block)
                                assert ret is True
                                mock_run_all_success.assert_called_with(
                                    scope_prefix + systemctl_command, **assert_kwargs
                                )

                            # Scope enabled, failed
                            with patch.dict(
                                systemd.__salt__,
                                {
                                    "config.get": mock_true,
                                    "cmd.run_all": mock_run_all_failure,
                                },
                            ):
                                if action in ("stop", "disable"):
                                    ret = func(unit_name, no_block=no_block)
                                    assert ret is False
                                else:
                                    with pytest.raises(CommandExecutionError):
                                        func(unit_name, no_block=no_block)
                                mock_run_all_failure.assert_called_with(
                                    scope_prefix + systemctl_command, **assert_kwargs
                                )

                            # Scope disabled, successful
                            with patch.dict(
                                systemd.__salt__,
                                {
                                    "config.get": mock_false,
                                    "cmd.run_all": mock_run_all_success,
                                },
                            ):
                                ret = func(unit_name, no_block=no_block)
                                assert ret is True
                                mock_run_all_success.assert_called_with(
                                    systemctl_command, **assert_kwargs
                                )

                            # Scope disabled, failed
                            with patch.dict(
                                systemd.__salt__,
                                {
                                    "config.get": mock_false,
                                    "cmd.run_all": mock_run_all_failure,
                                },
                            ):
                                if action in ("stop", "disable"):
                                    ret = func(unit_name, no_block=no_block)
                                    assert ret is False
                                else:
                                    with pytest.raises(CommandExecutionError):
                                        func(unit_name, no_block=no_block)
                                mock_run_all_failure.assert_called_with(
                                    systemctl_command, **assert_kwargs
                                )

                        # Does not have scopes available
                        with patch.object(salt.utils.systemd, "has_scope", mock_false):

                            # The results should be the same irrespective of
                            # whether or not scope is enabled, since scope is not
                            # available, so we repeat the below tests with it both
                            # enabled and disabled.
                            for scope_mock in (mock_true, mock_false):

                                # Successful
                                with patch.dict(
                                    systemd.__salt__,
                                    {
                                        "config.get": scope_mock,
                                        "cmd.run_all": mock_run_all_success,
                                    },
                                ):
                                    ret = func(unit_name, no_block=no_block)
                                    assert ret is True
                                    mock_run_all_success.assert_called_with(
                                        systemctl_command, **assert_kwargs
                                    )

                                # Failed
                                with patch.dict(
                                    systemd.__salt__,
                                    {
                                        "config.get": scope_mock,
                                        "cmd.run_all": mock_run_all_failure,
                                    },
                                ):
                                    if action in ("stop", "disable"):
                                        ret = func(unit_name, no_block=no_block)
                                        assert ret is False
                                    else:
                                        with pytest.raises(CommandExecutionError):
                                            func(unit_name, no_block=no_block)
                                    mock_run_all_failure.assert_called_with(
                                        systemctl_command, **assert_kwargs
                                    )


@pytest.mark.parametrize(
    "action,runtime",
    [
        ["mask", False],
        ["mask", True],
        ["unmask_", False],
        ["unmask_", True],
    ],
)
def test_mask_unmask(
    unit_name,
    mock_none,
    mock_true,
    mock_false,
    mock_run_all_success,
    mock_run_all_failure,
    action,
    runtime,
):
    """
    Common code for mask/unmask tests
    """
    # We want the traceback if the function name can't be found in the
    # systemd execution module, so don't provide a fallback value for the
    # call to getattr() here.
    func = getattr(systemd, action)
    # Remove trailing _ in "unmask_"
    action = action.rstrip("_").replace("_", "-")
    systemctl_command = ["/bin/systemctl", action]
    if runtime:
        systemctl_command.append("--runtime")
    systemctl_command.append(unit_name + ".service")
    scope_prefix = ["/bin/systemd-run", "--scope"]

    args = [unit_name, runtime]

    masked_mock = mock_true if action == "unmask" else mock_false

    with patch("salt.utils.path.which", lambda x: "/bin/" + x):
        with patch.object(systemd, "_check_for_unit_changes", mock_none):
            if action == "unmask":
                mock_not_run = MagicMock(
                    return_value={
                        "retcode": 0,
                        "stdout": "",
                        "stderr": "",
                        "pid": 12345,
                    }
                )
                with patch.dict(systemd.__salt__, {"cmd.run_all": mock_not_run}):
                    with patch.object(systemd, "masked", mock_false):
                        # Test not masked (should take no action and return True)
                        assert systemd.unmask_(unit_name) is True
                        # Also should not have called cmd.run_all
                        assert mock_not_run.call_count == 0

            with patch.object(systemd, "masked", masked_mock):

                # Has scopes available
                with patch.object(salt.utils.systemd, "has_scope", mock_true):

                    # Scope enabled, successful
                    with patch.dict(
                        systemd.__salt__,
                        {
                            "config.get": mock_true,
                            "cmd.run_all": mock_run_all_success,
                        },
                    ):
                        ret = func(*args)
                        assert ret is True
                        mock_run_all_success.assert_called_with(
                            scope_prefix + systemctl_command,
                            python_shell=False,
                            redirect_stderr=True,
                        )

                    # Scope enabled, failed
                    with patch.dict(
                        systemd.__salt__,
                        {
                            "config.get": mock_true,
                            "cmd.run_all": mock_run_all_failure,
                        },
                    ):
                        with pytest.raises(CommandExecutionError):
                            func(*args)
                        mock_run_all_failure.assert_called_with(
                            scope_prefix + systemctl_command,
                            python_shell=False,
                            redirect_stderr=True,
                        )

                    # Scope disabled, successful
                    with patch.dict(
                        systemd.__salt__,
                        {
                            "config.get": mock_false,
                            "cmd.run_all": mock_run_all_success,
                        },
                    ):
                        ret = func(*args)
                        assert ret is True
                        mock_run_all_success.assert_called_with(
                            systemctl_command,
                            python_shell=False,
                            redirect_stderr=True,
                        )

                    # Scope disabled, failed
                    with patch.dict(
                        systemd.__salt__,
                        {
                            "config.get": mock_false,
                            "cmd.run_all": mock_run_all_failure,
                        },
                    ):
                        with pytest.raises(CommandExecutionError):
                            func(*args)
                        mock_run_all_failure.assert_called_with(
                            systemctl_command,
                            python_shell=False,
                            redirect_stderr=True,
                        )

                # Does not have scopes available
                with patch.object(salt.utils.systemd, "has_scope", mock_false):

                    # The results should be the same irrespective of
                    # whether or not scope is enabled, since scope is not
                    # available, so we repeat the below tests with it both
                    # enabled and disabled.
                    for scope_mock in (mock_true, mock_false):

                        # Successful
                        with patch.dict(
                            systemd.__salt__,
                            {
                                "config.get": scope_mock,
                                "cmd.run_all": mock_run_all_success,
                            },
                        ):
                            ret = func(*args)
                            assert ret is True
                            mock_run_all_success.assert_called_with(
                                systemctl_command,
                                python_shell=False,
                                redirect_stderr=True,
                            )

                        # Failed
                        with patch.dict(
                            systemd.__salt__,
                            {
                                "config.get": scope_mock,
                                "cmd.run_all": mock_run_all_failure,
                            },
                        ):
                            with pytest.raises(CommandExecutionError):
                                func(*args)
                            mock_run_all_failure.assert_called_with(
                                systemctl_command,
                                python_shell=False,
                                redirect_stderr=True,
                            )


def test_firstboot():
    """
    Test service.firstboot without parameters
    """
    result = {"retcode": 0, "stdout": "stdout"}
    salt_mock = {
        "cmd.run_all": MagicMock(return_value=result),
    }
    with patch("salt.utils.path.which", lambda x: "/bin/" + x):
        with patch.dict(systemd.__salt__, salt_mock):
            assert systemd.firstboot()
            salt_mock["cmd.run_all"].assert_called_with(["/bin/systemd-firstboot"])


def test_firstboot_params():
    """
    Test service.firstboot with parameters
    """
    result = {"retcode": 0, "stdout": "stdout"}
    salt_mock = {
        "cmd.run_all": MagicMock(return_value=result),
    }
    with patch("salt.utils.path.which", lambda x: "/bin/" + x):
        with patch.dict(systemd.__salt__, salt_mock):
            assert systemd.firstboot(
                locale="en_US.UTF-8",
                locale_message="en_US.UTF-8",
                keymap="jp",
                timezone="Europe/Berlin",
                hostname="node-001",
                machine_id="1234567890abcdef",
                root="/mnt",
            )
            salt_mock["cmd.run_all"].assert_called_with(
                [
                    "/bin/systemd-firstboot",
                    "--locale",
                    "en_US.UTF-8",
                    "--locale-message",
                    "en_US.UTF-8",
                    "--keymap",
                    "jp",
                    "--timezone",
                    "Europe/Berlin",
                    "--hostname",
                    "node-001",
                    "--machine-ID",
                    "1234567890abcdef",
                    "--root",
                    "/mnt",
                ]
            )


def test_firstboot_error():
    """
    Test service.firstboot error
    """
    result = {"retcode": 1, "stderr": "error"}
    salt_mock = {
        "cmd.run_all": MagicMock(return_value=result),
    }
    with patch.dict(systemd.__salt__, salt_mock):
        with pytest.raises(CommandExecutionError):
            assert systemd.firstboot()
