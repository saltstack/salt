"""
    Unit tests for the salt.runners.heist_salt module
"""

import pytest
import salt.runners.heist as heist
import salt.runners.heist_salt as heist_salt
import salt.utils.hub as hub
from tests.support.mock import Mock, call, patch

pytest.importorskip("pop", reason="Test requires pop to be installed")
pytest.importorskip("heist", reason="Test requires heist to be installed")


@pytest.fixture
def configure_loader_modules():
    return {
        heist: {"__utils__": {"hub.hub": hub.hub}},
        hub: {"__context__": {}},
        heist_salt: {"__salt__": {"heist.deploy": heist.deploy}},
    }


@pytest.fixture()
def test_hub():
    """
    Test the hub using the heist project
    """
    return hub.hub(
        "heist",
        subs=["acct", "artifact", "rend", "roster", "service", "tunnel"],
        sub_dirs=["heist", "service"],
        confs=["heist", "acct"],
    )


def test_heist_salt_deploy(test_hub):
    """
    test heist salt deploy runner
    """
    mock_run = Mock(return_value=True)
    patch_platform = patch("salt.utils.platform.is_windows", return_value=False)
    patch_heist_hub = patch("salt.runners.heist.heist_hub", return_value=test_hub)
    patch_init = patch.object(test_hub.heist.init, "run_remotes", mock_run)
    patch_loop = patch.object(test_hub.pop.loop, "start", return_value=True)

    with patch_platform, patch_heist_hub, patch_init, patch_loop:
        heist_salt.deploy()
        assert mock_run.call_args_list == [
            call(
                "salt.minion",
                artifact_version="",
                roster=None,
                roster_data=None,
                roster_file="",
            )
        ]


def test_heist_salt_deploy_args(test_hub):
    """
    test heist_salt deploy runner when an
    args (roster_file) is passed.
    """
    mock_run = Mock(return_value=True)
    roster_file = "/tmp/testrosterfile"
    patch_platform = patch("salt.utils.platform.is_windows", return_value=False)
    patch_heist_hub = patch("salt.runners.heist.heist_hub", return_value=test_hub)
    patch_init = patch.object(test_hub.heist.init, "run_remotes", mock_run)
    patch_loop = patch.object(test_hub.pop.loop, "start", return_value=True)

    with patch_platform, patch_heist_hub, patch_init, patch_loop:
        heist_salt.deploy(roster_file=roster_file)
        assert mock_run.call_args_list == [
            call(
                "salt.minion",
                artifact_version="",
                roster=None,
                roster_data=None,
                roster_file=roster_file,
            )
        ]
