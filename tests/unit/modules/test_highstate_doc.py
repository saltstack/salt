# -*- coding: utf-8 -*-
import types

from salt.modules import highstate_doc
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, create_autospec, patch
from tests.support.unit import TestCase


def copy_func(func, globals=None):
    # I do not know that this is complete, but it's sufficient for now.
    # The key to "moving" the function to another module (or stubbed module)
    # is to update __globals__.

    copied_func = types.FunctionType(
        func.__code__, globals, func.__name__, func.__defaults__, func.__closure__
    )
    copied_func.__module__ = func.__module__
    copied_func.__doc__ = func.__doc__
    if hasattr(copied_func, "__kwdefaults__"):
        copied_func.__kwdefaults__ = func.__kwdefaults__
    copied_func.__dict__.update(func.__dict__)
    return copied_func


def mock_module(mod, exclude=[""]):
    mock = create_autospec(mod)

    # we need to provide a '__globals__' so functions being tested behave correctly.
    mock_globals = {}

    # exclude the system under test
    for name in exclude:
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
        return {highstate_doc: {"__opts__": {}}}

    def test_function_signatures_mock_mod(self):
        mock_hdoc = mock_module(highstate_doc, exclude=["proccesser_markdown"])
        mock_hdoc.proccesser_markdown(MagicMock(), MagicMock())

    def test_function_signatures_patch_mod(self):
        with patch.dict(
            globals(),
            {
                "highstate_doc": mock_module(
                    highstate_doc, exclude=["proccesser_markdown"]
                )
            },
        ):
            highstate_doc.proccesser_markdown(MagicMock(), MagicMock())
            raise Exception(highstate_doc.mock_calls)

    def test_function_signatures_original(self):
        # calls to manually mock for feature parity:
        # _format_markdown_requisite
        # _state_data_to_yaml_string
        # _format_markdown_system_file
        # __salt__['cp.get_file_str']
        # __salt__['file.find']
        highstate_doc.proccesser_markdown(MagicMock(), MagicMock())
