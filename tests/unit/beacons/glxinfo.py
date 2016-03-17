# coding: utf-8

# Python libs
from __future__ import absolute_import

# Salt libs
from salt.beacons import glxinfo

# Salt testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, patch, Mock

# Globals

glxinfo.__salt__ = {}

ensure_in_syspath('../../')


@skipIf(NO_MOCK, NO_MOCK_REASON)
class GLXInfoBeaconTestCase(TestCase):
    '''
    Test case for salt.beacons.glxinfo
    '''
    def setUp(self):
        glxinfo.last_state = {}

    def test_no_adb_command(self):
        with patch('salt.utils.which') as mock:
            mock.return_value = None

            ret = glxinfo.__virtual__()

            mock.assert_called_once_with('glxinfo')
            self.assertFalse(ret)

    def test_with_adb_command(self):
        with patch('salt.utils.which') as mock:
            mock.return_value = '/usr/bin/glxinfo'

            ret = glxinfo.__virtual__()

            mock.assert_called_once_with('glxinfo')
            self.assertEqual(ret, 'glxinfo')

    def test_non_dict_config(self):
        config = []

        log_mock = Mock()
        glxinfo.log = log_mock

        ret = glxinfo.beacon(config)

        self.assertEqual(ret, [])
        log_mock.info.assert_called_once_with('Configuration for glxinfo beacon must be a dict.')

    def test_no_user(self):
        config = {'screen_event': True}

        log_mock = Mock()
        glxinfo.log = log_mock

        ret = glxinfo.beacon(config)

        self.assertEqual(ret, [])
        log_mock.info.assert_called_once_with('Configuration for glxinfo beacon must include a user as '
                                              'glxinfo is not available to root.')

    def test_screen_state(self):
        config = {'screen_event': True, 'user': 'frank'}

        mock = Mock(return_value=0)
        with patch.dict(glxinfo.__salt__, {'cmd.retcode': mock}):
            ret = glxinfo.beacon(config)
            self.assertEqual(ret, [{'tag': 'screen_event', 'screen_available': True}])
            mock.assert_called_once_with('DISPLAY=:0 glxinfo', runas='frank', python_shell=True)

    def test_screen_state_missing(self):
        config = {'screen_event': True, 'user': 'frank'}

        mock = Mock(return_value=255)
        with patch.dict(glxinfo.__salt__, {'cmd.retcode': mock}):
            ret = glxinfo.beacon(config)
            self.assertEqual(ret, [{'tag': 'screen_event', 'screen_available': False}])

    def test_screen_state_no_repeat(self):
        config = {'screen_event': True, 'user': 'frank'}

        mock = Mock(return_value=255)
        with patch.dict(glxinfo.__salt__, {'cmd.retcode': mock}):
            ret = glxinfo.beacon(config)
            self.assertEqual(ret, [{'tag': 'screen_event', 'screen_available': False}])

            ret = glxinfo.beacon(config)
            self.assertEqual(ret, [])

    def test_screen_state_change(self):
        config = {'screen_event': True, 'user': 'frank'}

        mock = Mock(side_effect=[255, 0])
        with patch.dict(glxinfo.__salt__, {'cmd.retcode': mock}):
            ret = glxinfo.beacon(config)
            self.assertEqual(ret, [{'tag': 'screen_event', 'screen_available': False}])

            ret = glxinfo.beacon(config)
            self.assertEqual(ret, [{'tag': 'screen_event', 'screen_available': True}])
