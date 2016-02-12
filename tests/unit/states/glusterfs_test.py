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
import salt.utils.cloud
import socket

glusterfs.__salt__ = {}
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
        name = 'salt'

        ret = {'name': name,
               'result': True,
               'comment': '',
               'changes': {}}

        mock = MagicMock(side_effect=[[name], [''], [], [], [], [], [], [],
                                      [name]])
        mock_lst = MagicMock(return_value=[])
        with patch.dict(glusterfs.__salt__, {'glusterfs.list_peers': mock,
                                             'glusterfs.peer': mock_lst}):
            comt = ('Host {0} already peered'.format(name))
            ret.update({'comment': comt})
            self.assertDictEqual(glusterfs.peered(name), ret)

            with patch.dict(glusterfs.__opts__, {'test': True}):
                comt = ('Peer {0} will be added.'.format(name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(glusterfs.peered(name), ret)

            with patch.object(salt.utils.cloud, 'check_name',
                              MagicMock(return_value=True)):
                comt = ('Invalid characters in peer name.')
                ret.update({'comment': comt, 'result': False})
                self.assertDictEqual(glusterfs.peered(name), ret)

            with patch.object(socket, 'gethostname',
                              MagicMock(side_effect=[name, 'salt.host',
                                                     'salt.host'])):
                ret.update({'comment': '', 'result': True})
                self.assertDictEqual(glusterfs.peered(name), ret)

                comt = ('Host {0} already peered'.format(name))
                ret.update({'comment': '', 'result': True})
                self.assertDictEqual(glusterfs.peered(name), ret)

            comt = ('Host {0} already peered'.format(name))
            ret.update({'comment': '', 'result': True,
                        'changes': {'new': ['salt'], 'old': []}})
            self.assertDictEqual(glusterfs.peered(name), ret)

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
            self.assertDictEqual(glusterfs.add_volume_bricks(name, bricks), ret)

            ret.update({'comment': 'is not started'})
            self.assertDictEqual(glusterfs.add_volume_bricks(name, bricks), ret)

            ret.update({'comment': 'bricks successfully added', 'result': True,
                        'changes': {'new': ['host1'], 'old': ['host1']}})
            self.assertDictEqual(glusterfs.add_volume_bricks(name, bricks), ret)

            ret.update({'comment': 'Bricks already in volume', 'changes': {}})
            self.assertDictEqual(glusterfs.add_volume_bricks(name, bricks), ret)

            ret.update({'comment': '', 'result': False})
            self.assertDictEqual(glusterfs.add_volume_bricks(name, bricks), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(GlusterfsTestCase, needs_daemon=False)
