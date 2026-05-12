"""
Unit tests for the napalm_network module cli_kwargs feature
"""

import pytest

import salt.modules.napalm_network as napalm_network
import salt.utils.napalm
import tests.support.napalm as napalm
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    module_globals = {
        "__salt__": {
            "config.get": MagicMock(
                return_value={"test": {"driver": "test", "key": "3j9jla,LJ3j9laj"}}
            ),
            "file.file_exists": napalm.true,
            "file.join": napalm.join,
            "file.get_managed": napalm.get_managed_file,
            "random.hash": napalm.random_hash,
        },
        "__opts__": {},
        "__pillar__": {},
    }
    return {napalm_network: module_globals}


def test_cli_kwargs_not_provided():
    """
    Test that when cli_kwargs is not provided, only commands are passed to NAPALM.
    """
    with patch(
        "salt.utils.napalm.get_device",
        MagicMock(return_value=napalm.MockNapalmDevice()),
    ):
        with patch.object(
            salt.utils.napalm,
            "call",
            MagicMock(
                return_value={
                    "result": True,
                    "comment": "",
                    "out": {"show version": "EOS version 4.28"},
                }
            ),
        ) as mock_call:
            napalm_network.cli("show version")

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args[1]
            assert call_kwargs == {"commands": ["show version"]}


def test_cli_kwargs_with_encoding():
    """
    Test that when cli_kwargs contains encoding, it's passed to NAPALM.
    """
    with patch(
        "salt.utils.napalm.get_device",
        MagicMock(return_value=napalm.MockNapalmDevice()),
    ):
        with patch.object(
            salt.utils.napalm,
            "call",
            MagicMock(
                return_value={
                    "result": True,
                    "comment": "",
                    "out": {"show version": "EOS version 4.28"},
                }
            ),
        ) as mock_call:
            napalm_network.cli("show version", cli_kwargs={"encoding": "json"})

            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args[1]
            assert call_kwargs == {"commands": ["show version"], "encoding": "json"}
