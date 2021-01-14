"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
    :codeauthor: Joe Julian <me@joejulian.name>
"""


import salt.modules.glusterfs as glusterfs
from salt.exceptions import SaltInvocationError
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class GlusterResults:
    """ This class holds the xml results from gluster cli transactions """

    class v34:
        """ This is for version 3.4 results """

        class list_peers:
            """ results from "peer status" """

        class peer_probe:
            fail_cant_connect = fail_bad_hostname = "\n".join(
                [
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
                    "<cliOutput>",
                    "  <opRet>-1</opRet>",
                    "  <opErrno>107</opErrno>",
                    "  <opErrstr>Probe returned with unknown errno 107</opErrstr>",
                    "</cliOutput>",
                    "",
                ]
            )

            success_self = "\n".join(
                [
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    "  <cliOutput>",
                    "  <opRet>0</opRet>",
                    "  <opErrno>1</opErrno>",
                    "  <opErrstr>(null)</opErrstr>",
                    "  <output>success: on localhost not needed</output>",
                    "</cliOutput>",
                    "",
                ]
            )
            success_other = "\n".join(
                [
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    "  <cliOutput>",
                    "  <opRet>0</opRet>",
                    "  <opErrno>0</opErrno>",
                    "  <opErrstr>(null)</opErrstr>",
                    "  <output>success</output>",
                    "</cliOutput>",
                    "",
                ]
            )
            success_hostname_after_ip = success_other
            success_ip_after_hostname = success_other
            success_already_peer = {
                "ip": "\n".join(
                    [
                        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                        "  <cliOutput>",
                        "  <opRet>0</opRet>",
                        "  <opErrno>2</opErrno>",
                        "  <opErrstr>(null)</opErrstr>",
                        "  <output>success: host 10.0.0.2 port 24007 already in peer list</output>",
                        "</cliOutput>",
                        "",
                    ]
                ),
                "hostname": "\n".join(
                    [
                        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                        "  <cliOutput>",
                        "  <opRet>0</opRet>",
                        "  <opErrno>2</opErrno>",
                        "  <opErrstr>(null)</opErrstr>",
                        "  <output>success: host server2 port 24007 already in peer list</output>",
                        "</cliOutput>",
                        "",
                    ]
                ),
            }
            success_reverse_already_peer = {
                "ip": "\n".join(
                    [
                        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                        "  <cliOutput>",
                        "  <opRet>0</opRet>",
                        "  <opErrno>2</opErrno>",
                        "  <opErrstr>(null)</opErrstr>",
                        "  <output>success: host 10.0.0.1 port 24007 already in peer list</output>",
                        "</cliOutput>",
                        "",
                    ]
                ),
                "hostname": "\n".join(
                    [
                        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                        "  <cliOutput>",
                        "  <opRet>0</opRet>",
                        "  <opErrno>2</opErrno>",
                        "  <opErrstr>(null)</opErrstr>",
                        "  <output>success: host server1 port 24007 already in peer list</output>",
                        "</cliOutput>",
                        "",
                    ]
                ),
            }
            success_first_hostname_from_second_first_time = success_other
            success_first_hostname_from_second_second_time = success_reverse_already_peer[
                "hostname"
            ]
            success_first_ip_from_second_first_time = success_reverse_already_peer["ip"]

    class v37:
        class peer_probe:
            fail_cant_connect = fail_bad_hostname = "\n".join(
                [
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
                    "<cliOutput>",
                    "  <opRet>-1</opRet>",
                    "  <opErrno>107</opErrno>",
                    "  <opErrstr>Probe returned with Transport endpoint is not connected</opErrstr>",
                    "</cliOutput>",
                    "",
                ]
            )
            success_self = "\n".join(
                [
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    "  <cliOutput>",
                    "  <opRet>0</opRet>",
                    "  <opErrno>1</opErrno>",
                    "  <opErrstr/>",
                    "  <output>Probe on localhost not needed</output>",
                    "</cliOutput>",
                    "",
                ]
            )
            success_other = "\n".join(
                [
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    "  <cliOutput>",
                    "  <opRet>0</opRet>",
                    "  <opErrno>0</opErrno>",
                    "  <opErrstr/>",
                    "  <output/>",
                    "</cliOutput>",
                    "",
                ]
            )
            success_hostname_after_ip = success_other
            success_ip_after_hostname = success_other
            success_already_peer = {
                "ip": "\n".join(
                    [
                        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                        "  <cliOutput>",
                        "  <opRet>0</opRet>",
                        "  <opErrno>2</opErrno>",
                        "  <opErrstr/>",
                        "  <output>Host 10.0.0.2 port 24007 already in peer list</output>",
                        "</cliOutput>",
                        "",
                    ]
                ),
                "hostname": "\n".join(
                    [
                        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                        "  <cliOutput>",
                        "  <opRet>0</opRet>",
                        "  <opErrno>2</opErrno>",
                        "  <opErrstr/>",
                        "  <output>Host server2 port 24007 already in peer list</output>",
                        "</cliOutput>",
                        "",
                    ]
                ),
            }
            success_reverse_already_peer = {
                "ip": "\n".join(
                    [
                        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                        "  <cliOutput>",
                        "  <opRet>0</opRet>",
                        "  <opErrno>2</opErrno>",
                        "  <opErrstr/>",
                        "  <output>Host 10.0.0.1 port 24007 already in peer list</output>",
                        "</cliOutput>",
                        "",
                    ]
                ),
                "hostname": "\n".join(
                    [
                        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                        "  <cliOutput>",
                        "  <opRet>0</opRet>",
                        "  <opErrno>2</opErrno>",
                        "  <opErrstr/>",
                        "  <output>Host server1 port 24007 already in peer list</output>",
                        "</cliOutput>",
                        "",
                    ]
                ),
            }
            success_first_hostname_from_second_first_time = success_reverse_already_peer[
                "hostname"
            ]
            success_first_ip_from_second_first_time = success_other
            success_first_ip_from_second_second_time = success_reverse_already_peer[
                "ip"
            ]


#  gluster --version output collected in the wild.
version_output_362 = """
glusterfs 3.6.2 built on Jan 22 2015 12:59:57
Repository revision: git://git.gluster.com/glusterfs.git
Copyright (c) 2006-2011 Gluster Inc. <http://www.gluster.com>
GlusterFS comes with ABSOLUTELY NO WARRANTY.
You may redistribute copies of GlusterFS under the terms of the GNU General Public License
   """

version_output_61 = """
glusterfs 6.1
Repository revision: git://git.gluster.org/glusterfs.git
Copyright (c) 2006-2016 Red Hat, Inc. <https://www.gluster.org/>
GlusterFS comes with ABSOLUTELY NO WARRANTY.
It is licensed to you under your choice of the GNU Lesser
General Public License, version 3 or any later version (LGPLv3
or later), or the GNU General Public License, version 2 (GPLv2),
in all cases as published by the Free Software Foundation.
"""

xml_peer_present = """
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cliOutput>
  <opRet>0</opRet>
  <peer>
    <uuid>uuid1</uuid>
    <hostname>node02</hostname>
    <hostnames>
      <hostname>node02.domain.dom</hostname>
      <hostname>10.0.0.2</hostname>
    </hostnames>
  </peer>
