"""
Integration tests for the lxd states
"""

import pytest

import salt.modules.lxd
from tests.support.case import ModuleCase
from tests.support.mixins import SaltReturnAssertsMixin


@pytest.mark.destructive_test
@pytest.mark.skipif(salt.modules.lxd.HAS_PYLXD is False, reason="pylxd not installed")
@pytest.mark.skip_if_binaries_missing("lxd", reason="LXD not installed")
@pytest.mark.skip_if_binaries_missing("lxc", reason="LXC not installed")
class LxdTestCase(ModuleCase, SaltReturnAssertsMixin):
    @pytest.mark.flaky(max_runs=4)
    def test_01__init_lxd(self):
        ret = self.run_state("lxd.init", name="foobar")
        self.assertSaltTrueReturn(ret)
        name = "lxd_|-foobar_|-foobar_|-init"
        assert name in ret
        assert ret[name]["storage_backend"] == "dir"
