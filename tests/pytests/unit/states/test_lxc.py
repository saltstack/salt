"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.states.lxc as lxc
import salt.utils.versions
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {lxc: {}}


def test_present():
    """
    Test to verify the named container if it exist.
    """
    name = "web01"

    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    mock = MagicMock(side_effect=[False, True, True, True, True, True, True])
    mock_t = MagicMock(
        side_effect=[None, True, "frozen", "frozen", "stopped", "running", "running"]
    )
    with patch.dict(lxc.__salt__, {"lxc.exists": mock, "lxc.state": mock_t}):
        comt = "Clone source 'True' does not exist"
        ret.update({"comment": comt})
        assert lxc.present(name, clone_from=True) == ret

        with patch.dict(lxc.__opts__, {"test": True}):
            comt = "Container 'web01' will be cloned from True"
            ret.update({"comment": comt, "result": None})
            assert lxc.present(name, clone_from=True) == ret

            comt = "Container 'web01' already exists"
            ret.update({"comment": comt, "result": True})
            assert lxc.present(name, clone_from=True) == ret

            comt = "Container 'web01' would be unfrozen"
            ret.update({"comment": comt, "result": None})
            assert lxc.present(name, running=True, clone_from=True) == ret

            comt = "Container '{}' would be stopped".format(name)
            ret.update({"comment": comt, "result": None})
            assert lxc.present(name, running=False, clone_from=True) == ret

            comt = "Container 'web01' already exists and is stopped"
            ret.update({"comment": comt, "result": True})
            assert lxc.present(name, running=False, clone_from=True) == ret

        with patch.dict(lxc.__opts__, {"test": False}):
            comt = "Container 'web01' already exists"
            ret.update({"comment": comt, "result": True})
            assert lxc.present(name, clone_from=True) == ret


def test_absent():
    """
    Test to ensure a container is not present, destroying it if present.
    """
    name = "web01"

    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    mock = MagicMock(side_effect=[False, True, True])
    mock_des = MagicMock(return_value={"state": True})
    with patch.dict(lxc.__salt__, {"lxc.exists": mock, "lxc.destroy": mock_des}):
        comt = "Container '{}' does not exist".format(name)
        ret.update({"comment": comt})
        assert lxc.absent(name) == ret

        with patch.dict(lxc.__opts__, {"test": True}):
            comt = "Container '{}' would be destroyed".format(name)
            ret.update({"comment": comt, "result": None})
            assert lxc.absent(name) == ret

        with patch.dict(lxc.__opts__, {"test": False}):
            comt = "Container '{}' was destroyed".format(name)
            ret.update({"comment": comt, "result": True, "changes": {"state": True}})
            assert lxc.absent(name) == ret


def test_running():
    """
    Test to ensure that a container is running.
    """
    name = "web01"

    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    mock = MagicMock(return_value={"state": {"new": "stop"}})
    mock_t = MagicMock(side_effect=[None, "running", "stopped", "start"])
    with patch.dict(
        lxc.__salt__, {"lxc.exists": mock, "lxc.state": mock_t, "lxc.start": mock}
    ):
        comt = "Container '{}' does not exist".format(name)
        ret.update({"comment": comt})
        assert lxc.running(name) == ret

        comt = "Container 'web01' is already running"
        ret.update({"comment": comt, "result": True})
        assert lxc.running(name) == ret

        with patch.dict(lxc.__opts__, {"test": True}):
            comt = "Container 'web01' would be started"
            ret.update({"comment": comt, "result": None})
            assert lxc.running(name) == ret

        with patch.dict(lxc.__opts__, {"test": False}):
            comt = "Unable to start container 'web01'"
            ret.update(
                {
                    "comment": comt,
                    "result": False,
                    "changes": {"state": {"new": "stop", "old": "start"}},
                }
            )
            assert lxc.running(name) == ret


def test_frozen():
    """
    Test to ensure that a container is frozen.
    """
    name = "web01"

    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    mock = MagicMock(return_value={"state": {"new": "stop"}})
    mock_t = MagicMock(side_effect=["frozen", "stopped", "stopped"])
    with patch.dict(lxc.__salt__, {"lxc.freeze": mock, "lxc.state": mock_t}):
        comt = "Container '{}' is already frozen".format(name)
        ret.update({"comment": comt})
        assert lxc.frozen(name) == ret

        with patch.dict(lxc.__opts__, {"test": True}):
            comt = "Container 'web01' would be started and frozen"
            ret.update({"comment": comt, "result": None})
            assert lxc.frozen(name) == ret

        with patch.dict(lxc.__opts__, {"test": False}):
            comt = "Unable to start and freeze container 'web01'"
            ret.update(
                {
                    "comment": comt,
                    "result": False,
                    "changes": {"state": {"new": "stop", "old": "stopped"}},
                }
            )
            assert lxc.frozen(name) == ret


def test_stopped():
    """
    Test to ensure that a container is stopped.
    """
    name = "web01"

    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    mock = MagicMock(return_value={"state": {"new": "stop"}})
    mock_t = MagicMock(side_effect=[None, "stopped", "frozen", "frozen"])
    with patch.dict(lxc.__salt__, {"lxc.stop": mock, "lxc.state": mock_t}):
        comt = "Container '{}' does not exist".format(name)
        ret.update({"comment": comt})
        assert lxc.stopped(name) == ret

        comt = "Container '{}' is already stopped".format(name)
        ret.update({"comment": comt, "result": True})
        assert lxc.stopped(name) == ret

        with patch.dict(lxc.__opts__, {"test": True}):
            comt = "Container 'web01' would be stopped"
            ret.update({"comment": comt, "result": None})
            assert lxc.stopped(name) == ret

        with patch.dict(lxc.__opts__, {"test": False}):
            comt = "Unable to stop container 'web01'"
            ret.update(
                {
                    "comment": comt,
                    "result": False,
                    "changes": {"state": {"new": "stop", "old": "frozen"}},
                }
            )
            assert lxc.stopped(name) == ret


def test_set_pass():
    """
    Test to execute set_pass func.
    """
    comment = (
        "The lxc.set_pass state is no longer supported. Please see "
        "the LXC states documentation for further information."
    )
    ret = {"name": "web01", "comment": comment, "result": False, "changes": {}}

    assert lxc.set_pass("web01") == ret


def test_edited_conf():
    """
    Test to edit LXC configuration options
    """
    name = "web01"

    comment = "{} lxc.conf will be edited".format(name)

    ret = {"name": name, "result": True, "comment": comment, "changes": {}}

    with patch.object(salt.utils.versions, "warn_until", MagicMock()):
        with patch.dict(lxc.__opts__, {"test": True}):
            assert lxc.edited_conf(name) == ret

        with patch.dict(lxc.__opts__, {"test": False}):
            mock = MagicMock(return_value={})
            with patch.dict(lxc.__salt__, {"lxc.update_lxc_conf": mock}):
                assert lxc.edited_conf(name) == {"name": "web01"}
