"""
    :codeauthor: Gareth J. Greenaway <gareth@saltstack.com>

    Test cases for salt.states.netconfig
"""

import pytest

import salt.modules.napalm_network as net_mod
import salt.states.netconfig as netconfig
import salt.utils.files
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    state_loader_globals = {
        "__env__": "base",
        "__salt__": {"net.replace_pattern": net_mod.replace_pattern},
    }
    module_loader_globals = {
        "__env__": "base",
        "__salt__": {
            "net.replace_pattern": net_mod.replace_pattern,
            "net.load_config": net_mod.load_config,
        },
    }
    return {netconfig: state_loader_globals, net_mod: module_loader_globals}


def test_replace_pattern_test_is_true():
    """
    Test to replace_pattern to ensure that test=True
    is being passed correctly.
    """
    name = "name"
    pattern = "OLD-POLICY-NAME"
    repl = "new-policy-name"

    mock = MagicMock()
    mock_net_replace_pattern = MagicMock()
    mock_loaded_ret = MagicMock()

    with patch.dict(netconfig.__salt__, {"config.merge": mock}):
        with patch.dict(
            netconfig.__salt__, {"net.replace_pattern": mock_net_replace_pattern}
        ):
            with patch.object(salt.utils.napalm, "loaded_ret", mock_loaded_ret):
                # Test if test=True is passed as argument to state.apply
                with patch.dict(netconfig.__opts__, {"test": True}):
                    netconfig.replace_pattern(name, pattern, repl)

                    # Get the args and kwargs from the mocked call net.replace_pattern
                    args, kwargs = mock_net_replace_pattern.call_args_list[0]

                    # Verify that the keyword argument is True
                    assert kwargs["test"]

                    # Get the args and kwargs from the mocked call to salt.utils.napalm.loaded_ret
                    args, kwargs = mock_loaded_ret.call_args_list[0]

                    # Verify that the third positional argument is True
                    assert args[2]

                # Test if test=True is passed as argument to state directly
                netconfig.replace_pattern(name, pattern, repl, test=True)

                # Get the args and kwargs from the mocked call net.replace_pattern
                args, kwargs = mock_net_replace_pattern.call_args_list[0]

                # Verify that the keyword argument is True
                assert kwargs["test"]

                # Get the args and kwargs from the mocked call to salt.utils.napalm.loaded_ret
                args, kwargs = mock_loaded_ret.call_args_list[0]

                # Verify that the third positional argument is True
                assert args[2]


def test_managed_test_is_true():
    """
    Test to managed to ensure that test=True
    is being passed correctly.
    """
    name = "name"

    mock = MagicMock()
    mock_update_config = MagicMock()

    with patch.dict(netconfig.__salt__, {"config.merge": mock}):
        with patch.object(netconfig, "_update_config", mock_update_config):
            # Test if test=True is passed as argument to state.apply
            with patch.dict(netconfig.__opts__, {"test": True}):
                netconfig.managed(name)

                # Get the args and kwargs from the mocked call net.replace_pattern
                args, kwargs = mock_update_config.call_args_list[0]

                # Verify that the keyword argument is True
                assert kwargs["test"]

            # Test if test=True is passed as argument to state directly
            netconfig.managed(name, test=True)

            # Get the args and kwargs from the mocked call net.replace_pattern
            args, kwargs = mock_update_config.call_args_list[0]

            # Verify that the keyword argument is True
            assert kwargs["test"]
