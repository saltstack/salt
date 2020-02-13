# -*- coding: utf-8 -*-
import types

from tests.support.unit import TestCase
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import create_autospec, MagicMock

from salt.cloud.clouds import azurearm as azure


def copy_func(func, globals=None):
    # I do not know that this is complete, but it's sufficient for now.
    # The key to "moving" the function to another module (or stubbed module)
    # is to update __globals__.

    copied_func = types.FunctionType(func.__code__, globals,
                                     func.__name__, func.__defaults__, func.__closure__)
    copied_func.__module__ = func.__module__
    copied_func.__doc__ = func.__doc__
    copied_func.__kwdefaults__ = func.__kwdefaults__
    copied_func.__dict__.update(func.__dict__)
    return copied_func


def mock_module(mod, sut=[None]):
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


class AzureTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {azure: {'__opts__': {},
                        '__active_provider_name__': None}}

    def test_function_signatures(self):
        mock_azure = mock_module(azure, sut=['request_instance', 'six', '__opts__', '__utils__'])
        mock_azure.create_network_interface.return_value = [MagicMock(), MagicMock(), MagicMock()]
        mock_azure.salt.utils.stringutils.to_str.return_value = 'P4ssw0rd'
        mock_azure.salt.utils.cloud.gen_keys.return_value = [MagicMock(), MagicMock()]
        mock_azure.__opts__['pki_dir'] = None

        mock_azure.request_instance.__globals__['__builtins__'] = mock_azure.request_instance.__globals__['__builtins__'].copy()
        mock_azure.request_instance.__globals__['__builtins__']['getattr'] = MagicMock()

        mock_azure.__utils__['cloud.fire_event'] = mock_azure.salt.utils.cloud.fire_event
        mock_azure.__utils__['cloud.filter_event'] = mock_azure.salt.utils.cloud.filter_event
        mock_azure.__opts__['sock_dir'] = MagicMock()
        mock_azure.__opts__['transport'] = MagicMock()

        mock_azure.request_instance({'image': 'http://img',
                                     'storage_account': 'blah',
                                     'size': ''})

        # we literally only check that a final creation call occurred.
        mock_azure.get_conn.return_value.virtual_machines.create_or_update.assert_called_once()
