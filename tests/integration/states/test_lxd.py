"""
Integration tests for the lxd states
"""

import pytest
from tests.support.case import ModuleCase
from tests.support.mixins import SaltReturnAssertsMixin

try:
    import pylxd  # pylint: disable=import-error,unused-import

    HAS_PYLXD = True
except ImportError:
    HAS_PYLXD = False


@pytest.mark.destructive_test
@pytest.mark.skipif(HAS_PYLXD is False, "pylxd not installed")
@pytest.mark.skip_if_binaries_missing("lxd", message="LXD not installed")
@pytest.mark.skip_if_binaries_missing("lxc", message="LXC not installed")
class LxdTestCase(ModuleCase, SaltReturnAssertsMixin):

    run_once = False

    @pytest.mark.flaky(max_runs=4)
    def test_01__init_lxd(self):
        if LxdTestCase.run_once:
            return
        ret = self.run_state("lxd.init", name="foobar")
        self.assertSaltTrueReturn(ret)
        LxdTestCase.run_once = True
        name = "lxd_|-foobar_|-foobar_|-init"
        assert name in ret
        assert ret[name]["storage_backend"] == "dir"
