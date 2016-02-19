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
from salt.states import mount
import os

mount.__salt__ = {}
mount.__opts__ = {}
mount.__grains__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MountTestCase(TestCase):
    '''
    Test cases for salt.states.mount
    '''
    # 'mounted' function tests: 1

    def test_mounted(self):
        '''
        Test to verify that a device is mounted.
        '''
        name = '/mnt/sdb'
        device = '/dev/sdb5'
        fstype = 'xfs'

        name2 = '/mnt/cifs'
        device2 = '//SERVER/SHARE/'
        fstype2 = 'cifs'
        opts2 = ['noowners']
        superopts2 = ['uid=510', 'gid=100', 'username=cifsuser',
                      'domain=cifsdomain']

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {}}

        mock = MagicMock(side_effect=['new', 'present', 'new', 'change',
                                      'bad config', 'salt', 'present'])
        mock_t = MagicMock(return_value=True)
        mock_f = MagicMock(return_value=False)
        mock_ret = MagicMock(return_value={'retcode': 1})
        mock_mnt = MagicMock(return_value={name: {'device': device, 'opts': [],
                                                  'superopts': []},
                                           name2: {'device': device2, 'opts': opts2,
                                                   'superopts': superopts2}})
        mock_emt = MagicMock(return_value={})
        mock_str = MagicMock(return_value='salt')
        mock_user = MagicMock(return_value={'uid': 510})
        mock_group = MagicMock(return_value={'gid': 100})
        umount1 = ("Forced unmount because devices don't match. "
                   "Wanted: /dev/sdb6, current: /dev/sdb5, /dev/sdb5")
        with patch.dict(mount.__grains__, {'os': 'Darwin'}):
            with patch.dict(mount.__salt__, {'mount.active': mock_mnt,
                                             'cmd.run_all': mock_ret,
                                             'mount.umount': mock_f}):
                comt = ('Unable to find device with label /dev/sdb5.')
                ret.update({'comment': comt})
                self.assertDictEqual(mount.mounted(name, 'LABEL=/dev/sdb5',
                                                   fstype), ret)

                with patch.dict(mount.__opts__, {'test': True}):
                    comt = ('Remount would be forced because'
                            ' options (noowners) changed')
                    ret.update({'comment': comt, 'result': None})
                    self.assertDictEqual(mount.mounted(name, device, fstype),
                                         ret)

                with patch.dict(mount.__opts__, {'test': False}):
                    comt = ('Unable to unmount /mnt/sdb: False.')
                    umount = ('Forced unmount and mount because'
                              ' options (noowners) changed')
                    ret.update({'comment': comt, 'result': False,
                                'changes': {'umount': umount}})
                    self.assertDictEqual(mount.mounted(name, device, 'nfs'),
                                         ret)

                    comt = ('Unable to unmount')
                    ret.update({'comment': comt, 'result': None,
                                'changes': {'umount': umount1}})
                    self.assertDictEqual(mount.mounted(name, '/dev/sdb6',
                                                       fstype, opts=[]), ret)

                with patch.dict(mount.__salt__, {'mount.active': mock_emt,
                                                 'mount.mount': mock_str,
                                                 'mount.set_automaster': mock}):
                    with patch.dict(mount.__opts__, {'test': True}):
                        comt = ('{0} does not exist and would not be created'.format(name))
                        ret.update({'comment': comt, 'changes': {}})
                        self.assertDictEqual(mount.mounted(name, device,
                                                           fstype), ret)

                    with patch.dict(mount.__opts__, {'test': False}):
                        with patch.object(os.path, 'exists', mock_f):
                            comt = ('Mount directory is not present')
                            ret.update({'comment': comt, 'result': False})
                            self.assertDictEqual(mount.mounted(name, device,
                                                               fstype), ret)

                        with patch.object(os.path, 'exists', mock_t):
                            comt = ('Mount directory is not present')
                            ret.update({'comment': 'salt', 'result': False})
                            self.assertDictEqual(mount.mounted(name, device,
                                                               fstype), ret)

                    with patch.dict(mount.__opts__, {'test': True}):
                        comt = ('{0} does not exist and would neither be created nor mounted. '
                                '{0} needs to be written to the fstab in order to be made persistent.'.format(name))
                        ret.update({'comment': comt, 'result': None})
                        self.assertDictEqual(mount.mounted(name, device, fstype,
                                                           mount=False), ret)

                    with patch.dict(mount.__opts__, {'test': False}):
                        comt = ('{0} not present and not mounted. '
                                'Entry already exists in the fstab.'.format(name))
                        ret.update({'comment': comt, 'result': True})
                        self.assertDictEqual(mount.mounted(name, device, fstype,
                                                           mount=False), ret)

                        comt = ('{0} not present and not mounted. '
                                'Added new entry to the fstab.'.format(name))
                        ret.update({'comment': comt, 'result': True,
                                    'changes': {'persist': 'new'}})
                        self.assertDictEqual(mount.mounted(name, device, fstype,
                                                           mount=False), ret)

                        comt = ('{0} not present and not mounted. '
                                'Updated the entry in the fstab.'.format(name))
                        ret.update({'comment': comt, 'result': True,
                                    'changes': {'persist': 'update'}})
                        self.assertDictEqual(mount.mounted(name, device, fstype,
                                                           mount=False), ret)

                        comt = ('{0} not present and not mounted. '
                                'However, the fstab was not found.'.format(name))
                        ret.update({'comment': comt, 'result': False,
                                    'changes': {}})
                        self.assertDictEqual(mount.mounted(name, device, fstype,
                                                           mount=False), ret)

                        comt = ('{0} not present and not mounted'.format(name))
                        ret.update({'comment': comt, 'result': True,
                                    'changes': {}})
                        self.assertDictEqual(mount.mounted(name, device, fstype,
                                                           mount=False), ret)

        # Test no change for uid provided as a name #25293
        with patch.dict(mount.__grains__, {'os': 'CentOS'}):
            with patch.dict(mount.__salt__, {'mount.active': mock_mnt,
                                             'mount.mount': mock_str,
                                             'mount.umount': mock_f,
                                             'mount.set_fstab': mock,
                                             'user.info': mock_user,
                                             'group.info': mock_group}):
                with patch.dict(mount.__opts__, {'test': True}):
                    with patch.object(os.path, 'exists', mock_t):
                        comt = 'Target was already mounted. ' + \
                               'Entry already exists in the fstab.'
                        ret.update({'name': name2, 'result': True})
                        ret.update({'comment': comt, 'changes': {}})
                        self.assertDictEqual(mount.mounted(name2, device2,
                                                           fstype2,
                                                           opts=['uid=user1',
                                                                 'gid=group1']),
                                             ret)

    # 'swap' function tests: 1

    def test_swap(self):
        '''
        Test to activates a swap device.
        '''
        name = '/mnt/sdb'

        ret = {'name': name,
               'result': None,
               'comment': '',
               'changes': {}}

        mock = MagicMock(side_effect=['present', 'new', 'change', 'bad config'])
        mock_f = MagicMock(return_value=False)
        mock_swp = MagicMock(return_value=[name])
        mock_fs = MagicMock(return_value={'none': {'device': name,
                                                   'fstype': 'xfs'}})
        mock_emt = MagicMock(return_value={})
        with patch.dict(mount.__salt__, {'mount.swaps': mock_swp,
                                         'mount.fstab': mock_fs,
                                         'file.is_link': mock_f}):
            with patch.dict(mount.__opts__, {'test': True}):
                comt = ('Swap {0} is set to be added to the '
                        'fstab and to be activated'.format(name))
                ret.update({'comment': comt})
                self.assertDictEqual(mount.swap(name), ret)

            with patch.dict(mount.__opts__, {'test': False}):
                comt = ('Swap {0} already active'.format(name))
                ret.update({'comment': comt, 'result': True})
                self.assertDictEqual(mount.swap(name), ret)

                with patch.dict(mount.__salt__, {'mount.fstab': mock_emt,
                                                 'mount.set_fstab': mock}):
                    comt = ('Swap {0} already active'.format(name))
                    ret.update({'comment': comt, 'result': True})
                    self.assertDictEqual(mount.swap(name), ret)

                    comt = ('Swap /mnt/sdb already active. '
                            'Added new entry to the fstab.')
                    ret.update({'comment': comt, 'result': True,
                                'changes': {'persist': 'new'}})
                    self.assertDictEqual(mount.swap(name), ret)

                    comt = ('Swap /mnt/sdb already active. '
                            'Updated the entry in the fstab.')
                    ret.update({'comment': comt, 'result': True,
                                'changes': {'persist': 'update'}})
                    self.assertDictEqual(mount.swap(name), ret)

                    comt = ('Swap /mnt/sdb already active. '
                            'However, the fstab was not found.')
                    ret.update({'comment': comt, 'result': False,
                                'changes': {}})
                    self.assertDictEqual(mount.swap(name), ret)

    # 'unmounted' function tests: 1

    def test_unmounted(self):
        '''
        Test to verify that a device is not mounted
        '''
        name = '/mnt/sdb'
        device = '/dev/sdb5'

        ret = {'name': name,
               'result': None,
               'comment': '',
               'changes': {}}

        mock_f = MagicMock(return_value=False)
        mock_dev = MagicMock(return_value={name: {'device': device}})
        mock_fs = MagicMock(return_value={name: {'device': name}})
        mock_mnt = MagicMock(side_effect=[{name: {}}, {}, {}, {}])
        comt3 = ('Mount point /mnt/sdb is unmounted but needs to be purged '
                 'from /etc/auto_salt to be made persistent')
        with patch.dict(mount.__grains__, {'os': 'Darwin'}):
            with patch.dict(mount.__salt__, {'mount.active': mock_mnt,
                                             'mount.automaster': mock_fs,
                                             'file.is_link': mock_f}):
                with patch.dict(mount.__opts__, {'test': True}):
                    comt = ('Mount point {0} is mounted but should not '
                            'be'.format(name))
                    ret.update({'comment': comt})
                    self.assertDictEqual(mount.unmounted(name, device), ret)

                    comt = ('Target was already unmounted. '
                            'fstab entry for device /dev/sdb5 not found')
                    ret.update({'comment': comt, 'result': True})
                    self.assertDictEqual(mount.unmounted(name, device,
                                                         persist=True), ret)

                    with patch.dict(mount.__salt__,
                                    {'mount.automaster': mock_dev}):
                        ret.update({'comment': comt3, 'result': None})
                        self.assertDictEqual(mount.unmounted(name, device,
                                                             persist=True), ret)

                    comt = ('Target was already unmounted')
                    ret.update({'comment': comt, 'result': True})
                    self.assertDictEqual(mount.unmounted(name, device), ret)

    # 'mod_watch' function tests: 1

    def test_mod_watch(self):
        '''
        Test the mounted watcher, called to invoke the watch command.
        '''
        name = '/mnt/sdb'

        ret = {'name': name,
               'result': True,
               'comment': '',
               'changes': {}}

        comt = ('Watch not supported in unmount at this time')
        ret.update({'comment': comt})
        self.assertDictEqual(mount.mod_watch(name, sfun='unmount'), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MountTestCase, needs_daemon=False)
