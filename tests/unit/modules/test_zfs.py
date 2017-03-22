# -*- coding: utf-8 -*-
'''
    :codeauthor: Nitin Madhok <nmadhok@clemson.edu>`

    tests.unit.modules.zfs_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON,
)

# Import Salt Execution module to test
import salt.modules.zfs as zfs
from salt.utils.odict import OrderedDict


# Skip this test case if we don't have access to mock!
@skipIf(NO_MOCK, NO_MOCK_REASON)
class ZfsTestCase(TestCase, LoaderModuleMockMixin):
    '''
    This class contains a set of functions that test salt.modules.zfs module
    '''
    def setup_loader_modules(self):
        return {zfs: {}}

    @patch('salt.modules.zfs._check_zfs', MagicMock(return_value='/sbin/zfs'))
    def test_exists_success(self):
        '''
        Tests successful return of exists function
        '''
        ret = {}
        ret['stdout'] = "NAME        USED  AVAIL  REFER  MOUNTPOINT\nmyzpool/mydataset    30K   157G    30K  /myzpool/mydataset"
        ret['stderr'] = ''
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertTrue(zfs.exists('myzpool/mydataset'))

    @patch('salt.modules.zfs._check_zfs', MagicMock(return_value='/sbin/zfs'))
    def test_exists_failure_not_exists(self):
        '''
        Tests unsuccessful return of exists function if dataset does not exist
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "cannot open 'myzpool/mydataset': dataset does not exist"
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertFalse(zfs.exists('myzpool/mydataset'))

    @patch('salt.modules.zfs._check_zfs', MagicMock(return_value='/sbin/zfs'))
    def test_exists_failure_invalid_name(self):
        '''
        Tests unsuccessful return of exists function if dataset name is invalid
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "cannot open 'myzpool/': invalid dataset name"
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertFalse(zfs.exists('myzpool/'))

    @patch('salt.modules.zfs._check_zfs', MagicMock(return_value='/sbin/zfs'))
    def test_create_success(self):
        '''
        Tests successful return of create function on ZFS file system creation
        '''
        res = {'myzpool/mydataset': 'created'}
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertEqual(zfs.create('myzpool/mydataset'), res)

    @patch('salt.modules.zfs._check_zfs', MagicMock(return_value='/sbin/zfs'))
    def test_create_success_with_create_parent(self):
        '''
        Tests successful return of create function when ``create_parent=True``
        '''
        res = {'myzpool/mydataset/mysubdataset': 'created'}
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertEqual(zfs.create('myzpool/mydataset/mysubdataset', create_parent=True), res)

    @patch('salt.modules.zfs._check_zfs', MagicMock(return_value='/sbin/zfs'))
    def test_create_success_with_properties(self):
        '''
        Tests successful return of create function on ZFS file system creation (with properties)
        '''
        res = {'myzpool/mydataset': 'created'}
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertEqual(
                zfs.create(
                    'myzpool/mydataset',
                    properties={
                        'mountpoint': '/export/zfs',
                        'sharenfs': 'on'
                    }
                ), res
            )

    @patch('salt.modules.zfs._check_zfs', MagicMock(return_value='/sbin/zfs'))
    def test_create_error_missing_dataset(self):
        '''
        Tests unsuccessful return of create function if dataset name is missing
        '''
        res = {'myzpool': 'cannot create \'myzpool\': missing dataset name'}
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "cannot create 'myzpool': missing dataset name"
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertEqual(zfs.create('myzpool'), res)

    @patch('salt.modules.zfs._check_zfs', MagicMock(return_value='/sbin/zfs'))
    def test_create_error_trailing_slash(self):
        '''
        Tests unsuccessful return of create function if trailing slash in name is present
        '''
        res = {'myzpool/': 'cannot create \'myzpool/\': trailing slash in name'}
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "cannot create 'myzpool/': trailing slash in name"
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertEqual(zfs.create('myzpool/'), res)

    @patch('salt.modules.zfs._check_zfs', MagicMock(return_value='/sbin/zfs'))
    def test_create_error_no_such_pool(self):
        '''
        Tests unsuccessful return of create function if the pool is not present
        '''
        res = {'myzpool/mydataset': 'cannot create \'myzpool/mydataset\': no such pool \'myzpool\''}
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "cannot create 'myzpool/mydataset': no such pool 'myzpool'"
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertEqual(zfs.create('myzpool/mydataset'), res)

    @patch('salt.modules.zfs._check_zfs', MagicMock(return_value='/sbin/zfs'))
    def test_create_error_missing_parent(self):
        '''
        Tests unsuccessful return of create function if the parent datasets do not exist
        '''
        res = {'myzpool/mydataset/mysubdataset': 'cannot create \'myzpool/mydataset/mysubdataset\': parent does not exist'}
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "cannot create 'myzpool/mydataset/mysubdataset': parent does not exist"
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertEqual(zfs.create('myzpool/mydataset/mysubdataset'), res)

    @patch('salt.modules.zfs._check_zfs', MagicMock(return_value='/sbin/zfs'))
    def test_list_success(self):
        '''
        Tests zfs list
        '''
        res = OrderedDict([('myzpool', {'avail': '79.9M', 'mountpoint': '/myzpool', 'used': '113K', 'refer': '19K'})])
        ret = {'pid': 31817, 'retcode': 0, 'stderr': '', 'stdout': 'myzpool\t113K\t79.9M\t19K\t/myzpool'}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertEqual(zfs.list_('myzpool'), res)

    @patch('salt.modules.zfs._check_zfs', MagicMock(return_value='/sbin/zfs'))
    def test_mount_success(self):
        '''
        Tests zfs mount of filesystem
        '''
        res = {'myzpool/mydataset': 'mounted'}
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertEqual(zfs.mount('myzpool/mydataset'), res)

    @patch('salt.modules.zfs._check_zfs', MagicMock(return_value='/sbin/zfs'))
    def test_mount_failure(self):
        '''
        Tests zfs mount of already mounted filesystem
        '''
        res = {'myzpool/mydataset': "cannot mount 'myzpool/mydataset': filesystem already mounted"}
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "cannot mount 'myzpool/mydataset': filesystem already mounted"
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertEqual(zfs.mount('myzpool/mydataset'), res)

    @patch('salt.modules.zfs._check_zfs', MagicMock(return_value='/sbin/zfs'))
    def test_unmount_success(self):
        '''
        Tests zfs unmount of filesystem
        '''
        res = {'myzpool/mydataset': 'unmounted'}
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertEqual(zfs.unmount('myzpool/mydataset'), res)

    @patch('salt.modules.zfs._check_zfs', MagicMock(return_value='/sbin/zfs'))
    def test_unmount_failure(self):
        '''
        Tests zfs unmount of already mounted filesystem
        '''
        res = {'myzpool/mydataset': "cannot mount 'myzpool/mydataset': not currently mounted"}
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "cannot mount 'myzpool/mydataset': not currently mounted"
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertEqual(zfs.unmount('myzpool/mydataset'), res)

    @patch('salt.modules.zfs._check_zfs', MagicMock(return_value='/sbin/zfs'))
    def test_inherit_success(self):
        '''
        Tests zfs inherit of compression property
        '''
        res = {'myzpool/mydataset': {'compression': 'cleared'}}
        ret = {'pid': 45193, 'retcode': 0, 'stderr': '', 'stdout': ''}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertEqual(zfs.inherit('compression', 'myzpool/mydataset'), res)

    @patch('salt.modules.zfs._check_zfs', MagicMock(return_value='/sbin/zfs'))
    def test_inherit_failure(self):
        '''
        Tests zfs inherit of canmount
        '''
        res = {
            'myzpool/mydataset': {
                'canmount': "'canmount' property cannot be inherited, use revert=True to try and reset it to it's default value."
            }
        }
        ret = {'pid': 43898, 'retcode': 1, 'stderr': "'canmount' property cannot be inherited", 'stdout': ''}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertEqual(zfs.inherit('canmount', 'myzpool/mydataset'), res)

    @patch('salt.modules.zfs._check_zfs', MagicMock(return_value='/sbin/zfs'))
    def test_diff(self):
        '''
        Tests zfs diff
        '''
        res = ['M\t/\t/myzpool/mydataset/', '+\tF\t/myzpool/mydataset/hello']
        ret = {'pid': 51495, 'retcode': 0, 'stderr': '', 'stdout': 'M\t/\t/myzpool/mydataset/\n+\tF\t/myzpool/mydataset/hello'}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertEqual(zfs.diff('myzpool/mydataset@yesterday', 'myzpool/mydataset'), res)

    @patch('salt.modules.zfs._check_zfs', MagicMock(return_value='/sbin/zfs'))
    def test_rollback_success(self):
        '''
        Tests zfs rollback success
        '''
        res = {'myzpool/mydataset': 'rolledback to snapshot: yesterday'}
        ret = {'pid': 56502, 'retcode': 0, 'stderr': '', 'stdout': ''}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertEqual(zfs.rollback('myzpool/mydataset@yesterday'), res)

    @patch('salt.modules.zfs._check_zfs', MagicMock(return_value='/sbin/zfs'))
    def test_rollback_failure(self):
        '''
        Tests zfs rollback failure
        '''
        res = {'myzpool/mydataset': "cannot rollback to 'myzpool/mydataset@yesterday': more recent snapshots or bookmarks exist\nuse '-r' to force deletion of the following snapshots and bookmarks:\nmyzpool/mydataset@today"}
        ret = {
            'pid': 57471,
            'retcode': 1,
            'stderr': "cannot rollback to 'myzpool/mydataset@yesterday': more recent snapshots or bookmarks exist\nuse '-r' to force deletion of the following snapshots and bookmarks:\nmyzpool/mydataset@today",
            'stdout': ''
        }
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertEqual(zfs.rollback('myzpool/mydataset@yesterday'), res)

    @patch('salt.modules.zfs._check_zfs', MagicMock(return_value='/sbin/zfs'))
    def test_clone_success(self):
        '''
        Tests zfs clone success
        '''
        res = {'myzpool/yesterday': 'cloned from myzpool/mydataset@yesterday'}
        ret = {'pid': 64532, 'retcode': 0, 'stderr': '', 'stdout': ''}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertEqual(zfs.clone('myzpool/mydataset@yesterday', 'myzpool/yesterday'), res)

    @patch('salt.modules.zfs._check_zfs', MagicMock(return_value='/sbin/zfs'))
    def test_clone_failure(self):
        '''
        Tests zfs clone failure
        '''
        res = {'myzpool/archive/yesterday': "cannot create 'myzpool/archive/yesterday': parent does not exist"}
        ret = {'pid': 64864, 'retcode': 1, 'stderr': "cannot create 'myzpool/archive/yesterday': parent does not exist", 'stdout': ''}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertEqual(zfs.clone('myzpool/mydataset@yesterday', 'myzpool/archive/yesterday'), res)

    @patch('salt.modules.zfs._check_zfs', MagicMock(return_value='/sbin/zfs'))
    def test_promote_success(self):
        '''
        Tests zfs promote success
        '''
        res = {'myzpool/yesterday': 'promoted'}
        ret = {'pid': 69075, 'retcode': 0, 'stderr': '', 'stdout': ''}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertEqual(zfs.promote('myzpool/yesterday'), res)

    @patch('salt.modules.zfs._check_zfs', MagicMock(return_value='/sbin/zfs'))
    def test_promote_failure(self):
        '''
        Tests zfs promote failure
        '''
        res = {'myzpool/yesterday': "cannot promote 'myzpool/yesterday': not a cloned filesystem"}
        ret = {'pid': 69209, 'retcode': 1, 'stderr': "cannot promote 'myzpool/yesterday': not a cloned filesystem", 'stdout': ''}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertEqual(zfs.promote('myzpool/yesterday'), res)

    @patch('salt.modules.zfs._check_zfs', MagicMock(return_value='/sbin/zfs'))
    @patch('salt.utils.which', MagicMock(return_value='/usr/bin/man'))
    def test_bookmark_success(self):
        '''
        Tests zfs bookmark success
        '''
        res = {'myzpool/mydataset@yesterday': 'bookmarked as myzpool/mydataset#important'}
        ret = {'pid': 20990, 'retcode': 0, 'stderr': '', 'stdout': ''}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertEqual(zfs.bookmark('myzpool/mydataset@yesterday', 'myzpool/mydataset#important'), res)

    @patch('salt.modules.zfs._check_zfs', MagicMock(return_value='/sbin/zfs'))
    def test_holds_success(self):
        '''
        Tests zfs holds success
        '''
        res = {'myzpool/mydataset@baseline': {'important  ': 'Wed Dec 23 21:06 2015', 'release-1.0': 'Wed Dec 23 21:08 2015'}}
        ret = {'pid': 40216, 'retcode': 0, 'stderr': '', 'stdout': 'myzpool/mydataset@baseline\timportant  \tWed Dec 23 21:06 2015\nmyzpool/mydataset@baseline\trelease-1.0\tWed Dec 23 21:08 2015'}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertEqual(zfs.holds('myzpool/mydataset@baseline'), res)

    @patch('salt.modules.zfs._check_zfs', MagicMock(return_value='/sbin/zfs'))
    def test_holds_failure(self):
        '''
        Tests zfs holds failure
        '''
        res = {'myzpool/mydataset@baseline': "cannot open 'myzpool/mydataset@baseline': dataset does not exist"}
        ret = {'pid': 40993, 'retcode': 1, 'stderr': "cannot open 'myzpool/mydataset@baseline': dataset does not exist", 'stdout': 'no datasets available'}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertEqual(zfs.holds('myzpool/mydataset@baseline'), res)

    @patch('salt.modules.zfs._check_zfs', MagicMock(return_value='/sbin/zfs'))
    def test_hold_success(self):
        '''
        Tests zfs hold success
        '''
        res = {'myzpool/mydataset@baseline': {'important': 'held'}, 'myzpool/mydataset@release-1.0': {'important': 'held'}}
        ret = {'pid': 50876, 'retcode': 0, 'stderr': '', 'stdout': ''}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertEqual(zfs.hold('important', 'myzpool/mydataset@baseline', 'myzpool/mydataset@release-1.0'), res)

    @patch('salt.modules.zfs._check_zfs', MagicMock(return_value='/sbin/zfs'))
    def test_hold_failure(self):
        '''
        Tests zfs hold failure
        '''
        res = {'myzpool/mydataset@baseline': {'important': 'tag already exists on this dataset'}}
        ret = {'pid': 51006, 'retcode': 1, 'stderr': "cannot hold snapshot 'myzpool/mydataset@baseline': tag already exists on this dataset", 'stdout': ''}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertEqual(zfs.hold('important', 'myzpool/mydataset@baseline'), res)

    @patch('salt.modules.zfs._check_zfs', MagicMock(return_value='/sbin/zfs'))
    def test_release_success(self):
        '''
        Tests zfs release success
        '''
        res = {'myzpool/mydataset@baseline': {'important': 'released'}, 'myzpool/mydataset@release-1.0': {'important': 'released'}}
        ret = {'pid': 50876, 'retcode': 0, 'stderr': '', 'stdout': ''}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertEqual(zfs.release('important', 'myzpool/mydataset@baseline', 'myzpool/mydataset@release-1.0'), res)

    @patch('salt.modules.zfs._check_zfs', MagicMock(return_value='/sbin/zfs'))
    def test_release_failure(self):
        '''
        Tests zfs release failure
        '''
        res = {'myzpool/mydataset@baseline': {'important': 'no such tag on this dataset'}}
        ret = {'pid': 51006, 'retcode': 1, 'stderr': "cannot release hold from snapshot 'myzpool/mydataset@baseline': no such tag on this dataset", 'stdout': ''}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertEqual(zfs.release('important', 'myzpool/mydataset@baseline'), res)

    @patch('salt.modules.zfs._check_zfs', MagicMock(return_value='/sbin/zfs'))
    def test_snapshot_success(self):
        '''
        Tests zfs snapshot success
        '''
        res = {'myzpool/mydataset@baseline': 'snapshotted'}
        ret = {'pid': 69125, 'retcode': 0, 'stderr': '', 'stdout': ''}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertEqual(zfs.snapshot('myzpool/mydataset@baseline'), res)

    @patch('salt.modules.zfs._check_zfs', MagicMock(return_value='/sbin/zfs'))
    def test_snapshot_failure(self):
        '''
        Tests zfs snapshot failure
        '''
        res = {'myzpool/mydataset@baseline': 'dataset already exists'}
        ret = {'pid': 68526, 'retcode': 1, 'stderr': "cannot create snapshot 'myzpool/mydataset@baseline': dataset already exists", 'stdout': ''}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertEqual(zfs.snapshot('myzpool/mydataset@baseline'), res)

    @patch('salt.modules.zfs._check_zfs', MagicMock(return_value='/sbin/zfs'))
    def test_snapshot_failure2(self):
        '''
        Tests zfs snapshot failure
        '''
        res = {'myzpool/mydataset@baseline': 'dataset does not exist'}
        ret = {'pid': 69256, 'retcode': 2, 'stderr': "cannot open 'myzpool/mydataset': dataset does not exist\nusage:\n\tsnapshot [-r] [-o property=value] ... <filesystem|volume>@<snap> ...\n\nFor the property list, run: zfs set|get\n\nFor the delegated permission list, run: zfs allow|unallow", 'stdout': ''}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertEqual(zfs.snapshot('myzpool/mydataset@baseline'), res)

    @patch('salt.modules.zfs._check_zfs', MagicMock(return_value='/sbin/zfs'))
    def test_set_success(self):
        '''
        Tests zfs set success
        '''
        res = {'myzpool/mydataset': {'compression': 'set'}}
        ret = {'pid': 79736, 'retcode': 0, 'stderr': '', 'stdout': ''}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertEqual(zfs.set('myzpool/mydataset', compression='lz4'), res)

    @patch('salt.modules.zfs._check_zfs', MagicMock(return_value='/sbin/zfs'))
    def test_set_failure(self):
        '''
        Tests zfs set failure
        '''
        res = {'myzpool/mydataset': {'canmount': "'canmount' must be one of 'on | off | noauto'"}}
        ret = {'pid': 79887, 'retcode': 1, 'stderr': "cannot set property for 'myzpool/mydataset': 'canmount' must be one of 'on | off | noauto'", 'stdout': ''}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertEqual(zfs.set('myzpool/mydataset', canmount='lz4'), res)

    @patch('salt.modules.zfs._check_zfs', MagicMock(return_value='/sbin/zfs'))
    def test_get_success(self):
        '''
        Tests zfs get success
        '''
        res = OrderedDict([('myzpool', {'compression': {'value': 'off'}})])
        ret = {'pid': 562, 'retcode': 0, 'stderr': '', 'stdout': 'myzpool\tcompression\toff'}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertEqual(zfs.get('myzpool', properties='compression', fields='value'), res)
