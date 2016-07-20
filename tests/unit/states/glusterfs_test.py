# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.states import glusterfs
from tests.unit.modules.glusterfs_test import GlusterResults
import salt.modules.glusterfs as mod_glusterfs

import salt.utils.cloud

import salt.modules.glusterfs as mod_glusterfs
glusterfs.__salt__ = {'glusterfs.peer': mod_glusterfs.peer}
glusterfs.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class GlusterfsTestCase(TestCase):
    '''
    Test cases for salt.states.glusterfs
    '''
    # 'peered' function tests: 1

    def test_peered(self):
        '''
        Test to verify if node is peered.
        '''
        name = 'server1'
        other_name = 'server1'

        ret = {'name': name,
               'result': True,
               'comment': '',
               'changes': {}}

        # probe new peer server2 under gluster 3.4.x
        comt = ('Peer {0} added successfully.'.format(name))
        ret.update({'comment': comt, 'result': True,
                    'changes': {'new': {name: []}, 'old': {}}})
        mock_xml = MagicMock(
            return_value=GlusterResults.v34.peer_probe.success_other)
        with patch.dict('salt.modules.glusterfs.__salt__', {'cmd.run': mock_xml}):
            mock = MagicMock(side_effect=[{}, {name: []}])
            with patch.dict(glusterfs.__salt__, {'glusterfs.list_peers': mock}):
                self.assertDictEqual(glusterfs.peered(name), ret)

        # probe new peer server2 under gluster 3.7.x
        mock_xml = MagicMock(
            return_value=GlusterResults.v37.peer_probe.success_other)
        with patch.dict('salt.modules.glusterfs.__salt__', {'cmd.run': mock_xml}):
            mock = MagicMock(side_effect=[{}, {name: []}])
            with patch.dict(glusterfs.__salt__, {'glusterfs.list_peers': mock}):
                self.assertDictEqual(glusterfs.peered(name), ret)

        # probe already existing server2 under gluster 3.4.x
        comt = ('Host {0} already peered'.format(name))
        ret.update({'comment': comt, 'changes': {}})
        mock_xml = MagicMock(
            return_value=GlusterResults.v34.peer_probe.success_already_peer['hostname'])
        with patch.dict('salt.modules.glusterfs.__salt__', {'cmd.run': mock_xml}):
            mock = MagicMock(side_effect=[{name: []}, {name: []}])
            with patch.dict(glusterfs.__salt__, {'glusterfs.list_peers': mock}):
                self.assertDictEqual(glusterfs.peered(name), ret)

        # probe already existing server2 under gluster 3.7.x
        mock_xml = MagicMock(
            return_value=GlusterResults.v37.peer_probe.success_already_peer['hostname'])
        with patch.dict('salt.modules.glusterfs.__salt__', {'cmd.run': mock_xml}):
            mock = MagicMock(side_effect=[{name: []}, {name: []}])
            with patch.dict(glusterfs.__salt__, {'glusterfs.list_peers': mock}):
                self.assertDictEqual(glusterfs.peered(name), ret)

        # Issue 30932: Peering an existing server by IP fails with gluster 3.7+
        #
        # server2 was probed by address, 10.0.0.2. Under 3.4, server1 would be
        # known as 10.0.0.1 but starting with 3.7, its hostname of server1 would be
        # known instead. Subsequent probing of server1 by server2 used to result in
        # "success_already_peer" but now it should succeed in adding an alternate
        # hostname entry.

        name = 'server1'
        ip = '10.0.0.1'
        comt = ('Host {0} already peered'.format(ip))
        ret.update({'name': ip, 'comment': comt, 'changes': {}})
        mock_xml = MagicMock(
            return_value=GlusterResults.v34.peer_probe.success_first_ip_from_second_first_time)
        with patch.dict('salt.modules.glusterfs.__salt__', {'cmd.run': mock_xml}):
            mock = MagicMock(side_effect=[{ip: []}, {ip: []}])
            with patch.dict(glusterfs.__salt__, {'glusterfs.list_peers': mock}):
                self.assertDictEqual(glusterfs.peered(ip), ret)

        comt = ('Peer {0} added successfully.'.format(ip))
        ret.update({'name': ip, 'comment': comt, 'changes': {
                   'old': {name: []}, 'new': {name: [ip]}}})
        mock_xml = MagicMock(
            return_value=GlusterResults.v37.peer_probe.success_first_ip_from_second_first_time)
        with patch.dict('salt.modules.glusterfs.__salt__', {'cmd.run': mock_xml}):
            mock = MagicMock(side_effect=[{name: []}, {name: [ip]}])
            with patch.dict(glusterfs.__salt__, {'glusterfs.list_peers': mock}):
                self.assertDictEqual(glusterfs.peered(ip), ret)

        comt = ('Host {0} already peered'.format(ip))
        ret.update({'name': ip, 'comment': comt, 'changes': {}})
        mock_xml = MagicMock(
            return_value=GlusterResults.v37.peer_probe.success_first_ip_from_second_second_time)
        with patch.dict('salt.modules.glusterfs.__salt__', {'cmd.run': mock_xml}):
            mock = MagicMock(side_effect=[{name: [ip]}, {name: [ip]}])
            with patch.dict(glusterfs.__salt__, {'glusterfs.list_peers': mock}):
                self.assertDictEqual(glusterfs.peered(ip), ret)

        # test for invalid characters
        comt = ('Invalid characters in peer name.')
        ret.update({'name': '#badhostname', 'comment': comt, 'result': False})
        self.assertDictEqual(glusterfs.peered('#badhostname'), ret)

    # 'created' function tests: 1

    def test_created(self):
        '''
        Test to check if volume already exists
        '''
        name = 'salt'
        bricks = {'host1': '/srv/gluster/drive1',
                  'host2': '/srv/gluster/drive2'}

        ret = {'name': name,
               'result': True,
               'comment': '',
               'changes': {}}

        mock = MagicMock(side_effect=[[name], [], [], [], [name]])
        mock_lst = MagicMock(return_value=[])
        with patch.dict(glusterfs.__salt__, {'glusterfs.list_volumes': mock,
                                             'glusterfs.create': mock_lst}):
            comt = ('Volume {0} already exists.'.format(name))
            ret.update({'comment': comt})
            self.assertDictEqual(glusterfs.created(name, bricks), ret)

            with patch.dict(glusterfs.__opts__, {'test': True}):
                comt = ('Volume {0} will be created'.format(name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(glusterfs.created(name, bricks), ret)

            with patch.dict(glusterfs.__opts__, {'test': False}):
                with patch.object(salt.utils.cloud, 'check_name',
                                  MagicMock(return_value=True)):
                    comt = ('Invalid characters in volume name.')
                    ret.update({'comment': comt, 'result': False})
                    self.assertDictEqual(glusterfs.created(name, bricks), ret)

                comt = ('Host {0} already peered'.format(name))
                ret.update({'comment': [], 'result': True,
                            'changes': {'new': ['salt'], 'old': []}})
                self.assertDictEqual(glusterfs.created(name, bricks), ret)

    # 'started' function tests: 1

    def test_started(self):
        '''
        Test to check if volume has been started
        '''
        name = 'salt'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {}}

        mock = MagicMock(side_effect=[[], [name], [name], [name]])
        mock_t = MagicMock(return_value='started')
        mock_dict = MagicMock(side_effect=[{}, '', ''])
        with patch.dict(glusterfs.__salt__, {'glusterfs.list_volumes': mock,
                                             'glusterfs.status': mock_dict,
                                             'glusterfs.start_volume': mock_t}):
            comt = ('Volume {0} does not exist'.format(name))
            ret.update({'comment': comt})
            self.assertDictEqual(glusterfs.started(name), ret)

            comt = ('Volume {0} is already started'.format(name))
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(glusterfs.started(name), ret)

            with patch.dict(glusterfs.__opts__, {'test': True}):
                comt = ('Volume {0} will be started'.format(name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(glusterfs.started(name), ret)

            with patch.dict(glusterfs.__opts__, {'test': False}):
                ret.update({'comment': 'started', 'result': True,
                            'change': {'new': 'started', 'old': 'stopped'}})
                self.assertDictEqual(glusterfs.started(name), ret)

    # 'add_volume_bricks' function tests: 1

    def test_add_volume_bricks(self):
        '''
        Test to add brick(s) to an existing volume
        '''
        name = 'salt'
        bricks = {'bricks': {'host1': '/srv/gluster/drive1'}}

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {}}

        mock = MagicMock(side_effect=['does not exist', 'is not started',
                                      bricks, bricks, bricks, ''])
        mock_t = MagicMock(side_effect=['bricks successfully added',
                                        'Bricks already in volume', ''])
        with patch.dict(glusterfs.__salt__,
                        {'glusterfs.status': mock,
                         'glusterfs.add_volume_bricks': mock_t}):
            ret.update({'comment': 'does not exist'})
            self.assertDictEqual(
                glusterfs.add_volume_bricks(name, bricks), ret)

            ret.update({'comment': 'is not started'})
            self.assertDictEqual(
                glusterfs.add_volume_bricks(name, bricks), ret)

            ret.update({'comment': 'bricks successfully added', 'result': True,
                        'changes': {'new': ['host1'], 'old': ['host1']}})
            self.assertDictEqual(
                glusterfs.add_volume_bricks(name, bricks), ret)

            ret.update({'comment': 'Bricks already in volume', 'changes': {}})
            self.assertDictEqual(
                glusterfs.add_volume_bricks(name, bricks), ret)

            ret.update({'comment': '', 'result': False})
            self.assertDictEqual(
                glusterfs.add_volume_bricks(name, bricks), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(GlusterfsTestCase, needs_daemon=False)
