import pytest

import salt.loader
import salt.loader.lazy
import salt.modules.boto_vpc
import salt.modules.virt


@pytest.fixture
def minion_mods(minion_opts):
    utils = salt.loader.utils(minion_opts)
    return salt.loader.minion_mods(minion_opts, utils=utils)


@pytest.mark.skipif(
    not salt.modules.boto_vpc.HAS_BOTO, reason="boto must be installed."
)
def test_load_boto_vpc(minion_mods):
    func = None
    try:
        func = minion_mods["boto_vpc.check_vpc"]
    except KeyError:
        pytest.fail("loader should not raise KeyError")
    assert func is not None
    assert isinstance(func, salt.loader.lazy.LoadedFunc)


@pytest.mark.skipif(
    not salt.modules.virt.HAS_LIBVIRT, reason="libvirt-python must be installed."
)
def test_load_virt(minion_mods):
    func = None
    try:
        func = minion_mods["virt.ctrl_alt_del"]
    except KeyError:
        pytest.fail("loader should not raise KeyError")
    assert func is not None
    assert isinstance(func, salt.loader.lazy.LoadedFunc)
