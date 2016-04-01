# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
    :codeauthor: :email:`Joe Julian <me@joejulian.name>`
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.modules import glusterfs
import salt.utils.cloud as suc
from salt.exceptions import CommandExecutionError, SaltInvocationError

# Globals
glusterfs.__salt__ = {}


class GlusterResults(object):
    ''' This class holds the xml results from gluster cli transactions '''

    class v34(object):
        ''' This is for version 3.4 results '''

        class list_peers(object):
            ''' results from "peer status" '''
            pass

        class peer_probe(object):
            fail_cant_connect = fail_bad_hostname = '\n'.join([
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
                '<cliOutput>',
                '  <opRet>-1</opRet>',
                '  <opErrno>107</opErrno>',
                '  <opErrstr>Probe returned with unknown errno 107</opErrstr>',
                '</cliOutput>',
                ''])

            success_self = '\n'.join([
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '  <cliOutput>',
                '  <opRet>0</opRet>',
                '  <opErrno>1</opErrno>',
                '  <opErrstr>(null)</opErrstr>',
                '  <output>success: on localhost not needed</output>',
                '</cliOutput>',
                ''])
            success_other = '\n'.join([
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '  <cliOutput>',
                '  <opRet>0</opRet>',
                '  <opErrno>0</opErrno>',
                '  <opErrstr>(null)</opErrstr>',
                '  <output>success</output>',
                '</cliOutput>',
                ''])
            success_hostname_after_ip = success_other
            success_ip_after_hostname = success_other
            success_already_peer = {
                'ip': '\n'.join([
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '  <cliOutput>',
                    '  <opRet>0</opRet>',
                    '  <opErrno>2</opErrno>',
                    '  <opErrstr>(null)</opErrstr>',
                    '  <output>success: host 10.0.0.2 port 24007 already in peer list</output>',
                    '</cliOutput>',
                    '']),
                'hostname': '\n'.join([
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '  <cliOutput>',
                    '  <opRet>0</opRet>',
                    '  <opErrno>2</opErrno>',
                    '  <opErrstr>(null)</opErrstr>',
                    '  <output>success: host server2 port 24007 already in peer list</output>',
                    '</cliOutput>',
                    ''])}
            success_reverse_already_peer = {
                'ip': '\n'.join([
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '  <cliOutput>',
                    '  <opRet>0</opRet>',
                    '  <opErrno>2</opErrno>',
                    '  <opErrstr>(null)</opErrstr>',
                    '  <output>success: host 10.0.0.1 port 24007 already in peer list</output>',
                    '</cliOutput>',
                    '']),
                'hostname': '\n'.join([
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '  <cliOutput>',
                    '  <opRet>0</opRet>',
                    '  <opErrno>2</opErrno>',
                    '  <opErrstr>(null)</opErrstr>',
                    '  <output>success: host server1 port 24007 already in peer list</output>',
                    '</cliOutput>',
                    ''])}
            success_first_hostname_from_second_first_time = success_other
            success_first_hostname_from_second_second_time = success_reverse_already_peer[
                'hostname']
            success_first_ip_from_second_first_time = success_reverse_already_peer[
                'ip']

    class v37(object):

        class peer_probe(object):
            fail_cant_connect = fail_bad_hostname = '\n'.join([
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
                '<cliOutput>',
                '  <opRet>-1</opRet>',
                '  <opErrno>107</opErrno>',
                '  <opErrstr>Probe returned with Transport endpoint is not connected</opErrstr>',
                '</cliOutput>',
                ''])
            success_self = '\n'.join([
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '  <cliOutput>',
                '  <opRet>0</opRet>',
                '  <opErrno>1</opErrno>',
                '  <opErrstr/>',
                '  <output>Probe on localhost not needed</output>',
                '</cliOutput>',
                ''])
            success_other = '\n'.join([
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '  <cliOutput>',
                '  <opRet>0</opRet>',
                '  <opErrno>0</opErrno>',
                '  <opErrstr/>',
                '  <output/>',
                '</cliOutput>',
                ''])
            success_hostname_after_ip = success_other
            success_ip_after_hostname = success_other
            success_already_peer = {
                'ip': '\n'.join([
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '  <cliOutput>',
                    '  <opRet>0</opRet>',
                    '  <opErrno>2</opErrno>',
                    '  <opErrstr/>',
                    '  <output>Host 10.0.0.2 port 24007 already in peer list</output>',
                    '</cliOutput>',
                    '']),
                'hostname': '\n'.join([
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '  <cliOutput>',
                    '  <opRet>0</opRet>',
                    '  <opErrno>2</opErrno>',
                    '  <opErrstr/>',
                    '  <output>Host server2 port 24007 already in peer list</output>',
                    '</cliOutput>',
                    ''])}
            success_reverse_already_peer = {
                'ip': '\n'.join([
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '  <cliOutput>',
                    '  <opRet>0</opRet>',
                    '  <opErrno>2</opErrno>',
                    '  <opErrstr/>',
                    '  <output>Host 10.0.0.1 port 24007 already in peer list</output>',
                    '</cliOutput>',
                    '']),
                'hostname': '\n'.join([
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '  <cliOutput>',
                    '  <opRet>0</opRet>',
                    '  <opErrno>2</opErrno>',
                    '  <opErrstr/>',
                    '  <output>Host server1 port 24007 already in peer list</output>',
                    '</cliOutput>',
                    ''])}
            success_first_hostname_from_second_first_time = success_reverse_already_peer[
                'hostname']
            success_first_ip_from_second_first_time = success_other
            success_first_ip_from_second_second_time = success_reverse_already_peer[
                'ip']

