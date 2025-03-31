"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>

    Test cases for salt.modules.rh_service
"""

import textwrap

import pytest

import salt.modules.rh_service as rh_service
from tests.support.mock import MagicMock, patch


@pytest.fixture
def RET():
    return [
        "hostname",
        "mountall",
        "network-interface",
        "network-manager",
        "salt-api",
        "salt-master",
        "salt-minion",
    ]


@pytest.fixture
def configure_loader_modules():
    return {
        rh_service: {
            "_upstart_disable": None,
            "_upstart_enable": None,
            "_upstart_is_enabled": None,
        }
    }


def _m_lst():
    """
    Return value for [].
    """
    return MagicMock(return_value=[])


def _m_ret(RET):
    """
    Return value for RET.
    """
    return MagicMock(return_value=RET)


def _m_bool(bol=True):
    """
    Return Bool value.
    """
    return MagicMock(return_value=bol)


def test__chkconfig_is_enabled():
    """
    test _chkconfig_is_enabled function
    """
    name = "atd"
    chkconfig_out = textwrap.dedent(
        """\

        {}           0:off   1:off   2:off   3:on    4:on    5:on    6:off
        """.format(
            name
        )
    )
    xinetd_out = textwrap.dedent(
        """\
        xinetd based services:
                {}  on
        """.format(
            name
        )
    )

    with patch.object(rh_service, "_runlevel", MagicMock(return_value=3)):
        mock_run = MagicMock(return_value={"retcode": 0, "stdout": chkconfig_out})
        with patch.dict(rh_service.__salt__, {"cmd.run_all": mock_run}):
            assert rh_service._chkconfig_is_enabled(name)
            assert not rh_service._chkconfig_is_enabled(name, 2)
            assert rh_service._chkconfig_is_enabled(name, 3)

        mock_run = MagicMock(return_value={"retcode": 0, "stdout": xinetd_out})
        with patch.dict(rh_service.__salt__, {"cmd.run_all": mock_run}):
            assert rh_service._chkconfig_is_enabled(name)
            assert rh_service._chkconfig_is_enabled(name, 2)
            assert rh_service._chkconfig_is_enabled(name, 3)


# 'get_enabled' function tests: 1


def test_get_enabled(RET):
    """
    Test if it return the enabled services. Use the ``limit``
    param to restrict results to services of that type.
    """
    with patch.object(rh_service, "_upstart_services", _m_ret(RET)):
        with patch.object(
            rh_service, "_upstart_is_enabled", MagicMock(return_value=False)
        ):
            assert rh_service.get_enabled("upstart") == []

    mock_run = MagicMock(return_value="salt stack")
    with patch.dict(rh_service.__salt__, {"cmd.run": mock_run}):
        with patch.object(rh_service, "_sysv_services", _m_ret(RET)):
            with patch.object(rh_service, "_sysv_is_enabled", _m_bool()):
                assert rh_service.get_enabled("sysvinit") == RET

                with patch.object(rh_service, "_upstart_services", _m_lst()):
                    with patch.object(
                        rh_service,
                        "_upstart_is_enabled",
                        MagicMock(return_value=True),
                    ):
                        assert rh_service.get_enabled() == RET


# 'get_disabled' function tests: 1


def test_get_disabled(RET):
    """
    Test if it return the disabled services. Use the ``limit``
    param to restrict results to services of that type.
    """
    with patch.object(rh_service, "_upstart_services", _m_ret(RET)):
        with patch.object(
            rh_service, "_upstart_is_enabled", MagicMock(return_value=False)
        ):
            assert rh_service.get_disabled("upstart") == RET

    mock_run = MagicMock(return_value="salt stack")
    with patch.dict(rh_service.__salt__, {"cmd.run": mock_run}):
        with patch.object(rh_service, "_sysv_services", _m_ret(RET)):
            with patch.object(rh_service, "_sysv_is_enabled", _m_bool(False)):
                assert rh_service.get_disabled("sysvinit") == RET

                with patch.object(rh_service, "_upstart_services", _m_lst()):
                    with patch.object(
                        rh_service,
                        "_upstart_is_enabled",
                        MagicMock(return_value=False),
                    ):
                        assert rh_service.get_disabled() == RET


# 'get_all' function tests: 1


def test_get_all(RET):
    """
    Test if it return all installed services. Use the ``limit``
    param to restrict results to services of that type.
    """
    with patch.object(rh_service, "_upstart_services", _m_ret(RET)):
        assert rh_service.get_all("upstart") == RET

    with patch.object(rh_service, "_sysv_services", _m_ret(RET)):
        assert rh_service.get_all("sysvinit") == RET

        with patch.object(rh_service, "_upstart_services", _m_lst()):
            assert rh_service.get_all() == RET


# 'available' function tests: 1


def test_available():
    """
    Test if it return True if the named service is available.
    """
    with patch.object(rh_service, "_service_is_upstart", _m_bool()):
        assert rh_service.available("salt-api", "upstart")

    with patch.object(rh_service, "_service_is_sysv", _m_bool()):
        assert rh_service.available("salt-api", "sysvinit")

        with patch.object(rh_service, "_service_is_upstart", _m_bool()):
            assert rh_service.available("salt-api")


# 'missing' function tests: 1


def test_missing():
    """
    Test if it return True if the named service is not available.
    """
    with patch.object(rh_service, "_service_is_upstart", _m_bool(False)):
        assert rh_service.missing("sshd", "upstart")

        with patch.object(rh_service, "_service_is_sysv", _m_bool(False)):
            assert rh_service.missing("sshd")

    with patch.object(rh_service, "_service_is_sysv", _m_bool()):
        assert not rh_service.missing("sshd", "sysvinit")

        with patch.object(rh_service, "_service_is_upstart", _m_bool()):
            assert not rh_service.missing("sshd")


# 'start' function tests: 1


def test_start():
    """
    Test if it start the specified service.
    """
    with patch.object(rh_service, "_service_is_upstart", _m_bool()):
        with patch.dict(rh_service.__salt__, {"cmd.retcode": _m_bool(False)}):
            assert rh_service.start("salt-api")


# 'stop' function tests: 1


def test_stop():
    """
    Test if it stop the specified service.
    """
    with patch.object(rh_service, "_service_is_upstart", _m_bool()):
        with patch.dict(rh_service.__salt__, {"cmd.retcode": _m_bool(False)}):
            assert rh_service.stop("salt-api")


# 'restart' function tests: 1


def test_restart():
    """
    Test if it restart the specified service.
    """
    with patch.object(rh_service, "_service_is_upstart", _m_bool()):
        with patch.dict(rh_service.__salt__, {"cmd.retcode": _m_bool(False)}):
            assert rh_service.restart("salt-api")


# 'reload_' function tests: 1


def test_reload():
    """
    Test if it reload the specified service.
    """
    with patch.object(rh_service, "_service_is_upstart", _m_bool()):
        with patch.dict(rh_service.__salt__, {"cmd.retcode": _m_bool(False)}):
            assert rh_service.reload_("salt-api")


# 'status' function tests: 1


def test_status():
    """
    Test if it return the status for a service,
    returns a bool whether the service is running.
    """
    with patch.object(rh_service, "_service_is_upstart", _m_bool()):
        mock_run = MagicMock(return_value="start/running")
        with patch.dict(rh_service.__salt__, {"cmd.run": mock_run}):
            assert rh_service.status("salt-api")

    with patch.object(rh_service, "_service_is_upstart", _m_bool(False)):
        with patch.dict(rh_service.__salt__, {"status.pid": _m_bool()}):
            assert rh_service.status("salt-api", sig=True)

        mock_ret = MagicMock(return_value=0)
        with patch.dict(rh_service.__salt__, {"cmd.retcode": mock_ret}):
            assert rh_service.status("salt-api")


# 'enable' function tests: 1


def test_enable():
    """
    Test if it enable the named service to start at boot.
    """
    mock_bool = MagicMock(side_effect=[True, True, False])
    with patch.object(rh_service, "_service_is_upstart", mock_bool):
        with patch.object(
            rh_service, "_upstart_is_enabled", MagicMock(return_value=True)
        ):
            with patch.object(
                rh_service, "_upstart_enable", MagicMock(return_value=False)
            ):
                assert not rh_service.enable("salt-api")
            with patch.object(
                rh_service, "_upstart_enable", MagicMock(return_value=True)
            ):
                assert rh_service.enable("salt-api")

        with patch.object(rh_service, "_sysv_enable", _m_bool()):
            assert rh_service.enable("salt-api")


# 'disable' function tests: 1


def test_disable():
    """
    Test if it disable the named service to start at boot.
    """
    mock_bool = MagicMock(side_effect=[True, True, False])
    with patch.object(rh_service, "_service_is_upstart", mock_bool):
        with patch.object(
            rh_service, "_upstart_is_enabled", MagicMock(return_value=True)
        ):
            with patch.object(
                rh_service, "_upstart_disable", MagicMock(return_value=False)
            ):
                assert not rh_service.disable("salt-api")
            with patch.object(
                rh_service, "_upstart_disable", MagicMock(return_value=True)
            ):
                assert rh_service.disable("salt-api")

        with patch.object(rh_service, "_sysv_disable", _m_bool()):
            assert rh_service.disable("salt-api")


# 'enabled' function tests: 1


def test_enabled():
    """
    Test if it check to see if the named service is enabled
    to start on boot.
    """
    mock_bool = MagicMock(side_effect=[True, False])
    with patch.object(rh_service, "_service_is_upstart", mock_bool):
        with patch.object(
            rh_service, "_upstart_is_enabled", MagicMock(return_value=False)
        ):
            assert not rh_service.enabled("salt-api")

        with patch.object(rh_service, "_sysv_is_enabled", _m_bool()):
            assert rh_service.enabled("salt-api")


# 'disabled' function tests: 1


def test_disabled():
    """
    Test if it check to see if the named service is disabled
    to start on boot.
    """
    mock_bool = MagicMock(side_effect=[True, False])
    with patch.object(rh_service, "_service_is_upstart", mock_bool):
        with patch.object(
            rh_service, "_upstart_is_enabled", MagicMock(return_value=False)
        ):
            assert rh_service.disabled("salt-api")

        with patch.object(rh_service, "_sysv_is_enabled", _m_bool(False)):
            assert rh_service.disabled("salt-api")
