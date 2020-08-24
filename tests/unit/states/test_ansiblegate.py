#
# Copyright 2020 SUSE LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Import Salt Testing Libs

import json
import os

import salt.states.ansiblegate as ansible
import salt.utils.files
import salt.utils.platform
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase, skipIf

try:
    import pytest
except ImportError:
    pytest = None


@skipIf(pytest is None, "PyTest is missing")
@skipIf(salt.utils.platform.is_windows(), "Not supported on Windows")
class AnsiblegateTestCase(TestCase, LoaderModuleMockMixin):
    @classmethod
    def setUpClass(cls):
        cls.playbooks_examples_dir = os.path.join(
            RUNTIME_VARS.TESTS_DIR, "unit/files/playbooks/"
        )

    def setup_loader_modules(self):
        return {ansible: {}}

    def test_ansible_playbooks_states_success(self):
        """
        Test ansible.playbooks states executions success.
        :return:
        """

        with salt.utils.files.fopen(
            os.path.join(self.playbooks_examples_dir, "success_example.json")
        ) as f:
            success_output = json.loads(f.read())

        with patch.dict(
            ansible.__salt__,
            {"ansible.playbooks": MagicMock(return_value=success_output)},
        ), patch("salt.utils.path.which", MagicMock(return_value=True)):
            with patch.dict(ansible.__opts__, {"test": False}):
                ret = ansible.playbooks("foobar")
                self.assertTrue(ret["result"])
                self.assertEqual(ret["comment"], "Changes were made by playbook foobar")
                self.assertDictEqual(
                    ret["changes"],
                    {
                        "py2hosts": {
                            "Ansible copy file to remote server": {
                                "centos7-host1.tf.local": {}
                            }
                        }
                    },
                )

    def test_ansible_playbooks_states_failed(self):
        """
        Test ansible.playbooks failed states executions.
        :return:
        """

        with salt.utils.files.fopen(
            os.path.join(self.playbooks_examples_dir, "failed_example.json")
        ) as f:
            failed_output = json.loads(f.read())

        with patch.dict(
            ansible.__salt__,
            {"ansible.playbooks": MagicMock(return_value=failed_output)},
        ), patch("salt.utils.path.which", MagicMock(return_value=True)):
            with patch.dict(ansible.__opts__, {"test": False}):
                ret = ansible.playbooks("foobar")
                self.assertFalse(ret["result"])
                self.assertEqual(
                    ret["comment"], "There were some issues running the playbook foobar"
                )
                self.assertDictEqual(
                    ret["changes"],
                    {
                        "py2hosts": {
                            "yum": {
                                "centos7-host1.tf.local": [
                                    "No package matching 'rsyndc' found available, installed or updated"
                                ]
                            }
                        }
                    },
                )
