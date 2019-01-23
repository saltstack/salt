# -*- coding: utf-8 -*-
'''
Tests for the zfs utils library

:codeauthor:    Jorge Schrauwen <sjorge@blackdot.be>
:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:platform:      illumos,freebsd,linux

.. versionadded:: 2018.3.1
'''

# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Testing libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON,
)

# Import Salt Execution module to test
import salt.utils.zfs as zfs

# Import Salt Utils
from salt.utils.odict import OrderedDict


# Skip this test case if we don't have access to mock!
@skipIf(NO_MOCK, NO_MOCK_REASON)
class ZfsUtilsTestCase(TestCase):
    '''
    This class contains a set of functions that test salt.utils.zfs utils
    '''
    def setUp(self):
        # property_map mocks
        self.pmap_exec_zpool = {
            'retcode': 2,
            'stdout': '',
            'stderr': "\n".join([
                'missing property argument',
                'usage:',
                '        get [-Hp] [-o "all" | field[,...]] <"all" | property[,...]> <pool> ...',
                '',
                'the following properties are supported:',
                '',
                '        PROPERTY         EDIT   VALUES',
                '',
                '        allocated          NO   <size>',
                '        capacity           NO   <size>',
                '        dedupratio         NO   <1.00x or higher if deduped>',
                '        expandsize         NO   <size>',
                '        fragmentation      NO   <percent>',
                '        free               NO   <size>',
                '        freeing            NO   <size>',
                '        guid               NO   <guid>',
                '        health             NO   <state>',
                '        leaked             NO   <size>',
                '        size               NO   <size>',
                '        altroot           YES   <path>',
                '        autoexpand        YES   on | off',
                '        autoreplace       YES   on | off',
                '        bootfs            YES   <filesystem>',
                '        bootsize          YES   <size>',
                '        cachefile         YES   <file> | none',
                '        comment           YES   <comment-string>',
                '        dedupditto        YES   <threshold (min 100)>',
                '        delegation        YES   on | off',
                '        failmode          YES   wait | continue | panic',
                '        listsnapshots     YES   on | off',
                '        readonly          YES   on | off',
                '        version           YES   <version>',
                '        feature@...       YES   disabled | enabled | active',
                '',
                'The feature@ properties must be appended with a feature name.',
                'See zpool-features(5). ',
            ]),
        }
        self.pmap_zpool = {
          'comment': {
            'edit': True,
            'type': 'str',
            'values': '<comment-string>'
          },
          'freeing': {
            'edit': False,
            'type': 'size',
            'values': '<size>'
          },
          'listsnapshots': {
            'edit': True,
            'type': 'bool',
            'values': 'on | off'
          },
          'leaked': {
            'edit': False,
            'type': 'size',
            'values': '<size>'
          },
          'version': {
            'edit': True,
            'type': 'numeric',
            'values': '<version>'
          },
          'write': {
            'edit': False,
            'type': 'size',
            'values': '<size>'
          },
          'replace': {
            'edit': True,
            'type': 'bool',
            'values': 'on | off'
          },
          'delegation': {
            'edit': True,
            'type': 'bool',
            'values': 'on | off'
          },
          'dedupditto': {
            'edit': True,
            'type': 'str',
            'values': '<threshold (min 100)>'
          },
          'autoexpand': {
            'edit': True,
            'type': 'bool',
            'values': 'on | off'
          },
          'alloc': {
            'edit': False,
            'type': 'size',
            'values': '<size>'
          },
          'allocated': {
            'edit': False,
            'type': 'size',
            'values': '<size>'
          },
          'guid': {
            'edit': False,
            'type': 'numeric',
            'values': '<guid>'
          },
          'size': {
            'edit': False,
            'type': 'size',
            'values': '<size>'
          },
          'cap': {
            'edit': False,
            'type': 'numeric',
            'values': '<count>'
          },
          'capacity': {
            'edit': False,
            'type': 'size',
            'values': '<size>'
          },
          "capacity-alloc": {
            "edit": False,
            "type": "size",
            "values": "<size>"
          },
          "capacity-free": {
            "edit": False,
            "type": "size",
            "values": "<size>"
          },
          'cachefile': {
            'edit': True,
            'type': 'str',
            'values': '<file> | none'
          },
          "cksum": {
            "edit": False,
            "type": "numeric",
            "values": "<count>"
          },
          'bootfs': {
            'edit': True,
            'type': 'str',
            'values': '<filesystem>'
          },
          'autoreplace': {
            'edit': True,
            'type': 'bool',
            'values': 'on | off'
          },
          "bandwith-read": {
            "edit": False,
            "type": "size",
            "values": "<size>"
          },
          "bandwith-write": {
            "edit": False,
            "type": "size",
            "values": "<size>"
          },
          "operations-read": {
            "edit": False,
            "type": "size",
            "values": "<size>"
          },
          "operations-write": {
            "edit": False,
            "type": "size",
            "values": "<size>"
          },
          "read": {
            "edit": False,
            "type": "size",
            "values": "<size>"
          },
          'readonly': {
            'edit': True,
            'type': 'bool',
            'values': 'on | off'
          },
          'dedupratio': {
            'edit': False,
            'type': 'str',
            'values': '<1.00x or higher if deduped>'
          },
          'health': {
            'edit': False,
            'type': 'str',
            'values': '<state>'
          },
          'feature@': {
            'edit': True,
            'type': 'str',
            'values': 'disabled | enabled | active'
          },
          'expandsize': {
            'edit': False,
            'type': 'size',
            'values': '<size>'
          },
          'listsnaps': {
            'edit': True,
            'type': 'bool',
            'values': 'on | off'
          },
          'bootsize': {
            'edit': True,
            'type': 'size',
            'values': '<size>'
          },
          'free': {
            'edit': False,
            'type': 'size',
            'values': '<size>'
          },
          'failmode': {
            'edit': True,
            'type': 'str',
            'values': 'wait | continue | panic'
          },
          'altroot': {
            'edit': True,
            'type': 'str',
            'values': '<path>'
          },
          'expand': {
            'edit': True,
            'type': 'bool',
            'values': 'on | off'
          },
          'frag': {
            'edit': False,
            'type': 'str',
            'values': '<percent>'
          },
          'fragmentation': {
            'edit': False,
            'type': 'str',
            'values': '<percent>'
          }
        }
        self.pmap_exec_zfs = {
            'retcode': 2,
            'stdout': '',
            'stderr': "\n".join([
                'missing property argument',
                'usage:',
                '        get [-crHp] [-d max] [-o "all" | field[,...]]',
                '            [-t type[,...]] [-s source[,...]]',
                '            <"all" | property[,...]> [filesystem|volume|snapshot|bookmark] ...',
                '',
                'The following properties are supported:',
                '',
                '        PROPERTY       EDIT  INHERIT   VALUES',
                '',
                '        available        NO       NO   <size>',
                '        clones           NO       NO   <dataset>[,...]',
                '        compressratio    NO       NO   <1.00x or higher if compressed>',
                '        creation         NO       NO   <date>',
                '        defer_destroy    NO       NO   yes | no',
                '        filesystem_count  NO       NO   <count>',
                '        logicalreferenced  NO       NO   <size>',
                '        logicalused      NO       NO   <size>',
                '        mounted          NO       NO   yes | no',
                '        origin           NO       NO   <snapshot>',
                '        receive_resume_token  NO       NO   <string token>',
                '        refcompressratio  NO       NO   <1.00x or higher if compressed>',
                '        referenced       NO       NO   <size>',
                '        snapshot_count   NO       NO   <count>',
                '        type             NO       NO   filesystem | volume | snapshot | bookmark',
                '        used             NO       NO   <size>',
                '        usedbychildren   NO       NO   <size>',
                '        usedbydataset    NO       NO   <size>',
                '        usedbyrefreservation  NO       NO   <size>',
                '        usedbysnapshots  NO       NO   <size>',
                '        userrefs         NO       NO   <count>',
                '        written          NO       NO   <size>',
                '        aclinherit      YES      YES   discard | noallow | restricted | passthrough | passthrough-x',
                '        aclmode         YES      YES   discard | groupmask | passthrough | restricted',
                '        atime           YES      YES   on | off',
                '        canmount        YES       NO   on | off | noauto',
                '        casesensitivity  NO      YES   sensitive | insensitive | mixed',
                '        checksum        YES      YES   on | off | fletcher2 | fletcher4 | sha256 | sha512 | skein | edonr',
                '        compression     YES      YES   on | off | lzjb | gzip | gzip-[1-9] | zle | lz4',
                '        copies          YES      YES   1 | 2 | 3',
                '        dedup           YES      YES   on | off | verify | sha256[,verify], sha512[,verify], skein[,verify], edonr,verify',
                '        devices         YES      YES   on | off',
                '        exec            YES      YES   on | off',
                '        filesystem_limit YES       NO   <count> | none',
                '        logbias         YES      YES   latency | throughput',
                '        mlslabel        YES      YES   <sensitivity label>',
                '        mountpoint      YES      YES   <path> | legacy | none',
                '        nbmand          YES      YES   on | off',
                '        normalization    NO      YES   none | formC | formD | formKC | formKD',
                '        primarycache    YES      YES   all | none | metadata',
                '        quota           YES       NO   <size> | none',
                '        readonly        YES      YES   on | off',
                '        recordsize      YES      YES   512 to 1M, power of 2',
                '        redundant_metadata YES      YES   all | most',
                '        refquota        YES       NO   <size> | none',
                '        refreservation  YES       NO   <size> | none',
                '        reservation     YES       NO   <size> | none',
                '        secondarycache  YES      YES   all | none | metadata',
                '        setuid          YES      YES   on | off',
                '        sharenfs        YES      YES   on | off | share(1M) options',
                '        sharesmb        YES      YES   on | off | sharemgr(1M) options',
                '        snapdir         YES      YES   hidden | visible',
                '        snapshot_limit  YES       NO   <count> | none',
                '        sync            YES      YES   standard | always | disabled',
                '        utf8only         NO      YES   on | off',
                '        version         YES       NO   1 | 2 | 3 | 4 | 5 | current',
                '        volblocksize     NO      YES   512 to 128k, power of 2',
                '        volsize         YES       NO   <size>',
                '        vscan           YES      YES   on | off',
                '        xattr           YES      YES   on | off',
                '        zoned           YES      YES   on | off',
                '        userused@...     NO       NO   <size>',
                '        groupused@...    NO       NO   <size>',
                '        userquota@...   YES       NO   <size> | none',
                '        groupquota@...  YES       NO   <size> | none',
                '        written@<snap>   NO       NO   <size>',
                '',
                'Sizes are specified in bytes with standard units such as K, M, G, etc.',
                '',
                'User-defined properties can be specified by using a name containing a colon (:).',
                '',
                'The {user|group}{used|quota}@ properties must be appended with',
                'a user or group specifier of one of these forms:',
                '    POSIX name      (eg: "matt")',
                '    POSIX id        (eg: "126829")',
                '    SMB name@domain (eg: "matt@sun")',
                '    SMB SID         (eg: "S-1-234-567-89")',
            ]),
        }
        self.pmap_zfs = {
          "origin": {
            "edit": False,
            "inherit": False,
            "values": "<snapshot>",
            "type": "str"
          },
          "setuid": {
            "edit": True,
            "inherit": True,
            "values": "on | off",
            "type": "bool"
          },
          "referenced": {
            "edit": False,
            "inherit": False,
            "values": "<size>",
            "type": "size"
          },
          "vscan": {
            "edit": True,
            "inherit": True,
            "values": "on | off",
            "type": "bool"
          },
          "logicalused": {
            "edit": False,
            "inherit": False,
            "values": "<size>",
            "type": "size"
          },
          "userrefs": {
            "edit": False,
            "inherit": False,
            "values": "<count>",
            "type": "numeric"
          },
          "primarycache": {
            "edit": True,
            "inherit": True,
            "values": "all | none | metadata",
            "type": "str"
          },
          "logbias": {
            "edit": True,
            "inherit": True,
            "values": "latency | throughput",
            "type": "str"
          },
          "creation": {
            "edit": False,
            "inherit": False,
            "values": "<date>",
            "type": "str"
          },
          "sync": {
            "edit": True,
            "inherit": True,
            "values": "standard | always | disabled",
            "type": "str"
          },
          "dedup": {
            "edit": True,
            "inherit": True,
            "values": "on | off | verify | sha256[,verify], sha512[,verify], skein[,verify], edonr,verify",
            "type": "bool"
          },
          "sharenfs": {
            "edit": True,
            "inherit": True,
            "values": "on | off | share(1m) options",
            "type": "bool"
          },
          "receive_resume_token": {
            "edit": False,
            "inherit": False,
            "values": "<string token>",
            "type": "str"
          },
          "usedbyrefreservation": {
            "edit": False,
            "inherit": False,
            "values": "<size>",
            "type": "size"
          },
          "sharesmb": {
            "edit": True,
            "inherit": True,
            "values": "on | off | sharemgr(1m) options",
            "type": "bool"
          },
          "rdonly": {
            "edit": True,
            "inherit": True,
            "values": "on | off",
            "type": "bool"
          },
          "reservation": {
            "edit": True,
            "inherit": False,
            "values": "<size> | none",
            "type": "size"
          },
          "reserv": {
            "edit": True,
            "inherit": False,
            "values": "<size> | none",
            "type": "size"
          },
          "mountpoint": {
            "edit": True,
            "inherit": True,
            "values": "<path> | legacy | none",
            "type": "str"
          },
          "casesensitivity": {
            "edit": False,
            "inherit": True,
            "values": "sensitive | insensitive | mixed",
            "type": "str"
          },
          "utf8only": {
            "edit": False,
            "inherit": True,
            "values": "on | off",
            "type": "bool"
          },
          "usedbysnapshots": {
            "edit": False,
            "inherit": False,
            "values": "<size>",
            "type": "size"
          },
          "readonly": {
            "edit": True,
            "inherit": True,
            "values": "on | off",
            "type": "bool"
          },
          "written@": {
            "edit": False,
            "inherit": False,
            "values": "<size>",
            "type": "size"
          },
          "avail": {
            "edit": False,
            "inherit": False,
            "values": "<size>",
            "type": "size"
          },
          "recsize": {
            "edit": True,
            "inherit": True,
            "values": "512 to 1m, power of 2",
            "type": "str"
          },
          "atime": {
            "edit": True,
            "inherit": True,
            "values": "on | off",
            "type": "bool"
          },
          "compression": {
            "edit": True,
            "inherit": True,
            "values": "on | off | lzjb | gzip | gzip-[1-9] | zle | lz4",
            "type": "bool"
          },
          "snapdir": {
            "edit": True,
            "inherit": True,
            "values": "hidden | visible",
            "type": "str"
          },
          "aclmode": {
            "edit": True,
            "inherit": True,
            "values": "discard | groupmask | passthrough | restricted",
            "type": "str"
          },
          "zoned": {
            "edit": True,
            "inherit": True,
            "values": "on | off",
            "type": "bool"
          },
          "copies": {
            "edit": True,
            "inherit": True,
            "values": "1 | 2 | 3",
            "type": "numeric"
          },
          "snapshot_limit": {
            "edit": True,
            "inherit": False,
            "values": "<count> | none",
            "type": "numeric"
          },
          "aclinherit": {
            "edit": True,
            "inherit": True,
            "values": "discard | noallow | restricted | passthrough | passthrough-x",
            "type": "str"
          },
          "compressratio": {
            "edit": False,
            "inherit": False,
            "values": "<1.00x or higher if compressed>",
            "type": "str"
          },
          "xattr": {
            "edit": True,
            "inherit": True,
            "values": "on | off",
            "type": "bool"
          },
          "written": {
            "edit": False,
            "inherit": False,
            "values": "<size>",
            "type": "size"
          },
          "version": {
            "edit": True,
            "inherit": False,
            "values": "1 | 2 | 3 | 4 | 5 | current",
            "type": "numeric"
          },
          "recordsize": {
            "edit": True,
            "inherit": True,
            "values": "512 to 1m, power of 2",
            "type": "str"
          },
          "refquota": {
            "edit": True,
            "inherit": False,
            "values": "<size> | none",
            "type": "size"
          },
          "filesystem_limit": {
            "edit": True,
            "inherit": False,
            "values": "<count> | none",
            "type": "numeric"
          },
          "lrefer.": {
            "edit": False,
            "inherit": False,
            "values": "<size>",
            "type": "size"
          },
          "type": {
            "edit": False,
            "inherit": False,
            "values": "filesystem | volume | snapshot | bookmark",
            "type": "str"
          },
          "secondarycache": {
            "edit": True,
            "inherit": True,
            "values": "all | none | metadata",
            "type": "str"
          },
          "refer": {
            "edit": False,
            "inherit": False,
            "values": "<size>",
            "type": "size"
          },
          "available": {
            "edit": False,
            "inherit": False,
            "values": "<size>",
            "type": "size"
          },
          "used": {
            "edit": False,
            "inherit": False,
            "values": "<size>",
            "type": "size"
          },
          "exec": {
            "edit": True,
            "inherit": True,
            "values": "on | off",
            "type": "bool"
          },
          "compress": {
            "edit": True,
            "inherit": True,
            "values": "on | off | lzjb | gzip | gzip-[1-9] | zle | lz4",
            "type": "bool"
          },
          "volblock": {
            "edit": False,
            "inherit": True,
            "values": "512 to 128k, power of 2",
            "type": "str"
          },
          "refcompressratio": {
            "edit": False,
            "inherit": False,
            "values": "<1.00x or higher if compressed>",
            "type": "str"
          },
          "quota": {
            "edit": True,
            "inherit": False,
            "values": "<size> | none",
            "type": "size"
          },
          "groupquota@": {
            "edit": True,
            "inherit": False,
            "values": "<size> | none",
            "type": "size"
          },
          "userquota@": {
            "edit": True,
            "inherit": False,
            "values": "<size> | none",
            "type": "size"
          },
          "snapshot_count": {
            "edit": False,
            "inherit": False,
            "values": "<count>",
            "type": "numeric"
          },
          "volsize": {
            "edit": True,
            "inherit": False,
            "values": "<size>",
            "type": "size"
          },
          "clones": {
            "edit": False,
            "inherit": False,
            "values": "<dataset>[,...]",
            "type": "str"
          },
          "canmount": {
            "edit": True,
            "inherit": False,
            "values": "on | off | noauto",
            "type": "bool"
          },
          "mounted": {
            "edit": False,
            "inherit": False,
            "values": "yes | no",
            "type": "bool_alt"
          },
          "groupused@": {
            "edit": False,
            "inherit": False,
            "values": "<size>",
            "type": "size"
          },
          "normalization": {
            "edit": False,
            "inherit": True,
            "values": "none | formc | formd | formkc | formkd",
            "type": "str"
          },
          "usedbychildren": {
            "edit": False,
            "inherit": False,
            "values": "<size>",
            "type": "size"
          },
          "usedbydataset": {
            "edit": False,
            "inherit": False,
            "values": "<size>",
            "type": "size"
          },
          "mlslabel": {
            "edit": True,
            "inherit": True,
            "values": "<sensitivity label>",
            "type": "str"
          },
          "refreserv": {
            "edit": True,
            "inherit": False,
            "values": "<size> | none",
            "type": "size"
          },
          "defer_destroy": {
            "edit": False,
            "inherit": False,
            "values": "yes | no",
            "type": "bool_alt"
          },
          "volblocksize": {
            "edit": False,
            "inherit": True,
            "values": "512 to 128k, power of 2",
            "type": "str"
          },
          "lused.": {
            "edit": False,
            "inherit": False,
            "values": "<size>",
            "type": "size"
          },
          "redundant_metadata": {
            "edit": True,
            "inherit": True,
            "values": "all | most",
            "type": "str"
          },
          "filesystem_count": {
            "edit": False,
            "inherit": False,
            "values": "<count>",
            "type": "numeric"
          },
          "devices": {
            "edit": True,
            "inherit": True,
            "values": "on | off",
            "type": "bool"
          },
          "refreservation": {
            "edit": True,
            "inherit": False,
            "values": "<size> | none",
            "type": "size"
          },
          "userused@": {
            "edit": False,
            "inherit": False,
            "values": "<size>",
            "type": "size"
          },
          "logicalreferenced": {
            "edit": False,
            "inherit": False,
            "values": "<size>",
            "type": "size"
          },
          "checksum": {
            "edit": True,
            "inherit": True,
            "values": "on | off | fletcher2 | fletcher4 | sha256 | sha512 | skein | edonr",
            "type": "bool"
          },
          "nbmand": {
            "edit": True,
            "inherit": True,
            "values": "on | off",
            "type": "bool"
          }
        }

    ## NOTE: test parameter parsing
    def test_is_supported(self):
        '''
        Test zfs.is_supported method
        '''
        for value in [False, True]:
            with patch('salt.utils.path.which',
                       MagicMock(return_value=value)):
                with patch('salt.utils.platform.is_linux',
                                  MagicMock(return_value=value)):
                    self.assertEqual(value, zfs.is_supported())

    def test_property_data_zpool(self):
        '''
        Test parsing of zpool get output
        '''
        with patch.object(zfs, '_zfs_cmd', MagicMock(return_value='/sbin/zfs')):
            with patch.object(zfs, '_zpool_cmd', MagicMock(return_value='/sbin/zpool')):
                with patch.object(zfs, '_exec', MagicMock(return_value=self.pmap_exec_zpool)):
                    self.assertEqual(zfs.property_data_zpool(), self.pmap_zpool)

    def test_property_data_zfs(self):
        '''
        Test parsing of zfs get output
        '''
        with patch.object(zfs, '_zfs_cmd', MagicMock(return_value='/sbin/zfs')):
            with patch.object(zfs, '_zpool_cmd', MagicMock(return_value='/sbin/zpool')):
                with patch.object(zfs, '_exec', MagicMock(return_value=self.pmap_exec_zfs)):
                    self.assertEqual(zfs.property_data_zfs(), self.pmap_zfs)

    ## NOTE: testing from_bool results
    def test_from_bool_on(self):
        '''
        Test from_bool with 'on'
        '''
        self.assertTrue(zfs.from_bool('on'))
        self.assertTrue(zfs.from_bool(zfs.from_bool('on')))

    def test_from_bool_off(self):
        '''
        Test from_bool with 'off'
        '''
        self.assertFalse(zfs.from_bool('off'))
        self.assertFalse(zfs.from_bool(zfs.from_bool('off')))

    def test_from_bool_none(self):
        '''
        Test from_bool with 'none'
        '''
        self.assertEqual(zfs.from_bool('none'), None)
        self.assertEqual(zfs.from_bool(zfs.from_bool('none')), None)

    def test_from_bool_passthrough(self):
        '''
        Test from_bool with 'passthrough'
        '''
        self.assertEqual(zfs.from_bool('passthrough'), 'passthrough')
        self.assertEqual(zfs.from_bool(zfs.from_bool('passthrough')), 'passthrough')

    def test_from_bool_alt_yes(self):
        '''
        Test from_bool_alt with 'yes'
        '''
        self.assertTrue(zfs.from_bool_alt('yes'))
        self.assertTrue(zfs.from_bool_alt(zfs.from_bool_alt('yes')))

    def test_from_bool_alt_no(self):
        '''
        Test from_bool_alt with 'no'
        '''
        self.assertFalse(zfs.from_bool_alt('no'))
        self.assertFalse(zfs.from_bool_alt(zfs.from_bool_alt('no')))

    def test_from_bool_alt_none(self):
        '''
        Test from_bool_alt with 'none'
        '''
        self.assertEqual(zfs.from_bool_alt('none'), None)
        self.assertEqual(zfs.from_bool_alt(zfs.from_bool_alt('none')), None)

    def test_from_bool_alt_passthrough(self):
        '''
        Test from_bool_alt with 'passthrough'
        '''
        self.assertEqual(zfs.from_bool_alt('passthrough'), 'passthrough')
        self.assertEqual(zfs.from_bool_alt(zfs.from_bool_alt('passthrough')), 'passthrough')

    ## NOTE: testing to_bool results
    def test_to_bool_true(self):
        '''
        Test to_bool with True
        '''
        self.assertEqual(zfs.to_bool(True), 'on')
        self.assertEqual(zfs.to_bool(zfs.to_bool(True)), 'on')

    def test_to_bool_false(self):
        '''
        Test to_bool with False
        '''
        self.assertEqual(zfs.to_bool(False), 'off')
        self.assertEqual(zfs.to_bool(zfs.to_bool(False)), 'off')

    def test_to_bool_none(self):
        '''
        Test to_bool with None
        '''
        self.assertEqual(zfs.to_bool(None), 'none')
        self.assertEqual(zfs.to_bool(zfs.to_bool(None)), 'none')

    def test_to_bool_passthrough(self):
        '''
        Test to_bool with 'passthrough'
        '''
        self.assertEqual(zfs.to_bool('passthrough'), 'passthrough')
        self.assertEqual(zfs.to_bool(zfs.to_bool('passthrough')), 'passthrough')

    def test_to_bool_alt_true(self):
        '''
        Test to_bool_alt with True
        '''
        self.assertEqual(zfs.to_bool_alt(True), 'yes')
        self.assertEqual(zfs.to_bool_alt(zfs.to_bool_alt(True)), 'yes')

    def test_to_bool_alt_false(self):
        '''
        Test to_bool_alt with False
        '''
        self.assertEqual(zfs.to_bool_alt(False), 'no')
        self.assertEqual(zfs.to_bool_alt(zfs.to_bool_alt(False)), 'no')

    def test_to_bool_alt_none(self):
        '''
        Test to_bool_alt with None
        '''
        self.assertEqual(zfs.to_bool_alt(None), 'none')
        self.assertEqual(zfs.to_bool_alt(zfs.to_bool_alt(None)), 'none')

    def test_to_bool_alt_passthrough(self):
        '''
        Test to_bool_alt with 'passthrough'
        '''
        self.assertEqual(zfs.to_bool_alt('passthrough'), 'passthrough')
        self.assertEqual(zfs.to_bool_alt(zfs.to_bool_alt('passthrough')), 'passthrough')

    ## NOTE: testing from_numeric results
    def test_from_numeric_str(self):
        '''
        Test from_numeric with '42'
        '''
        self.assertEqual(zfs.from_numeric('42'), 42)
        self.assertEqual(zfs.from_numeric(zfs.from_numeric('42')), 42)

    def test_from_numeric_int(self):
        '''
        Test from_numeric with 42
        '''
        self.assertEqual(zfs.from_numeric(42), 42)
        self.assertEqual(zfs.from_numeric(zfs.from_numeric(42)), 42)

    def test_from_numeric_none(self):
        '''
        Test from_numeric with 'none'
        '''
        self.assertEqual(zfs.from_numeric('none'), None)
        self.assertEqual(zfs.from_numeric(zfs.from_numeric('none')), None)

    def test_from_numeric_passthrough(self):
        '''
        Test from_numeric with 'passthrough'
        '''
        self.assertEqual(zfs.from_numeric('passthrough'), 'passthrough')
        self.assertEqual(zfs.from_numeric(zfs.from_numeric('passthrough')), 'passthrough')

    ## NOTE: testing to_numeric results
    def test_to_numeric_str(self):
        '''
        Test to_numeric with '42'
        '''
        self.assertEqual(zfs.to_numeric('42'), 42)
        self.assertEqual(zfs.to_numeric(zfs.to_numeric('42')), 42)

    def test_to_numeric_int(self):
        '''
        Test to_numeric with 42
        '''
        self.assertEqual(zfs.to_numeric(42), 42)
        self.assertEqual(zfs.to_numeric(zfs.to_numeric(42)), 42)

    def test_to_numeric_none(self):
        '''
        Test to_numeric with 'none'
        '''
        self.assertEqual(zfs.to_numeric(None), 'none')
        self.assertEqual(zfs.to_numeric(zfs.to_numeric(None)), 'none')

    def test_to_numeric_passthrough(self):
        '''
        Test to_numeric with 'passthrough'
        '''
        self.assertEqual(zfs.to_numeric('passthrough'), 'passthrough')
        self.assertEqual(zfs.to_numeric(zfs.to_numeric('passthrough')), 'passthrough')

    ## NOTE: testing from_size results
    def test_from_size_absolute(self):
        '''
        Test from_size with '5G'
        '''
        self.assertEqual(zfs.from_size('5G'), 5368709120)
        self.assertEqual(zfs.from_size(zfs.from_size('5G')), 5368709120)

    def test_from_size_decimal(self):
        '''
        Test from_size with '4.20M'
        '''
        self.assertEqual(zfs.from_size('4.20M'), 4404019)
        self.assertEqual(zfs.from_size(zfs.from_size('4.20M')), 4404019)

    def test_from_size_none(self):
        '''
        Test from_size with 'none'
        '''
        self.assertEqual(zfs.from_size('none'), None)
        self.assertEqual(zfs.from_size(zfs.from_size('none')), None)

    def test_from_size_passthrough(self):
        '''
        Test from_size with 'passthrough'
        '''
        self.assertEqual(zfs.from_size('passthrough'), 'passthrough')
        self.assertEqual(zfs.from_size(zfs.from_size('passthrough')), 'passthrough')

    ## NOTE: testing to_size results
    def test_to_size_str_absolute(self):
        '''
        Test to_size with '5368709120'
        '''
        self.assertEqual(zfs.to_size('5368709120'), '5G')
        self.assertEqual(zfs.to_size(zfs.to_size('5368709120')), '5G')

    def test_to_size_str_decimal(self):
        '''
        Test to_size with '4404019'
        '''
        self.assertEqual(zfs.to_size('4404019'), '4.20M')
        self.assertEqual(zfs.to_size(zfs.to_size('4404019')), '4.20M')

    def test_to_size_int_absolute(self):
        '''
        Test to_size with 5368709120
        '''
        self.assertEqual(zfs.to_size(5368709120), '5G')
        self.assertEqual(zfs.to_size(zfs.to_size(5368709120)), '5G')

    def test_to_size_int_decimal(self):
        '''
        Test to_size with 4404019
        '''
        self.assertEqual(zfs.to_size(4404019), '4.20M')
        self.assertEqual(zfs.to_size(zfs.to_size(4404019)), '4.20M')

    def test_to_size_none(self):
        '''
        Test to_size with 'none'
        '''
        self.assertEqual(zfs.to_size(None), 'none')
        self.assertEqual(zfs.to_size(zfs.to_size(None)), 'none')

    def test_to_size_passthrough(self):
        '''
        Test to_size with 'passthrough'
        '''
        self.assertEqual(zfs.to_size('passthrough'), 'passthrough')
        self.assertEqual(zfs.to_size(zfs.to_size('passthrough')), 'passthrough')

    ## NOTE: testing from_str results
    def test_from_str_space(self):
        '''
        Test from_str with "\"my pool/my dataset\"
        '''
        self.assertEqual(zfs.from_str('"my pool/my dataset"'), 'my pool/my dataset')
        self.assertEqual(zfs.from_str(zfs.from_str('"my pool/my dataset"')), 'my pool/my dataset')

    def test_from_str_squote_space(self):
        '''
        Test from_str with "my pool/jorge's dataset"
        '''
        self.assertEqual(zfs.from_str("my pool/jorge's dataset"), "my pool/jorge's dataset")
        self.assertEqual(zfs.from_str(zfs.from_str("my pool/jorge's dataset")), "my pool/jorge's dataset")

    def test_from_str_dquote_space(self):
        '''
        Test from_str with "my pool/the \"good\" stuff"
        '''
        self.assertEqual(zfs.from_str("my pool/the \"good\" stuff"), 'my pool/the "good" stuff')
        self.assertEqual(zfs.from_str(zfs.from_str("my pool/the \"good\" stuff")), 'my pool/the "good" stuff')

    def test_from_str_none(self):
        '''
        Test from_str with 'none'
        '''
        self.assertEqual(zfs.from_str('none'), None)
        self.assertEqual(zfs.from_str(zfs.from_str('none')), None)

    def test_from_str_passthrough(self):
        '''
        Test from_str with 'passthrough'
        '''
        self.assertEqual(zfs.from_str('passthrough'), 'passthrough')
        self.assertEqual(zfs.from_str(zfs.from_str('passthrough')), 'passthrough')

    ## NOTE: testing to_str results
    def test_to_str_space(self):
        '''
        Test to_str with 'my pool/my dataset'
        '''
        ## NOTE: for fun we use both the '"str"' and "\"str\"" way of getting the literal string: "str"
        self.assertEqual(zfs.to_str('my pool/my dataset'), '"my pool/my dataset"')
        self.assertEqual(zfs.to_str(zfs.to_str('my pool/my dataset')), "\"my pool/my dataset\"")

    def test_to_str_squote_space(self):
        '''
        Test to_str with "my pool/jorge's dataset"
        '''
        self.assertEqual(zfs.to_str("my pool/jorge's dataset"), "\"my pool/jorge's dataset\"")
        self.assertEqual(zfs.to_str(zfs.to_str("my pool/jorge's dataset")), "\"my pool/jorge's dataset\"")

    def test_to_str_none(self):
        '''
        Test to_str with 'none'
        '''
        self.assertEqual(zfs.to_str(None), 'none')
        self.assertEqual(zfs.to_str(zfs.to_str(None)), 'none')

    def test_to_str_passthrough(self):
        '''
        Test to_str with 'passthrough'
        '''
        self.assertEqual(zfs.to_str('passthrough'), 'passthrough')
        self.assertEqual(zfs.to_str(zfs.to_str('passthrough')), 'passthrough')

    ## NOTE: testing is_snapshot
    def test_is_snapshot_snapshot(self):
        '''
        Test is_snapshot with a valid snapshot name
        '''
        self.assertTrue(zfs.is_snapshot('zpool_name/dataset@backup'))

    def test_is_snapshot_bookmark(self):
        '''
        Test is_snapshot with a valid bookmark name
        '''
        self.assertFalse(zfs.is_snapshot('zpool_name/dataset#backup'))

    def test_is_snapshot_filesystem(self):
        '''
        Test is_snapshot with a valid filesystem name
        '''
        self.assertFalse(zfs.is_snapshot('zpool_name/dataset'))

    ## NOTE: testing is_bookmark
    def test_is_bookmark_snapshot(self):
        '''
        Test is_bookmark with a valid snapshot name
        '''
        self.assertFalse(zfs.is_bookmark('zpool_name/dataset@backup'))

    def test_is_bookmark_bookmark(self):
        '''
        Test is_bookmark with a valid bookmark name
        '''
        self.assertTrue(zfs.is_bookmark('zpool_name/dataset#backup'))

    def test_is_bookmark_filesystem(self):
        '''
        Test is_bookmark with a valid filesystem name
        '''
        self.assertFalse(zfs.is_bookmark('zpool_name/dataset'))

    ## NOTE: testing is_dataset
    def test_is_dataset_snapshot(self):
        '''
        Test is_dataset with a valid snapshot name
        '''
        self.assertFalse(zfs.is_dataset('zpool_name/dataset@backup'))

    def test_is_dataset_bookmark(self):
        '''
        Test is_dataset with a valid bookmark name
        '''
        self.assertFalse(zfs.is_dataset('zpool_name/dataset#backup'))

    def test_is_dataset_filesystem(self):
        '''
        Test is_dataset with a valid filesystem/volume name
        '''
        self.assertTrue(zfs.is_dataset('zpool_name/dataset'))

    ## NOTE: testing zfs_command
    def test_zfs_command_simple(self):
        '''
        Test if zfs_command builds the correct string
        '''
        with patch.object(zfs, '_zfs_cmd', MagicMock(return_value='/sbin/zfs')):
            with patch.object(zfs, '_zpool_cmd', MagicMock(return_value='/sbin/zpool')):
                with patch.object(zfs, 'property_data_zfs', MagicMock(return_value=self.pmap_zfs)):
                    with patch.object(zfs, 'property_data_zpool', MagicMock(return_value=self.pmap_zpool)):
                        self.assertEqual(
                            zfs.zfs_command('list'),
                            "/sbin/zfs list"
                        )

    def test_zfs_command_none_target(self):
        '''
        Test if zfs_command builds the correct string with a target of None
        '''
        with patch.object(zfs, '_zfs_cmd', MagicMock(return_value='/sbin/zfs')):
            with patch.object(zfs, '_zpool_cmd', MagicMock(return_value='/sbin/zpool')):
                with patch.object(zfs, 'property_data_zfs', MagicMock(return_value=self.pmap_zfs)):
                    with patch.object(zfs, 'property_data_zpool', MagicMock(return_value=self.pmap_zpool)):
                        self.assertEqual(
                            zfs.zfs_command('list', target=[None, 'mypool', None]),
                            "/sbin/zfs list mypool"
                        )

    def test_zfs_command_flag(self):
        '''
        Test if zfs_command builds the correct string
        '''
        with patch.object(zfs, '_zfs_cmd', MagicMock(return_value='/sbin/zfs')):
            with patch.object(zfs, '_zpool_cmd', MagicMock(return_value='/sbin/zpool')):
                with patch.object(zfs, 'property_data_zfs', MagicMock(return_value=self.pmap_zfs)):
                    with patch.object(zfs, 'property_data_zpool', MagicMock(return_value=self.pmap_zpool)):
                        my_flags = [
                            '-r',  # recursive
                        ]
                        self.assertEqual(
                            zfs.zfs_command('list', flags=my_flags),
                            "/sbin/zfs list -r"
                        )

    def test_zfs_command_opt(self):
        '''
        Test if zfs_command builds the correct string
        '''
        with patch.object(zfs, '_zfs_cmd', MagicMock(return_value='/sbin/zfs')):
            with patch.object(zfs, '_zpool_cmd', MagicMock(return_value='/sbin/zpool')):
                with patch.object(zfs, 'property_data_zfs', MagicMock(return_value=self.pmap_zfs)):
                    with patch.object(zfs, 'property_data_zpool', MagicMock(return_value=self.pmap_zpool)):
                        my_opts = {
                            '-t': 'snap',  # only list snapshots
                        }
                        self.assertEqual(
                            zfs.zfs_command('list', opts=my_opts),
                            "/sbin/zfs list -t snap"
                        )

    def test_zfs_command_flag_opt(self):
        '''
        Test if zfs_command builds the correct string
        '''
        with patch.object(zfs, '_zfs_cmd', MagicMock(return_value='/sbin/zfs')):
            with patch.object(zfs, '_zpool_cmd', MagicMock(return_value='/sbin/zpool')):
                with patch.object(zfs, 'property_data_zfs', MagicMock(return_value=self.pmap_zfs)):
                    with patch.object(zfs, 'property_data_zpool', MagicMock(return_value=self.pmap_zpool)):
                        my_flags = [
                            '-r',  # recursive
                        ]
                        my_opts = {
                            '-t': 'snap',  # only list snapshots
                        }
                        self.assertEqual(
                            zfs.zfs_command('list', flags=my_flags, opts=my_opts),
                            "/sbin/zfs list -r -t snap"
                        )

    def test_zfs_command_target(self):
        '''
        Test if zfs_command builds the correct string
        '''
        with patch.object(zfs, '_zfs_cmd', MagicMock(return_value='/sbin/zfs')):
            with patch.object(zfs, '_zpool_cmd', MagicMock(return_value='/sbin/zpool')):
                with patch.object(zfs, 'property_data_zfs', MagicMock(return_value=self.pmap_zfs)):
                    with patch.object(zfs, 'property_data_zpool', MagicMock(return_value=self.pmap_zpool)):
                        my_flags = [
                            '-r',  # recursive
                        ]
                        my_opts = {
                            '-t': 'snap',  # only list snapshots
                        }
                        self.assertEqual(
                            zfs.zfs_command('list', flags=my_flags, opts=my_opts, target='mypool'),
                            "/sbin/zfs list -r -t snap mypool"
                        )

    def test_zfs_command_target_with_space(self):
        '''
        Test if zfs_command builds the correct string
        '''
        with patch.object(zfs, '_zfs_cmd', MagicMock(return_value='/sbin/zfs')):
            with patch.object(zfs, '_zpool_cmd', MagicMock(return_value='/sbin/zpool')):
                with patch.object(zfs, 'property_data_zfs', MagicMock(return_value=self.pmap_zfs)):
                    with patch.object(zfs, 'property_data_zpool', MagicMock(return_value=self.pmap_zpool)):
                        my_flags = [
                            '-r',  # recursive
                        ]
                        my_opts = {
                            '-t': 'snap',  # only list snapshots
                        }
                        self.assertEqual(
                            zfs.zfs_command('list', flags=my_flags, opts=my_opts, target='my pool'),
                            '/sbin/zfs list -r -t snap "my pool"'
                        )

    def test_zfs_command_property(self):
        '''
        Test if zfs_command builds the correct string
        '''
        with patch.object(zfs, '_zfs_cmd', MagicMock(return_value='/sbin/zfs')):
            with patch.object(zfs, '_zpool_cmd', MagicMock(return_value='/sbin/zpool')):
                with patch.object(zfs, 'property_data_zfs', MagicMock(return_value=self.pmap_zfs)):
                    with patch.object(zfs, 'property_data_zpool', MagicMock(return_value=self.pmap_zpool)):
                        self.assertEqual(
                            zfs.zfs_command('get', property_name='quota', target='mypool'),
                            "/sbin/zfs get quota mypool"
                        )

    def test_zfs_command_property_value(self):
        '''
        Test if zfs_command builds the correct string
        '''
        with patch.object(zfs, '_zfs_cmd', MagicMock(return_value='/sbin/zfs')):
            with patch.object(zfs, '_zpool_cmd', MagicMock(return_value='/sbin/zpool')):
                with patch.object(zfs, 'property_data_zfs', MagicMock(return_value=self.pmap_zfs)):
                    with patch.object(zfs, 'property_data_zpool', MagicMock(return_value=self.pmap_zpool)):
                        my_flags = [
                            '-r',  # recursive
                        ]
                        self.assertEqual(
                            zfs.zfs_command('set', flags=my_flags, property_name='quota', property_value='5G', target='mypool'),
                            "/sbin/zfs set -r quota=5368709120 mypool"
                        )

    def test_zfs_command_multi_property_value(self):
        '''
        Test if zfs_command builds the correct string
        '''
        with patch.object(zfs, '_zfs_cmd', MagicMock(return_value='/sbin/zfs')):
            with patch.object(zfs, '_zpool_cmd', MagicMock(return_value='/sbin/zpool')):
                with patch.object(zfs, 'property_data_zfs', MagicMock(return_value=self.pmap_zfs)):
                    with patch.object(zfs, 'property_data_zpool', MagicMock(return_value=self.pmap_zpool)):
                        property_name = ['quota', 'readonly']
                        property_value = ['5G', 'no']
                        self.assertEqual(
                            zfs.zfs_command('set', property_name=property_name, property_value=property_value, target='mypool'),
                            "/sbin/zfs set quota=5368709120 readonly=off mypool"
                        )

    def test_zfs_command_fs_props(self):
        '''
        Test if zfs_command builds the correct string
        '''
        with patch.object(zfs, '_zfs_cmd', MagicMock(return_value='/sbin/zfs')):
            with patch.object(zfs, '_zpool_cmd', MagicMock(return_value='/sbin/zpool')):
                with patch.object(zfs, 'property_data_zfs', MagicMock(return_value=self.pmap_zfs)):
                    with patch.object(zfs, 'property_data_zpool', MagicMock(return_value=self.pmap_zpool)):
                        my_flags = [
                            '-p',  # create parent
                        ]
                        my_props = {
                            'quota': '1G',
                            'compression': 'lz4',
                        }
                        self.assertEqual(
                            zfs.zfs_command('create', flags=my_flags, filesystem_properties=my_props, target='mypool/dataset'),
                            "/sbin/zfs create -p -o compression=lz4 -o quota=1073741824 mypool/dataset"
                        )

    def test_zfs_command_fs_props_with_space(self):
        '''
        Test if zfs_command builds the correct string
        '''
        with patch.object(zfs, '_zfs_cmd', MagicMock(return_value='/sbin/zfs')):
            with patch.object(zfs, '_zpool_cmd', MagicMock(return_value='/sbin/zpool')):
                with patch.object(zfs, 'property_data_zfs', MagicMock(return_value=self.pmap_zfs)):
                    with patch.object(zfs, 'property_data_zpool', MagicMock(return_value=self.pmap_zpool)):
                        my_props = {
                            'quota': '4.2M',
                            'compression': 'lz4',
                        }
                        self.assertEqual(
                            zfs.zfs_command('create', filesystem_properties=my_props, target="my pool/jorge's dataset"),
                            '/sbin/zfs create -o compression=lz4 -o quota=4404019 "my pool/jorge\'s dataset"'
                        )

    ## NOTE: testing zpool_command
    def test_zpool_command_simple(self):
        '''
        Test if zfs_command builds the correct string
        '''
        with patch.object(zfs, '_zfs_cmd', MagicMock(return_value='/sbin/zfs')):
            with patch.object(zfs, '_zpool_cmd', MagicMock(return_value='/sbin/zpool')):
                with patch.object(zfs, 'property_data_zfs', MagicMock(return_value=self.pmap_zfs)):
                    with patch.object(zfs, 'property_data_zpool', MagicMock(return_value=self.pmap_zpool)):
                        self.assertEqual(
                            zfs.zpool_command('list'),
                            "/sbin/zpool list"
                        )

    def test_zpool_command_opt(self):
        '''
        Test if zpool_command builds the correct string
        '''
        with patch.object(zfs, '_zfs_cmd', MagicMock(return_value='/sbin/zfs')):
            with patch.object(zfs, '_zpool_cmd', MagicMock(return_value='/sbin/zpool')):
                with patch.object(zfs, 'property_data_zfs', MagicMock(return_value=self.pmap_zfs)):
                    with patch.object(zfs, 'property_data_zpool', MagicMock(return_value=self.pmap_zpool)):
                        my_opts = {
                            '-o': 'name,size',  # show only name and size
                        }
                        self.assertEqual(
                            zfs.zpool_command('list', opts=my_opts),
                            "/sbin/zpool list -o name,size"
                        )

    def test_zpool_command_opt_list(self):
        '''
        Test if zpool_command builds the correct string
        '''
        with patch.object(zfs, '_zfs_cmd', MagicMock(return_value='/sbin/zfs')):
            with patch.object(zfs, '_zpool_cmd', MagicMock(return_value='/sbin/zpool')):
                with patch.object(zfs, 'property_data_zfs', MagicMock(return_value=self.pmap_zfs)):
                    with patch.object(zfs, 'property_data_zpool', MagicMock(return_value=self.pmap_zpool)):
                        my_opts = {
                            '-d': ['/tmp', '/zvol'],
                        }
                        self.assertEqual(
                            zfs.zpool_command('import', opts=my_opts, target='mypool'),
                            "/sbin/zpool import -d /tmp -d /zvol mypool"
                        )

    def test_zpool_command_flag_opt(self):
        '''
        Test if zpool_command builds the correct string
        '''
        with patch.object(zfs, '_zfs_cmd', MagicMock(return_value='/sbin/zfs')):
            with patch.object(zfs, '_zpool_cmd', MagicMock(return_value='/sbin/zpool')):
                with patch.object(zfs, 'property_data_zfs', MagicMock(return_value=self.pmap_zfs)):
                    with patch.object(zfs, 'property_data_zpool', MagicMock(return_value=self.pmap_zpool)):
                        my_opts = {
                            '-o': 'name,size',  # show only name and size
                        }
                        self.assertEqual(
                            zfs.zpool_command('list', opts=my_opts),
                            "/sbin/zpool list -o name,size"
                        )

    def test_zpool_command_target(self):
        '''
        Test if zpool_command builds the correct string
        '''
        with patch.object(zfs, '_zfs_cmd', MagicMock(return_value='/sbin/zfs')):
            with patch.object(zfs, '_zpool_cmd', MagicMock(return_value='/sbin/zpool')):
                with patch.object(zfs, 'property_data_zfs', MagicMock(return_value=self.pmap_zfs)):
                    with patch.object(zfs, 'property_data_zpool', MagicMock(return_value=self.pmap_zpool)):
                        my_opts = {
                            '-o': 'name,size',  # show only name and size
                        }
                        self.assertEqual(
                            zfs.zpool_command('list', opts=my_opts, target='mypool'),
                            "/sbin/zpool list -o name,size mypool"
                        )

    def test_zpool_command_target_with_space(self):
        '''
        Test if zpool_command builds the correct string
        '''
        with patch.object(zfs, '_zfs_cmd', MagicMock(return_value='/sbin/zfs')):
            with patch.object(zfs, '_zpool_cmd', MagicMock(return_value='/sbin/zpool')):
                with patch.object(zfs, 'property_data_zfs', MagicMock(return_value=self.pmap_zfs)):
                    with patch.object(zfs, 'property_data_zpool', MagicMock(return_value=self.pmap_zpool)):
                        fs_props = {
                            'quota': '100G',
                        }
                        pool_props = {
                            'comment': "jorge's comment has a space",
                        }
                        self.assertEqual(
                            zfs.zpool_command('create', pool_properties=pool_props, filesystem_properties=fs_props, target='my pool'),
                            "/sbin/zpool create -O quota=107374182400 -o comment=\"jorge's comment has a space\" \"my pool\""
                        )

    def test_zpool_command_property(self):
        '''
        Test if zpool_command builds the correct string
        '''
        with patch.object(zfs, '_zfs_cmd', MagicMock(return_value='/sbin/zfs')):
            with patch.object(zfs, '_zpool_cmd', MagicMock(return_value='/sbin/zpool')):
                with patch.object(zfs, 'property_data_zfs', MagicMock(return_value=self.pmap_zfs)):
                    with patch.object(zfs, 'property_data_zpool', MagicMock(return_value=self.pmap_zpool)):
                        self.assertEqual(
                            zfs.zpool_command('get', property_name='comment', target='mypool'),
                            "/sbin/zpool get comment mypool"
                        )

    def test_zpool_command_property_value(self):
        '''
        Test if zpool_command builds the correct string
        '''
        with patch.object(zfs, '_zfs_cmd', MagicMock(return_value='/sbin/zfs')):
            with patch.object(zfs, '_zpool_cmd', MagicMock(return_value='/sbin/zpool')):
                with patch.object(zfs, 'property_data_zfs', MagicMock(return_value=self.pmap_zfs)):
                    with patch.object(zfs, 'property_data_zpool', MagicMock(return_value=self.pmap_zpool)):
                        my_flags = [
                            '-v',  # verbose
                        ]
                        self.assertEqual(
                            zfs.zpool_command('iostat', flags=my_flags, target=['mypool', 60, 1]),
                            "/sbin/zpool iostat -v mypool 60 1"
                        )

    def test_parse_command_result_success(self):
        '''
        Test if parse_command_result returns the expected result
        '''
        with patch.object(zfs, '_zfs_cmd', MagicMock(return_value='/sbin/zfs')):
            with patch.object(zfs, '_zpool_cmd', MagicMock(return_value='/sbin/zpool')):
                with patch.object(zfs, 'property_data_zfs', MagicMock(return_value=self.pmap_zfs)):
                    with patch.object(zfs, 'property_data_zpool', MagicMock(return_value=self.pmap_zpool)):
                        res = {}
                        res['retcode'] = 0
                        res['stderr'] = ''
                        res['stdout'] = ''
                        self.assertEqual(
                            zfs.parse_command_result(res, 'tested'),
                            OrderedDict([('tested', True)]),
                        )

    def test_parse_command_result_success_nolabel(self):
        '''
        Test if parse_command_result returns the expected result
        '''
        with patch.object(zfs, '_zfs_cmd', MagicMock(return_value='/sbin/zfs')):
            with patch.object(zfs, '_zpool_cmd', MagicMock(return_value='/sbin/zpool')):
                with patch.object(zfs, 'property_data_zfs', MagicMock(return_value=self.pmap_zfs)):
                    with patch.object(zfs, 'property_data_zpool', MagicMock(return_value=self.pmap_zpool)):
                        res = {}
                        res['retcode'] = 0
                        res['stderr'] = ''
                        res['stdout'] = ''
                        self.assertEqual(
                            zfs.parse_command_result(res),
                            OrderedDict(),
                        )

    def test_parse_command_result_fail(self):
        '''
        Test if parse_command_result returns the expected result on failure
        '''
        with patch.object(zfs, '_zfs_cmd', MagicMock(return_value='/sbin/zfs')):
            with patch.object(zfs, '_zpool_cmd', MagicMock(return_value='/sbin/zpool')):
                with patch.object(zfs, 'property_data_zfs', MagicMock(return_value=self.pmap_zfs)):
                    with patch.object(zfs, 'property_data_zpool', MagicMock(return_value=self.pmap_zpool)):
                        res = {}
                        res['retcode'] = 1
                        res['stderr'] = ''
                        res['stdout'] = ''
                        self.assertEqual(
                            zfs.parse_command_result(res, 'tested'),
                            OrderedDict([('tested', False)]),
                        )

    def test_parse_command_result_nolabel(self):
        '''
        Test if parse_command_result returns the expected result on failure
        '''
        with patch.object(zfs, '_zfs_cmd', MagicMock(return_value='/sbin/zfs')):
            with patch.object(zfs, '_zpool_cmd', MagicMock(return_value='/sbin/zpool')):
                with patch.object(zfs, 'property_data_zfs', MagicMock(return_value=self.pmap_zfs)):
                    with patch.object(zfs, 'property_data_zpool', MagicMock(return_value=self.pmap_zpool)):
                        res = {}
                        res['retcode'] = 1
                        res['stderr'] = ''
                        res['stdout'] = ''
                        self.assertEqual(
                            zfs.parse_command_result(res),
                            OrderedDict(),
                        )

    def test_parse_command_result_fail_message(self):
        '''
        Test if parse_command_result returns the expected result on failure with stderr
        '''
        with patch.object(zfs, '_zfs_cmd', MagicMock(return_value='/sbin/zfs')):
            with patch.object(zfs, '_zpool_cmd', MagicMock(return_value='/sbin/zpool')):
                with patch.object(zfs, 'property_data_zfs', MagicMock(return_value=self.pmap_zfs)):
                    with patch.object(zfs, 'property_data_zpool', MagicMock(return_value=self.pmap_zpool)):
                        res = {}
                        res['retcode'] = 1
                        res['stderr'] = "\n".join([
                            'ice is not hot',
                            'usage:',
                            'this should not be printed',
                        ])
                        res['stdout'] = ''
                        self.assertEqual(
                            zfs.parse_command_result(res, 'tested'),
                            OrderedDict([('tested', False), ('error', 'ice is not hot')]),
                        )

    def test_parse_command_result_fail_message_nolabel(self):
        '''
        Test if parse_command_result returns the expected result on failure with stderr
        '''
        with patch.object(zfs, '_zfs_cmd', MagicMock(return_value='/sbin/zfs')):
            with patch.object(zfs, '_zpool_cmd', MagicMock(return_value='/sbin/zpool')):
                with patch.object(zfs, 'property_data_zfs', MagicMock(return_value=self.pmap_zfs)):
                    with patch.object(zfs, 'property_data_zpool', MagicMock(return_value=self.pmap_zpool)):
                        res = {}
                        res['retcode'] = 1
                        res['stderr'] = "\n".join([
                            'ice is not hot',
                            'usage:',
                            'this should not be printed',
                        ])
                        res['stdout'] = ''
                        self.assertEqual(
                            zfs.parse_command_result(res),
                            OrderedDict([('error', 'ice is not hot')]),
                        )

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
