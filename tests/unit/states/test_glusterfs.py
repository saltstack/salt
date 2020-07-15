# -*- coding: utf-8 -*-
"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import salt.modules.glusterfs as mod_glusterfs

# Import Salt Libs
import salt.states.glusterfs as glusterfs
import salt.utils.cloud
import salt.utils.network

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class GlusterfsTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.glusterfs
    """

    def setup_loader_modules(self):
        return {glusterfs: {"__salt__": {"glusterfs.peer": mod_glusterfs.peer}}}

    # 'peered' function tests: 1

    def test_peered(self):
        """
        Test to verify if node is peered.
        """
        name = "server1"

        ret = {"name": name, "result": True, "comment": "", "changes": {}}

        mock_ip = MagicMock(return_value=["1.2.3.4", "1.2.3.5"])
        mock_ip6 = MagicMock(return_value=["2001:db8::1"])
        mock_host_ips = MagicMock(return_value=["1.2.3.5"])
        mock_peer = MagicMock(return_value=True)
        mock_status = MagicMock(return_value={"uuid1": {"hostnames": [name]}})

        with patch.dict(
            glusterfs.__salt__,
            {"glusterfs.peer_status": mock_status, "glusterfs.peer": mock_peer},
        ):
            with patch.object(salt.utils.network, "ip_addrs", mock_ip), patch.object(
                salt.utils.network, "ip_addrs6", mock_ip6
            ), patch.object(salt.utils.network, "host_to_ips", mock_host_ips):
                comt = "Peering with localhost is not needed"
                ret.update({"comment": comt})
                self.assertDictEqual(glusterfs.peered(name), ret)

                mock_host_ips.return_value = ["2001:db8::1"]
                self.assertDictEqual(glusterfs.peered(name), ret)

                mock_host_ips.return_value = ["1.2.3.42"]
                comt = "Host {0} already peered".format(name)
                ret.update({"comment": comt})
                self.assertDictEqual(glusterfs.peered(name), ret)

                with patch.dict(glusterfs.__opts__, {"test": False}):
                    old = {"uuid1": {"hostnames": ["other1"]}}
                    new = {
                        "uuid1": {"hostnames": ["other1"]},
                        "uuid2": {"hostnames": ["someAlias", name]},
                    }
                    mock_status.side_effect = [old, new]
                    comt = "Host {0} successfully peered".format(name)
                    ret.update({"comment": comt, "changes": {"old": old, "new": new}})
                    self.assertDictEqual(glusterfs.peered(name), ret)
                    mock_status.side_effect = None

                    mock_status.return_value = {"uuid1": {"hostnames": ["other"]}}
                    mock_peer.return_value = False

                    ret.update({"result": False})

                    comt = (
                        "Failed to peer with {0}," + " please check logs for errors"
                    ).format(name)
                    ret.update({"comment": comt, "changes": {}})
                    self.assertDictEqual(glusterfs.peered(name), ret)

                    comt = "Invalid characters in peer name."
                    ret.update({"comment": comt, "name": ":/"})
                    self.assertDictEqual(glusterfs.peered(":/"), ret)
                    ret.update({"name": name})

                with patch.dict(glusterfs.__opts__, {"test": True}):
                    comt = "Peer {0} will be added.".format(name)
                    ret.update({"comment": comt, "result": None})
                    self.assertDictEqual(glusterfs.peered(name), ret)

    # 'volume_present' function tests: 1

    def test_volume_present(self):
        """
        Test to ensure that a volume exists
        """
        name = "salt"
        bricks = ["host1:/brick1"]
        ret = {"name": name, "result": True, "comment": "", "changes": {}}

        started_info = {name: {"status": "1"}}
        stopped_info = {name: {"status": "0"}}

        mock_info = MagicMock()
        mock_list = MagicMock()
        mock_create = MagicMock()
        mock_start = MagicMock(return_value=True)

        with patch.dict(
            glusterfs.__salt__,
            {
                "glusterfs.info": mock_info,
                "glusterfs.list_volumes": mock_list,
                "glusterfs.create_volume": mock_create,
                "glusterfs.start_volume": mock_start,
            },
        ):
            with patch.dict(glusterfs.__opts__, {"test": False}):
                mock_list.return_value = [name]
                mock_info.return_value = started_info
                comt = "Volume {0} already exists and is started".format(name)
                ret.update({"comment": comt})
                self.assertDictEqual(
                    glusterfs.volume_present(name, bricks, start=True), ret
                )

                mock_info.return_value = stopped_info
                comt = "Volume {0} already exists and is now started".format(name)
                ret.update(
                    {"comment": comt, "changes": {"old": "stopped", "new": "started"}}
                )
                self.assertDictEqual(
                    glusterfs.volume_present(name, bricks, start=True), ret
                )

                comt = "Volume {0} already exists".format(name)
                ret.update({"comment": comt, "changes": {}})
                self.assertDictEqual(
                    glusterfs.volume_present(name, bricks, start=False), ret
                )
            with patch.dict(glusterfs.__opts__, {"test": True}):
                comt = "Volume {0} already exists".format(name)
                ret.update({"comment": comt, "result": None})
                self.assertDictEqual(
                    glusterfs.volume_present(name, bricks, start=False), ret
                )

                comt = ("Volume {0} already exists" + " and will be started").format(
                    name
                )
                ret.update({"comment": comt, "result": None})
                self.assertDictEqual(
                    glusterfs.volume_present(name, bricks, start=True), ret
                )

                mock_list.return_value = []
                comt = "Volume {0} will be created".format(name)
                ret.update({"comment": comt, "result": None})
                self.assertDictEqual(
                    glusterfs.volume_present(name, bricks, start=False), ret
                )

                comt = ("Volume {0} will be created" + " and started").format(name)
                ret.update({"comment": comt, "result": None})
                self.assertDictEqual(
                    glusterfs.volume_present(name, bricks, start=True), ret
                )

            with patch.dict(glusterfs.__opts__, {"test": False}):
                mock_list.side_effect = [[], [name]]
                comt = "Volume {0} is created".format(name)
                ret.update(
                    {
                        "comment": comt,
                        "result": True,
                        "changes": {"old": [], "new": [name]},
                    }
                )
                self.assertDictEqual(
                    glusterfs.volume_present(name, bricks, start=False), ret
                )

                mock_list.side_effect = [[], [name]]
                comt = "Volume {0} is created and is now started".format(name)
                ret.update({"comment": comt, "result": True})
                self.assertDictEqual(
                    glusterfs.volume_present(name, bricks, start=True), ret
                )

                mock_list.side_effect = None
                mock_list.return_value = []
                mock_create.return_value = False
                comt = "Creation of volume {0} failed".format(name)
                ret.update({"comment": comt, "result": False, "changes": {}})
                self.assertDictEqual(glusterfs.volume_present(name, bricks), ret)

            with patch.object(
                salt.utils.cloud, "check_name", MagicMock(return_value=True)
            ):
                comt = "Invalid characters in volume name."
                ret.update({"comment": comt, "result": False})
                self.assertDictEqual(glusterfs.volume_present(name, bricks), ret)

    # 'started' function tests: 1

    def test_started(self):
        """
        Test to check if volume has been started
        """
        name = "salt"

        ret = {"name": name, "result": False, "comment": "", "changes": {}}

        started_info = {name: {"status": "1"}}
        stopped_info = {name: {"status": "0"}}
        mock_info = MagicMock(return_value={})
        mock_start = MagicMock(return_value=True)

        with patch.dict(
            glusterfs.__salt__,
            {"glusterfs.info": mock_info, "glusterfs.start_volume": mock_start},
        ):
            comt = "Volume {0} does not exist".format(name)
            ret.update({"comment": comt})
            self.assertDictEqual(glusterfs.started(name), ret)

            mock_info.return_value = started_info
            comt = "Volume {0} is already started".format(name)
            ret.update({"comment": comt, "result": True})
            self.assertDictEqual(glusterfs.started(name), ret)

            with patch.dict(glusterfs.__opts__, {"test": True}):
                mock_info.return_value = stopped_info
                comt = "Volume {0} will be started".format(name)
                ret.update({"comment": comt, "result": None})
                self.assertDictEqual(glusterfs.started(name), ret)

            with patch.dict(glusterfs.__opts__, {"test": False}):
                comt = "Volume {0} is started".format(name)
                ret.update(
                    {
                        "comment": comt,
                        "result": True,
                        "change": {"new": "started", "old": "stopped"},
                    }
                )
                self.assertDictEqual(glusterfs.started(name), ret)

    # 'add_volume_bricks' function tests: 1

    def test_add_volume_bricks(self):
        """
        Test to add brick(s) to an existing volume
        """
        name = "salt"
        bricks = ["host1:/drive1"]
        old_bricks = ["host1:/drive2"]

        ret = {"name": name, "result": False, "comment": "", "changes": {}}

        stopped_volinfo = {"salt": {"status": "0"}}
        volinfo = {
            "salt": {"status": "1", "bricks": {"brick1": {"path": old_bricks[0]}}}
        }
        new_volinfo = {
            "salt": {
                "status": "1",
                "bricks": {
                    "brick1": {"path": old_bricks[0]},
                    "brick2": {"path": bricks[0]},
                },
            }
        }

        mock_info = MagicMock(return_value={})
        mock_add = MagicMock(side_effect=[False, True])

        with patch.dict(
            glusterfs.__salt__,
            {"glusterfs.info": mock_info, "glusterfs.add_volume_bricks": mock_add},
        ):
            ret.update({"comment": "Volume salt does not exist"})
            self.assertDictEqual(glusterfs.add_volume_bricks(name, bricks), ret)

            mock_info.return_value = stopped_volinfo
            ret.update({"comment": "Volume salt is not started"})
            self.assertDictEqual(glusterfs.add_volume_bricks(name, bricks), ret)

            mock_info.return_value = volinfo
            ret.update({"comment": "Adding bricks to volume salt failed"})
            self.assertDictEqual(glusterfs.add_volume_bricks(name, bricks), ret)

            ret.update({"result": True})
            ret.update({"comment": "Bricks already added in volume salt"})
            self.assertDictEqual(glusterfs.add_volume_bricks(name, old_bricks), ret)

            mock_info.side_effect = [volinfo, new_volinfo]
            ret.update(
                {
                    "comment": "Bricks successfully added to volume salt",
                    "changes": {"new": bricks + old_bricks, "old": old_bricks},
                }
            )
            # Let's sort ourselves because the test under python 3 sometimes fails
            # just because of the new changes list order
            result = glusterfs.add_volume_bricks(name, bricks)
            ret["changes"]["new"] = sorted(ret["changes"]["new"])
            result["changes"]["new"] = sorted(result["changes"]["new"])
            self.assertDictEqual(result, ret)

    # 'op_version' function tests: 1

    def test_op_version(self):
        """
        Test setting the Glusterfs op-version
        """
        name = "salt"
        current = 30707
        new = 31200

        ret = {"name": name, "result": False, "comment": "", "changes": {}}

        mock_get_version = MagicMock(return_value={})
        mock_set_version = MagicMock(return_value={})

        with patch.dict(
            glusterfs.__salt__,
            {
                "glusterfs.get_op_version": mock_get_version,
                "glusterfs.set_op_version": mock_set_version,
            },
        ):
            mock_get_version.return_value = [False, "some error message"]
            ret.update({"result": False})
            ret.update({"comment": "some error message"})
            self.assertDictEqual(glusterfs.op_version(name, current), ret)

            mock_get_version.return_value = current
            ret.update({"result": True})
            ret.update(
                {
                    "comment": "Glusterfs cluster.op-version for {0} already set to {1}".format(
                        name, current
                    )
                }
            )
            self.assertDictEqual(glusterfs.op_version(name, current), ret)

            with patch.dict(glusterfs.__opts__, {"test": True}):
                mock_set_version.return_value = [False, "Failed to set version"]
                ret.update({"result": None})
                ret.update(
                    {
                        "comment": "An attempt would be made to set the cluster.op-version for {0} to {1}.".format(
                            name, new
                        )
                    }
                )
                self.assertDictEqual(glusterfs.op_version(name, new), ret)

            with patch.dict(glusterfs.__opts__, {"test": False}):
                mock_set_version.return_value = [False, "Failed to set version"]
                ret.update({"result": False})
                ret.update({"comment": "Failed to set version"})
                self.assertDictEqual(glusterfs.op_version(name, new), ret)

                mock_set_version.return_value = "some success message"
                ret.update({"comment": "some success message"})
                ret.update({"changes": {"old": current, "new": new}})
                ret.update({"result": True})
                self.assertDictEqual(glusterfs.op_version(name, new), ret)

    # 'max_op_version' function tests: 1

    def test_max_op_version(self):
        """
        Test setting the Glusterfs to its self reported max-op-version
        """
        name = "salt"
        current = 30707
        new = 31200

        ret = {"name": name, "result": False, "comment": "", "changes": {}}

        mock_get_version = MagicMock(return_value={})
        mock_get_max_op_version = MagicMock(return_value={})
        mock_set_version = MagicMock(return_value={})

        with patch.dict(
            glusterfs.__salt__,
            {
                "glusterfs.get_op_version": mock_get_version,
                "glusterfs.set_op_version": mock_set_version,
                "glusterfs.get_max_op_version": mock_get_max_op_version,
            },
        ):
            mock_get_version.return_value = [False, "some error message"]
            ret.update({"result": False})
            ret.update({"comment": "some error message"})
            self.assertDictEqual(glusterfs.max_op_version(name), ret)

            mock_get_version.return_value = current
            mock_get_max_op_version.return_value = [False, "some error message"]
            ret.update({"result": False})
            ret.update({"comment": "some error message"})
            self.assertDictEqual(glusterfs.max_op_version(name), ret)

            mock_get_version.return_value = current
            mock_get_max_op_version.return_value = current
            ret.update({"result": True})
            ret.update(
                {
                    "comment": "The cluster.op-version is already set to the cluster.max-op-version of {0}".format(
                        current
                    )
                }
            )
            self.assertDictEqual(glusterfs.max_op_version(name), ret)

            with patch.dict(glusterfs.__opts__, {"test": True}):
                mock_get_max_op_version.return_value = new
                ret.update({"result": None})
                ret.update(
                    {
                        "comment": "An attempt would be made to set the cluster.op-version to {0}.".format(
                            new
                        )
                    }
                )
                self.assertDictEqual(glusterfs.max_op_version(name), ret)

            with patch.dict(glusterfs.__opts__, {"test": False}):
                mock_set_version.return_value = [False, "Failed to set version"]
                ret.update({"result": False})
                ret.update({"comment": "Failed to set version"})
                self.assertDictEqual(glusterfs.max_op_version(name), ret)

                mock_set_version.return_value = "some success message"
                ret.update({"comment": "some success message"})
                ret.update({"changes": {"old": current, "new": new}})
                ret.update({"result": True})
                self.assertDictEqual(glusterfs.max_op_version(name), ret)
