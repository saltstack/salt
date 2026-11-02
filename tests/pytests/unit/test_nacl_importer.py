import importlib.machinery
import os
import sys
import types

import pytest

from salt import NaclImporter
from tests.support.mock import MagicMock


@pytest.mark.parametrize("fullname", ["nacl", "nacl.signing"])
def test_find_spec_accepts_nacl(fullname, monkeypatch):
    monkeypatch.setattr(NaclImporter, "loading", False)
    importer = NaclImporter()

    spec = importer.find_spec(fullname)

    assert spec is not None
    assert spec.name == fullname
    assert spec.loader is importer
    assert NaclImporter.loading is True


def test_find_spec_declines_unrelated_module(monkeypatch):
    monkeypatch.setattr(NaclImporter, "loading", False)
    importer = NaclImporter()

    assert importer.find_spec("json") is None
    assert NaclImporter.loading is False


def test_find_spec_declines_while_loading(monkeypatch):
    monkeypatch.setattr(NaclImporter, "loading", True)
    importer = NaclImporter()

    assert importer.find_spec("nacl.signing") is None
    assert NaclImporter.loading is True


@pytest.mark.parametrize(
    "dlopen,deepbind", [(False, False), (True, False), (True, True)]
)
def test_create_module_restores_dlopen_flags(monkeypatch, dlopen, deepbind):
    importer = NaclImporter()
    monkeypatch.setattr(NaclImporter, "loading", True)
    module = types.ModuleType("nacl.test_import_hook")
    import_module = MagicMock(return_value=module)
    monkeypatch.setattr("salt.importlib.import_module", import_module)
    set_flags = MagicMock()
    monkeypatch.setattr(sys, "setdlopenflags", set_flags, raising=False)
    if dlopen:
        monkeypatch.setattr(sys, "getdlopenflags", lambda: 2, raising=False)
    else:
        monkeypatch.delattr(sys, "getdlopenflags", raising=False)
    if deepbind:
        monkeypatch.setattr(os, "RTLD_DEEPBIND", 8, raising=False)
    else:
        monkeypatch.delattr(os, "RTLD_DEEPBIND", raising=False)
    spec = importlib.machinery.ModuleSpec(module.__name__, importer)
    # Ensure the import hook publishes the module, without retaining it after the test.
    monkeypatch.setitem(sys.modules, module.__name__, None)

    assert importer.create_module(spec) is module
    assert sys.modules[module.__name__] is module
    assert NaclImporter.loading is False
    import_module.assert_called_once_with(module.__name__)
    if dlopen:
        assert [call.args[0] for call in set_flags.call_args_list] == [
            10 if deepbind else 2,
            2,
        ]
    else:
        set_flags.assert_not_called()
    assert importer.exec_module(module) is None
