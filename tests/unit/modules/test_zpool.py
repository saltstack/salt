# -*- coding: utf-8 -*-
'''
    :codeauthor: Nitin Madhok <nmadhok@clemson.edu>`

    tests.unit.modules.zpool_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    Mock,
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON,
)

# Import Salt Execution module to test
import salt.modules.zpool as zpool

# Import Salt Utils
from salt.utils.odict import OrderedDict


# Skip this test case if we don't have access to mock!
@skipIf(NO_MOCK, NO_MOCK_REASON)
class ZpoolTestCase(TestCase, LoaderModuleMockMixin):
    '''
    This class contains a set of functions that test salt.modules.zpool module
    '''
    def setup_loader_modules(self):
        patcher = patch('salt.modules.zpool._check_zpool',
                        MagicMock(return_value='/sbin/zpool'))
        patcher.start()
        self.addCleanup(patcher.stop)
        return {zpool: {}}

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
        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}):
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
        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}):
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
        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}):
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
            "        NAME        STATE     READ WRITE CKSUM",
            "        mypool      ONLINE       0     0     0",
            "          mirror-0  ONLINE       0     0     0",
            "            c2t0d0  ONLINE       0     0     0",
            "            c2t1d0  ONLINE       0     0     0",
            "",
            "errors: No known data errors",
        ])
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}):
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
        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}):
            ret = zpool.iostat('mypool')
            self.assertEqual('46.7G', ret['mypool']['mypool']['capacity-alloc'])

    def test_list(self):
        '''
        Tests successful return of list function
        '''
        ret = {}
        ret['stdout'] = "mypool\t1.81T\t714G\t1.11T\t38%\tONLINE"
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
                patch('salt.modules.zpool._check_features',
                      MagicMock(return_value=False)):
            ret = zpool.list_()
            res = OrderedDict([('mypool', {'alloc': '714G', 'cap': '38%', 'free': '1.11T',
                                           'health': 'ONLINE', 'size': '1.81T'})])
            self.assertEqual(res, ret)

    def test_list_parsable(self):
        '''
        Tests successful return of list function with parsable output
        '''
        ret = {}
        ret['stdout'] = "mypool\t1992864825344\t767076794368\t1225788030976\t38\tONLINE"
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}), \
                patch('salt.modules.zpool._check_features',
                      MagicMock(return_value=False)):
            ret = zpool.list_()
            res = OrderedDict([('mypool', {'alloc': 767076794368, 'cap': 38,
                                           'free': 1225788030976, 'health': 'ONLINE',
                                           'size': 1992864825344})])
            self.assertEqual(res, ret)

    def test_get(self):
        '''
        Tests successful return of get function
        '''
        ret = {}
        ret['stdout'] = "size\t1.81T\t-\n"
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}):
            ret = zpool.get('mypool', 'size')
            res = OrderedDict([('mypool', OrderedDict([('size', '1.81T')]))])
            self.assertEqual(res, ret)

    def test_get_parsable(self):
        '''
        Tests successful return of get function with parsable output
        '''
        ret = {}
        ret['stdout'] = "size\t1992864825344\t-\n"
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}):
            ret = zpool.get('mypool', 'size')
            res = OrderedDict([('mypool', OrderedDict([('size', 1992864825344)]))])
            self.assertEqual(res, ret)

    def test_get_whitespace(self):
        '''
        Tests successful return of get function with a string with whitespaces
        '''
        ret = {}
        ret['stdout'] = "comment\tmy testing pool\t-\n"
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}):
            ret = zpool.get('mypool', 'comment')
            res = OrderedDict([('mypool', OrderedDict([('comment', "'my testing pool'")]))])
            self.assertEqual(res, ret)

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

        with patch.dict(zpool.__salt__, {'zpool.exists': mock_exists}):
            with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}):
                ret = zpool.scrub('mypool')
                res = OrderedDict([('mypool', OrderedDict([('scrubbing', True)]))])
                self.assertEqual(res, ret)

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

        with patch.dict(zpool.__salt__, {'zpool.exists': mock_exists}):
            with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}):
                ret = zpool.scrub('mypool', pause=True)
                res = OrderedDict([('mypool', OrderedDict([('scrubbing', False)]))])
                self.assertEqual(res, ret)

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

        with patch.dict(zpool.__salt__, {'zpool.exists': mock_exists}):
            with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}):
                ret = zpool.scrub('mypool', stop=True)
                res = OrderedDict([('mypool', OrderedDict([('scrubbing', False)]))])
                self.assertEqual(res, ret)

    def test_split_success(self):
        '''
        Tests split on success
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)
        mock_exists = Mock()
        mock_exists.side_effect = [False, True]

        with patch.dict(zpool.__salt__, {'zpool.exists': mock_exists}):
            with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}):
                ret = zpool.split('datapool', 'backuppool')
                res = OrderedDict([('backuppool', 'split off from datapool')])
                self.assertEqual(res, ret)

    def test_split_exist_new(self):
        '''
        Tests split on exising new pool
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)
        mock_exists = Mock()
        mock_exists.side_effect = [True, True]

        with patch.dict(zpool.__salt__, {'zpool.exists': mock_exists}):
            with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}):
                ret = zpool.split('datapool', 'backuppool')
                res = OrderedDict([('backuppool', 'storage pool already exists')])
                self.assertEqual(res, ret)

    def test_split_missing_pool(self):
        '''
        Tests split on missing source pool
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)
        mock_exists = Mock()
        mock_exists.side_effect = [False, False]

        with patch.dict(zpool.__salt__, {'zpool.exists': mock_exists}):
            with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}):
                ret = zpool.split('datapool', 'backuppool')
                res = OrderedDict([('datapool', 'storage pool does not exists')])
                self.assertEqual(res, ret)

    def test_split_not_mirror(self):
        '''
        Tests split on source pool is not a mirror
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "Unable to split datapool: Source pool must be composed only of mirrors"
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)
        mock_exists = Mock()
        mock_exists.side_effect = [False, True]

        with patch.dict(zpool.__salt__, {'zpool.exists': mock_exists}):
            with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}):
                ret = zpool.split('datapool', 'backuppool')
                res = OrderedDict([('backuppool', 'Unable to split datapool: '
                                                  'Source pool must be composed only of mirrors')])
                self.assertEqual(res, ret)

    def test_labelclear_success(self):
        '''
        Tests labelclear on succesful label removal
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}):
            ret = zpool.labelclear('/dev/rdsk/c0t0d0', force=False)
            res = OrderedDict([('/dev/rdsk/c0t0d0', 'cleared')])
            self.assertEqual(res, ret)

    def test_labelclear_cleared(self):
        '''
        Tests labelclear on device with no label
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "failed to read label from /dev/rdsk/c0t0d0"
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}):
            ret = zpool.labelclear('/dev/rdsk/c0t0d0', force=False)
            res = OrderedDict([('/dev/rdsk/c0t0d0', 'failed to read label from /dev/rdsk/c0t0d0')])
            self.assertEqual(res, ret)

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
        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}):
            ret = zpool.labelclear('/dev/rdsk/c0t0d0', force=False)
            res = OrderedDict([('/dev/rdsk/c0t0d0', '/dev/rdsk/c0t0d0 is a member of exported pool "mypool"')])
            self.assertEqual(res, ret)
