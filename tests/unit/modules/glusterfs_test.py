# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
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

# Globals
glusterfs.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class GitTestCase(TestCase):
    '''
    Test cases for salt.modules.glusterfs
    '''
    # 'list_peers' function tests: 1

    def test_list_peers(self):
        '''
        Test if it return a list of gluster peers
        '''
        mock = MagicMock(return_value='')
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertListEqual(glusterfs.list_peers(), [])

        mock = MagicMock(return_value='No peers present')
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertIsNone(glusterfs.list_peers())

    # 'peer' function tests: 1

    def test_peer(self):
        '''
        Test if it add another node into the peer list.
        '''
        mock = MagicMock(return_value='')
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertEqual(glusterfs.peer('salt'), '')

        mock = MagicMock(return_value=True)
        with patch.object(suc, 'check_name', mock):
            self.assertEqual(glusterfs.peer('a'),
                             'Invalid characters in peer name')

    # 'create' function tests: 1

    def test_create(self):
        '''
        Test if it create a glusterfs volume.
        '''
        mock = MagicMock(return_value='')
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertEqual(glusterfs.create('newvolume', 'host1:brick'),
                             'Error: Brick paths must start with /')

        mock = MagicMock(return_value='')
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertEqual(glusterfs.create('newvolume', 'host1/brick'),
                             'Error: Brick syntax is <peer>:<path>')

        mock = MagicMock(return_value='creation success')
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertEqual(glusterfs.create('newvolume', 'host1:/brick',
                                              True, True, True, 'tcp', True),
                             'Volume newvolume created and started')

        mock = MagicMock(return_value='')
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertEqual(glusterfs.create('newvolume', 'host1:/brick',
                                              True, True, True,
                                              'tcp', True), '')

        mock = MagicMock(return_value='')
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertEqual(glusterfs.create('newvolume', 'host1:/brick'),
                             'Volume newvolume created. Start volume to use')

    # 'list_volumes' function tests: 1

    def test_list_volumes(self):
        '''
        Test if it list configured volumes
        '''
        mock = MagicMock(return_value='No volumes present in cluster')
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertListEqual(glusterfs.list_volumes(), [])

        mock = MagicMock(return_value='Newvolume1\nNewvolume2')
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertListEqual(glusterfs.list_volumes(),
                                 ['Newvolume1', 'Newvolume2'])

    # 'status' function tests: 1

    def test_status(self):
        '''
        Test if it check the status of a gluster volume.
        '''
        mock = MagicMock(return_value='No volumes present in cluster')
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertDictEqual(glusterfs.status('myvolume'),
                                 {'bricks': {}, 'healers': {}, 'nfs': {}})

        mock = MagicMock(return_value='does not exist\n')
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertEqual(glusterfs.status('myvolume'), 'does not exist')

        mock = MagicMock(return_value='is not started')
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertEqual(glusterfs.status('myvolume'), 'is not started')

    # 'start_volume' function tests: 1

    def test_start_volume(self):
        '''
        Test if it start a gluster volume.
        '''
        mock = MagicMock(return_value=['Newvolume1', 'Newvolume2'])
        with patch.object(glusterfs, 'list_volumes', mock):
            mock = MagicMock(return_value='creation success')
            with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
                self.assertEqual(glusterfs.start_volume('Newvolume1'),
                                 'Volume already started')

            mock = MagicMock(side_effect=['does not exist',
                                          'creation success'])
            with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
                self.assertEqual(glusterfs.start_volume('Newvolume1'),
                                 'Volume Newvolume1 started')

            mock = MagicMock(return_value='does not exist')
            with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
                self.assertEqual(glusterfs.start_volume('Newvolume1'),
                                 'does not exist')

        mock = MagicMock(return_value='No volumes present in cluster')
        with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
            self.assertEqual(glusterfs.start_volume('mycluster'),
                             'Volume does not exist')

    # 'stop_volume' function tests: 1

    def test_stop_volume(self):
        '''
        Test if it stop a gluster volume.
        '''
        mock = MagicMock(return_value={})
        with patch.object(glusterfs, 'status', mock):
            mock = MagicMock(return_value='creation success')
            with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
                self.assertEqual(glusterfs.stop_volume('Newvolume1'),
                                 'Volume Newvolume1 stopped')

            mock = MagicMock(return_value='No volume exist')
            with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
                self.assertEqual(glusterfs.stop_volume('Newvolume1'),
                                 'No volume exist')

        mock = MagicMock(return_value='')
        with patch.object(glusterfs, 'status', mock):
            self.assertEqual(glusterfs.stop_volume('Newvolume1'), '')

    # 'delete' function tests: 1

    def test_delete(self):
        '''
        Test if it deletes a gluster volume.
        '''
        ret = 'Error: Volume must be stopped before deletion'
        mock = MagicMock(return_value=['Newvolume1', 'Newvolume2'])
        with patch.object(glusterfs, 'list_volumes', mock):
            self.assertEqual(glusterfs.delete('Newvolume3'),
                             'Volume does not exist')

            mock = MagicMock(return_value='creation success')
            with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
                self.assertEqual(glusterfs.delete('Newvolume1', False), ret)

            mock = MagicMock(return_value='creation success')
            with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
                self.assertEqual(glusterfs.delete('Newvolume1'),
                                 'Volume Newvolume1 stopped and deleted')

            mock = MagicMock(return_value='')
            with patch.object(glusterfs, 'status', mock):
                mock = MagicMock(return_value='creation success')
                with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
                    self.assertEqual(glusterfs.delete('Newvolume1'),
                                     'Volume Newvolume1 deleted')

            mock = MagicMock(return_value='does not exist')
            with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
                self.assertEqual(glusterfs.delete('Newvolume1'),
                                 'does not exist')

    # 'add_volume_bricks' function tests: 1

    def test_add_volume_bricks(self):
        '''
        Test if it add brick(s) to an existing volume
        '''
        mock = MagicMock(return_value='does not exist')
        with patch.object(glusterfs, 'status', mock):
            self.assertEqual(glusterfs.add_volume_bricks('Newvolume1',
                                                         ['bricks']),
                             'does not exist')

        mock = MagicMock(return_value='is not started')
        with patch.object(glusterfs, 'status', mock):
            self.assertEqual(glusterfs.add_volume_bricks('Newvolume1',
                                                         ['bricks']),
                             'is not started')

        ret = '1 bricks successfully added to the volume Newvolume1'
        mock = MagicMock(return_value={'bricks': {}, 'healers': {}, 'nfs': {}})
        with patch.object(glusterfs, 'status', mock):
            mock = MagicMock(return_value='creation success')
            with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
                self.assertEqual(glusterfs.add_volume_bricks('Newvolume1',
                                                             ['bricks']), ret)

            mock = MagicMock(return_value='')
            with patch.dict(glusterfs.__salt__, {'cmd.run': mock}):
                self.assertEqual(glusterfs.add_volume_bricks('Newvolume1',
                                                             ['bricks']), '')

                self.assertEqual(glusterfs.add_volume_bricks('Newvolume1', []),
                                 'Bricks already in volume Newvolume1')


if __name__ == '__main__':
    from integration import run_tests
    run_tests(GitTestCase, needs_daemon=False)
