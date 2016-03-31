# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import rpm

# Globals
rpm.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class RpmTestCase(TestCase):
    '''
    Test cases for salt.modules.rpm
    '''
    # 'list_pkgs' function tests: 1

    def test_list_pkgs(self):
        '''
        Test if it list the packages currently installed in a dict
        '''
        mock = MagicMock(return_value='')
        with patch.dict(rpm.__salt__, {'cmd.run': mock}):
            self.assertDictEqual(rpm.list_pkgs(), {})

    # 'verify' function tests: 1

    def test_verify(self):
        '''
        Test if it runs an rpm -Va on a system,
        and returns the results in a dict
        '''
        mock = MagicMock(return_value='')
        with patch.dict(rpm.__salt__, {'cmd.run': mock}):
            self.assertDictEqual(rpm.verify('httpd'), {})

    # 'file_list' function tests: 1

    def test_file_list(self):
        '''
        Test if it list the files that belong to a package.
        '''
        mock = MagicMock(return_value='')
        with patch.dict(rpm.__salt__, {'cmd.run': mock}):
            self.assertDictEqual(rpm.file_list('httpd'),
                                 {'errors': [], 'files': []})

    # 'file_dict' function tests: 1

    def test_file_dict(self):
        '''
        Test if it list the files that belong to a package
        '''
        mock = MagicMock(return_value='')
        with patch.dict(rpm.__salt__, {'cmd.run': mock}):
            self.assertDictEqual(rpm.file_dict('httpd'),
                                 {'errors': [], 'packages': {}})

    # 'owner' function tests: 1

    def test_owner(self):
        '''
        Test if it return the name of the package that owns the file.
        '''
        self.assertEqual(rpm.owner(), '')

        ret = 'file /usr/bin/salt-jenkins-build is not owned by any package'
        mock = MagicMock(return_value=ret)
        with patch.dict(rpm.__salt__, {'cmd.run_stdout': mock}):
            self.assertEqual(rpm.owner('/usr/bin/salt-jenkins-build'), '')

        ret = {'/usr/bin/vim': 'vim-enhanced-7.4.160-1.e17.x86_64',
               '/usr/bin/python': 'python-2.7.5-16.e17.x86_64'}
        mock = MagicMock(side_effect=['python-2.7.5-16.e17.x86_64',
                                      'vim-enhanced-7.4.160-1.e17.x86_64'])
        with patch.dict(rpm.__salt__, {'cmd.run_stdout': mock}):
            self.assertDictEqual(rpm.owner('/usr/bin/python', '/usr/bin/vim'),
                                 ret)

    @patch('salt.modules.rpm.HAS_RPM', True)
    def test_version_cmp_rpm(self):
        '''
        Test package version is called RPM version if RPM-Python is installed

        :return:
        '''
        rpm.rpm = MagicMock(return_value=MagicMock)
        with patch('salt.modules.rpm.rpm.labelCompare', MagicMock(return_value=0)):
            self.assertEqual(0, rpm.version_cmp('1', '2'))  # mock returns 0, which means RPM was called

    @patch('salt.modules.rpm.HAS_RPM', False)
    def test_version_cmp_fallback(self):
        '''
        Test package version is called RPM version if RPM-Python is installed

        :return:
        '''
        rpm.rpm = MagicMock(return_value=MagicMock)
        with patch('salt.modules.rpm.rpm.labelCompare', MagicMock(return_value=0)):
            self.assertEqual(-1, rpm.version_cmp('1', '2'))  # mock returns -1, a python implementation was called

if __name__ == '__main__':
    from integration import run_tests
    run_tests(RpmTestCase, needs_daemon=False)
