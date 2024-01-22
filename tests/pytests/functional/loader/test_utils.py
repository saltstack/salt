import warnings

import pytest
from saltfactories.utils import random_string

import salt.config
import salt.loader
from salt.loader.lazy import LazyLoader


@pytest.fixture(scope="module")
def loaded_base_name():
    return random_string(f"{__name__}.", digits=False, uppercase=False)


def ast_dunder_virtual_deprecate_only_ids(value):
    return f"ast_dunder_virtual_deprecate_only={value}"


@pytest.fixture(params=(True, False), ids=ast_dunder_virtual_deprecate_only_ids)
def ast_dunder_virtual_deprecate_only(request):
    return request.param


@pytest.fixture
def loader(request, minion_opts, loaded_base_name, ast_dunder_virtual_deprecate_only):
    loader = salt.loader.utils(minion_opts, loaded_base_name=loaded_base_name)
    loader._ast_dunder_virtual_deprecate_only = ast_dunder_virtual_deprecate_only
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            # Force loading all functions
            list(loader)
            yield loader
    finally:
        if not isinstance(loader, LazyLoader):
            for loaded_func in loader.values():
                loader = loaded_func.loader
                break
        if isinstance(loader, LazyLoader):
            loader.clean_modules()


def test_ast_inspect_loading(loader):
    loaded_functions = list(loader)
    # Check that utils modules defining __virtual__ are loaded by the loader
    # Of course, we can only check modules which load in most/all circumstances.
    assert "boto3.get_connection" in loaded_functions
    # However, modules which do not define a __virtual__ function should not load,
    # at all!
    modules_which_do_not_define_dunder_virtual = (
        "args.",
        "ansible.",
        "environment.",
        "entrypoints.",
        "process.",
    )
    for loaded_func in loaded_functions:
        if loader._ast_dunder_virtual_deprecate_only:
            if loaded_func.startswith(modules_which_do_not_define_dunder_virtual):
                assert hasattr(loader[loaded_func], "__wrapped__")
            else:
                assert not loaded_func.startswith(
                    modules_which_do_not_define_dunder_virtual
                )
