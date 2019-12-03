# -*- coding: utf-8 -*-
'''
Tests for salt.modules.zpool

:codeauthor:    Nitin Madhok <nmadhok@clemson.edu>, Jorge Schrauwen <sjorge@blackdot.be>
:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:depends:       salt.utils.zfs
:platform:      illumos,freebsd,linux
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

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
import salt.modules.zpool as zpool

# Import Salt Utils
import salt.loader
from salt.utils.odict import OrderedDict
import salt.utils.decorators
import salt.utils.decorators.path


# Skip this test case if we don't have access to mock!
@skipIf(NO_MOCK, NO_MOCK_REASON)
class ZpoolTestCase(TestCase, LoaderModuleMockMixin):
    '''
    This class contains a set of functions that test salt.modules.zpool module
    '''
    def setup_loader_modules(self):
        self.opts = opts = salt.config.DEFAULT_MINION_OPTS.copy()
        self.utils_patch = ZFSMockData().get_patched_utils()
        for key in ('opts', 'utils_patch'):
            self.addCleanup(delattr, self, key)
        utils = salt.loader.utils(
            opts,
            whitelist=['zfs', 'args', 'systemd', 'path', 'platform'])
        zpool_obj = {
            zpool: {
                '__opts__': opts,
                '__utils__': utils,
            }
        }

        return zpool_obj

    def test_exists_success(self):
        '''
        Tests successful return of exists function
        '''
        ret = {}
        ret['stdout'] = "NAME      SIZE  ALLOC   FREE    CAP  DEDUP  HEALTH  ALTROOT\n" \
                        "myzpool   149G   128K   149G     0%  1.00x  ONLINE  -"
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            self.assertTrue(zpool.exists('myzpool'))

    def test_exists_failure(self):
        '''
        Tests failure return of exists function
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "cannot open 'myzpool': no such pool"
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)

        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            self.assertFalse(zpool.exists('myzpool'))

    def test_healthy(self):
        '''
        Tests successful return of healthy function
        '''
        ret = {}
        ret['stdout'] = "all pools are healthy"
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)

        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            self.assertTrue(zpool.healthy())

    def test_status(self):
        '''
        Tests successful return of status function
        '''
        ret = {}
        ret['stdout'] = "\n".join([
            "  pool: mypool",
            " state: ONLINE",
            "  scan: scrub repaired 0 in 0h6m with 0 errors on Mon Dec 21 02:06:17 2015",
            "config:",
            "",
            "\tNAME        STATE     READ WRITE CKSUM",
            "\tmypool      ONLINE       0     0     0",
            "\t  mirror-0  ONLINE       0     0     0",
            "\t    c2t0d0  ONLINE       0     0     0",
            "\t    c2t1d0  ONLINE       0     0     0",
            "",
            "errors: No known data errors",
        ])
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
                patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.status()
            self.assertEqual('ONLINE', ret['mypool']['state'])

    def test_iostat(self):
        '''
        Tests successful return of iostat function
        '''
        ret = {}
        ret['stdout'] = "\n".join([
            "               capacity     operations    bandwidth",
            "pool        alloc   free   read  write   read  write",
            "----------  -----  -----  -----  -----  -----  -----",
            "mypool      46.7G  64.3G      4     19   113K   331K",
            "  mirror    46.7G  64.3G      4     19   113K   331K",
            "    c2t0d0      -      -      1     10   114K   334K",
            "    c2t1d0      -      -      1     10   114K   334K",
            "----------  -----  -----  -----  -----  -----  -----",
        ])
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.iostat('mypool', parsable=False)
            self.assertEqual('46.7G', ret['mypool']['capacity-alloc'])

    def test_iostat_parsable(self):
        '''
        Tests successful return of iostat function

        .. note:
            The command output is the same as the non parsable!
            There is no -p flag for zpool iostat, but our type
            conversions can handle this!
        '''
        ret = {}
        ret['stdout'] = "\n".join([
            "               capacity     operations    bandwidth",
            "pool        alloc   free   read  write   read  write",
            "----------  -----  -----  -----  -----  -----  -----",
            "mypool      46.7G  64.3G      4     19   113K   331K",
            "  mirror    46.7G  64.3G      4     19   113K   331K",
            "    c2t0d0      -      -      1     10   114K   334K",
            "    c2t1d0      -      -      1     10   114K   334K",
            "----------  -----  -----  -----  -----  -----  -----",
        ])
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.iostat('mypool', parsable=True)
            self.assertEqual(50143743180, ret['mypool']['capacity-alloc'])

    def test_list(self):
        '''
        Tests successful return of list function
        '''
        ret = {}
        ret['stdout'] = "mypool\t1.81T\t661G\t1.17T\t35%\t11%\tONLINE"
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
                patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.list_(parsable=False)
            res = OrderedDict([('mypool', OrderedDict([
                ('size', '1.81T'),
                ('alloc', '661G'),
                ('free', '1.17T'),
                ('cap', '35%'),
                ('frag', '11%'),
                ('health', 'ONLINE'),
            ]))])
            self.assertEqual(ret, res)

    def test_list_parsable(self):
        '''
        Tests successful return of list function with parsable output
        '''
        ret = {}
        ret['stdout'] = "mypool\t1.81T\t661G\t1.17T\t35%\t11%\tONLINE"
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
                patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.list_(parsable=True)
            res = OrderedDict([('mypool', OrderedDict([
                ('size', 1990116046274),
                ('alloc', 709743345664),
                ('free', 1286428604497),
                ('cap', '35%'),
                ('frag', '11%'),
                ('health', 'ONLINE'),
            ]))])
            self.assertEqual(ret, res)

    def test_get(self):
        '''
        Tests successful return of get function
        '''
        ret = {}
        ret['stdout'] = "mypool\tsize\t1.81T\t-\n"
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.get('mypool', 'size', parsable=False)
            res = OrderedDict(OrderedDict([('size', '1.81T')]))
            self.assertEqual(ret, res)

    def test_get_parsable(self):
        '''
        Tests successful return of get function with parsable output
        '''
        ret = {}
        ret['stdout'] = "mypool\tsize\t1.81T\t-\n"
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.get('mypool', 'size', parsable=True)
            res = OrderedDict(OrderedDict([('size', 1990116046274)]))
            self.assertEqual(ret, res)

    def test_get_whitespace(self):
        '''
        Tests successful return of get function with a string with whitespaces
        '''
        ret = {}
        ret['stdout'] = "mypool\tcomment\tmy testing pool\t-\n"
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.get('mypool', 'comment')
            res = OrderedDict(OrderedDict([('comment', "my testing pool")]))
            self.assertEqual(ret, res)

    def test_scrub_start(self):
        '''
        Tests start of scrub
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)
        mock_exists = MagicMock(return_value=True)

        with patch.dict(zpool.__salt__, {'zpool.exists': mock_exists}), \
             patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.scrub('mypool')
            res = OrderedDict(OrderedDict([('scrubbing', True)]))
            self.assertEqual(ret, res)

    def test_scrub_pause(self):
        '''
        Tests pause of scrub
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)
        mock_exists = MagicMock(return_value=True)

        with patch.dict(zpool.__salt__, {'zpool.exists': mock_exists}), \
             patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.scrub('mypool', pause=True)
            res = OrderedDict(OrderedDict([('scrubbing', False)]))
            self.assertEqual(ret, res)

    def test_scrub_stop(self):
        '''
        Tests pauze of scrub
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)
        mock_exists = MagicMock(return_value=True)

        with patch.dict(zpool.__salt__, {'zpool.exists': mock_exists}), \
             patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.scrub('mypool', stop=True)
            res = OrderedDict(OrderedDict([('scrubbing', False)]))
            self.assertEqual(ret, res)

    def test_split_success(self):
        '''
        Tests split on success
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)

        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.split('datapool', 'backuppool')
            res = OrderedDict([('split', True)])
            self.assertEqual(ret, res)

    def test_split_exist_new(self):
        '''
        Tests split on exising new pool
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "Unable to split datapool: pool already exists"
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)

        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.split('datapool', 'backuppool')
            res = OrderedDict([('split', False), ('error', 'Unable to split datapool: pool already exists')])
            self.assertEqual(ret, res)

    def test_split_missing_pool(self):
        '''
        Tests split on missing source pool
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "cannot open 'datapool': no such pool"
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)

        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.split('datapool', 'backuppool')
            res = OrderedDict([('split', False), ('error', "cannot open 'datapool': no such pool")])
            self.assertEqual(ret, res)

    def test_split_not_mirror(self):
        '''
        Tests split on source pool is not a mirror
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "Unable to split datapool: Source pool must be composed only of mirrors"
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)

        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.split('datapool', 'backuppool')
            res = OrderedDict([('split', False), ('error', 'Unable to split datapool: Source pool must be composed only of mirrors')])
            self.assertEqual(ret, res)

    def test_labelclear_success(self):
        '''
        Tests labelclear on succesful label removal
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)

        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.labelclear('/dev/rdsk/c0t0d0', force=False)
            res = OrderedDict([('labelcleared', True)])
            self.assertEqual(ret, res)

    def test_labelclear_nodevice(self):
        '''
        Tests labelclear on non existing device
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "failed to open /dev/rdsk/c0t0d0: No such file or directory"
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)

        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.labelclear('/dev/rdsk/c0t0d0', force=False)
            res = OrderedDict([
                ('labelcleared', False),
                ('error', 'failed to open /dev/rdsk/c0t0d0: No such file or directory'),
            ])
            self.assertEqual(ret, res)

    def test_labelclear_cleared(self):
        '''
        Tests labelclear on device with no label
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "failed to read label from /dev/rdsk/c0t0d0"
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)

        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.labelclear('/dev/rdsk/c0t0d0', force=False)
            res = OrderedDict([
                ('labelcleared', False),
                ('error', 'failed to read label from /dev/rdsk/c0t0d0'),
            ])
            self.assertEqual(ret, res)

    def test_labelclear_exported(self):
        '''
        Tests labelclear on device with from exported pool
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "\n".join([
            "use '-f' to override the following error:",
            '/dev/rdsk/c0t0d0 is a member of exported pool "mypool"',
        ])
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.labelclear('/dev/rdsk/c0t0d0', force=False)
            res = OrderedDict([
                ('labelcleared', False),
                ('error', 'use \'force=True\' to override the following error:\n/dev/rdsk/c0t0d0 is a member of exported pool "mypool"'),
            ])
            self.assertEqual(ret, res)

    @skipIf(not salt.utils.path.which('mkfile'), 'Cannot find mkfile executable')
    def test_create_file_vdev_success(self):
        '''
        Tests create_file_vdev when out of space
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)

        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.create_file_vdev('64M', '/vdisks/disk0')
            res = OrderedDict([
                ('/vdisks/disk0', 'created'),
            ])
            self.assertEqual(ret, res)

    @skipIf(not salt.utils.path.which('mkfile'), 'Cannot find mkfile executable')
    def test_create_file_vdev_nospace(self):
        '''
        Tests create_file_vdev when out of space
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "/vdisks/disk0: initialized 10424320 of 67108864 bytes: No space left on device"
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)

        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.create_file_vdev('64M', '/vdisks/disk0')
            res = OrderedDict([
                ('/vdisks/disk0', 'failed'),
                ('error', OrderedDict([
                    ('/vdisks/disk0', ' initialized 10424320 of 67108864 bytes: No space left on device'),
                ])),
            ])
            self.assertEqual(ret, res)

    def test_export_success(self):
        '''
        Tests export
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)

        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.export('mypool')
            res = OrderedDict([('exported', True)])
            self.assertEqual(ret, res)

    def test_export_nopool(self):
        '''
        Tests export when the pool does not exists
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "cannot open 'mypool': no such pool"
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)

        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.export('mypool')
            res = OrderedDict([('exported', False), ('error', "cannot open 'mypool': no such pool")])
            self.assertEqual(ret, res)

    def test_import_success(self):
        '''
        Tests import
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)

        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.import_('mypool')
            res = OrderedDict([('imported', True)])
            self.assertEqual(ret, res)

    def test_import_duplicate(self):
        '''
        Tests import with already imported pool
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "\n".join([
            "cannot import 'mypool': a pool with that name already exists",
            "use the form 'zpool import <pool | id> <newpool>' to give it a new name",
        ])
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)

        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.import_('mypool')
            res = OrderedDict([
                ('imported', False),
                ('error', "cannot import 'mypool': a pool with that name already exists\nuse the form 'zpool import <pool | id> <newpool>' to give it a new name"),
            ])
            self.assertEqual(ret, res)

    def test_import_nopool(self):
        '''
        Tests import
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "cannot import 'mypool': no such pool available"
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)

        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.import_('mypool')
            res = OrderedDict([
                ('imported', False),
                ('error', "cannot import 'mypool': no such pool available"),
            ])
            self.assertEqual(ret, res)

    def test_online_success(self):
        '''
        Tests online
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)

        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.online('mypool', '/dev/rdsk/c0t0d0')
            res = OrderedDict([('onlined', True)])
            self.assertEqual(ret, res)

    def test_online_nodevice(self):
        '''
        Tests online
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "cannot online /dev/rdsk/c0t0d1: no such device in pool"
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)

        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.online('mypool', '/dev/rdsk/c0t0d1')
            res = OrderedDict([
                ('onlined', False),
                ('error', 'cannot online /dev/rdsk/c0t0d1: no such device in pool'),
            ])
            self.assertEqual(ret, res)

    def test_offline_success(self):
        '''
        Tests offline
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)

        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.offline('mypool', '/dev/rdsk/c0t0d0')
            res = OrderedDict([('offlined', True)])
            self.assertEqual(ret, res)

    def test_offline_nodevice(self):
        '''
        Tests offline
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "cannot offline /dev/rdsk/c0t0d1: no such device in pool"
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)

        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.offline('mypool', '/dev/rdsk/c0t0d1')
            res = OrderedDict([
                ('offlined', False),
                ('error', 'cannot offline /dev/rdsk/c0t0d1: no such device in pool'),
            ])
            self.assertEqual(ret, res)

    def test_offline_noreplica(self):
        '''
        Tests offline
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "cannot offline /dev/rdsk/c0t0d1: no valid replicas"
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)

        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.offline('mypool', '/dev/rdsk/c0t0d1')
            res = OrderedDict([
                ('offlined', False),
                ('error', 'cannot offline /dev/rdsk/c0t0d1: no valid replicas'),
            ])
            self.assertEqual(ret, res)

    def test_reguid_success(self):
        '''
        Tests reguid
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)

        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.reguid('mypool')
            res = OrderedDict([('reguided', True)])
            self.assertEqual(ret, res)

    def test_reguid_nopool(self):
        '''
        Tests reguid with missing pool
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "cannot open 'mypool': no such pool"
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)

        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.reguid('mypool')
            res = OrderedDict([
                ('reguided', False),
                ('error', "cannot open 'mypool': no such pool"),
            ])
            self.assertEqual(ret, res)

    def test_reopen_success(self):
        '''
        Tests reopen
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)

        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.reopen('mypool')
            res = OrderedDict([('reopened', True)])
            self.assertEqual(ret, res)

    def test_reopen_nopool(self):
        '''
        Tests reopen with missing pool
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "cannot open 'mypool': no such pool"
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)

        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.reopen('mypool')
            res = OrderedDict([
                ('reopened', False),
                ('error', "cannot open 'mypool': no such pool"),
            ])
            self.assertEqual(ret, res)

    def test_upgrade_success(self):
        '''
        Tests upgrade
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)

        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.upgrade('mypool')
            res = OrderedDict([('upgraded', True)])
            self.assertEqual(ret, res)

    def test_upgrade_nopool(self):
        '''
        Tests upgrade with missing pool
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "cannot open 'mypool': no such pool"
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)

        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.upgrade('mypool')
            res = OrderedDict([
                ('upgraded', False),
                ('error', "cannot open 'mypool': no such pool"),
            ])
            self.assertEqual(ret, res)

    def test_history_success(self):
        '''
        Tests history
        '''
        ret = {}
        ret['stdout'] = "\n".join([
            "History for 'mypool':",
            "2018-01-18.16:56:12 zpool create -f mypool /dev/rdsk/c0t0d0",
            "2018-01-19.16:01:55 zpool attach -f mypool /dev/rdsk/c0t0d0 /dev/rdsk/c0t0d1",
        ])
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)

        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.history('mypool')
            res = OrderedDict([
                ('mypool', OrderedDict([
                    ('2018-01-18.16:56:12', 'zpool create -f mypool /dev/rdsk/c0t0d0'),
                    ('2018-01-19.16:01:55', 'zpool attach -f mypool /dev/rdsk/c0t0d0 /dev/rdsk/c0t0d1'),
                ])),
            ])
            self.assertEqual(ret, res)

    def test_history_nopool(self):
        '''
        Tests history with missing pool
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "cannot open 'mypool': no such pool"
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)

        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.history('mypool')
            res = OrderedDict([
                ('error', "cannot open 'mypool': no such pool"),
            ])
            self.assertEqual(ret, res)

    def test_clear_success(self):
        '''
        Tests clear
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)

        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.clear('mypool')
            res = OrderedDict([('cleared', True)])
            self.assertEqual(ret, res)

    def test_clear_nopool(self):
        '''
        Tests clear with missing pool
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "cannot open 'mypool': no such pool"
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)

        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.clear('mypool')
            res = OrderedDict([
                ('cleared', False),
                ('error', "cannot open 'mypool': no such pool"),
            ])

    def test_clear_nodevice(self):
        '''
        Tests clear with non existign device
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "cannot clear errors for /dev/rdsk/c0t0d0: no such device in pool"
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)

        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
             patch.dict(zpool.__utils__, self.utils_patch):
            ret = zpool.clear('mypool', '/dev/rdsk/c0t0d0')
            res = OrderedDict([
                ('cleared', False),
                ('error', "cannot clear errors for /dev/rdsk/c0t0d0: no such device in pool"),
            ])
            self.assertEqual(ret, res)
