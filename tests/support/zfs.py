# -*- coding: utf-8 -*-
'''
    tests.support.zfs
    ~~~~~~~~~~~~~~~~~

    ZFS related unit test data structures
'''

# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function

# Import salt libs
import salt.utils.zfs

# Import Salt tests libs
from tests.support.mock import MagicMock, patch


class ZFSMockData(object):

    def __init__(self):
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

    def _from_auto(self, name, value, source='auto'):
        '''
        some more complex patching for zfs.from_auto
        '''
        with patch.object(salt.utils.zfs, 'property_data_zpool', MagicMock(return_value=self.pmap_zpool)), \
                patch.object(salt.utils.zfs, 'property_data_zfs', MagicMock(return_value=self.pmap_zfs)):
            return salt.utils.zfs.from_auto(name, value, source)

    def _from_auto_dict(self, values, source='auto'):
        '''
        some more complex patching for zfs.from_auto_dict
        '''
        with patch.object(salt.utils.zfs, 'property_data_zpool', MagicMock(return_value=self.pmap_zpool)), \
                patch.object(salt.utils.zfs, 'property_data_zfs', MagicMock(return_value=self.pmap_zfs)):
            return salt.utils.zfs.from_auto_dict(values, source)

    def _to_auto(self, name, value, source='auto', convert_to_human=True):
        '''
        some more complex patching for zfs.to_auto
        '''
        with patch.object(salt.utils.zfs, 'property_data_zpool', MagicMock(return_value=self.pmap_zpool)), \
                patch.object(salt.utils.zfs, 'property_data_zfs', MagicMock(return_value=self.pmap_zfs)):
            return salt.utils.zfs.to_auto(name, value, source, convert_to_human)

    def _to_auto_dict(self, values, source='auto', convert_to_human=True):
        '''
        some more complex patching for zfs.to_auto_dict
        '''
        with patch.object(salt.utils.zfs, 'property_data_zpool', MagicMock(return_value=self.pmap_zpool)), \
                patch.object(salt.utils.zfs, 'property_data_zfs', MagicMock(return_value=self.pmap_zfs)):
            return salt.utils.zfs.to_auto_dict(values, source, convert_to_human)

    def get_patched_utils(self):
        return {
            'zfs.is_supported': MagicMock(return_value=True),
            'zfs.has_feature_flags': MagicMock(return_value=True),
            'zfs.property_data_zpool': MagicMock(return_value=self.pmap_zpool),
            'zfs.property_data_zfs': MagicMock(return_value=self.pmap_zfs),
            # NOTE: we make zpool_command and zfs_command a NOOP
            #       these are extensively tested in tests.unit.utils.test_zfs
            'zfs.zpool_command': MagicMock(return_value='/bin/false'),
            'zfs.zfs_command': MagicMock(return_value='/bin/false'),
            # NOTE: from_auto_dict is a special snowflake
            #       internally it calls multiple calls from
            #       salt.utils.zfs but we cannot patch those using
            #       the common methode, __utils__ is not available
            #       so they are direct calls, we do some voodoo here.
            'zfs.from_auto_dict': self._from_auto_dict,
            'zfs.from_auto': self._from_auto,
            'zfs.to_auto_dict': self._to_auto_dict,
            'zfs.to_auto': self._to_auto,
        }
