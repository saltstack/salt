"""
Integration tests for the lxd states
"""

import pytest

import salt.modules.lxd
from tests.support.case import ModuleCase
from tests.support.mixins import SaltReturnAssertsMixin


@pytest.mark.skipif(salt.modules.lxd.HAS_PYLXD is False, reason="pylxd not installed")
@pytest.mark.skip_if_binaries_missing("lxd", reason="LXD not installed")
@pytest.mark.skip_if_binaries_missing("lxc", reason="LXC not installed")
class LxdImageTestCase(ModuleCase, SaltReturnAssertsMixin):
    def test_02__pull_image(self):
        ret = self.run_state(
            "lxd_image.present",
            name="images:centos/7",
            source={
                "name": "centos/7",
                "type": "simplestreams",
                "server": "https://images.linuxcontainers.org",
            },
        )
        name = "lxd_image_|-images:centos/7_|-images:centos/7_|-present"
        self.assertSaltTrueReturn(ret)
        assert name in ret
        assert ret[name]["changes"]["aliases"] == ['Added alias "images:centos/7"']

    def test_03__delete_image(self):
        ret = self.run_state(
            "lxd_image.absent",
            name="images:centos/7",
        )
        name = "lxd_image_|-images:centos/7_|-images:centos/7_|-absent"
        self.assertSaltTrueReturn(ret)
        assert name in ret
        assert (
            ret[name]["changes"]["removed"]
            == 'Image "images:centos/7" has been deleted.'
        )
