# coding: utf-8

# Python libs
from __future__ import absolute_import

# Salt testing libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch, mock_open
from tests.support.mixins import LoaderModuleMockMixin

# Salt libs
import salt.beacons.log as log

import logging
_log = logging.getLogger(__name__)


_STUB_LOG_ENTRY = 'Jun 29 12:58:51 hostname sshd[6536]: ' \
                  'pam_unix(sshd:session): session opened ' \
                  'for user username by (uid=0)\n'


@skipIf(NO_MOCK, NO_MOCK_REASON)
class LogBeaconTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test case for salt.beacons.log
    '''

    def setup_loader_modules(self):
        return {
            log: {
                '__context__': {'log.loc': 2},
                '__salt__': {},
            }
        }

    def test_non_list_config(self):
        config = {}

        ret = log.validate(config)

        self.assertEqual(ret, (False, 'Configuration for log beacon must'
                                      ' be a list.'))

    def test_empty_config(self):
        config = [{}]

        ret = log.validate(config)

        self.assertEqual(ret, (False, 'Configuration for log beacon '
                                      'must contain file option.'))

    def test_log_match(self):
        with patch('salt.utils.files.fopen',
                   mock_open(read_data=_STUB_LOG_ENTRY)):
            config = [{'file': '/var/log/auth.log',
                       'tags': {'sshd': {'regex': '.*sshd.*'}}
                       }]

            ret = log.validate(config)

            self.assertEqual(ret, (True, 'Valid beacon configuration'))

            _expected_return = [{'error': '',
                                 'match': 'yes',
                                 'raw': _STUB_LOG_ENTRY.rstrip('\n'),
                                 'tag': 'sshd'
                                 }]
            ret = log.beacon(config)
            self.assertEqual(ret, _expected_return)