xml_peer_present = """
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cliOutput>
  <opRet>0</opRet>
  <peer>
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


@skipIf(NO_MOCK, NO_MOCK_REASON)
class GlusterfsTestCase(TestCase):

    '''
    Test cases for salt.modules.glusterfs
    '''
    # 'list_peers' function tests: 1

    maxDiff = None

    def test_list_peers(self):
        '''
        Test if it return a list of gluster peers
        '''
        mock = MagicMock(return_value=xml_peer_present)
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertDictEqual(glusterfs.list_peers(), {
                                 'node02': ['node02.domain.dom', '10.0.0.2']})

        mock = MagicMock(return_value=xml_command_success)
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertIsNone(glusterfs.list_peers())

    # 'peer' function tests: 1

    def test_peer(self):
        '''
        Test if it adds another node into the peer list.
        '''

        # invalid characters
        mock = MagicMock(return_value=True)
        with patch.object(suc, 'check_name', mock):
            self.assertRaises(SaltInvocationError, glusterfs.peer, 'a')
        # version 3.4
        #   by hostname
        #      peer failed unknown hostname
        #      peer failed can't connect
        mock = MagicMock(
            return_value=GlusterResults.v34.peer_probe.fail_cant_connect)
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertRaises(CommandExecutionError, glusterfs.peer, 'server2')
        #      peer self
        mock = MagicMock(
            return_value=GlusterResults.v34.peer_probe.success_self)
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertEqual(glusterfs.peer('server1'),
                             {'exitval': '1', 'output': 'success: on localhost not needed'})
        #      peer added
        mock = MagicMock(
            return_value=GlusterResults.v34.peer_probe.success_other)
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertEqual(glusterfs.peer('server2'),
                             {'exitval': '0', 'output': 'success'})
        #      peer already member
        mock = MagicMock(
            return_value=GlusterResults.v34.peer_probe.success_already_peer['hostname'])
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertEqual(glusterfs.peer('server2'),
                             {'exitval': '2', 'output': 'success: host server2 port 24007 already in peer list'})
        mock = MagicMock(
            return_value=GlusterResults.v34.peer_probe.success_already_peer['ip'])
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertEqual(glusterfs.peer('10.0.0.2'),
                             {'exitval': '2', 'output': 'success: host 10.0.0.2 port 24007 already in peer list'})
        #      peer in reverse (probe server1 from server2)
        mock = MagicMock(
            return_value=GlusterResults.v34.peer_probe.success_first_hostname_from_second_first_time)
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertEqual(glusterfs.peer('server1'),
                             {'exitval': '0', 'output': 'success'})
        mock = MagicMock(
            return_value=GlusterResults.v34.peer_probe.success_first_hostname_from_second_second_time)
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertEqual(glusterfs.peer('server1'),
                             {'exitval': '2', 'output': 'success: host server1 port 24007 already in peer list'})
        #      peer in reverse using ip address instead of hostname
        mock = MagicMock(
            return_value=GlusterResults.v34.peer_probe.success_reverse_already_peer['ip'])
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertEqual(glusterfs.peer('10.0.0.1'),
                             {'exitval': '2', 'output': 'success: host 10.0.0.1 port 24007 already in peer list'})
        #   by ip address
        #      peer self
        mock = MagicMock(
            return_value=GlusterResults.v34.peer_probe.success_self)
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertEqual(glusterfs.peer('10.0.0.1'),
                             {'exitval': '1', 'output': 'success: on localhost not needed'})
        #      peer added
        mock = MagicMock(
            return_value=GlusterResults.v34.peer_probe.success_other)
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertEqual(glusterfs.peer('10.0.0.2'),
                             {'exitval': '0', 'output': 'success'})
        #      peer already member
        mock = MagicMock(
            return_value=GlusterResults.v34.peer_probe.success_already_peer['ip'])
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertEqual(glusterfs.peer('10.0.0.2'),
                             {'exitval': '2', 'output': 'success: host 10.0.0.2 port 24007 already in peer list'})
        # version 3.7
        #      peer failed unknown hostname
        #      peer failed can't connect
        mock = MagicMock(
            return_value=GlusterResults.v37.peer_probe.fail_cant_connect)
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertRaises(CommandExecutionError, glusterfs.peer, 'server2')
        #      peer self
        mock = MagicMock(
            return_value=GlusterResults.v37.peer_probe.success_self)
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertEqual(glusterfs.peer('server1'),
                             {'exitval': '1', 'output': 'Probe on localhost not needed'})
        #      peer added
        mock = MagicMock(
            return_value=GlusterResults.v37.peer_probe.success_other)
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertEqual(glusterfs.peer('server2'),
                             {'exitval': '0', 'output': None})
        #      peer already member
        mock = MagicMock(
            return_value=GlusterResults.v37.peer_probe.success_already_peer['hostname'])
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertEqual(glusterfs.peer('server2'),
                             {'exitval': '2', 'output': 'Host server2 port 24007 already in peer list'})
        #      peer in reverse
        #   by ip address
        #      peer added
        mock = MagicMock(
            return_value=GlusterResults.v37.peer_probe.success_other)
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertEqual(glusterfs.peer('10.0.0.2'),
                             {'exitval': '0', 'output': None})
        #      peer already member
        mock = MagicMock(
            return_value=GlusterResults.v37.peer_probe.success_already_peer['ip'])
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertEqual(glusterfs.peer('10.0.0.2'),
                             {'exitval': '2', 'output': 'Host 10.0.0.2 port 24007 already in peer list'})
        #      peer self
        mock = MagicMock(
            return_value=GlusterResults.v37.peer_probe.success_self)
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertEqual(glusterfs.peer('10.0.0.1'),
                             {'exitval': '1', 'output': 'Probe on localhost not needed'})
        #      peer in reverse (probe server1 from server2)
        mock = MagicMock(
            return_value=GlusterResults.v37.peer_probe.success_first_hostname_from_second_first_time)
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertEqual(glusterfs.peer('server1'),
                             {'exitval': '2', 'output': 'Host server1 port 24007 already in peer list'})
        #      peer in reverse using ip address instead of hostname first time
        mock = MagicMock(
            return_value=GlusterResults.v37.peer_probe.success_first_ip_from_second_first_time)
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertEqual(glusterfs.peer('10.0.0.1'),
                             {'exitval': '0', 'output': None})
        mock = MagicMock(
            return_value=GlusterResults.v37.peer_probe.success_first_ip_from_second_second_time)
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertEqual(glusterfs.peer('10.0.0.1'),
                             {'exitval': '2', 'output': 'Host 10.0.0.1 port 24007 already in peer list'})

    # 'create' function tests: 1

    def test_create(self):
        '''
        Test if it create a glusterfs volume.
        '''
        mock = MagicMock(return_value='')
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertRaises(
                SaltInvocationError,
                glusterfs.create,
                'newvolume',
                'host1:brick')

        mock = MagicMock(return_value='')
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertRaises(
                SaltInvocationError,
                glusterfs.create,
                'newvolume',
                'host1/brick')

        mock = MagicMock(return_value=xml_command_fail)
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertRaises(
                CommandExecutionError,
                glusterfs.create,
                'newvolume',
                'host1:/brick',
                True,
                True,
                True,
                'tcp',
                True)

        mock = MagicMock(return_value=xml_command_success)
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertEqual(glusterfs.create('newvolume', 'host1:/brick',
                                              True, True, True, 'tcp', True),
                             'Volume newvolume created and started')

        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertEqual(glusterfs.create('newvolume', 'host1:/brick'),
                             'Volume newvolume created. Start volume to use')

    # 'list_volumes' function tests: 1

    def test_list_volumes(self):
        '''
        Test if it list configured volumes
        '''
        mock = MagicMock(return_value=xml_volume_absent)
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertListEqual(glusterfs.list_volumes(), [])

        mock = MagicMock(return_value=xml_volume_present)
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertListEqual(glusterfs.list_volumes(),
                                 ['Newvolume1', 'Newvolume2'])

    # 'status' function tests: 1

    def test_status(self):
        '''
        Test if it check the status of a gluster volume.
        '''
        mock = MagicMock(return_value=xml_command_fail)
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertRaises(
                CommandExecutionError, glusterfs.status, 'myvol1')

        res = {'bricks': {
            'node01:/tmp/foo': {
                'host': 'node01',
                'hostname': 'node01',
                'online': True,
                'path': '/tmp/foo',
                'peerid': '830700d7-0684-497c-a12c-c02e365fb90b',
                'pid': '2470',
                'port': '49155',
                'ports': {
                    'rdma': 'N/A',
                    'tcp': '49155'},
                'status': '1'}},
               'healers': {},
               'nfs': {
            'node01': {
                'host': 'NFS Server',
                'hostname': 'NFS Server',
                'online': False,
                'path': 'localhost',
                'peerid': '830700d7-0684-497c-a12c-c02e365fb90b',
                'pid': '-1',
                'port': 'N/A',
                'ports': {
                        'rdma': 'N/A',
                        'tcp': 'N/A'},
                'status': '0'}}}
        mock = MagicMock(return_value=xml_volume_status)
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertDictEqual(glusterfs.status('myvol1'), res)

    # 'start_volume' function tests: 1

    def test_volume_info(self):
        '''
        Test if it returns the volume info.
        '''
        res = {'myvol1': {
            'brickCount': '1',
            'bricks': {
                'brick1': {
                    'hostUuid': '830700d7-0684-497c-a12c-c02e365fb90b',
                    'path': 'node01:/tmp/foo',
                    'uuid': '830700d7-0684-497c-a12c-c02e365fb90b'}},
                'disperseCount': '0',
                'distCount': '1',
                'id': 'f03c2180-cf55-4f77-ae0b-3650f57c82a1',
                'name': 'myvol1',
                'optCount': '1',
                'options': {
                    'performance.readdir-ahead': 'on'},
                'redundancyCount': '0',
                'replicaCount': '1',
                'status': '1',
                'statusStr': 'Started',
                'stripeCount': '1',
                'transport': '0',
                'type': '0',
                'typeStr': 'Distribute'}}
        mock = MagicMock(return_value=xml_volume_info_running)
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertDictEqual(glusterfs.info('myvol1'), res)

    def test_start_volume(self):
        '''
        Test if it start a gluster volume.
        '''
        mock_list = MagicMock(return_value=['Newvolume1', 'Newvolume2'])
        with patch.object(glusterfs, 'list_volumes', mock_list):
            mock_status = MagicMock(return_value={'status': '1'})
            with patch.object(glusterfs, 'info', mock_status):
                mock = MagicMock(return_value=xml_command_success)
                with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
                    self.assertEqual(glusterfs.start_volume('Newvolume1'),
                                     'Volume already started')

            mock_status = MagicMock(return_value={'status': '0'})
            with patch.object(glusterfs, 'info', mock_status):
                mock_run = MagicMock(return_value=xml_command_success)
                with patch.dict(glusterfs.__salt__, {'cmd.run': mock_run}):
                    self.assertEqual(glusterfs.start_volume('Newvolume1'),
                                     'Volume Newvolume1 started')

        mock = MagicMock(return_value=xml_command_fail)
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertRaises(
                CommandExecutionError, glusterfs.start_volume, 'Newvolume1')

    # 'stop_volume' function tests: 1

    def test_stop_volume(self):
        '''
        Test if it stop a gluster volume.
        '''
        mock = MagicMock(return_value={})
        with patch.object(glusterfs, 'status', mock):
            mock = MagicMock(return_value=xml_command_success)
            with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
                self.assertEqual(glusterfs.stop_volume('Newvolume1'),
                                 'Volume Newvolume1 stopped')

            mock = MagicMock(return_value=xml_command_fail)
            with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
                self.assertRaises(
                    CommandExecutionError, glusterfs.stop_volume, 'Newvolume1')

        mock = MagicMock(return_value=xml_command_fail)
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertRaises(
                CommandExecutionError, glusterfs.stop_volume, 'Newvolume1')

    # 'delete' function tests: 1

    def test_delete(self):
        '''
        Test if it deletes a gluster volume.
        '''
        mock = MagicMock(return_value=['Newvolume1', 'Newvolume2'])
        with patch.object(glusterfs, 'list_volumes', mock):
            # volume doesn't exist
            self.assertRaises(
                SaltInvocationError, glusterfs.delete, 'Newvolume3')

            mock = MagicMock(return_value={'status': '1'})
            with patch.object(glusterfs, 'info', mock):
                mock = MagicMock(return_value=xml_command_success)
                # volume exists, should not be stopped, and is started
                with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
                    self.assertRaises(
                        SaltInvocationError,
                        glusterfs.delete,
                        'Newvolume1',
                        False)

                # volume exists, should be stopped, and is started
                with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
                    self.assertEqual(glusterfs.delete('Newvolume1'),
                                     'Volume Newvolume1 stopped and deleted')

            # volume exists and isn't started
            mock = MagicMock(return_value={'status': '0'})
            with patch.object(glusterfs, 'info', mock):
                mock = MagicMock(return_value=xml_command_success)
                with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
                    self.assertEqual(glusterfs.delete('Newvolume1'),
                                     'Volume Newvolume1 deleted')

    # 'add_volume_bricks' function tests: 1

    def test_add_volume_bricks(self):
        '''
        Test if it add brick(s) to an existing volume
        '''
        # volume does not exist
        mock = MagicMock(return_value=xml_command_fail)
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertRaises(
                CommandExecutionError,
                glusterfs.add_volume_bricks,
                'Newvolume1',
                ['bricks'])

        ret = '1 bricks successfully added to the volume Newvolume1'
        # volume does exist
        mock = MagicMock(return_value={'bricks': {}})
        with patch.object(glusterfs, 'info', mock):
            mock = MagicMock(return_value=xml_command_success)
            # ... and the added brick does not exist
            with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
                self.assertEqual(glusterfs.add_volume_bricks('Newvolume1',
                                                             ['bricks']), ret)

        mock = MagicMock(
            return_value={'bricks': {'brick1': {'path': 'bricks'}}})
        with patch.object(glusterfs, 'info', mock):
            # ... and the added brick does exist
            with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
                # As a list
                self.assertEqual(
                    glusterfs.add_volume_bricks(
                        'Newvolume1',
                        ['bricks']),
                    'Bricks already in volume Newvolume1')
                # As a string
                self.assertEqual(
                    glusterfs.add_volume_bricks(
                        'Newvolume1',
                        'bricks'),
                    'Bricks already in volume Newvolume1')
                # And empty list
                self.assertEqual(glusterfs.add_volume_bricks('Newvolume1', []),
                                 'Bricks already in volume Newvolume1')


if __name__ == '__main__':
    from integration import run_tests
    run_tests(GlusterfsTestCase, needs_daemon=False)
