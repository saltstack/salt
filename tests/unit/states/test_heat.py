import os

import salt.modules.file as file_
import salt.modules.heat
import salt.modules.win_file as win_file
import salt.states.heat as heat
import salt.utils.platform
import salt.utils.win_dacl as dacl
import tests.unit.modules.test_heat
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase


class HeatTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.heat
    """

    def setup_loader_modules(self):
        return {
            heat: {
                "_auth": tests.unit.modules.test_heat.MockClient,
                "__opts__": {"test": False},
            },
            salt.modules.heat: {"_auth": tests.unit.modules.test_heat.MockClient},
            file_: {
                "__opts__": {
                    "hash_type": "sha256",
                    "cachedir": os.path.join(RUNTIME_VARS.TMP, "rootdir", "cache"),
                    "test": False,
                },
                "__salt__": {
                    "config.option": MagicMock(
                        return_value={"obfuscate_templates": False}
                    ),
                    "config.backup_mode": MagicMock(return_value=False),
                },
            },
            win_file: {
                "__utils__": {"dacl.check_perms": salt.utils.win_dacl.check_perms}
            },
            dacl: {"__opts__": {"test": False}},
        }

    def setUp(self):
        self.patch_check = patch("salt.modules.file.check_perms", file_.check_perms)
        if salt.utils.platform.is_windows():
            self.patch_check = patch(
                "salt.modules.file.check_perms", win_file.check_perms
            )

    def test_heat_deployed(self):
        """
        Test salt.states.heat.deployed method
        """
        exp_ret = {
            "name": ("mystack",),
            "comment": "Created stack 'mystack'.",
            "changes": {"stack_name": "mystack", "comment": "Create stack"},
            "result": True,
        }

        patch_heat = patch.dict(
            heat.__salt__,
            {
                "heat.show_stack": MagicMock(return_value={"result": False}),
                "heat.create_stack": salt.modules.heat.create_stack,
            },
        )

        patch_file = patch.dict(
            "salt.modules.heat.__salt__",
            {
                "file.get_managed": file_.get_managed,
                "file.manage_file": file_.manage_file,
            },
        )

        patch_create = patch(
            "salt.modules.heat.create_stack",
            MagicMock(
                return_value={"result": True, "comment": "Created stack 'mystack'."}
            ),
        )

        with patch_heat, patch_file, patch_create, self.patch_check:
            ret = heat.deployed(
                name="mystack",
                profile="openstack1",
                template=os.path.join(
                    RUNTIME_VARS.BASE_FILES, "templates", "heat-template.yml"
                ),
                poll=0,
            )
        assert ret == exp_ret

    def test_heat_deployed_environment(self):
        """
        Test salt.states.heat.deployed method
        with environment set
        """
        exp_ret = {
            "name": ("mystack",),
            "comment": "Created stack 'mystack'.",
            "changes": {"stack_name": "mystack", "comment": "Create stack"},
            "result": True,
        }

        patch_heat = patch.dict(
            heat.__salt__,
            {
                "heat.show_stack": MagicMock(return_value={"result": False}),
                "heat.create_stack": salt.modules.heat.create_stack,
            },
        )

        patch_file = patch.dict(
            "salt.modules.heat.__salt__",
            {
                "file.get_managed": file_.get_managed,
                "file.manage_file": file_.manage_file,
            },
        )

        patch_create = patch(
            "salt.modules.heat.create_stack",
            MagicMock(
                return_value={"result": True, "comment": "Created stack 'mystack'."}
            ),
        )

        with patch_heat, patch_file, patch_create, self.patch_check:
            ret = heat.deployed(
                name="mystack",
                profile="openstack1",
                template=os.path.join(
                    RUNTIME_VARS.BASE_FILES, "templates", "heat-template.yml"
                ),
                poll=0,
                environment=os.path.join(
                    RUNTIME_VARS.BASE_FILES, "templates", "heat-env.yml"
                ),
            )
        assert ret == exp_ret

    def test_heat_deployed_environment_error(self):
        """
        Test salt.states.heat.deployed method
        with environment set and there is an error
        reading the environment file.
        """
        exp_ret = {
            "name": ("mystack",),
            "comment": "Error parsing template Template format version not found.",
            "changes": {"stack_name": "mystack", "comment": "Create stack"},
            "result": False,
        }

        patch_heat = patch.dict(
            heat.__salt__,
            {
                "heat.show_stack": MagicMock(return_value={"result": False}),
                "heat.create_stack": salt.modules.heat.create_stack,
            },
        )

        patch_file = patch.dict(
            "salt.modules.heat.__salt__",
            {
                "file.get_managed": file_.get_managed,
                "file.manage_file": MagicMock(
                    side_effect=[{"result": True}, {"result": False}]
                ),
            },
        )

        patch_create = patch(
            "salt.modules.heat.create_stack",
            MagicMock(
                return_value={"result": True, "comment": "Created stack 'mystack'."}
            ),
        )

        with patch_heat, patch_file, patch_create, self.patch_check:
            ret = heat.deployed(
                name="mystack",
                profile="openstack1",
                template=os.path.join(
                    RUNTIME_VARS.BASE_FILES, "templates", "heat-template.yml"
                ),
                poll=0,
                environment=os.path.join(
                    RUNTIME_VARS.BASE_FILES, "templates", "heat-env.yml"
                ),
            )
        assert ret == exp_ret
