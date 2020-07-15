# -*- coding: utf-8 -*-
"""
Integration tests for the lxd states
"""
# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Lxd Test Case
import tests.integration.states.test_lxd


class LxdImageTestCase(tests.integration.states.test_lxd.LxdTestCase):
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
        ret = self.run_state("lxd_image.absent", name="images:centos/7",)
        name = "lxd_image_|-images:centos/7_|-images:centos/7_|-absent"
        self.assertSaltTrueReturn(ret)
        assert name in ret
        assert (
            ret[name]["changes"]["removed"]
            == 'Image "images:centos/7" has been deleted.'
        )