</cliOutput>
"""

xml_volume_present = """
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cliOutput>
  <opRet>0</opRet>
  <volList>
    <volume>Newvolume1</volume>
    <volume>Newvolume2</volume>
  </volList>
</cliOutput>
"""

xml_volume_absent = """
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cliOutput>
  <opRet>0</opRet>
  <volList>
    <count>0</count>
  </volList>
</cliOutput>
"""

xml_volume_status = """
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cliOutput>
  <opRet>0</opRet>
  <volStatus>
    <volumes>
      <volume>
        <volName>myvol1</volName>
        <nodeCount>3</nodeCount>
        <node>
          <hostname>node01</hostname>
          <path>/tmp/foo</path>
          <peerid>830700d7-0684-497c-a12c-c02e365fb90b</peerid>
          <status>1</status>
          <port>49155</port>
          <ports>
            <tcp>49155</tcp>
            <rdma>N/A</rdma>
          </ports>
          <pid>2470</pid>
        </node>
        <node>
          <hostname>NFS Server</hostname>
          <path>localhost</path>
          <peerid>830700d7-0684-497c-a12c-c02e365fb90b</peerid>
          <status>0</status>
          <port>N/A</port>
          <ports>
            <tcp>N/A</tcp>
            <rdma>N/A</rdma>
          </ports>
          <pid>-1</pid>
        </node>
        <tasks/>
      </volume>
    </volumes>
  </volStatus>
