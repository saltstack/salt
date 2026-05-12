"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>

    Test cases for salt.modules.smf
"""

import pytest

import salt.modules.smf_service as smf
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {smf: {}}


def test_get_running():
    """
    Test to return the running services
    """
    with patch.dict(smf.__salt__, {"cmd.run": MagicMock(return_value="A online\n")}):
        assert smf.get_running() == ["A"]


def test_get_stopped():
    """
    Test to return the stopped services
    """
    with patch.dict(smf.__salt__, {"cmd.run": MagicMock(return_value="A\n")}):
        assert smf.get_stopped() == ["A"]


def test_available():
    """
    Test to returns ``True`` if the specified service is available,
    otherwise returns ``False``.
    """
    with patch.dict(smf.__salt__, {"cmd.run": MagicMock(return_value="A")}):
        with patch.object(smf, "get_all", return_value="A"):
            assert smf.available("A")


def test_missing():
    """
    The inverse of service.available.
    Returns ``True`` if the specified service is not available, otherwise
    returns ``False``.
    """
    with patch.dict(smf.__salt__, {"cmd.run": MagicMock(return_value="A")}):
        with patch.object(smf, "get_all", return_value="A"):
            assert not smf.missing("A")


def test_get_all():
    """
    Test to return all installed services
    """
    with patch.dict(smf.__salt__, {"cmd.run": MagicMock(return_value="A\n")}):
        assert smf.get_all() == ["A"]


def test_start():
    """
    Test to start the specified service
    """
    with patch.dict(
        smf.__salt__,
        {"cmd.retcode": MagicMock(side_effect=[False, 3, None, False, 4])},
    ):
        assert smf.start("name")

        assert smf.start("name")

        assert not smf.start("name")


def test_stop():
    """
    Test to stop the specified service
    """
    with patch.dict(smf.__salt__, {"cmd.retcode": MagicMock(return_value=False)}):
        assert smf.stop("name")


def test_restart():
    """
    Test to restart the named service
    """
    with patch.dict(
        smf.__salt__, {"cmd.retcode": MagicMock(side_effect=[False, True])}
    ):

        with patch.object(smf, "start", return_value="A"):
            assert smf.restart("name") == "A"

        assert not smf.restart("name")


def test_reload_():
    """
    Test to reload the named service
    """
    with patch.dict(
        smf.__salt__, {"cmd.retcode": MagicMock(side_effect=[False, True])}
    ):

        with patch.object(smf, "start", return_value="A"):
            assert smf.reload_("name") == "A"

        assert not smf.reload_("name")


def test_status():
    """
    Test to return the status for a service, returns a bool whether the
    service is running.
    """
    with patch.dict(
        smf.__salt__, {"cmd.run": MagicMock(side_effect=["online", "online1"])}
    ):
        assert smf.status("name")

        assert not smf.status("name")


def test_enable():
    """
    Test to enable the named service to start at boot
    """
    with patch.dict(smf.__salt__, {"cmd.retcode": MagicMock(return_value=False)}):
        assert smf.enable("name")


def test_disable():
    """
    Test to disable the named service to start at boot
    """
    with patch.dict(smf.__salt__, {"cmd.retcode": MagicMock(return_value=False)}):
        assert smf.disable("name")


def test_enabled():
    """
    Test to check to see if the named service is enabled to start on boot
    """
    with patch.dict(
        smf.__salt__,
        {"cmd.run": MagicMock(side_effect=["fmri", "A B true", "fmri", "A B false"])},
    ):
        assert smf.enabled("name")

        assert not smf.enabled("name")


def test_disabled():
    """
    Test to check to see if the named service is disabled to start on boot
    """
    with patch.object(smf, "enabled", return_value=False):
        assert smf.disabled("name")


def test_get_enabled():
    """
    Test to return the enabled services
    """
    with patch.object(smf, "_get_enabled_disabled", return_value=True):
        assert smf.get_enabled()


def test_get_disabled():
    """
    Test to return the disabled services
    """
    with patch.object(smf, "_get_enabled_disabled", return_value=True):
        assert smf.get_disabled()
