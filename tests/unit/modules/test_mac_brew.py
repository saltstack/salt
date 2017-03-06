# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Libs
from salt.modules import mac_brew
from salt.exceptions import CommandExecutionError

# Import Salt Testing Libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import MagicMock, patch, NO_MOCK, NO_MOCK_REASON

# Global Variables
mac_brew.__context__ = {}
mac_brew.__salt__ = {}
mac_brew.__opts__ = {'user': MagicMock(return_value='bar')}

TAPS_STRING = 'homebrew/dupes\nhomebrew/science\nhomebrew/x11'
TAPS_LIST = ['homebrew/dupes', 'homebrew/science', 'homebrew/x11']
HOMEBREW_BIN = '/usr/local/bin/brew'


@skipIf(NO_MOCK, NO_MOCK_REASON)
class BrewTestCase(TestCase):
    '''
    TestCase for salt.modules.mac_brew module
    '''

    # '_list_taps' function tests: 1

    def test_list_taps(self):
        '''
        Tests the return of the list of taps
        '''
        mock_taps = MagicMock(return_value={'stdout': TAPS_STRING,
                                            'retcode': 0})
        mock_user = MagicMock(return_value='foo')
        mock_cmd = MagicMock(return_value='')
        with patch.dict(mac_brew.__salt__, {'file.get_user': mock_user,
                                        'cmd.run_all': mock_taps,
                                        'cmd.run': mock_cmd}):
            self.assertEqual(mac_brew._list_taps(), TAPS_LIST)

    # '_tap' function tests: 3

    @patch('salt.modules.mac_brew._list_taps', MagicMock(return_value=TAPS_LIST))
    def test_tap_installed(self):
        '''
        Tests if tap argument is already installed or not
        '''
        self.assertTrue(mac_brew._tap('homebrew/science'))

    @patch('salt.modules.mac_brew._list_taps', MagicMock(return_value={}))
    def test_tap_failure(self):
        '''
        Tests if the tap installation failed
        '''
        mock_failure = MagicMock(return_value={'stdout': '',
                                               'stderr': '',
                                               'retcode': 1})
        mock_user = MagicMock(return_value='foo')
        mock_cmd = MagicMock(return_value='')
        with patch.dict(mac_brew.__salt__, {'cmd.run_all': mock_failure,
                                        'file.get_user': mock_user,
                                        'cmd.run': mock_cmd}):
            self.assertFalse(mac_brew._tap('homebrew/test'))

    @patch('salt.modules.mac_brew._list_taps', MagicMock(return_value=TAPS_LIST))
    def test_tap(self):
        '''
        Tests adding unofficial GitHub repos to the list of brew taps
        '''
        mock_failure = MagicMock(return_value={'retcode': 0})
        mock_user = MagicMock(return_value='foo')
        mock_cmd = MagicMock(return_value='')
        with patch.dict(mac_brew.__salt__, {'cmd.run_all': mock_failure,
                                        'file.get_user': mock_user,
                                        'cmd.run': mock_cmd}):
            self.assertTrue(mac_brew._tap('homebrew/test'))

    # '_homebrew_bin' function tests: 1

    def test_homebrew_bin(self):
        '''
        Tests the path to the homebrew binary
        '''
        mock_path = MagicMock(return_value='/usr/local')
        with patch.dict(mac_brew.__salt__, {'cmd.run': mock_path}):
            self.assertEqual(mac_brew._homebrew_bin(), '/usr/local/bin/brew')

    # 'list_pkgs' function tests: 2
    # Only tested a few basics
    # Full functionality should be tested in integration phase

    def test_list_pkgs_removed(self):
        '''
        Tests removed implementation
        '''
        self.assertEqual(mac_brew.list_pkgs(removed=True), {})

    def test_list_pkgs_versions_true(self):
        '''
        Tests if pkg.list_pkgs is already in context and is a list
        '''
        mock_context = {'foo': ['bar']}
        with patch.dict(mac_brew.__context__, {'pkg.list_pkgs': mock_context}):
            self.assertEqual(mac_brew.list_pkgs(versions_as_list=True),
                             mock_context)

    # 'version' function tests: 1

    def test_version(self):
        '''
        Tests version name returned
        '''
        mock_version = MagicMock(return_value='0.1.5')
        with patch.dict(mac_brew.__salt__, {'pkg_resource.version': mock_version}):
            self.assertEqual(mac_brew.version('foo'), '0.1.5')

    # 'latest_version' function tests: 0
    # It has not been fully implemented

    # 'remove' function tests: 1
    # Only tested a few basics
    # Full functionality should be tested in integration phase

    @patch('salt.modules.mac_brew.list_pkgs',
           MagicMock(return_value={'test': '0.1.5'}))
    def test_remove(self):
        '''
        Tests if package to be removed exists
        '''
        mock_params = MagicMock(return_value=({'foo': None}, 'repository'))
        with patch.dict(mac_brew.__salt__,
                        {'pkg_resource.parse_targets': mock_params}):
            self.assertEqual(mac_brew.remove('foo'), {})

    # 'refresh_db' function tests: 2

    @patch('salt.modules.mac_brew._homebrew_bin',
           MagicMock(return_value=HOMEBREW_BIN))
    def test_refresh_db_failure(self):
        '''
        Tests an update of homebrew package repository failure
        '''
        mock_user = MagicMock(return_value='foo')
        mock_failure = MagicMock(return_value={'stdout': '',
                                               'stderr': '',
                                               'retcode': 1})
        with patch.dict(mac_brew.__salt__, {'file.get_user': mock_user,
                                        'cmd.run_all': mock_failure}):
            self.assertRaises(CommandExecutionError, mac_brew.refresh_db)

    @patch('salt.modules.mac_brew._homebrew_bin',
           MagicMock(return_value=HOMEBREW_BIN))
    def test_refresh_db(self):
        '''
        Tests a successful update of homebrew package repository
        '''
        mock_user = MagicMock(return_value='foo')
        mock_success = MagicMock(return_value={'retcode': 0})
        with patch.dict(mac_brew.__salt__, {'file.get_user': mock_user,
                                        'cmd.run_all': mock_success}):
            self.assertTrue(mac_brew.refresh_db())

    # 'install' function tests: 1
    # Only tested a few basics
    # Full functionality should be tested in integration phase

    def test_install(self):
        '''
        Tests if package to be installed exists
        '''
        mock_params = MagicMock(return_value=[None, None])
        with patch.dict(mac_brew.__salt__,
                        {'pkg_resource.parse_targets': mock_params}):
            self.assertEqual(mac_brew.install('name=foo'), {})
