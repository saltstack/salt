# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import MagicMock, patch

# Import Salt Libs
from salt.modules import mac_user

# Import python Libs
import pwd, grp


class MacUserTestCase(TestCase):

    mac_user.__context__ = {}
    mac_user.__grains__ = {}
    mac_user.__salt__ = {}

    mock_pwall = [pwd.struct_passwd(('_amavisd', '*', 83, 83, 'AMaViS Daemon',
                                    '/var/virusmails', '/usr/bin/false')),
                  pwd.struct_passwd(('_appleevents', '*', 55, 55, 'AppleEvents Daemon',
                                    '/var/empty', '/usr/bin/false')),
                  pwd.struct_passwd(('_appowner', '*', 87, 87, 'Application Owner',
                                     '/var/empty', '/usr/bin/false'))]

    mock_pwnam = pwd.struct_passwd(('_amavisd', '*', 83, 83, 'AMaViS Daemon',
                                    '/var/virusmails', '/usr/bin/false'))

    def test_osmajor(self):
        with patch.dict(mac_user.__grains__, {'kernel': 'Darwin', 'osrelease': '10.9.1'}):
            self.assertEqual(mac_user._osmajor(), 10.9)

    @skipIf(True, 'Waiting on some clarifications from bug report')
    def test_flush_dscl_cache(self):
        # TODO: Implement tests after clarifications come in
        pass

    def test_dscl(self):
        mac_mock = MagicMock(return_value={'pid': 4948,
                                           'retcode': 0,
                                           'stderr': '',
                                           'stdout': ''})
        with patch.dict(mac_user.__salt__, {'cmd.run_all': mac_mock}):
            with patch.dict(mac_user.__grains__, {'kernel': 'Darwin', 'osrelease': '10.9.1'}):
                self.assertEqual(mac_user._dscl('username'), {'pid': 4948,
                                                              'retcode': 0,
                                                              'stderr': '',
                                                              'stdout': ''})

    @patch('pwd.getpwall', MagicMock(return_value=mock_pwall))
    def test_first_avail_uid(self):
        self.assertEqual(mac_user._first_avail_uid(), 501)

    @skipIf(True, 'Test not implemented yet')
    def test_add(self):
        # TODO: Implement this guy last
        pass

    @skipIf(True, 'Test not implemented yet')
    def test_delete(self):
        # TODO: Implement after chgroups is tested
        pass

    @patch('pwd.getpwall', MagicMock(return_value=mock_pwall))
    @patch('salt.modules.mac_user.list_groups', MagicMock(return_value=['TEST_GROUP']))
    def test_getent(self):
        ret = [{'shell': '/usr/bin/false', 'name': '_amavisd', 'gid': 83,
                'groups': ['TEST_GROUP'], 'home': '/var/virusmails',
                'fullname': 'AMaViS Daemon', 'uid': 83},
               {'shell': '/usr/bin/false', 'name': '_appleevents', 'gid': 55,
                'groups': ['TEST_GROUP'], 'home': '/var/empty',
                'fullname': 'AppleEvents Daemon', 'uid': 55},
               {'shell': '/usr/bin/false', 'name': '_appowner', 'gid': 87,
                'groups': ['TEST_GROUP'], 'home': '/var/empty',
                'fullname': 'Application Owner', 'uid': 87}]
        self.assertEqual(mac_user.getent(), ret)

    @patch('salt.modules.mac_user.list_groups', MagicMock(return_value=['_TEST_GROUP']))
    def test_format_info(self):
        data = pwd.struct_passwd(('_TEST_GROUP', '*', 83, 83, 'AMaViS Daemon',
                                  '/var/virusmails', '/usr/bin/false'))
        ret = {'shell': '/usr/bin/false', 'name': '_TEST_GROUP', 'gid': 83,
                     'groups': ['_TEST_GROUP'], 'home': '/var/virusmails',
                     'fullname': 'AMaViS Daemon', 'uid': 83}
        self.assertEqual(mac_user._format_info(data), ret)

    @patch('pwd.getpwnam', MagicMock(return_value=mock_pwnam))
    def test_list_groups(self):
        mock_getgrgid = grp.struct_group(('_TEST_GROUP', '*', 83, []))
        with patch('grp.getgrgid', MagicMock(return_value=mock_getgrgid)):
            self.assertEqual(mac_user.list_groups('name'), ['_TEST_GROUP'])

    @patch('pwd.getpwall', MagicMock(return_value=mock_pwall))
    def test_list_users(self):
        ret = ['_amavisd', '_appleevents', '_appowner']
        self.assertEqual(mac_user.list_users(), ret)
