# -*- coding: utf-8 -*-

from __future__ import absolute_import, unicode_literals, print_function

from tests.support.unit import TestCase, skipIf
from tests.support.mock import MagicMock, patch, NO_MOCK, NO_MOCK_REASON
import salt.utils.pkg
from salt.utils.pkg import rpm


class PkgUtilsTestCase(TestCase):
    '''
    TestCase for salt.utils.pkg module
    '''
    test_parameters = [
        ("16.0.0.49153-0+f1", "", "16.0.0.49153-0+f1"),
        ("> 15.0.0", ">", "15.0.0"),
        ("< 15.0.0", "<", "15.0.0"),
        ("<< 15.0.0", "<<", "15.0.0"),
        (">> 15.0.0", ">>", "15.0.0"),
        (">= 15.0.0", ">=", "15.0.0"),
        ("<= 15.0.0", "<=", "15.0.0"),
        ("!= 15.0.0", "!=", "15.0.0"),
        ("<=> 15.0.0", "<=>", "15.0.0"),
        ("<> 15.0.0", "<>", "15.0.0"),
        ("= 15.0.0", "=", "15.0.0"),
        (">15.0.0", ">", "15.0.0"),
        ("<15.0.0", "<", "15.0.0"),
        ("<<15.0.0", "<<", "15.0.0"),
        (">>15.0.0", ">>", "15.0.0"),
        (">=15.0.0", ">=", "15.0.0"),
        ("<=15.0.0", "<=", "15.0.0"),
        ("!=15.0.0", "!=", "15.0.0"),
        ("<=>15.0.0", "<=>", "15.0.0"),
        ("<>15.0.0", "<>", "15.0.0"),
        ("=15.0.0", "=", "15.0.0"),
        ("", "", "")
    ]

    def test_split_comparison(self):
        '''
        Tests salt.utils.pkg.split_comparison
        '''
        for test_parameter in self.test_parameters:
            oper, verstr = salt.utils.pkg.split_comparison(test_parameter[0])
            self.assertEqual(test_parameter[1], oper)
            self.assertEqual(test_parameter[2], verstr)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PkgRPMTestCase(TestCase):
    '''
    Test case for pkg.rpm utils
    '''

    @patch('salt.utils.path.which', MagicMock(return_value=True))
    def test_get_osarch_by_rpm(self):
        '''
        Get os_arch if RPM package is installed.
        :return:
        '''
        subprocess_mock = MagicMock()
        subprocess_mock.Popen = MagicMock()
        subprocess_mock.Popen().communicate = MagicMock(return_value=['Z80'])
        with patch('salt.utils.pkg.rpm.subprocess', subprocess_mock):
            assert rpm.get_osarch() == 'Z80'
        assert subprocess_mock.Popen.call_count == 2  # One within the mock
        assert subprocess_mock.Popen.call_args[1]['close_fds']
        assert subprocess_mock.Popen.call_args[1]['shell']
        assert len(subprocess_mock.Popen.call_args_list) == 2
        assert subprocess_mock.Popen.call_args[0][0] == 'rpm --eval "%{_host_cpu}"'

    @patch('salt.utils.path.which', MagicMock(return_value=False))
    @patch('salt.utils.pkg.rpm.subprocess', MagicMock(return_value=False))
    @patch('salt.utils.pkg.rpm.platform.uname', MagicMock(
        return_value=('Sinclair BASIC', 'motophone', '1982 Sinclair Research Ltd', '1.0', 'ZX81', 'Z80')))
    def test_get_osarch_by_platform(self):
        '''
        Get os_arch if RPM package is not installed (inird image, for example).
        :return:
        '''
        assert rpm.get_osarch() == 'Z80'

    @patch('salt.utils.path.which', MagicMock(return_value=False))
    @patch('salt.utils.pkg.rpm.subprocess', MagicMock(return_value=False))
    @patch('salt.utils.pkg.rpm.platform.uname', MagicMock(
        return_value=('Sinclair BASIC', 'motophone', '1982 Sinclair Research Ltd', '1.0', 'ZX81', '')))
    def test_get_osarch_by_platform_no_cpu_arch(self):
        '''
        Get os_arch if RPM package is not installed (inird image, for example) but cpu arch cannot be determined.
        :return:
        '''
        assert rpm.get_osarch() == 'ZX81'

    @patch('salt.utils.path.which', MagicMock(return_value=False))
    @patch('salt.utils.pkg.rpm.subprocess', MagicMock(return_value=False))
    @patch('salt.utils.pkg.rpm.platform.uname', MagicMock(
        return_value=('Sinclair BASIC', 'motophone', '1982 Sinclair Research Ltd', '1.0', '', '')))
    def test_get_osarch_by_platform_no_cpu_arch_no_machine(self):
        '''
        Get os_arch if RPM package is not installed (inird image, for example)
        where both cpu arch and machine cannot be determined.
        :return:
        '''
        assert rpm.get_osarch() == 'unknown'