</cliOutput>
"""

xml_volume_info_running = """
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cliOutput>
  <opRet>0</opRet>
  <volInfo>
    <volumes>
      <volume>
        <name>myvol1</name>
        <id>f03c2180-cf55-4f77-ae0b-3650f57c82a1</id>
        <status>1</status>
        <statusStr>Started</statusStr>
        <brickCount>1</brickCount>
        <distCount>1</distCount>
        <stripeCount>1</stripeCount>
        <replicaCount>1</replicaCount>
        <disperseCount>0</disperseCount>
        <redundancyCount>0</redundancyCount>
        <type>0</type>
        <typeStr>Distribute</typeStr>
        <transport>0</transport>
        <bricks>
          <brick uuid="830700d7-0684-497c-a12c-c02e365fb90b">node01:/tmp/foo<name>node01:/tmp/foo</name><hostUuid>830700d7-0684-497c-a12c-c02e365fb90b</hostUuid></brick>
        </bricks>
        <optCount>1</optCount>
        <options>
          <option>
            <name>performance.readdir-ahead</name>
            <value>on</value>
          </option>
        </options>
      </volume>
      <count>1</count>
    </volumes>
  </volInfo>
</cliOutput>
"""

xml_volume_info_stopped = """
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cliOutput>
  <opRet>0</opRet>
  <volInfo>
    <volumes>
      <volume>
        <name>myvol1</name>
        <status>1</status>
      </volume>
    </volumes>
  </volInfo>
</cliOutput>
"""

xml_peer_probe_success = """
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cliOutput>
  <opRet>0</opRet>
  <opErrno>0</opErrno>
  <opErrstr/>
  <output/>
</cliOutput>
"""

xml_peer_probe_already_member = """
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cliOutput>
  <opRet>0</opRet>
  <opErrno>2</opErrno>
  <opErrstr/>
  <output>Host salt port 24007 already in peer list</output>
</cliOutput>
"""

xml_peer_probe_localhost = """
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cliOutput>
  <opRet>0</opRet>
  <opErrno>1</opErrno>
  <opErrstr/>
  <output>Probe on localhost not needed</output>
</cliOutput>
"""

xml_peer_probe_fail_cant_connect = """
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cliOutput>
  <opRet>-1</opRet>
  <opErrno>107</opErrno>
  <opErrstr>Probe returned with Transport endpoint is not connected</opErrstr>
</cliOutput>
"""

xml_command_success = """
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cliOutput>
  <opRet>0</opRet>
</cliOutput>
"""

xml_command_fail = """
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cliOutput>
  <opRet>-1</opRet>
    <opErrno>0</opErrno>
  <opErrstr>Command Failed</opErrstr>
</cliOutput>
"""

xml_op_version_37 = """
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cliOutput>
  <opRet>0</opRet>
  <opErrno>0</opErrno>
  <opErrstr/>
  <volGetopts>
    <count>1</count>
    <Option>cluster.op-version</Option>
    <Value>30707</Value>
  </volGetopts>
</cliOutput>
"""

xml_op_version_312 = """
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cliOutput>
  <opRet>0</opRet>
  <opErrno>0</opErrno>
  <opErrstr/>
  <volGetopts>
    <count>1</count>
    <Opt>
      <Option>cluster.op-version</Option>
      <Value>30707</Value>
    </Opt>
  </volGetopts>
