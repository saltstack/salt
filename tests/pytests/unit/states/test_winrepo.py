"""
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
"""

import os

import pytest
import salt.config
import salt.states.winrepo as winrepo
import salt.utils.path
from salt.syspaths import BASE_FILE_ROOTS_DIR
from tests.support.mock import MagicMock, patch


class MockRunnerClient:
    """
    Mock RunnerClient class
    """

    def __init__(self):
        pass

    class RunnerClient:
        """
        Mock RunnerClient class
        """

        def __init__(self, master_config):
            """
            init method
            """

        @staticmethod
        def cmd(arg1, arg2):
            """
            Mock cmd method
            """
            # TODO: Figure out how to have this return an empty dict or a dict
            # TODO: with expected data
            return []


@pytest.fixture
def configure_loader_modules():
    patcher = patch("salt.states.winrepo.salt.runner", MockRunnerClient)
    patcher.start()
    return {winrepo: {}}


def test_genrepo():
    """
    Test to refresh the winrepo.p file of the repository
    """
    expected = {"name": "salt", "changes": {}, "result": False, "comment": ""}
    mock_config = MagicMock(
        return_value={"winrepo_dir": "salt", "winrepo_cachefile": "abc"}
    )
    mock_stat = MagicMock(return_value=[0, 1, 2, 3, 4, 5, 6, 7, 8])
    mock_empty_list = MagicMock(return_value=[])
    with patch.object(salt.config, "master_config", mock_config), patch.object(
        os, "stat", mock_stat
    ), patch.object(salt.utils.path, "os_walk", mock_empty_list), patch.dict(
        winrepo.__opts__, {"test": True}
    ):
        # With test=True
        expected.update({"comment": "", "result": None})
        assert winrepo.genrepo("salt") == expected

        with patch.dict(winrepo.__opts__, {"test": False}):
            # With test=False
            expected.update({"result": True})
            assert winrepo.genrepo("salt") == expected

            # Now with no changes, existing winrepo.p
            expected.update({"changes": {"winrepo": []}})
            assert winrepo.genrepo("salt", True) == expected


def test_genrepo_no_dir():
    """
    Test genrepo when the dir does not exist
    """
    expected = {
        "name": "salt",
        "changes": {},
        "result": False,
        "comment": "{} is missing".format(
            os.sep.join([BASE_FILE_ROOTS_DIR, "win", "repo"])
        ),
    }
    with patch.dict(winrepo.__opts__, {"test": False}), patch(
        "os.path.exists", MagicMock(return_value=False)
    ):
        ret = winrepo.genrepo("salt")
        assert ret == expected


def test_genrepo_no_dir_force():
    """
    Test genrepo when the dir does not exist and force=True
    """
    expected = {
        "name": "salt",
        "changes": {"winrepo": []},
        "result": True,
        "comment": "",
    }
    with patch.dict(winrepo.__opts__, {"test": False}), patch(
        "os.path.exists", MagicMock(return_value=False)
    ):
        ret = winrepo.genrepo("salt", force=True)
        assert ret == expected
