"""
Unit tests for chocolatey state
"""

import logging

import pytest

import salt.modules.chocolatey as chocolatey_mod
import salt.states.chocolatey as chocolatey
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def choco_path():
    return "C:\\path\\to\\chocolatey.exe"


@pytest.fixture
def configure_loader_modules(minion_opts):
    return {
        chocolatey: {
            "__opts__": minion_opts,
            "__salt__": {},
            "__context__": {},
        },
        chocolatey_mod: {
            "__opts__": minion_opts,
            "__context__": {},
        },
    }


@pytest.fixture(scope="module")
def pkgs():
    return {
        "pkga": {"old": "1.0.1", "new": "2.0.1"},
        "pkgb": {"old": "1.0.2", "new": "2.0.2"},
        "pkgc": {"old": "1.0.3", "new": "2.0.3"},
    }


@pytest.fixture(scope="module")
def list_sources():
    _ret = {
        "chocolatey": {
            "URL": "https://community.chocolatey.org/api/v2/",
            "Disabled": False,
            "User": "user",
        },
        "community": {
            "URL": "https://community.chocolatey.org/api/v2/",
            "Disabled": False,
            "User": "user",
        },
    }
    return _ret


def test_source_present(list_sources):
    """
    Test chocolatey.source_present with simulated changes
    """

    before_list_sources = {
        "chocolatey": {
            "URL": "https://community.chocolatey.org/api/v2/",
            "Disabled": False,
            "User": "user",
        }
    }

    list_sources_sideeffect = MagicMock(side_effect=[before_list_sources, list_sources])

    with patch.dict(
        chocolatey.__salt__,
        {
            "chocolatey.list_sources": list_sources_sideeffect,
            "chocolatey.add_source": chocolatey_mod.add_source,
        },
    ):

        # Run state with test=true
        stdout_ret = (
            "Added community - https://community.chocolatey.org/api/v2/ (Priority 5)"
        )
        cmd_run_all_mock = MagicMock(return_value={"retcode": 0, "stdout": stdout_ret})
        cmd_run_which_mock = MagicMock(return_value=choco_path)
        with patch.dict(
            chocolatey_mod.__salt__,
            {
                "cmd.which": cmd_run_which_mock,
                "cmd.run_all": cmd_run_all_mock,
            },
        ):
            ret = chocolatey.source_present(
                "community",
                source_location="https://community.chocolatey.org/api/v2/",
                username="username",
                password="password",
                priority="5",
            )
            assert ret["result"] is True
            assert ret["name"] == "community"
            assert ret["comment"] == "Source community added successfully"
            assert ret["changes"] == {
                "community": {
                    "old": "",
                    "new": {
                        "URL": "https://community.chocolatey.org/api/v2/",
                        "Disabled": False,
                        "User": "user",
                    },
                }
            }
