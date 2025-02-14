import types

import pytest

from salt.cloud.clouds import azurearm as azure
from tests.support.mock import MagicMock, create_autospec, patch


def copy_func(func, globals=None):
    # I do not know that this is complete, but it's sufficient for now.
    # The key to "moving" the function to another module (or stubbed module)
    # is to update __globals__.

    copied_func = types.FunctionType(
        func.__code__, globals, func.__name__, func.__defaults__, func.__closure__
    )
    copied_func.__module__ = func.__module__
    copied_func.__doc__ = func.__doc__
    copied_func.__kwdefaults__ = func.__kwdefaults__
    copied_func.__dict__.update(func.__dict__)
    return copied_func


def mock_module(mod, sut=None):
    if sut is None:
        sut = [None]

    mock = create_autospec(mod)

    # we need to provide a '__globals__' so functions being tested behave correctly.
    mock_globals = {}

    # exclude the system under test
    for name in sut:
        attr = getattr(mod, name)
        if isinstance(attr, types.FunctionType):
            attr = copy_func(attr, mock_globals)
        setattr(mock, name, attr)

    # fully populate our mock_globals
    for name in mod.__dict__:
        if name in mock.__dict__:
            mock_globals[name] = mock.__dict__[name]
        elif type(getattr(mod, name)) is type(types):  # is a module
            mock_globals[name] = getattr(mock, name)
        else:
            mock_globals[name] = mod.__dict__[name]

    return mock


@pytest.fixture
def configure_loader_modules():
    return {azure: {"__opts__": {}, "__active_provider_name__": None}}


@pytest.mark.skipif(not azure.HAS_LIBS, reason="azure not available")
def test_function_signatures():
    mock_azure = mock_module(azure, sut=["request_instance", "__opts__", "__utils__"])
    mock_azure.create_network_interface.return_value = [
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ]
    mock_azure.salt.utils.stringutils.to_str.return_value = "P4ssw0rd"
    mock_azure.salt.utils.cloud.gen_keys.return_value = [MagicMock(), MagicMock()]
    mock_azure.__opts__["pki_dir"] = None

    mock_azure.request_instance.__globals__["__builtins__"] = (
        mock_azure.request_instance.__globals__["__builtins__"].copy()
    )
    mock_azure.request_instance.__globals__["__builtins__"]["getattr"] = MagicMock()

    mock_azure.__utils__["cloud.fire_event"] = mock_azure.salt.utils.cloud.fire_event
    mock_azure.__utils__["cloud.filter_event"] = (
        mock_azure.salt.utils.cloud.filter_event
    )
    mock_azure.__opts__["sock_dir"] = MagicMock()
    mock_azure.__opts__["transport"] = MagicMock()

    mock_azure.request_instance(
        {"image": "http://img", "storage_account": "blah", "size": ""}
    )

    # we literally only check that a final creation call occurred.
    mock_azure.get_conn.return_value.virtual_machines.create_or_update.assert_called_once()


def test_get_configured_provider():
    mock_azure = mock_module(
        azure, sut=["get_configured_provider", "__opts__", "__utils__"]
    )

    good_combos = [
        {
            "subscription_id": "3287abc8-f98a-c678-3bde-326766fd3617",
            "tenant": "ABCDEFAB-1234-ABCD-1234-ABCDEFABCDEF",
            "client_id": "ABCDEFAB-1234-ABCD-1234-ABCDEFABCDEF",
            "secret": "XXXXXXXXXXXXXXXXXXXXXXXX",
        },
        {
            "subscription_id": "3287abc8-f98a-c678-3bde-326766fd3617",
            "username": "larry",
            "password": "123pass",
        },
        {"subscription_id": "3287abc8-f98a-c678-3bde-326766fd3617"},
    ]

    for combo in good_combos:
        mock_azure.__opts__["providers"] = {"azure_test": {"azurearm": combo}}
        assert azure.get_configured_provider() == combo

    bad_combos = [
        {"subscrption": "3287abc8-f98a-c678-3bde-326766fd3617"},
        {},
    ]

    for combo in bad_combos:
        mock_azure.__opts__["providers"] = {"azure_test": {"azurearm": combo}}
        assert not azure.get_configured_provider()


def test_get_conn():
    mock_azure = mock_module(azure, sut=["get_conn", "__opts__", "__utils__"])

    mock_azure.__opts__["providers"] = {
        "azure_test": {
            "azurearm": {
                "subscription_id": "3287abc8-f98a-c678-3bde-326766fd3617",
                "driver": "azurearm",
                "password": "monkeydonkey",
            }
        }
    }
    # password is stripped if username not provided
    expected = {"subscription_id": "3287abc8-f98a-c678-3bde-326766fd3617"}
    with patch(
        "salt.utils.azurearm.get_client", side_effect=lambda client_type, **kw: kw
    ):
        assert azure.get_conn(client_type="compute") == expected

    mock_azure.__opts__["providers"] = {
        "azure_test": {
            "azurearm": {
                "subscription_id": "3287abc8-f98a-c678-3bde-326766fd3617",
                "driver": "azurearm",
                "username": "donkeymonkey",
                "password": "monkeydonkey",
            }
        }
    }
    # username and password via provider config
    expected = {
        "subscription_id": "3287abc8-f98a-c678-3bde-326766fd3617",
        "username": "donkeymonkey",
        "password": "monkeydonkey",
    }
    with patch(
        "salt.utils.azurearm.get_client", side_effect=lambda client_type, **kw: kw
    ):
        assert azure.get_conn(client_type="compute") == expected
