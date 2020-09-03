"""
Test AnsibleGate State Module
"""

import os
import shutil
import tempfile

import pytest
import salt.utils.files
import salt.utils.path
import yaml
from tests.support.case import ModuleCase
from tests.support.helpers import destructiveTest, flaky, requires_system_grains
from tests.support.mixins import SaltReturnAssertsMixin
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import SkipTest, skipIf


@destructiveTest
@pytest.mark.requires_sshd_server
@skipIf(
    not salt.utils.path.which("ansible-playbook"), "ansible-playbook is not installed"
)
class AnsiblePlaybooksTestCase(ModuleCase, SaltReturnAssertsMixin):
    """
    Test ansible.playbooks states
    """

    @classmethod
    @requires_system_grains
    def setUpClass(cls, grains=None):  # pylint: disable=arguments-differ
        if grains.get("os_family") == "RedHat" and grains.get("osmajorrelease") == 6:
            raise SkipTest(
                "This test hangs the test suite on RedHat 6. Skipping for now."
            )

    def setUp(self):
        priv_file = os.path.join(RUNTIME_VARS.TMP_SSH_CONF_DIR, "client_key")
        data = {
            "all": {
                "hosts": {
                    "localhost": {
                        "ansible_host": "127.0.0.1",
                        "ansible_port": 2827,
                        "ansible_user": RUNTIME_VARS.RUNNING_TESTS_USER,
                        "ansible_ssh_private_key_file": priv_file,
                        "ansible_ssh_extra_args": (
                            "-o StrictHostKeyChecking=false "
                            "-o UserKnownHostsFile=/dev/null "
                        ),
                    },
                },
            },
        }
        self.tempdir = tempfile.mkdtemp()
        self.inventory = self.tempdir + "inventory"
        with salt.utils.files.fopen(self.inventory, "w") as yaml_file:
            yaml.dump(data, yaml_file, default_flow_style=False)

    def tearDown(self):
        shutil.rmtree(self.tempdir)
        delattr(self, "tempdir")
        delattr(self, "inventory")

    @flaky
    def test_ansible_playbook(self):
        ret = self.run_state(
            "ansible.playbooks",
            name="remove.yml",
            git_repo="git://github.com/gtmanfred/playbooks.git",
            ansible_kwargs={"inventory": self.inventory},
        )
        self.assertSaltTrueReturn(ret)
        ret = self.run_state(
            "ansible.playbooks",
            name="install.yml",
            git_repo="git://github.com/gtmanfred/playbooks.git",
            ansible_kwargs={"inventory": self.inventory},
        )
        self.assertSaltTrueReturn(ret)
