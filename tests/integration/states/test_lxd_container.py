"""
Integration tests for the lxd states
"""

import pytest
import salt.modules.lxd
from tests.support.case import ModuleCase
from tests.support.mixins import SaltReturnAssertsMixin


@pytest.mark.flaky(max_runs=4)
@pytest.mark.skipif(salt.modules.lxd.HAS_PYLXD is False, reason="pylxd not installed")
@pytest.mark.skip_if_binaries_missing("lxd", reason="LXD not installed")
@pytest.mark.skip_if_binaries_missing("lxc", reason="LXC not installed")
class LxdContainerTestCase(ModuleCase, SaltReturnAssertsMixin):
    def setUp(self):
        self.run_state(
            "lxd_image.present",
            name="images:centos/7",
            source={
                "name": "centos/7",
                "type": "simplestreams",
                "server": "https://images.linuxcontainers.org",
            },
        )

    def tearDown(self):
        self.run_state(
            "lxd_image.absent",
            name="images:centos/7",
        )
        self.run_state(
            "lxd_container.absent",
            name="test-container",
        )

    def test_02__create_container(self):
        ret = self.run_state(
            "lxd_container.present",
            name="test-container",
            running=True,
            source={"type": "image", "alias": "images:centos/7"},
        )
        name = "lxd_container_|-test-container_|-test-container_|-present"
        self.assertSaltTrueReturn(ret)
        assert name in ret
        assert (
            ret[name]["changes"]["started"] == 'Started the container "test-container"'
        )

    def test_03__change_container(self):
        self.run_state(
            "lxd_container.present",
            name="test-container",
            running=True,
            source={"type": "image", "alias": "images:centos/7"},
        )
        ret = self.run_state(
            "lxd_container.present",
            name="test-container",
            running=True,
            source={"type": "image", "alias": "images:centos/7"},
            restart_on_change=True,
            config=[
                {"key": "boot.autostart", "value": 1},
                {"key": "security.privileged", "value": "1"},
            ],
        )
        name = "lxd_container_|-test-container_|-test-container_|-present"
        self.assertSaltTrueReturn(ret)
        assert name in ret
        assert ret[name]["changes"]["config"] == {
            "boot.autostart": 'Added config key "boot.autostart" = "1"',
            "security.privileged": 'Added config key "security.privileged" = "1"',
        }

    def test_08__running_container(self):
        self.run_state(
            "lxd_container.present",
            name="test-container",
            running=True,
            source={"type": "image", "alias": "images:centos/7"},
        )
        ret = self.run_state(
            "lxd_container.running",
            name="test-container",
        )
        self.assertSaltTrueReturn(ret)
        name = "lxd_container_|-test-container_|-test-container_|-running"
        assert name in ret
        assert not ret[name]["changes"]
        assert (
            ret[name]["comment"] == 'The container "test-container" is already running'
        )
        ret = self.run_state(
            "lxd_container.running",
            name="test-container",
            restart=True,
        )
        self.assertSaltTrueReturn(ret)
        assert name in ret
        assert ret[name]["changes"] == {
            "restarted": 'Restarted the container "test-container"'
        }
        assert ret[name]["comment"] == 'Restarted the container "test-container"'

    def test_09__stop_container(self):
        self.run_state(
            "lxd_container.present",
            name="test-container",
            running=True,
            source={"type": "image", "alias": "images:centos/7"},
        )
        ret = self.run_state(
            "lxd_container.stopped",
            name="test-container",
        )
        name = "lxd_container_|-test-container_|-test-container_|-stopped"
        self.assertSaltTrueReturn(ret)
        assert ret[name]["changes"] == {
            "stopped": 'Stopped the container "test-container"'
        }
        ret = self.run_state(
            "lxd_container.stopped",
            name="test-container",
        )
        name = "lxd_container_|-test-container_|-test-container_|-stopped"
        self.assertSaltTrueReturn(ret)
        assert not ret[name]["changes"]

    def test_10__delete_container(self):
        self.run_state(
            "lxd_container.present",
            name="test-container",
            running=True,
            source={"type": "image", "alias": "images:centos/7"},
        )
        ret = self.run_state(
            "lxd_container.absent",
            name="test-container",
        )
        name = "lxd_container_|-test-container_|-test-container_|-absent"
        assert name in ret
        assert ret[name]["result"] is False
        ret = self.run_state(
            "lxd_container.stopped",
            name="test-container",
        )
        name = "lxd_container_|-test-container_|-test-container_|-stopped"
        assert name in ret
        assert ret[name]["result"] is True
        ret = self.run_state(
            "lxd_container.absent",
            name="test-container",
        )
        name = "lxd_container_|-test-container_|-test-container_|-absent"
        self.assertSaltTrueReturn(ret)
        assert name in ret
        assert ret[name]["changes"] == {
            "deleted": 'Container "test-container" has been deleted.'
        }