</cliOutput>
"""

xml_max_op_version = """
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cliOutput>
  <opRet>0</opRet>
  <opErrno>0</opErrno>
  <opErrstr/>
  <volGetopts>
    <count>1</count>
    <Opt>
      <Option>cluster.max-op-version</Option>
      <Value>31200</Value>
    </Opt>
  </volGetopts>
</cliOutput>
"""

xml_set_op_version_failure = """
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cliOutput>
  <opRet>-1</opRet>
  <opErrno>30800</opErrno>
  <opErrstr>Required op-version (30707) should not be equal or lower than current cluster op-version (30707).</opErrstr>
  <cliOp>volSet</cliOp>
  <output>Set volume unsuccessful</output>
</cliOutput>
"""

xml_set_op_version_success = """
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cliOutput>
  <opRet>0</opRet>
  <opErrno>0</opErrno>
  <opErrstr/>
  <cliOp>volSet</cliOp>
  <output>Set volume successful</output>
</cliOutput>
"""


class GlusterfsTestCase(TestCase, LoaderModuleMockMixin):

    """
    Test cases for salt.modules.glusterfs
    """

    def setup_loader_modules(self):
        return {glusterfs: {}}

    maxDiff = None

    # 'peer_status' function tests: 1

    def test__get_version(self):
        """
        Test parsing of gluster --version.
        """
        mock_version = MagicMock(return_value="foo")
        with patch.dict(glusterfs.__salt__, {"cmd.run": mock_version}):
            self.assertEqual(glusterfs._get_version(), (3, 6), msg="default behaviour")

        mock_version = MagicMock(return_value=version_output_362)
        with patch.dict(glusterfs.__salt__, {"cmd.run": mock_version}):
            self.assertEqual(glusterfs._get_version(), (3, 6, 2))

        mock_version = MagicMock(return_value=version_output_61)
        with patch.dict(glusterfs.__salt__, {"cmd.run": mock_version}):
            self.assertEqual(glusterfs._get_version(), (6, 1))

        more_versions = {
            "6.0": (6, 0),
            "4.1.10": (4, 1, 10),
            "5.13": (5, 13),
            "10.0": (10, 0),
        }
        for v in more_versions:
            mock_version = MagicMock(return_value="glusterfs {}".format(v))
            with patch.dict(glusterfs.__salt__, {"cmd.run": mock_version}):
                self.assertEqual(glusterfs._get_version(), more_versions[v])

    def test_peer_status(self):
        """
        Test gluster peer status
        """
        mock_run = MagicMock(return_value=xml_peer_present)
        with patch.dict(glusterfs.__salt__, {"cmd.run": mock_run}):
            self.assertDictEqual(
                glusterfs.peer_status(),
                {"uuid1": {"hostnames": ["node02", "node02.domain.dom", "10.0.0.2"]}},
            )

        mock_run = MagicMock(return_value=xml_command_success)
        with patch.dict(glusterfs.__salt__, {"cmd.run": mock_run}):
            self.assertDictEqual(glusterfs.peer_status(), {})

    # 'peer' function tests: 1

    def test_peer(self):
        """
        Test if gluster peer call is successful.
        """
        mock_run = MagicMock()
        with patch.dict(glusterfs.__salt__, {"cmd.run": mock_run}):
            mock_run.return_value = xml_peer_probe_already_member
            self.assertTrue(glusterfs.peer("salt"))

            mock_run.return_value = xml_peer_probe_localhost
            self.assertTrue(glusterfs.peer("salt"))

            mock_run.return_value = xml_peer_probe_fail_cant_connect
            self.assertFalse(glusterfs.peer("salt"))

    # 'create_volume' function tests: 1

    def test_create_volume(self):
        """
        Test if it creates a glusterfs volume.
        """
        mock_run = MagicMock(return_value=xml_command_success)
        with patch.dict(glusterfs.__salt__, {"cmd.run": mock_run}):
            self.assertRaises(
                SaltInvocationError, glusterfs.create_volume, "newvolume", "host1:brick"
            )

            self.assertRaises(
                SaltInvocationError, glusterfs.create_volume, "newvolume", "host1/brick"
            )

            self.assertFalse(mock_run.called)

            mock_start_volume = MagicMock(return_value=True)
            with patch.object(glusterfs, "start_volume", mock_start_volume):
                # Create, do not start
                self.assertTrue(glusterfs.create_volume("newvolume", "host1:/brick"))
                self.assertFalse(mock_start_volume.called)

                # Create and start
                self.assertTrue(
                    glusterfs.create_volume("newvolume", "host1:/brick", start=True)
                )
                self.assertTrue(mock_start_volume.called)

                mock_start_volume.return_value = False
                # Create and fail start
                self.assertFalse(
                    glusterfs.create_volume("newvolume", "host1:/brick", start=True)
                )

            mock_run.return_value = xml_command_fail
            self.assertFalse(
                glusterfs.create_volume(
                    "newvolume", "host1:/brick", True, True, True, "tcp", True
                )
            )

    # 'list_volumes' function tests: 1

    def test_list_volumes(self):
        """
        Test if it list configured volumes
        """
        mock = MagicMock(return_value=xml_volume_absent)
        with patch.dict(glusterfs.__salt__, {"cmd.run": mock}):
            self.assertListEqual(glusterfs.list_volumes(), [])

        mock = MagicMock(return_value=xml_volume_present)
        with patch.dict(glusterfs.__salt__, {"cmd.run": mock}):
            self.assertListEqual(glusterfs.list_volumes(), ["Newvolume1", "Newvolume2"])

    # 'status' function tests: 1

    def test_status(self):
        """
        Test if it check the status of a gluster volume.
        """
        mock_run = MagicMock(return_value=xml_command_fail)
        with patch.dict(glusterfs.__salt__, {"cmd.run": mock_run}):
            self.assertIsNone(glusterfs.status("myvol1"))

        res = {
            "bricks": {
                "node01:/tmp/foo": {
                    "host": "node01",
                    "hostname": "node01",
                    "online": True,
                    "path": "/tmp/foo",
                    "peerid": "830700d7-0684-497c-a12c-c02e365fb90b",
                    "pid": "2470",
                    "port": "49155",
                    "ports": {"rdma": "N/A", "tcp": "49155"},
                    "status": "1",
                }
            },
            "healers": {},
            "nfs": {
                "node01": {
                    "host": "NFS Server",
                    "hostname": "NFS Server",
                    "online": False,
                    "path": "localhost",
                    "peerid": "830700d7-0684-497c-a12c-c02e365fb90b",
                    "pid": "-1",
                    "port": "N/A",
                    "ports": {"rdma": "N/A", "tcp": "N/A"},
                    "status": "0",
                }
            },
        }
        mock = MagicMock(return_value=xml_volume_status)
        with patch.dict(glusterfs.__salt__, {"cmd.run": mock}):
            self.assertDictEqual(glusterfs.status("myvol1"), res)

    # 'start_volume' function tests: 1

    def test_volume_info(self):
        """
        Test if it returns the volume info.
        """
        res = {
            "myvol1": {
                "brickCount": "1",
                "bricks": {
                    "brick1": {
                        "hostUuid": "830700d7-0684-497c-a12c-c02e365fb90b",
                        "path": "node01:/tmp/foo",
                        "uuid": "830700d7-0684-497c-a12c-c02e365fb90b",
                    }
                },
                "disperseCount": "0",
                "distCount": "1",
                "id": "f03c2180-cf55-4f77-ae0b-3650f57c82a1",
                "name": "myvol1",
                "optCount": "1",
                "options": {"performance.readdir-ahead": "on"},
                "redundancyCount": "0",
                "replicaCount": "1",
                "status": "1",
                "statusStr": "Started",
                "stripeCount": "1",
                "transport": "0",
                "type": "0",
                "typeStr": "Distribute",
            }
        }
        mock = MagicMock(return_value=xml_volume_info_running)
        with patch.dict(glusterfs.__salt__, {"cmd.run": mock}):
            self.assertDictEqual(glusterfs.info("myvol1"), res)

    def test_start_volume(self):
        """
        Test if it start a gluster volume.
        """
        # Stopped volume
        mock_info = MagicMock(return_value={"Newvolume1": {"status": "0"}})
        with patch.object(glusterfs, "info", mock_info):
            mock_run = MagicMock(return_value=xml_command_success)
            with patch.dict(glusterfs.__salt__, {"cmd.run": mock_run}):
                self.assertEqual(glusterfs.start_volume("Newvolume1"), True)
                self.assertEqual(glusterfs.start_volume("nonExisting"), False)
            mock_run = MagicMock(return_value=xml_command_fail)
            with patch.dict(glusterfs.__salt__, {"cmd.run": mock_run}):
                self.assertEqual(glusterfs.start_volume("Newvolume1"), False)

        # Started volume
        mock_info = MagicMock(return_value={"Newvolume1": {"status": "1"}})
        with patch.object(glusterfs, "info", mock_info):
            mock_run = MagicMock(return_value=xml_command_success)
            with patch.dict(glusterfs.__salt__, {"cmd.run": mock_run}):
                self.assertEqual(glusterfs.start_volume("Newvolume1", force=True), True)
            mock_run = MagicMock(return_value=xml_command_fail)
            with patch.dict(glusterfs.__salt__, {"cmd.run": mock_run}):
                # cmd.run should not be called for already running volume:
                self.assertEqual(glusterfs.start_volume("Newvolume1"), True)
                # except when forcing:
                self.assertEqual(
                    glusterfs.start_volume("Newvolume1", force=True), False
                )

    # 'stop_volume' function tests: 1

    def test_stop_volume(self):
        """
        Test if it stop a gluster volume.
        """
        # Stopped volume
        mock_info = MagicMock(return_value={"Newvolume1": {"status": "0"}})
        with patch.object(glusterfs, "info", mock_info):
            mock_run = MagicMock(return_value=xml_command_success)
            with patch.dict(glusterfs.__salt__, {"cmd.run": mock_run}):
                self.assertEqual(glusterfs.stop_volume("Newvolume1"), True)
                self.assertEqual(glusterfs.stop_volume("nonExisting"), False)
            mock_run = MagicMock(return_value=xml_command_fail)
            with patch.dict(glusterfs.__salt__, {"cmd.run": mock_run}):
                # cmd.run should not be called for already stopped volume:
                self.assertEqual(glusterfs.stop_volume("Newvolume1"), True)

        # Started volume
        mock_info = MagicMock(return_value={"Newvolume1": {"status": "1"}})
        with patch.object(glusterfs, "info", mock_info):
            mock_run = MagicMock(return_value=xml_command_success)
            with patch.dict(glusterfs.__salt__, {"cmd.run": mock_run}):
                self.assertEqual(glusterfs.stop_volume("Newvolume1"), True)
                self.assertEqual(glusterfs.stop_volume("nonExisting"), False)
            mock_run = MagicMock(return_value=xml_command_fail)
            with patch.dict(glusterfs.__salt__, {"cmd.run": mock_run}):
                self.assertEqual(glusterfs.stop_volume("Newvolume1"), False)

    # 'delete_volume' function tests: 1

    def test_delete_volume(self):
        """
        Test if it deletes a gluster volume.
        """
        mock_info = MagicMock(return_value={"Newvolume1": {"status": "1"}})
        with patch.object(glusterfs, "info", mock_info):
            # volume doesn't exist
            self.assertFalse(glusterfs.delete_volume("Newvolume3"))

            mock_stop_volume = MagicMock(return_value=True)
            mock_run = MagicMock(return_value=xml_command_success)
            with patch.dict(glusterfs.__salt__, {"cmd.run": mock_run}):
                with patch.object(glusterfs, "stop_volume", mock_stop_volume):
                    # volume exists, should not be stopped, and is started
                    self.assertFalse(glusterfs.delete_volume("Newvolume1", False))
                    self.assertFalse(mock_run.called)
                    self.assertFalse(mock_stop_volume.called)

                    # volume exists, should be stopped, and is started
                    self.assertTrue(glusterfs.delete_volume("Newvolume1"))
                    self.assertTrue(mock_run.called)
                    self.assertTrue(mock_stop_volume.called)

        # volume exists and isn't started
        mock_info = MagicMock(return_value={"Newvolume1": {"status": "2"}})
        with patch.object(glusterfs, "info", mock_info):
            mock_run = MagicMock(return_value=xml_command_success)
            with patch.dict(glusterfs.__salt__, {"cmd.run": mock_run}):
                self.assertTrue(glusterfs.delete_volume("Newvolume1"))
                mock_run.return_value = xml_command_fail
                self.assertFalse(glusterfs.delete_volume("Newvolume1"))

    # 'add_volume_bricks' function tests: 1

    def test_add_volume_bricks(self):
        """
        Test if it add brick(s) to an existing volume
        """
        mock_info = MagicMock(
            return_value={
                "Newvolume1": {
                    "status": "1",
                    "bricks": {
                        "brick1": {"path": "host:/path1"},
                        "brick2": {"path": "host:/path2"},
                    },
                }
            }
        )
        with patch.object(glusterfs, "info", mock_info):
            mock_run = MagicMock(return_value=xml_command_success)
            with patch.dict(glusterfs.__salt__, {"cmd.run": mock_run}):
                # Volume does not exist
                self.assertFalse(glusterfs.add_volume_bricks("nonExisting", ["bricks"]))
                # Brick already exists
                self.assertTrue(
                    glusterfs.add_volume_bricks("Newvolume1", ["host:/path2"])
                )
                # Already existing brick as a string
                self.assertTrue(
                    glusterfs.add_volume_bricks("Newvolume1", "host:/path2")
                )
                self.assertFalse(mock_run.called)
                # A new brick:
                self.assertTrue(
                    glusterfs.add_volume_bricks("Newvolume1", ["host:/new1"])
                )
                self.assertTrue(mock_run.called)

                # Gluster call fails
                mock_run.return_value = xml_command_fail
                self.assertFalse(
                    glusterfs.add_volume_bricks("Newvolume1", ["new:/path"])
                )

    # 'get_op_version' function tests: 1

    def test_get_op_version(self):
        """
        Test retrieving the glusterfs op-version
        """

        # Test with xml output structure from v3.7
        mock_run = MagicMock(return_value=xml_op_version_37)
        with patch.dict(glusterfs.__salt__, {"cmd.run": mock_run}):
            self.assertEqual(glusterfs.get_op_version("test"), "30707")

        # Test with xml output structure from v3.12
        mock_run = MagicMock(return_value=xml_op_version_312)
        with patch.dict(glusterfs.__salt__, {"cmd.run": mock_run}):
            self.assertEqual(glusterfs.get_op_version("test"), "30707")

    # 'get_max_op_version' function tests: 1

    def test_get_max_op_version(self):
        """
        Test retrieving the glusterfs max-op-version.
        """

        mock_xml = MagicMock(return_value=xml_max_op_version)
        mock_version = MagicMock(return_value="glusterfs 3.9.1")

        with patch.dict(glusterfs.__salt__, {"cmd.run": mock_version}):
            self.assertFalse(glusterfs.get_max_op_version()[0])

        with patch.object(glusterfs, "_get_version", return_value=(3, 12, 0)):
            with patch.dict(glusterfs.__salt__, {"cmd.run": mock_xml}):
                self.assertEqual(glusterfs.get_max_op_version(), "31200")

    # 'set_op_version' function tests: 1

    def test_set_op_version(self):
        """
        Test setting the glusterfs op-version
        """
        mock_failure = MagicMock(return_value=xml_set_op_version_failure)
        mock_success = MagicMock(return_value=xml_set_op_version_success)

        with patch.dict(glusterfs.__salt__, {"cmd.run": mock_failure}):
            self.assertFalse(glusterfs.set_op_version(30707)[0])

        with patch.dict(glusterfs.__salt__, {"cmd.run": mock_success}):
            self.assertEqual(glusterfs.set_op_version(31200), "Set volume successful")
