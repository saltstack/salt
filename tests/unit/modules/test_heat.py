import os

import salt.modules.file as file_
import salt.modules.heat as heat
import salt.modules.win_file as win_file
import salt.utils.platform
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase


class MockStacks:
    """
    Mock stacks.StackManager
    """

    def validate(self, **kwargs):
        """
        Mock of stacks.StackManager.validate method
        """
        self.mock_val_ret = MagicMock()
        self.mock_val_ret.json.return_value = {"result": "mocked response"}
        self.mock_validate = MagicMock()
        self.mock_validate.post.return_value = self.mock_val_ret
        return self.mock_validate

    def create(self, **kwargs):
        self.mock_create_ret = MagicMock()
        self.mock_create_ret.json.return_value = {
            "result": "mocked create",
            "fields": kwargs,
        }
        self.mock_create = MagicMock()
        self.mock_create.post.return_value = self.mock_create_ret
        return self.mock_create

    def update(self, name, **kwargs):
        self.mock_update_ret = MagicMock()
        self.mock_update_ret.json.return_value = {
            "result": "mocked update",
            "fields": kwargs,
            "name": name,
        }
        self.mock_update = MagicMock()
        self.mock_update.post.return_value = self.mock_update_ret
        return self.mock_update


class MockClient:
    """
    Mock of Client class
    """

    def __init__(self, profile=None, **conn_args):
        self.stacks = MockStacks()


class HeatTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.heat
    """

    def setup_loader_modules(self):
        return {
            heat: {"_auth": MockClient},
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
            win_file: {"__opts__": {"test": False}},
        }

    def setUp(self):
        self.patch_check = patch("salt.modules.file.check_perms", file_.check_perms)
        if salt.utils.platform.is_windows():
            self.patch_check = patch(
                "salt.modules.file.check_perms", win_file.check_perms
            )

    def test_heat_create_stack(self):
        """
        Test salt.modules.heat.create_stack method
        """
        patch_file = patch.dict(
            heat.__salt__,
            {
                "file.get_managed": file_.get_managed,
                "file.manage_file": file_.manage_file,
            },
        )

        with patch_file, self.patch_check:
            ret = heat.create_stack(
                name="mystack",
                profile="openstack1",
                template_file=os.path.join(
                    RUNTIME_VARS.BASE_FILES, "templates", "heat-template.yml"
                ),
            )
        assert ret == {"result": True, "comment": "Created stack 'mystack'."}

    def test_heat_create_stack_environment(self):
        """
        Test salt.modules.heat.create_stack method with environment set
        """
        patch_file = patch.dict(
            "salt.modules.heat.__salt__",
            {
                "file.get_managed": file_.get_managed,
                "file.manage_file": file_.manage_file,
            },
        )
        with patch_file, self.patch_check:
            ret = heat.create_stack(
                name="mystack",
                profile="openstack1",
                environment=os.path.join(
                    RUNTIME_VARS.BASE_FILES, "templates", "heat-env.yml"
                ),
                template_file=os.path.join(
                    RUNTIME_VARS.BASE_FILES, "templates", "heat-template.yml"
                ),
            )
        assert ret == {"result": True, "comment": "Created stack 'mystack'."}

    def test_heat_create_stack_environment_err(self):
        """
        Test salt.modules.heat.create_stack method with environment set
        and there is an error reading the environment file
        """
        patch_file = patch.dict(
            "salt.modules.heat.__salt__",
            {
                "file.get_managed": file_.get_managed,
                "file.manage_file": MagicMock(
                    side_effect=[{"result": True}, {"result": False}]
                ),
            },
        )
        patch_template = patch(
            "salt.modules.heat._parse_template", MagicMock(return_value=True)
        )
        env_file = os.path.join(RUNTIME_VARS.BASE_FILES, "templates", "heat-env.yml")
        with patch_file, patch_template, self.patch_check:
            ret = heat.create_stack(
                name="mystack",
                profile="openstack1",
                environment=env_file,
                template_file=os.path.join(
                    RUNTIME_VARS.BASE_FILES, "templates", "heat-template.yml"
                ),
            )
        assert ret == {
            "result": False,
            "comment": f"Can not open environment: {env_file}, ",
        }

    def test_heat_update_stack(self):
        """
        Test salt.modules.heat.update_method method
        """
        patch_file = patch.dict(
            heat.__salt__,
            {
                "file.get_managed": file_.get_managed,
                "file.manage_file": file_.manage_file,
            },
        )
        with patch_file, self.patch_check:
            ret = heat.update_stack(
                name="mystack",
                profile="openstack1",
                template_file=os.path.join(
                    RUNTIME_VARS.BASE_FILES, "templates", "heat-template.yml"
                ),
            )
        assert ret == {"result": True, "comment": ("Updated stack 'mystack'.",)}

    def test_heat_update_stack_env(self):
        """
        Test salt.modules.heat.update_method method
        with environment set
        """
        patch_file = patch.dict(
            heat.__salt__,
            {
                "file.get_managed": file_.get_managed,
                "file.manage_file": file_.manage_file,
            },
        )
        with patch_file, self.patch_check:
            ret = heat.update_stack(
                name="mystack",
                profile="openstack1",
                template_file=os.path.join(
                    RUNTIME_VARS.BASE_FILES, "templates", "heat-template.yml"
                ),
                environment=os.path.join(
                    RUNTIME_VARS.BASE_FILES, "templates", "heat-env.yml"
                ),
            )
        assert ret == {"result": True, "comment": ("Updated stack 'mystack'.",)}

    def test_heat_update_stack_env_err(self):
        """
        Test salt.modules.heat.update_method method
        with environment set and there is an error
        reading the environment file
        """
        patch_file = patch.dict(
            heat.__salt__,
            {
                "file.get_managed": file_.get_managed,
                "file.manage_file": MagicMock(
                    side_effect=[{"result": True}, {"result": False}]
                ),
            },
        )
        with patch_file, self.patch_check:
            ret = heat.update_stack(
                name="mystack",
                profile="openstack1",
                template_file=os.path.join(
                    RUNTIME_VARS.BASE_FILES, "templates", "heat-template.yml"
                ),
                environment=os.path.join(
                    RUNTIME_VARS.BASE_FILES, "templates", "heat-env.yml"
                ),
            )
        assert ret == {
            "result": False,
            "comment": "Error parsing template Template format version not found.",
        }
