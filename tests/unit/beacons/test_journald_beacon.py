# coding: utf-8

# Python libs
from __future__ import absolute_import
import datetime
from uuid import UUID

# Salt testing libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, Mock
from tests.support.mixins import LoaderModuleMockMixin

# Salt libs
import salt.beacons.journald as journald
import salt.utils.data

import logging
log = logging.getLogger(__name__)

_STUB_JOURNALD_ENTRY = {'_BOOT_ID': UUID('ad3915a5-9008-4fec-a635-140606525497'),
                        '__MONOTONIC_TIMESTAMP': (datetime.timedelta(4, 28586, 703069),
                                                  UUID('ad3915a5-9008-4fec-a635-140606525497')),
                        '_AUDIT_LOGINUID': 1000, 'SYSLOG_FACILITY': 10,
                        '_SYSTEMD_SLICE': u'system.slice',
                        '_GID': 0,
                        '__REALTIME_TIMESTAMP': datetime.datetime(2017, 6, 27,
                                                                  20, 8, 16,
                                                                  468468),
                        '_AUDIT_SESSION': 351, 'PRIORITY': 6,
                        '_TRANSPORT': u'syslog',
                        '_HOSTNAME': u'hostname',
                        '_CAP_EFFECTIVE': u'3fffffffff',
                        '_SYSTEMD_UNIT': u'ssh.service',
                        '_MACHINE_ID': UUID('14fab5bb-228d-414b-bdf4-cbc62cb7ba54'),
                        '_PID': 15091,
                        'SYSLOG_IDENTIFIER': u'sshd',
                        '_SOURCE_REALTIME_TIMESTAMP': datetime.datetime(2017,
                                                                        6,
                                                                        27,
                                                                        20,
                                                                        8,
                                                                        16,
                                                                        468454),
                        '_SYSTEMD_CGROUP': u'/system.slice/ssh.service',
                        '__CURSOR': 's=7711ee01b03446309383870171dd5839;i=a74e;b=ad3915a590084feca635140606525497;m=571f43f8 dd;t=552fc7ed1cdf4;x=4ca0a3d4f1905736',
                        '_COMM': u'sshd',
                        '_CMDLINE': u'sshd: gareth [priv]',
                        '_SYSTEMD_INVOCATION_ID': u'38a5d5aad292426d93bfaab72a69c2ab',
                        '_EXE': u'/usr/sbin/sshd',
                        '_UID': 0,
                        'SYSLOG_PID': 15091,
                        'MESSAGE': u'pam_unix(sshd:session): session opened for user username by (uid=0)'}


class SystemdJournaldMock(Mock):
    ''' Request Mock'''

    returned_once = False

    def get_next(self, *args, **kwargs):
        if not self.returned_once:
            self.returned_once = True
            return _STUB_JOURNALD_ENTRY
        else:
            return None

    def seek_tail(self, *args, **kwargs):
        return {}

    def get_previous(self, *args, **kwargs):
        return {}


SYSTEMD_MOCK = SystemdJournaldMock()


@skipIf(NO_MOCK, NO_MOCK_REASON)
class JournaldBeaconTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test case for salt.beacons.journald
    '''

    def setup_loader_modules(self):
        return {
            journald: {
                '__context__': {
                    'systemd.journald': SYSTEMD_MOCK,
                },
                '__salt__': {},
            }
        }

    def test_non_list_config(self):
        config = {}

        ret = journald.validate(config)

        self.assertEqual(ret, (False, 'Configuration for journald beacon must'
                                      ' be a list.'))

    def test_empty_config(self):
        config = [{}]

        ret = journald.validate(config)

        self.assertEqual(ret, (True, 'Valid beacon configuration'))

    def test_journald_match(self):
        config = [{'services': {'sshd': {'SYSLOG_IDENTIFIER': 'sshd',
                                         'PRIORITY': 6}}}]

        ret = journald.validate(config)

        self.assertEqual(ret, (True, 'Valid beacon configuration'))

        _expected_return = salt.utils.data.simple_types_filter(_STUB_JOURNALD_ENTRY)
        _expected_return['tag'] = 'sshd'

        ret = journald.beacon(config)
        self.assertEqual(ret, [_expected_return])
