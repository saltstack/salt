# coding: utf-8

# Python libs
from __future__ import absolute_import

# Salt libs
import salt.beacons.glxinfo as glxinfo

# Salt testing libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch, Mock

# Import test suite libs
from tests.support.mixins import LoaderModuleMockMixin


@skipIf(NO_MOCK, NO_MOCK_REASON)
class GLXInfoBeaconTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test case for salt.beacons.glxinfo
    '''

    def setup_loader_modules(self):
        return {glxinfo: {'last_state': {}}}

    def test_no_glxinfo_command(self):
        with patch('salt.utils.path.which') as mock:
            mock.return_value = None

            ret = glxinfo.__virtual__()

            mock.assert_called_once_with('glxinfo')
            self.assertFalse(ret)

    def test_with_glxinfo_command(self):
        with patch('salt.utils.path.which') as mock:
            mock.return_value = '/usr/bin/glxinfo'

            ret = glxinfo.__virtual__()

            mock.assert_called_once_with('glxinfo')
            self.assertEqual(ret, 'glxinfo')

    def test_non_list_config(self):
        config = {}

        ret = glxinfo.validate(config)

        self.assertEqual(ret, (False, 'Configuration for glxinfo '
                                      'beacon must be a list.'))

    def test_no_user(self):
        config = [{'screen_event': True}]

        _expected = (False, 'Configuration for glxinfo beacon must '
                            'include a user as glxinfo is not '
                            'available to root.')
        ret = glxinfo.validate(config)
        self.assertEqual(ret, _expected)

    def test_screen_state(self):
        config = [{'screen_event': True,
                  'user': 'frank'}]

        mock = Mock(return_value=0)
        with patch.dict(glxinfo.__salt__, {'cmd.retcode': mock}):

            ret = glxinfo.validate(config)
            self.assertEqual(ret, (True, 'Valid beacon configuration'))

            ret = glxinfo.beacon(config)
            self.assertEqual(ret, [{'tag': 'screen_event',
                                    'screen_available': True}])
            mock.assert_called_once_with('DISPLAY=:0 glxinfo',
                                         runas='frank', python_shell=True)

    def test_screen_state_missing(self):
        config = [{'screen_event': True, 'user': 'frank'}]

        mock = Mock(return_value=255)
        with patch.dict(glxinfo.__salt__, {'cmd.retcode': mock}):
            ret = glxinfo.validate(config)
            self.assertEqual(ret, (True, 'Valid beacon configuration'))

            ret = glxinfo.beacon(config)
            self.assertEqual(ret, [{'tag': 'screen_event',
                                    'screen_available': False}])

    def test_screen_state_no_repeat(self):
        config = [{'screen_event': True, 'user': 'frank'}]

        mock = Mock(return_value=255)
        with patch.dict(glxinfo.__salt__, {'cmd.retcode': mock}):
            ret = glxinfo.validate(config)
            self.assertEqual(ret, (True, 'Valid beacon configuration'))

            ret = glxinfo.beacon(config)
            self.assertEqual(ret, [{'tag': 'screen_event',
                                    'screen_available': False}])

            ret = glxinfo.beacon(config)
            self.assertEqual(ret, [])

    def test_screen_state_change(self):
        config = [{'screen_event': True, 'user': 'frank'}]

        mock = Mock(side_effect=[255, 0])
        with patch.dict(glxinfo.__salt__, {'cmd.retcode': mock}):
            ret = glxinfo.validate(config)
            self.assertEqual(ret, (True, 'Valid beacon configuration'))

            ret = glxinfo.beacon(config)
            self.assertEqual(ret, [{'tag': 'screen_event',
                                    'screen_available': False}])

            ret = glxinfo.beacon(config)
            self.assertEqual(ret, [{'tag': 'screen_event',
                                    'screen_available': True}])
