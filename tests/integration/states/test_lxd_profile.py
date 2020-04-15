# -*- coding: utf-8 -*-
"""
Integration tests for the lxd states
"""
# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Lxd Test Case
import tests.integration.states.test_lxd


class LxdProfileTestCase(tests.integration.states.test_lxd.LxdTestCase):
    def tearDown(self):
        self.run_state(
            "lxd_profile.absent", name="test-profile",
        )

    def test_02__create_profile(self):
        self.run_state(
            "lxd_profile.absent", name="test-profile",
        )
        ret = self.run_state(
            "lxd_profile.present",
            name="test-profile",
            config=[{"key": "boot.autostart", "value": 1}],
        )
        name = "lxd_profile_|-test-profile_|-test-profile_|-present"
        self.assertSaltTrueReturn(ret)
        assert name in ret
        assert ret[name]["changes"] == {
            "created": 'Profile "test-profile" has been created'
        }

    def test_03__change_profile(self):
        self.run_state(
            "lxd_profile.present",
            name="test-profile",
            config=[{"key": "boot.autostart", "value": 1}],
        )
        ret = self.run_state(
            "lxd_profile.present",
            name="test-profile",
            config=[
                {"key": "boot.autostart", "value": 1},
                {"key": "security.privileged", "value": "1"},
            ],
        )
        name = "lxd_profile_|-test-profile_|-test-profile_|-present"
        self.assertSaltTrueReturn(ret)
        assert name in ret
        assert ret[name]["changes"]["config"] == {
            "security.privileged": 'Added config key "security.privileged" = "1"'
        }

    def test_04__delete_profile(self):
        self.run_state(
            "lxd_profile.present",
            name="test-profile",
            config=[{"key": "boot.autostart", "value": 1}],
        )
        ret = self.run_state("lxd_profile.absent", name="test-profile",)
        name = "lxd_profile_|-test-profile_|-test-profile_|-absent"
        self.assertSaltTrueReturn(ret)
        assert name in ret
        assert ret[name]["changes"] == {
            "removed": 'Profile "test-profile" has been deleted.'
        }
