import pytest

import salt.loader
import salt.loader.lazy


@pytest.fixture
def minion_mods(minion_opts):
    utils = salt.loader.utils(minion_opts)
    return salt.loader.minion_mods(minion_opts, utils=utils)


@pytest.mark.skip("Great module migration")
def test_load_boto_vpc(minion_mods):
    func = None
    try:
        func = minion_mods["boto_vpc.check_vpc"]
    except KeyError:
        pytest.fail("loader should not raise KeyError")
    assert func is not None
    assert isinstance(func, salt.loader.lazy.LoadedFunc)


@pytest.mark.skip("Great module migration")
def test_load_virt(minion_mods):
    func = None
    try:
        func = minion_mods["virt.ctrl_alt_del"]
    except KeyError:
        pytest.fail("loader should not raise KeyError")
    assert func is not None
    assert isinstance(func, salt.loader.lazy.LoadedFunc)
