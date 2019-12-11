# -*- coding: utf-8 -*-
'''
Tests for salt.modules.zfs

:codeauthor:    Nitin Madhok <nmadhok@clemson.edu>, Jorge Schrauwen <sjorge@blackdot.be>
:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:depends:       salt.utils.zfs
:platform:      illumos,freebsd,linux
'''

# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Testing libs
from tests.support.zfs import ZFSMockData
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON,
)

# Import Salt Execution module to test
import salt.utils.zfs
import salt.modules.zfs as zfs

# Import Salt Utils
import salt.loader
from salt.utils.odict import OrderedDict
from salt.utils.dateutils import strftime


# Skip this test case if we don't have access to mock!
@skipIf(NO_MOCK, NO_MOCK_REASON)
class ZfsTestCase(TestCase, LoaderModuleMockMixin):
    '''
    This class contains a set of functions that test salt.modules.zfs module
    '''
    def setup_loader_modules(self):
        self.opts = opts = salt.config.DEFAULT_MINION_OPTS.copy()
        self.utils_patch = ZFSMockData().get_patched_utils()
        for key in ('opts', 'utils_patch'):
            self.addCleanup(delattr, self, key)

        utils = salt.loader.utils(
            opts,
            whitelist=['zfs', 'args', 'systemd', 'path', 'platform'])
        zfs_obj = {
            zfs: {
                '__opts__': opts,
                '__utils__': utils,
            }
        }

        return zfs_obj

    def test_exists_success(self):
        '''
        Tests successful return of exists function
        '''
        ret = {}
        ret['stdout'] = "NAME        USED  AVAIL  REFER  MOUNTPOINT\nmyzpool/mydataset    30K   157G    30K  /myzpool/mydataset"
        ret['stderr'] = ''
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertTrue(zfs.exists('myzpool/mydataset'))

    def test_exists_failure_not_exists(self):
        '''
        Tests unsuccessful return of exists function if dataset does not exist
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "cannot open 'myzpool/mydataset': dataset does not exist"
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertFalse(zfs.exists('myzpool/mydataset'))

    def test_exists_failure_invalid_name(self):
        '''
        Tests unsuccessful return of exists function if dataset name is invalid
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "cannot open 'myzpool/': invalid dataset name"
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertFalse(zfs.exists('myzpool/'))

    def test_create_success(self):
        '''
        Tests successful return of create function on ZFS file system creation
        '''
        res = OrderedDict([('created', True)])
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.create('myzpool/mydataset'))

    def test_create_success_with_create_parent(self):
        '''
        Tests successful return of create function when ``create_parent=True``
        '''
        res = OrderedDict([('created', True)])
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.create('myzpool/mydataset/mysubdataset', create_parent=True))

    def test_create_success_with_properties(self):
        '''
        Tests successful return of create function on ZFS file system creation (with properties)
        '''
        res = OrderedDict([('created', True)])
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(
                res,
                zfs.create(
                    'myzpool/mydataset',
                    properties={
                        'mountpoint': '/export/zfs',
                        'sharenfs': 'on'
                    }
                ),
            )

    def test_create_error_missing_dataset(self):
        '''
        Tests unsuccessful return of create function if dataset name is missing
        '''
        res = OrderedDict([
            ('created', False),
            ('error', "cannot create 'myzpool': missing dataset name"),
        ])
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "cannot create 'myzpool': missing dataset name"
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.create('myzpool'))

    def test_create_error_trailing_slash(self):
        '''
        Tests unsuccessful return of create function if trailing slash in name is present
        '''
        res = OrderedDict([
            ('created', False),
            ('error', "cannot create 'myzpool/': trailing slash in name"),
        ])
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "cannot create 'myzpool/': trailing slash in name"
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.create('myzpool/'))

    def test_create_error_no_such_pool(self):
        '''
        Tests unsuccessful return of create function if the pool is not present
        '''
        res = OrderedDict([
            ('created', False),
            ('error', "cannot create 'myzpool/mydataset': no such pool 'myzpool'"),
        ])
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "cannot create 'myzpool/mydataset': no such pool 'myzpool'"
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.create('myzpool/mydataset'))

    def test_create_error_missing_parent(self):
        '''
        Tests unsuccessful return of create function if the parent datasets do not exist
        '''
        res = OrderedDict([
            ('created', False),
            ('error', "cannot create 'myzpool/mydataset/mysubdataset': parent does not exist"),
        ])
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "cannot create 'myzpool/mydataset/mysubdataset': parent does not exist"
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.create('myzpool/mydataset/mysubdataset'))

    def test_destroy_success(self):
        '''
        Tests successful return of destroy function on ZFS file system destruction
        '''
        res = OrderedDict([('destroyed', True)])
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.destroy('myzpool/mydataset'))

    def test_destroy_error_not_exists(self):
        '''
        Tests failure return of destroy function on ZFS file system destruction
        '''
        res = OrderedDict([
            ('destroyed', False),
            ('error', "cannot open 'myzpool/mydataset': dataset does not exist"),
        ])
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "cannot open 'myzpool/mydataset': dataset does not exist"
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.destroy('myzpool/mydataset'))

    def test_destroy_error_has_children(self):
        '''
        Tests failure return of destroy function on ZFS file system destruction
        '''
        res = OrderedDict([
            ('destroyed', False),
            ('error', "\n".join([
                "cannot destroy 'myzpool/mydataset': filesystem has children",
                "use 'recursive=True' to destroy the following datasets:",
                "myzpool/mydataset@snapshot",
            ])),
        ])
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "\n".join([
            "cannot destroy 'myzpool/mydataset': filesystem has children",
            "use '-r' to destroy the following datasets:",
            "myzpool/mydataset@snapshot",
        ])
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.destroy('myzpool/mydataset'))

    def test_rename_success(self):
        '''
        Tests successful return of rename function
        '''
        res = OrderedDict([('renamed', True)])
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.rename('myzpool/mydataset', 'myzpool/newdataset'))

    def test_rename_error_not_exists(self):
        '''
        Tests failure return of rename function
        '''
        res = OrderedDict([
            ('renamed', False),
            ('error', "cannot open 'myzpool/mydataset': dataset does not exist"),
        ])
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "cannot open 'myzpool/mydataset': dataset does not exist"
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.rename('myzpool/mydataset', 'myzpool/newdataset'))

    def test_list_success(self):
        '''
        Tests zfs list
        '''
        res = OrderedDict([
            ('myzpool', OrderedDict([
                ('used', 849329782784),
                ('avail', 1081258016768),
                ('refer', 98304),
                ('mountpoint', '/myzpool'),
            ])),
        ])
        ret = {}
        ret['retcode'] = 0
        ret['stdout'] = 'myzpool\t791G\t1007G\t96K\t/myzpool'
        ret['stderr'] = ''
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.list_('myzpool'))

    def test_list_parsable_success(self):
        '''
        Tests zfs list with parsable set to False
        '''
        res = OrderedDict([
            ('myzpool', OrderedDict([
                ('used', '791G'),
                ('avail', '1007G'),
                ('refer', '96K'),
                ('mountpoint', '/myzpool'),
            ])),
        ])
        ret = {}
        ret['retcode'] = 0
        ret['stdout'] = 'myzpool\t791G\t1007G\t96K\t/myzpool'
        ret['stderr'] = ''
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.list_('myzpool', parsable=False))

    def test_list_custom_success(self):
        '''
        Tests zfs list
        '''
        res = OrderedDict([
            ('myzpool', OrderedDict([
                ('canmount', True),
                ('used', 849329782784),
                ('avail', 1081258016768),
                ('compression', False),
            ])),
        ])
        ret = {}
        ret['retcode'] = 0
        ret['stdout'] = 'myzpool\ton\t791G\t1007G\toff'
        ret['stderr'] = ''
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.list_('myzpool', properties='canmount,used,avail,compression'))

    def test_list_custom_parsable_success(self):
        '''
        Tests zfs list
        '''
        res = OrderedDict([
            ('myzpool', OrderedDict([
                ('canmount', 'on'),
                ('used', '791G'),
                ('avail', '1007G'),
                ('compression', 'off'),
            ])),
        ])
        ret = {}
        ret['retcode'] = 0
        ret['stdout'] = 'myzpool\ton\t791G\t1007G\toff'
        ret['stderr'] = ''
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.list_('myzpool', properties='canmount,used,avail,compression', parsable=False))

    def test_list_error_no_dataset(self):
        '''
        Tests zfs list
        '''
        res = OrderedDict()
        ret = {}
        ret['retcode'] = 1
        ret['stdout'] = "cannot open 'myzpool': dataset does not exist"
        ret['stderr'] = ''
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.list_('myzpool'))

    def test_list_mount_success(self):
        '''
        Tests zfs list_mount
        '''
        res = OrderedDict([
            ('myzpool/data', '/data'),
            ('myzpool/data/ares', '/data/ares'),
        ])
        ret = {}
        ret['retcode'] = 0
        ret['stdout'] = "\n".join([
            "myzpool/data\t\t\t\t/data",
            "myzpool/data/ares\t\t\t/data/ares",
        ])
        ret['stderr'] = ''
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.list_mount())

    def test_mount_success(self):
        '''
        Tests zfs mount of filesystem
        '''
        res = OrderedDict([('mounted', True)])
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.mount('myzpool/mydataset'))

    def test_mount_failure(self):
        '''
        Tests zfs mount of already mounted filesystem
        '''
        res = OrderedDict([('mounted', False), ('error', "cannot mount 'myzpool/mydataset': filesystem already mounted")])
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "cannot mount 'myzpool/mydataset': filesystem already mounted"
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.mount('myzpool/mydataset'))

    def test_unmount_success(self):
        '''
        Tests zfs unmount of filesystem
        '''
        res = OrderedDict([('unmounted', True)])
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.unmount('myzpool/mydataset'))

    def test_unmount_failure(self):
        '''
        Tests zfs unmount of already mounted filesystem
        '''
        res = OrderedDict([
            ('unmounted', False),
            ('error', "cannot mount 'myzpool/mydataset': not currently mounted"),
        ])
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "cannot mount 'myzpool/mydataset': not currently mounted"
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.unmount('myzpool/mydataset'))

    def test_inherit_success(self):
        '''
        Tests zfs inherit of compression property
        '''
        res = OrderedDict([('inherited', True)])
        ret = {'pid': 45193, 'retcode': 0, 'stderr': '', 'stdout': ''}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.inherit('compression', 'myzpool/mydataset'))

    def test_inherit_failure(self):
        '''
        Tests zfs inherit of canmount
        '''
        res = OrderedDict([
            ('inherited', False),
            ('error', "'canmount' property cannot be inherited"),
        ])
        ret = {'pid': 43898, 'retcode': 1, 'stderr': "'canmount' property cannot be inherited", 'stdout': ''}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.inherit('canmount', 'myzpool/mydataset'))

    def test_diff(self):
        '''
        Tests zfs diff
        '''
        res = [
            "1517063879.144517494\tM\t\t/data/test/",
            "1517063875.296592355\t+\t\t/data/test/world",
            "1517063879.274438467\t+\t\t/data/test/hello",
        ]
        ret = {}
        ret['retcode'] = 0
        ret['stdout'] = "\n".join([
            "1517063879.144517494\tM\t\t/data/test/",
            "1517063875.296592355\t+\t\t/data/test/world",
            "1517063879.274438467\t+\t\t/data/test/hello",
        ])
        ret['stderr'] = ''
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.diff('myzpool/mydataset@yesterday', 'myzpool/mydataset'))

    def test_diff_parsed_time(self):
        '''
        Tests zfs diff
        '''
        ## NOTE: do not hardcode parsed timestamps, timezone play a role here.
        ##       zfs diff output seems to be timezone aware
        res = OrderedDict([
            (strftime(1517063879.144517494, '%Y-%m-%d.%H:%M:%S.%f'), 'M\t\t/data/test/'),
            (strftime(1517063875.296592355, '%Y-%m-%d.%H:%M:%S.%f'), '+\t\t/data/test/world'),
            (strftime(1517063879.274438467, '%Y-%m-%d.%H:%M:%S.%f'), '+\t\t/data/test/hello'),
        ])
        ret = {}
        ret['retcode'] = 0
        ret['stdout'] = "\n".join([
            "1517063879.144517494\tM\t\t/data/test/",
            "1517063875.296592355\t+\t\t/data/test/world",
            "1517063879.274438467\t+\t\t/data/test/hello",
        ])
        ret['stderr'] = ''
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.diff('myzpool/data@yesterday', 'myzpool/data', parsable=False))

    def test_rollback_success(self):
        '''
        Tests zfs rollback success
        '''
        res = OrderedDict([('rolledback', True)])
        ret = {'pid': 56502, 'retcode': 0, 'stderr': '', 'stdout': ''}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.rollback('myzpool/mydataset@yesterday'))

    def test_rollback_failure(self):
        '''
        Tests zfs rollback failure
        '''
        res = OrderedDict([
            ('rolledback', False),
            ('error', "\n".join([
                    "cannot rollback to 'myzpool/mydataset@yesterday': more recent snapshots or bookmarks exist",
                    "use 'recursive=True' to force deletion of the following snapshots and bookmarks:",
                    "myzpool/mydataset@today"
                ]),
            ),
        ])
        ret = {
            'pid': 57471,
            'retcode': 1,
            'stderr': "cannot rollback to 'myzpool/mydataset@yesterday': more recent snapshots or bookmarks "
                      "exist\nuse '-r' to force deletion of the following snapshots and "
                      "bookmarks:\nmyzpool/mydataset@today",
            'stdout': ''
        }
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.rollback('myzpool/mydataset@yesterday'))

    def test_clone_success(self):
        '''
        Tests zfs clone success
        '''
        res = OrderedDict([('cloned', True)])
        ret = {'pid': 64532, 'retcode': 0, 'stderr': '', 'stdout': ''}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.clone('myzpool/mydataset@yesterday', 'myzpool/yesterday'))

    def test_clone_failure(self):
        '''
        Tests zfs clone failure
        '''
        res = OrderedDict([
            ('cloned', False),
            ('error', "cannot create 'myzpool/archive/yesterday': parent does not exist"),
        ])
        ret = {'pid': 64864, 'retcode': 1, 'stderr': "cannot create 'myzpool/archive/yesterday': parent does not exist", 'stdout': ''}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.clone('myzpool/mydataset@yesterday', 'myzpool/archive/yesterday'))

    def test_promote_success(self):
        '''
        Tests zfs promote success
        '''
        res = OrderedDict([('promoted', True)])
        ret = {'pid': 69075, 'retcode': 0, 'stderr': '', 'stdout': ''}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.promote('myzpool/yesterday'))

    def test_promote_failure(self):
        '''
        Tests zfs promote failure
        '''
        res = OrderedDict([
            ('promoted', False),
            ('error', "cannot promote 'myzpool/yesterday': not a cloned filesystem"),
        ])
        ret = {'pid': 69209, 'retcode': 1, 'stderr': "cannot promote 'myzpool/yesterday': not a cloned filesystem", 'stdout': ''}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.promote('myzpool/yesterday'))

    def test_bookmark_success(self):
        '''
        Tests zfs bookmark success
        '''
        with patch('salt.utils.path.which', MagicMock(return_value='/usr/bin/man')):
            res = OrderedDict([('bookmarked', True)])
            ret = {'pid': 20990, 'retcode': 0, 'stderr': '', 'stdout': ''}
            mock_cmd = MagicMock(return_value=ret)
            with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
                 patch.dict(zfs.__utils__, self.utils_patch):
                self.assertEqual(res, zfs.bookmark('myzpool/mydataset@yesterday', 'myzpool/mydataset#important'))

    def test_holds_success(self):
        '''
        Tests zfs holds success
        '''
        res = OrderedDict([
            ('important', 'Wed Dec 23 21:06 2015'),
            ('release-1.0', 'Wed Dec 23 21:08 2015'),
        ])
        ret = {'pid': 40216, 'retcode': 0, 'stderr': '', 'stdout': 'myzpool/mydataset@baseline\timportant  \tWed Dec 23 21:06 2015\nmyzpool/mydataset@baseline\trelease-1.0\tWed Dec 23 21:08 2015'}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.holds('myzpool/mydataset@baseline'))

    def test_holds_failure(self):
        '''
        Tests zfs holds failure
        '''
        res = OrderedDict([
            ('error', "cannot open 'myzpool/mydataset@baseline': dataset does not exist"),
        ])
        ret = {'pid': 40993, 'retcode': 1, 'stderr': "cannot open 'myzpool/mydataset@baseline': dataset does not exist", 'stdout': 'no datasets available'}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.holds('myzpool/mydataset@baseline'))

    def test_hold_success(self):
        '''
        Tests zfs hold success
        '''
        res = OrderedDict([('held', True)])
        ret = {'pid': 50876, 'retcode': 0, 'stderr': '', 'stdout': ''}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.hold('important', 'myzpool/mydataset@baseline', 'myzpool/mydataset@release-1.0'))

    def test_hold_failure(self):
        '''
        Tests zfs hold failure
        '''
        res = OrderedDict([
            ('held', False),
            ('error', "cannot hold snapshot 'myzpool/mydataset@baseline': tag already exists on this dataset"),
        ])
        ret = {'pid': 51006, 'retcode': 1, 'stderr': "cannot hold snapshot 'myzpool/mydataset@baseline': tag already exists on this dataset", 'stdout': ''}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.hold('important', 'myzpool/mydataset@baseline'))

    def test_release_success(self):
        '''
        Tests zfs release success
        '''
        res = OrderedDict([('released', True)])
        ret = {'pid': 50876, 'retcode': 0, 'stderr': '', 'stdout': ''}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.release('important', 'myzpool/mydataset@baseline', 'myzpool/mydataset@release-1.0'))

    def test_release_failure(self):
        '''
        Tests zfs release failure
        '''
        res = OrderedDict([
            ('released', False),
        ('error', "cannot release hold from snapshot 'myzpool/mydataset@baseline': no such tag on this dataset"),
        ])
        ret = {'pid': 51006, 'retcode': 1, 'stderr': "cannot release hold from snapshot 'myzpool/mydataset@baseline': no such tag on this dataset", 'stdout': ''}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.release('important', 'myzpool/mydataset@baseline'))

    def test_snapshot_success(self):
        '''
        Tests zfs snapshot success
        '''
        res = OrderedDict([('snapshotted', True)])
        ret = {'pid': 69125, 'retcode': 0, 'stderr': '', 'stdout': ''}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.snapshot('myzpool/mydataset@baseline'))

    def test_snapshot_failure(self):
        '''
        Tests zfs snapshot failure
        '''
        res = OrderedDict([
            ('snapshotted', False),
            ('error', "cannot create snapshot 'myzpool/mydataset@baseline': dataset already exists"),
        ])
        ret = {'pid': 68526, 'retcode': 1, 'stderr': "cannot create snapshot 'myzpool/mydataset@baseline': dataset already exists", 'stdout': ''}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.snapshot('myzpool/mydataset@baseline'))

    def test_snapshot_failure2(self):
        '''
        Tests zfs snapshot failure
        '''
        res = OrderedDict([
            ('snapshotted', False),
            ('error', "cannot open 'myzpool/mydataset': dataset does not exist"),
        ])
        ret = {'pid': 69256, 'retcode': 2, 'stderr': "cannot open 'myzpool/mydataset': dataset does not exist\nusage:\n\tsnapshot [-r] [-o property=value] ... <filesystem|volume>@<snap> ...\n\nFor the property list, run: zfs set|get\n\nFor the delegated permission list, run: zfs allow|unallow", 'stdout': ''}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.snapshot('myzpool/mydataset@baseline'))

    def test_set_success(self):
        '''
        Tests zfs set success
        '''
        res = OrderedDict([('set', True)])
        ret = {'pid': 79736, 'retcode': 0, 'stderr': '', 'stdout': ''}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.set('myzpool/mydataset', compression='lz4'))

    def test_set_failure(self):
        '''
        Tests zfs set failure
        '''
        res = OrderedDict([
            ('set', False),
    ('error', "cannot set property for 'myzpool/mydataset': 'canmount' must be one of 'on | off | noauto'"),
        ])
        ret = {'pid': 79887, 'retcode': 1, 'stderr': "cannot set property for 'myzpool/mydataset': 'canmount' must be one of 'on | off | noauto'", 'stdout': ''}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.set('myzpool/mydataset', canmount='lz4'))

    def test_get_success(self):
        '''
        Tests zfs get success
        '''
        res = OrderedDict([
            ('myzpool', OrderedDict([
                ('used', OrderedDict([
                    ('value', 906238099456),
                ])),
            ])),
        ])
        ret = {'pid': 562, 'retcode': 0, 'stderr': '', 'stdout': 'myzpool\tused\t906238099456'}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.get('myzpool', properties='used', fields='value'))

    def test_get_parsable_success(self):
        '''
        Tests zfs get with parsable output
        '''
        res = OrderedDict([
            ('myzpool', OrderedDict([
                ('used', OrderedDict([
                    ('value', '844G'),
                ])),
            ])),
        ])
        ret = {'pid': 562, 'retcode': 0, 'stderr': '', 'stdout': 'myzpool\tused\t906238099456'}
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zfs.__utils__, self.utils_patch):
            self.assertEqual(res, zfs.get('myzpool', properties='used', fields='value', parsable=False))
