# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.modules import deb_apache
# Globals
deb_apache.__grains__ = {}
deb_apache.__salt__ = {}
deb_apache.__context__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class DebApacheTestCase(TestCase):
    '''
    Test cases for salt.modules.deb_apache
    '''
    # 'check_site_enabled' function tests: 3

    @patch('os.path.islink', MagicMock(return_value=True))
    def test_check_site_enabled(self):
        '''
        Test if the specific Site symlink is enabled.
        '''
        self.assertTrue(deb_apache.check_site_enabled('saltstack.com'))

    @patch('os.path.islink', MagicMock(side_effect=[False, True]))
    def test_check_site_enabled_default(self):
        '''
        Test if the specific Site symlink is enabled.
        '''
        self.assertTrue(deb_apache.check_site_enabled('default'))

    @patch('os.path.islink', MagicMock(return_value=False))
    def test_check_site_enabled_false(self):
        '''
        Test if the specific Site symlink is enabled.
        '''
        self.assertFalse(deb_apache.check_site_enabled('saltstack.com'))

    # 'a2ensite' function tests: 4

    def test_a2ensite_notfound(self):
        '''
        Test if it runs a2ensite for the given site.
        '''
        mock = MagicMock(return_value=1)
        with patch.dict(deb_apache.__salt__, {'cmd.retcode': mock}):
            self.assertEqual(deb_apache.a2ensite('saltstack.com'),
                             {'Name': 'Apache2 Enable Site',
                               'Site': 'saltstack.com',
                                'Status': 'Site saltstack.com Not found'})

    def test_a2ensite_enabled(self):
        '''
        Test if it runs a2ensite for the given site.
        '''
        mock = MagicMock(return_value=0)
        with patch.dict(deb_apache.__salt__, {'cmd.retcode': mock}):
            self.assertEqual(deb_apache.a2ensite('saltstack.com'),
                             {'Name': 'Apache2 Enable Site',
                               'Site': 'saltstack.com',
                                'Status': 'Site saltstack.com enabled'})

    def test_a2ensite(self):
        '''
        Test if it runs a2ensite for the given site.
        '''
        mock = MagicMock(return_value=2)
        with patch.dict(deb_apache.__salt__, {'cmd.retcode': mock}):
            self.assertEqual(deb_apache.a2ensite('saltstack.com'),
                             {'Name': 'Apache2 Enable Site',
                               'Site': 'saltstack.com',
                                'Status': 2})

    def test_a2ensite_exception(self):
        '''
        Test if it runs a2ensite for the given site.
        '''
        mock = MagicMock(side_effect=Exception('error'))
        with patch.dict(deb_apache.__salt__, {'cmd.retcode': mock}):
            self.assertEqual(str(deb_apache.a2ensite('saltstack.com')),
                             'error')

    # 'a2dissite' function tests: 4

    def test_a2dissite_notfound(self):
        '''
        Test if it runs a2dissite for the given site.
        '''
        mock = MagicMock(return_value=256)
        with patch.dict(deb_apache.__salt__, {'cmd.retcode': mock}):
            self.assertEqual(deb_apache.a2dissite('saltstack.com'),
                             {'Name': 'Apache2 Disable Site',
                               'Site': 'saltstack.com',
                                'Status': 'Site saltstack.com Not found'})

    def test_a2dissite_disabled(self):
        '''
        Test if it runs a2dissite for the given site.
        '''
        mock = MagicMock(return_value=0)
        with patch.dict(deb_apache.__salt__, {'cmd.retcode': mock}):
            self.assertEqual(deb_apache.a2dissite('saltstack.com'),
                             {'Name': 'Apache2 Disable Site',
                               'Site': 'saltstack.com',
                                'Status': 'Site saltstack.com disabled'})

    def test_a2dissite(self):
        '''
        Test if it runs a2dissite for the given site.
        '''
        mock = MagicMock(return_value=2)
        with patch.dict(deb_apache.__salt__, {'cmd.retcode': mock}):
            self.assertEqual(deb_apache.a2dissite('saltstack.com'),
                             {'Name': 'Apache2 Disable Site',
                               'Site': 'saltstack.com',
                                'Status': 2})

    def test_a2dissite_exception(self):
        '''
        Test if it runs a2dissite for the given site.
        '''
        mock = MagicMock(side_effect=Exception('error'))
        with patch.dict(deb_apache.__salt__, {'cmd.retcode': mock}):
            self.assertEqual(str(deb_apache.a2dissite('saltstack.com')),
                             'error')

    # 'check_mod_enabled' function tests: 3

    @patch('os.path.islink', MagicMock(return_value=True))
    def test_check_mod_enabled(self):
        '''
        Test if the specific mod symlink is enabled.
        '''
        self.assertTrue(deb_apache.check_mod_enabled('status.conf'))

    @patch('os.path.islink', MagicMock(side_effect=[False, True]))
    def test_check_mod_enabled_default(self):
        '''
        Test if the specific mod symlink is enabled.
        '''
        self.assertTrue(deb_apache.check_mod_enabled('default'))

    @patch('os.path.islink', MagicMock(return_value=False))
    def test_check_mod_enabled_false(self):
        '''
        Test if the specific mod symlink is enabled.
        '''
        self.assertFalse(deb_apache.check_mod_enabled('status.conf'))

    # 'a2enmod' function tests: 4

    def test_a2enmod_notfound(self):
        '''
        Test if it runs a2enmod for the given site.
        '''
        mock = MagicMock(return_value=1)
        with patch.dict(deb_apache.__salt__, {'cmd.retcode': mock}):
            self.assertEqual(deb_apache.a2enmod('vhost_alias'),
                             {'Name': 'Apache2 Enable Mod',
                               'Mod': 'vhost_alias',
                                'Status': 'Mod vhost_alias Not found'})

    def test_a2enmod_enabled(self):
        '''
        Test if it runs a2enmod for the given site.
        '''
        mock = MagicMock(return_value=0)
        with patch.dict(deb_apache.__salt__, {'cmd.retcode': mock}):
            self.assertEqual(deb_apache.a2enmod('vhost_alias'),
                             {'Name': 'Apache2 Enable Mod',
                               'Mod': 'vhost_alias',
                                'Status': 'Mod vhost_alias enabled'})

    def test_a2enmod(self):
        '''
        Test if it runs a2enmod for the given site.
        '''
        mock = MagicMock(return_value=2)
        with patch.dict(deb_apache.__salt__, {'cmd.retcode': mock}):
            self.assertEqual(deb_apache.a2enmod('vhost_alias'),
                             {'Name': 'Apache2 Enable Mod',
                               'Mod': 'vhost_alias',
                                'Status': 2})

    def test_a2enmod_exception(self):
        '''
        Test if it runs a2enmod for the given site.
        '''
        mock = MagicMock(side_effect=Exception('error'))
        with patch.dict(deb_apache.__salt__, {'cmd.retcode': mock}):
            self.assertEqual(str(deb_apache.a2enmod('vhost_alias')),
                             'error')

    # 'a2dismod' function tests: 4

    def test_a2dismod_notfound(self):
        '''
        Test if it runs a2dismod for the given site.
        '''
        mock = MagicMock(return_value=256)
        with patch.dict(deb_apache.__salt__, {'cmd.retcode': mock}):
            self.assertEqual(deb_apache.a2dismod('vhost_alias'),
                             {'Name': 'Apache2 Disable Mod',
                               'Mod': 'vhost_alias',
                                'Status': 'Mod vhost_alias Not found'})

    def test_a2dismod_disabled(self):
        '''
        Test if it runs a2dismod for the given site.
        '''
        mock = MagicMock(return_value=0)
        with patch.dict(deb_apache.__salt__, {'cmd.retcode': mock}):
            self.assertEqual(deb_apache.a2dismod('vhost_alias'),
                             {'Name': 'Apache2 Disable Mod',
                               'Mod': 'vhost_alias',
                                'Status': 'Mod vhost_alias disabled'})

    def test_a2dismod(self):
        '''
        Test if it runs a2dismod for the given site.
        '''
        mock = MagicMock(return_value=2)
        with patch.dict(deb_apache.__salt__, {'cmd.retcode': mock}):
            self.assertEqual(deb_apache.a2dismod('vhost_alias'),
                             {'Name': 'Apache2 Disable Mod',
                               'Mod': 'vhost_alias',
                                'Status': 2})

    def test_a2dismod_exception(self):
        '''
        Test if it runs a2dismod for the given site.
        '''
        mock = MagicMock(side_effect=Exception('error'))
        with patch.dict(deb_apache.__salt__, {'cmd.retcode': mock}):
            self.assertEqual(str(deb_apache.a2dismod('vhost_alias')),
                             'error')


if __name__ == '__main__':
    from integration import run_tests
    run_tests(DebApacheTestCase, needs_daemon=False)
