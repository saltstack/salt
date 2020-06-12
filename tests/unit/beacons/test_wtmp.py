# coding: utf-8

# Python libs
from __future__ import absolute_import
import datetime
import logging

# Salt testing libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch, MagicMock, mock_open
from tests.support.mixins import LoaderModuleMockMixin

# Salt libs
import salt.beacons.wtmp as wtmp
from salt.ext import six

# pylint: disable=import-error
try:
    import dateutil.parser as dateutil_parser  # pylint: disable=unused-import
    _TIME_SUPPORTED = True
except ImportError:
    _TIME_SUPPORTED = False

raw = b'\x07\x00\x00\x00H\x18\x00\x00pts/14\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00s/14gareth\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00::1\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x13I\xc5YZf\x05\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
pack = (7, 6216, b'pts/14\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00', b's/14', b'gareth\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00', b'::1\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00', 0, 0, 0, 1506101523, 353882, 0, 0, 0, 16777216)

log = logging.getLogger(__name__)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class WTMPBeaconTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test case for salt.beacons.[s]
    '''

    def setup_loader_modules(self):
        return {
            wtmp: {
                '__context__': {'wtmp.loc': 2},
                '__salt__': {},
            }
        }

    def test_non_list_config(self):
        config = {}
        ret = wtmp.validate(config)

        self.assertEqual(ret, (False, 'Configuration for wtmp beacon must'
                                      ' be a list.'))

    def test_empty_config(self):
        config = [{}]

        ret = wtmp.validate(config)

        self.assertEqual(ret, (True, 'Valid beacon configuration'))

    def test_no_match(self):
        config = [{'users': {'gareth': {'time_range': {'end': '09-22-2017 5pm',
                                                       'start': '09-22-2017 3pm'}}}}
                  ]

        ret = wtmp.validate(config)

        self.assertEqual(ret, (True, 'Valid beacon configuration'))

        with patch('salt.utils.files.fopen', mock_open(b'')) as m_open:
            ret = wtmp.beacon(config)
            call_args = next(six.itervalues(m_open.filehandles))[0].call.args
            assert call_args == (wtmp.WTMP, 'rb'), call_args
            assert ret == [], ret

    def test_invalid_users(self):
        config = [{'users': ['gareth']}]

        ret = wtmp.validate(config)

        self.assertEqual(ret, (False, 'User configuration for wtmp beacon must be a dictionary.'))

    def test_invalid_groups(self):
        config = [{'groups': ['docker']}]

        ret = wtmp.validate(config)

        self.assertEqual(ret, (False, 'Group configuration for wtmp beacon must be a dictionary.'))

    def test_default_invalid_time_range(self):
        config = [{'defaults': {'time_range': {'start': '3pm'}}}]

        ret = wtmp.validate(config)

        self.assertEqual(ret, (False, 'The time_range parameter for wtmp beacon must contain start & end options.'))

    def test_users_invalid_time_range(self):
        config = [{'users': {'gareth': {'time_range': {'start': '3pm'}}}}]

        ret = wtmp.validate(config)

        self.assertEqual(ret, (False, 'The time_range parameter for wtmp beacon must contain start & end options.'))

    def test_groups_invalid_time_range(self):
        config = [{'groups': {'docker': {'time_range': {'start': '3pm'}}}}]

        ret = wtmp.validate(config)

        self.assertEqual(ret, (False, 'The time_range parameter for wtmp beacon must contain start & end options.'))

    def test_match(self):
        with patch('salt.utils.files.fopen',
                   mock_open(read_data=raw)):
            with patch('struct.unpack',
                       MagicMock(return_value=pack)):
                config = [{'users': {'gareth': {}}}]

                ret = wtmp.validate(config)

                self.assertEqual(ret, (True, 'Valid beacon configuration'))

                _expected = [{'PID': 6216,
                              'action': 'login',
                              'line': 'pts/14',
                              'session': 0,
                              'time': 0,
                              'exit_status': 0,
                              'inittab': 's/14',
                              'type': 7,
                              'addr': 1506101523,
                              'hostname': '::1',
                              'user': 'gareth'}]

                ret = wtmp.beacon(config)
                log.debug('%s', ret)
                self.assertEqual(ret, _expected)

    @skipIf(not _TIME_SUPPORTED, 'dateutil.parser is missing.')
    def test_match_time(self):
        with patch('salt.utils.files.fopen',
                   mock_open(read_data=raw)):
            mock_now = datetime.datetime(2017, 9, 22, 16, 0, 0, 0)
            with patch('datetime.datetime', MagicMock()), \
                    patch('datetime.datetime.now',
                          MagicMock(return_value=mock_now)):
                with patch('struct.unpack',
                           MagicMock(return_value=pack)):
                    config = [{'users': {'gareth': {'time': {'end': '09-22-2017 5pm',
                                                             'start': '09-22-2017 3pm'}}}}
                              ]

                    ret = wtmp.validate(config)

                    self.assertEqual(ret, (True, 'Valid beacon configuration'))

                    _expected = [{'PID': 6216,
                                  'action': 'login',
                                  'line': 'pts/14',
                                  'session': 0,
                                  'time': 0,
                                  'exit_status': 0,
                                  'inittab': 's/14',
                                  'type': 7,
                                  'addr': 1506101523,
                                  'hostname': '::1',
                                  'user': 'gareth'}]

                    ret = wtmp.beacon(config)
                    self.assertEqual(ret, _expected)

    def test_match_group(self):

        for groupadd in ('salt.modules.aix_group',
                         'salt.modules.mac_group',
                         'salt.modules.pw_group',
                         'salt.modules.solaris_group',
                         'salt.modules.win_groupadd'):
            mock_group_info = {'passwd': 'x',
                               'gid': 100,
                               'name': 'users',
                               'members': ['gareth']}

            with patch('salt.utils.files.fopen',
                       mock_open(read_data=raw)):
                with patch('time.time',
                           MagicMock(return_value=1506121200)):
                    with patch('struct.unpack',
                               MagicMock(return_value=pack)):
                        with patch('{0}.info'.format(groupadd),
                                   new=MagicMock(return_value=mock_group_info)):
                            config = [{'group': {'users': {'time': {'end': '09-22-2017 5pm',
                                                                    'start': '09-22-2017 3pm'}}}}
                                      ]

                            ret = wtmp.validate(config)

                            self.assertEqual(ret,
                                             (True, 'Valid beacon configuration'))

                            _expected = [{'PID': 6216,
                                          'action': 'login',
                                          'line': 'pts/14',
                                          'session': 0,
                                          'time': 0,
                                          'exit_status': 0,
                                          'inittab': 's/14',
                                          'type': 7,
                                          'addr': 1506101523,
                                          'hostname': '::1',
                                          'user': 'gareth'}]

                            ret = wtmp.beacon(config)
                            self.assertEqual(ret, _expected)
