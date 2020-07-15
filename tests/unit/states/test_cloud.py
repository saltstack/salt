# -*- coding: utf-8 -*-
"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.states.cloud as cloud
import salt.utils.cloud

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class CloudTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.cloud
    """

    def setup_loader_modules(self):
        return {cloud: {}}

    # 'present' function tests: 1

    def test_present(self):
        """
        Test to spin up a single instance on a cloud provider, using salt-cloud.
        """
        name = "mycloud"
        cloud_provider = "my_cloud_provider"

        ret = {"name": name, "result": True, "changes": {}, "comment": ""}

        mock = MagicMock(side_effect=[True, False])
        mock_bool = MagicMock(side_effect=[True, False, False])
        mock_dict = MagicMock(return_value={"cloud": "saltcloud"})
        with patch.dict(
            cloud.__salt__,
            {
                "cmd.retcode": mock,
                "cloud.has_instance": mock_bool,
                "cloud.create": mock_dict,
            },
        ):
            comt = "onlyif condition is false"
            ret.update({"comment": comt})
            self.assertDictEqual(cloud.present(name, cloud_provider, onlyif=False), ret)

            self.assertDictEqual(cloud.present(name, cloud_provider, onlyif=""), ret)

            comt = "unless condition is true"
            ret.update({"comment": comt})
            self.assertDictEqual(cloud.present(name, cloud_provider, unless=True), ret)

            self.assertDictEqual(cloud.present(name, cloud_provider, unless=""), ret)

            comt = "Already present instance {0}".format(name)
            ret.update({"comment": comt})
            self.assertDictEqual(cloud.present(name, cloud_provider), ret)

            with patch.dict(cloud.__opts__, {"test": True}):
                comt = "Instance {0} needs to be created".format(name)
                ret.update({"comment": comt, "result": None})
                self.assertDictEqual(cloud.present(name, cloud_provider), ret)

            with patch.dict(cloud.__opts__, {"test": False}):
                comt = (
                    "Created instance mycloud using provider "
                    "my_cloud_provider and the following options: {}"
                )
                ret.update(
                    {"comment": comt, "result": True, "changes": {"cloud": "saltcloud"}}
                )
                self.assertDictEqual(cloud.present(name, cloud_provider), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        """
        Test to ensure that no instances with the specified names exist.
        """
        name = "mycloud"

        ret = {"name": name, "result": True, "changes": {}, "comment": ""}

        mock = MagicMock(side_effect=[True, False])
        mock_bool = MagicMock(side_effect=[False, True, True])
        mock_dict = MagicMock(return_value={"cloud": "saltcloud"})
        with patch.dict(
            cloud.__salt__,
            {
                "cmd.retcode": mock,
                "cloud.has_instance": mock_bool,
                "cloud.destroy": mock_dict,
            },
        ):
            comt = "onlyif condition is false"
            ret.update({"comment": comt})
            self.assertDictEqual(cloud.absent(name, onlyif=False), ret)

            self.assertDictEqual(cloud.absent(name, onlyif=""), ret)

            comt = "unless condition is true"
            ret.update({"comment": comt})
            self.assertDictEqual(cloud.absent(name, unless=True), ret)

            self.assertDictEqual(cloud.absent(name, unless=""), ret)

            comt = "Already absent instance {0}".format(name)
            ret.update({"comment": comt})
            self.assertDictEqual(cloud.absent(name), ret)

            with patch.dict(cloud.__opts__, {"test": True}):
                comt = "Instance {0} needs to be destroyed".format(name)
                ret.update({"comment": comt, "result": None})
                self.assertDictEqual(cloud.absent(name), ret)

            with patch.dict(cloud.__opts__, {"test": False}):
                comt = ("Destroyed instance {0}").format(name)
                ret.update(
                    {"comment": comt, "result": True, "changes": {"cloud": "saltcloud"}}
                )
                self.assertDictEqual(cloud.absent(name), ret)

    # 'profile' function tests: 1

    def test_profile(self):
        """
        Test to create a single instance on a cloud provider,
        using a salt-cloud profile.
        """
        name = "mycloud"
        profile = "myprofile"

        ret = {"name": name, "result": True, "changes": {}, "comment": ""}

        mock = MagicMock(side_effect=[True, False])
        mock_dict = MagicMock(
            side_effect=[
                {"cloud": "saltcloud"},
                {"Not Actioned": True},
                {"Not Actioned": True},
                {"Not Found": True, "Not Actioned/Not Running": True},
            ]
        )
        mock_d = MagicMock(return_value={})
        with patch.dict(
            cloud.__salt__,
            {"cmd.retcode": mock, "cloud.profile": mock_d, "cloud.action": mock_dict},
        ):
            comt = "onlyif condition is false"
            ret.update({"comment": comt})
            self.assertDictEqual(cloud.profile(name, profile, onlyif=False), ret)

            self.assertDictEqual(cloud.profile(name, profile, onlyif=""), ret)

            comt = "unless condition is true"
            ret.update({"comment": comt})
            self.assertDictEqual(cloud.profile(name, profile, unless=True), ret)

            self.assertDictEqual(cloud.profile(name, profile, unless=""), ret)

            comt = "Already present instance {0}".format(name)
            ret.update({"comment": comt})
            self.assertDictEqual(cloud.profile(name, profile), ret)

            with patch.dict(cloud.__opts__, {"test": True}):
                comt = "Instance {0} needs to be created".format(name)
                ret.update({"comment": comt, "result": None})
                self.assertDictEqual(cloud.profile(name, profile), ret)

            with patch.dict(cloud.__opts__, {"test": False}):
                comt = ("Failed to create instance {0}" "using profile {1}").format(
                    name, profile
                )
                ret.update({"comment": comt, "result": False})
                self.assertDictEqual(cloud.profile(name, profile), ret)

            with patch.dict(cloud.__opts__, {"test": False}):
                comt = ("Failed to create instance {0}" "using profile {1}").format(
                    name, profile
                )
                ret.update({"comment": comt, "result": False})
                self.assertDictEqual(cloud.profile(name, profile), ret)

    # 'volume_present' function tests: 1

    def test_volume_present(self):
        """
        Test to check that a block volume exists.
        """
        name = "mycloud"

        ret = {"name": name, "result": False, "changes": {}, "comment": ""}

        mock = MagicMock(return_value=name)
        mock_lst = MagicMock(side_effect=[[name], [], []])
        with patch.dict(
            cloud.__salt__, {"cloud.volume_list": mock_lst, "cloud.volume_create": mock}
        ):
            with patch.object(
                salt.utils.cloud, "check_name", MagicMock(return_value=True)
            ):
                comt = "Invalid characters in name."
                ret.update({"comment": comt})
                self.assertDictEqual(cloud.volume_present(name), ret)

            comt = "Volume exists: {0}".format(name)
            ret.update({"comment": comt, "result": True})
            self.assertDictEqual(cloud.volume_present(name), ret)

            with patch.dict(cloud.__opts__, {"test": True}):
                comt = "Volume {0} will be created.".format(name)
                ret.update({"comment": comt, "result": None})
                self.assertDictEqual(cloud.volume_present(name), ret)

            with patch.dict(cloud.__opts__, {"test": False}):
                comt = "Volume {0} was created".format(name)
                ret.update(
                    {
                        "comment": comt,
                        "result": True,
                        "changes": {"old": None, "new": name},
                    }
                )
                self.assertDictEqual(cloud.volume_present(name), ret)

    # 'volume_absent' function tests: 1

    def test_volume_absent(self):
        """
        Test to check that a block volume exists.
        """
        name = "mycloud"

        ret = {"name": name, "result": False, "changes": {}, "comment": ""}

        mock = MagicMock(return_value=False)
        mock_lst = MagicMock(side_effect=[[], [name], [name]])
        with patch.dict(
            cloud.__salt__, {"cloud.volume_list": mock_lst, "cloud.volume_delete": mock}
        ):
            with patch.object(
                salt.utils.cloud, "check_name", MagicMock(return_value=True)
            ):
                comt = "Invalid characters in name."
                ret.update({"comment": comt})
                self.assertDictEqual(cloud.volume_absent(name), ret)

            comt = "Volume is absent."
            ret.update({"comment": comt, "result": True})
            self.assertDictEqual(cloud.volume_absent(name), ret)

            with patch.dict(cloud.__opts__, {"test": True}):
                comt = "Volume {0} will be deleted.".format(name)
                ret.update({"comment": comt, "result": None})
                self.assertDictEqual(cloud.volume_absent(name), ret)

            with patch.dict(cloud.__opts__, {"test": False}):
                comt = "Volume {0} failed to delete.".format(name)
                ret.update({"comment": comt, "result": False})
                self.assertDictEqual(cloud.volume_absent(name), ret)

    # 'volume_attached' function tests: 1

    def test_volume_attached(self):
        """
        Test to check if a block volume is attached.
        """
        name = "mycloud"
        server_name = "mycloud_server"
        disk_name = "trogdor"

        ret = {"name": name, "result": False, "changes": {}, "comment": ""}

        mock = MagicMock(return_value=False)
        mock_dict = MagicMock(
            side_effect=[
                {name: {"name": disk_name, "attachments": True}},
                {},
                {name: {"name": disk_name, "attachments": False}},
                {name: {"name": disk_name, "attachments": False}},
                {name: {"name": disk_name, "attachments": False}},
            ]
        )
        with patch.dict(
            cloud.__salt__, {"cloud.volume_list": mock_dict, "cloud.action": mock}
        ):
            with patch.object(
                salt.utils.cloud,
                "check_name",
                MagicMock(side_effect=[True, False, True]),
            ):
                comt = "Invalid characters in name."
                ret.update({"comment": comt})
                self.assertDictEqual(cloud.volume_attached(name, server_name), ret)

                ret.update({"name": server_name})
                self.assertDictEqual(cloud.volume_attached(name, server_name), ret)

            comt = "Volume {0} is already attached: True".format(disk_name)
            ret.update({"comment": comt, "result": True})
            self.assertDictEqual(cloud.volume_attached(name, server_name), ret)

            comt = "Volume {0} does not exist".format(name)
            ret.update({"comment": comt, "result": False})
            self.assertDictEqual(cloud.volume_attached(name, server_name), ret)

            comt = "Server {0} does not exist".format(server_name)
            ret.update({"comment": comt, "result": False})
            self.assertDictEqual(cloud.volume_attached(name, server_name), ret)

            mock = MagicMock(return_value=True)
            with patch.dict(
                cloud.__salt__, {"cloud.action": mock, "cloud.volume_attach": mock}
            ):
                with patch.dict(cloud.__opts__, {"test": True}):
                    comt = "Volume {0} will be will be attached.".format(name)
                    ret.update({"comment": comt, "result": None})
                    self.assertDictEqual(cloud.volume_attached(name, server_name), ret)

                with patch.dict(cloud.__opts__, {"test": False}):
                    comt = "Volume {0} was created".format(name)
                    ret.update(
                        {
                            "comment": comt,
                            "result": True,
                            "changes": {
                                "new": True,
                                "old": {"name": disk_name, "attachments": False},
                            },
                        }
                    )
                    self.assertDictEqual(cloud.volume_attached(name, server_name), ret)

    # 'volume_detached' function tests: 1

    def test_volume_detached(self):
        """
        Test to check if a block volume is detached.
        """
        name = "mycloud"
        server_name = "mycloud_server"
        disk_name = "trogdor"

        ret = {"name": name, "result": False, "changes": {}, "comment": ""}

        mock = MagicMock(return_value=False)
        mock_dict = MagicMock(
            side_effect=[
                {name: {"name": disk_name, "attachments": False}},
                {},
                {name: {"name": disk_name, "attachments": True}},
                {name: {"name": disk_name, "attachments": True}},
                {name: {"name": disk_name, "attachments": True}},
            ]
        )
        with patch.dict(
            cloud.__salt__, {"cloud.volume_list": mock_dict, "cloud.action": mock}
        ):
            with patch.object(
                salt.utils.cloud,
                "check_name",
                MagicMock(side_effect=[True, False, True]),
            ):
                comt = "Invalid characters in name."
                ret.update({"comment": comt})
                self.assertDictEqual(cloud.volume_detached(name, server_name), ret)

                ret.update({"name": server_name})
                self.assertDictEqual(cloud.volume_detached(name, server_name), ret)

            comt = "Volume {0} is not currently attached to anything.".format(disk_name)
            ret.update({"comment": comt, "result": True})
            self.assertDictEqual(cloud.volume_detached(name, server_name), ret)

            comt = "Volume {0} does not exist".format(name)
            ret.update({"comment": comt})
            self.assertDictEqual(cloud.volume_detached(name, server_name), ret)

            comt = "Server {0} does not exist".format(server_name)
            ret.update({"comment": comt})
            self.assertDictEqual(cloud.volume_detached(name, server_name), ret)

            mock = MagicMock(return_value=True)
            with patch.dict(
                cloud.__salt__, {"cloud.action": mock, "cloud.volume_detach": mock}
            ):
                with patch.dict(cloud.__opts__, {"test": True}):
                    comt = "Volume {0} will be will be detached.".format(name)
                    ret.update({"comment": comt, "result": None})
                    self.assertDictEqual(cloud.volume_detached(name, server_name), ret)

                with patch.dict(cloud.__opts__, {"test": False}):
                    comt = "Volume {0} was created".format(name)
                    ret.update(
                        {
                            "comment": comt,
                            "result": True,
                            "changes": {
                                "new": True,
                                "old": {"name": disk_name, "attachments": True},
                            },
                        }
                    )
                    self.assertDictEqual(cloud.volume_detached(name, server_name), ret)
