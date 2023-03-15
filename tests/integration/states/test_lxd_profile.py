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
class LxdProfileTestCase(ModuleCase, SaltReturnAssertsMixin):
    def tearDown(self):
        self.run_state(
            "lxd_profile.absent",
            name="test-profile",
        )

    def test_02__create_profile(self):
        self.run_state(
            "lxd_profile.absent",
            name="test-profile",
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
        ret = self.run_state(
            "lxd_profile.absent",
            name="test-profile",
        )
        name = "lxd_profile_|-test-profile_|-test-profile_|-absent"
        self.assertSaltTrueReturn(ret)
        assert name in ret
        assert ret[name]["changes"] == {
            "removed": 'Profile "test-profile" has been deleted.'
        }
