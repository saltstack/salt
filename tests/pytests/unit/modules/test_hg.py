"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>

    Test cases for salt.modules.hg
"""


import pytest

import salt.modules.hg as hg
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {hg: {}}


def test_revision():
    """
    Test for Returns the long hash of a given identifier
    """
    mock = MagicMock(
        side_effect=[{"retcode": 0, "stdout": "A"}, {"retcode": 1, "stdout": "A"}]
    )
    with patch.dict(hg.__salt__, {"cmd.run_all": mock}):
        assert hg.revision("cwd") == "A"

        assert hg.revision("cwd") == ""


def test_describe():
    """
    Test for Mimic git describe.
    """
    with patch.dict(hg.__salt__, {"cmd.run_stdout": MagicMock(return_value="A")}):
        with patch.object(hg, "revision", return_value=False):
            assert hg.describe("cwd") == "A"


def test_archive():
    """
    Test for Export a tarball from the repository
    """
    with patch.dict(hg.__salt__, {"cmd.run": MagicMock(return_value="A")}):
        assert hg.archive("cwd", "output") == "A"


def test_pull():
    """
    Test for Perform a pull on the given repository
    """
    with patch.dict(
        hg.__salt__,
        {"cmd.run_all": MagicMock(return_value={"retcode": 0, "stdout": "A"})},
    ):
        assert hg.pull("cwd") == "A"


def test_update():
    """
    Test for Update to a given revision
    """
    with patch.dict(
        hg.__salt__,
        {"cmd.run_all": MagicMock(return_value={"retcode": 0, "stdout": "A"})},
    ):
        assert hg.update("cwd", "rev") == "A"


def test_clone():
    """
    Test for Clone a new repository
    """
    with patch.dict(
        hg.__salt__,
        {"cmd.run_all": MagicMock(return_value={"retcode": 0, "stdout": "A"})},
    ):
        assert hg.clone("cwd", "repository") == "A"


def test_status_single():
    """
    Test for Status to a given repository
    """
    with patch.dict(
        hg.__salt__,
        {"cmd.run_stdout": MagicMock(return_value="A added 0\nA added 1\nM modified")},
    ):
        assert hg.status("cwd") == {
            "added": ["added 0", "added 1"],
            "modified": ["modified"],
        }


def test_status_multiple():
    """
    Test for Status to a given repository (cwd is list)
    """
    with patch.dict(
        hg.__salt__,
        {
            "cmd.run_stdout": MagicMock(
                side_effect=(
                    lambda *args, **kwargs: {
                        "dir 0": "A file 0\n",
                        "dir 1": "M file 1",
                    }[kwargs["cwd"]]
                )
            )
        },
    ):
        assert hg.status(["dir 0", "dir 1"]) == {
            "dir 0": {"added": ["file 0"]},
            "dir 1": {"modified": ["file 1"]},
        }
