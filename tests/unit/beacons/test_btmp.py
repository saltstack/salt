# coding: utf-8

# Python libs
from __future__ import absolute_import
import datetime
import logging

# Salt testing libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import patch, MagicMock, mock_open
from tests.support.mixins import LoaderModuleMockMixin

# Salt libs
import salt.beacons.btmp as btmp
from salt.ext import six

# pylint: disable=import-error
try:
    import dateutil.parser as dateutil_parser  # pylint: disable=unused-import
    _TIME_SUPPORTED = True
except ImportError:
    _TIME_SUPPORTED = False

raw = b'\x06\x00\x00\x00Nt\x00\x00ssh:notty\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00garet\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00::1\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xdd\xc7\xc2Y\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
pack = (6, 29774, b'ssh:notty\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00', b'\x00\x00\x00\x00', b'garet\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00', b'::1\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00', 0, 0, 0, 1505937373, 0, 0, 0, 0, 16777216)

log = logging.getLogger(__name__)


class BTMPBeaconTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test case for salt.beacons.[s]
    '''

    def setup_loader_modules(self):
        return {
            btmp: {
                '__context__': {'btmp.loc': 2},
                '__salt__': {},
            }
        }

    def test_non_list_config(self):
        config = {}
        ret = btmp.validate(config)

        self.assertEqual(ret, (False, 'Configuration for btmp beacon must'
                                      ' be a list.'))

    def test_empty_config(self):
        config = [{}]

        ret = btmp.validate(config)

        self.assertEqual(ret, (True, 'Valid beacon configuration'))

    def test_no_match(self):
        config = [{'users': {'gareth': {'time_range': {'end': '09-22-2017 5pm',
                                                       'start': '09-22-2017 3pm'}}}}
                  ]

        ret = btmp.validate(config)

        self.assertEqual(ret, (True, 'Valid beacon configuration'))

        with patch('salt.utils.files.fopen', mock_open(b'')) as m_open:
            ret = btmp.beacon(config)
            call_args = next(six.itervalues(m_open.filehandles))[0].call.args
            assert call_args == (btmp.BTMP, 'rb'), call_args
            assert ret == [], ret

    def test_invalid_users(self):
        config = [{'users': ['gareth']}]

        ret = btmp.validate(config)

        self.assertEqual(ret, (False, 'User configuration for btmp beacon must be a dictionary.'))

    def test_invalid_groups(self):
        config = [{'groups': ['docker']}]

        ret = btmp.validate(config)

        self.assertEqual(ret, (False, 'Group configuration for btmp beacon must be a dictionary.'))

    def test_default_invalid_time_range(self):
        config = [{'defaults': {'time_range': {'start': '3pm'}}}]

        ret = btmp.validate(config)

        self.assertEqual(ret, (False, 'The time_range parameter for btmp beacon must contain start & end options.'))

    def test_users_invalid_time_range(self):
        config = [{'users': {'gareth': {'time_range': {'start': '3pm'}}}}]

        ret = btmp.validate(config)

        self.assertEqual(ret, (False, 'The time_range parameter for btmp beacon must contain start & end options.'))

    def test_groups_invalid_time_range(self):
        config = [{'groups': {'docker': {'time_range': {'start': '3pm'}}}}]

        ret = btmp.validate(config)

        self.assertEqual(ret, (False, 'The time_range parameter for btmp beacon must contain start & end options.'))

    def test_match(self):
        with patch('salt.utils.files.fopen',
                   mock_open(read_data=raw)):
            with patch('struct.unpack',
                       MagicMock(return_value=pack)):
                config = [{'users': {'garet': {}}}]

                ret = btmp.validate(config)

                self.assertEqual(ret, (True, 'Valid beacon configuration'))

                _expected = [{'addr': 1505937373,
                              'exit_status': 0,
                              'inittab': '',
                              'hostname': '::1',
                              'PID': 29774,
                              'session': 0,
                              'user':
                              'garet',
                              'time': 0,
                              'line': 'ssh:notty',
                              'type': 6}]
                ret = btmp.beacon(config)
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
                    config = [{'users': {'garet': {'time_range': {'end': '09-22-2017 5pm',
                                                                  'start': '09-22-2017 3pm'}}}}
                              ]

                    ret = btmp.validate(config)

                    self.assertEqual(ret, (True, 'Valid beacon configuration'))

                    _expected = [{'addr': 1505937373,
                                  'exit_status': 0,
                                  'inittab': '',
                                  'hostname': '::1',
                                  'PID': 29774,
                                  'session': 0,
                                  'user':
                                  'garet',
                                  'time': 0,
                                  'line': 'ssh:notty',
                                  'type': 6}]
                    ret = btmp.beacon(config)
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
                               'members': ['garet']}

            with patch('salt.utils.files.fopen',
                       mock_open(read_data=raw)):
                with patch('time.time',
                           MagicMock(return_value=1506121200)):
                    with patch('struct.unpack',
                               MagicMock(return_value=pack)):
                        with patch('{0}.info'.format(groupadd),
                                   new=MagicMock(return_value=mock_group_info)):
                            config = [{'group': {'users': {'time_range': {'end': '5pm',
                                                                          'start': '3pm'}}}}
                                      ]

                            ret = btmp.validate(config)

                            self.assertEqual(ret,
                                             (True, 'Valid beacon configuration'))

                            _expected = [{'addr': 1505937373,
                                          'exit_status': 0,
                                          'inittab': '',
                                          'hostname': '::1',
                                          'PID': 29774,
                                          'session': 0,
                                          'user':
                                          'garet',
                                          'time': 0,
                                          'line': 'ssh:notty',
                                          'type': 6}]
                            ret = btmp.beacon(config)
                            self.assertEqual(ret, _expected)
