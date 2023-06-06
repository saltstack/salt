import warnings

import pytest
from saltfactories.utils import random_string

import salt.config
import salt.loader
from salt.loader.lazy import LazyLoader


@pytest.fixture(scope="module")
def loaded_base_name():
    return random_string(f"{__name__}.", digits=False, uppercase=False)


@pytest.fixture
def loader(minion_opts, loaded_base_name):
    loader = salt.loader.utils(minion_opts, loaded_base_name=loaded_base_name)
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
    assert "ansible.targets" in loaded_functions
    # However, modules which do not define a __virtual__ function should not load,
    # at all!
    modules_which_do_not_define_dunder_virtual = (
        "args.",
        "environment.",
        "entrypoints.",
        "process.",
    )
    for loaded_func in loaded_functions:
        assert not loaded_func.startswith(modules_which_do_not_define_dunder_virtual)
