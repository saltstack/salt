# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import MagicMock, patch, NO_MOCK, NO_MOCK_REASON
from salttesting.helpers import ensure_in_syspath, requires_salt_modules
ensure_in_syspath('../../')

# Import salt libs
from salt.modules import dig


@skipIf(NO_MOCK, NO_MOCK_REASON)
@requires_salt_modules('dig')
class DigTestCase(TestCase):

    def test_check_ip(self):
        self.assertTrue(dig.check_ip('127.0.0.1'), msg='Not a valid ip address')

    def test_check_ip_ipv6(self):
        self.assertTrue(dig.check_ip('1111:2222:3333:4444:5555:6666:7777:8888'), msg='Not a valid ip address')

    @skipIf(True, 'Waiting for 2014.1 release')
    def test_check_ip_ipv6_valid(self):
        self.assertTrue(dig.check_ip('2607:fa18:0:3::4'))

    def test_check_ip_neg(self):
        self.assertFalse(dig.check_ip('-127.0.0.1'), msg="Did not detect negative value as invalid")

    def test_check_ip_empty(self):
        self.assertFalse(dig.check_ip(''), msg="Did not detect empty value as invalid")

    def test_a(self):
        dig.__salt__ = {}
        dig_mock = MagicMock(return_value={
                'pid': 3656, 'retcode': 0, 'stderr': '', 'stdout': '74.125.193.104\n'
                                                                   '74.125.193.105\n'
                                                                   '74.125.193.99\n'
                                                                   '74.125.193.106\n'
                                                                   '74.125.193.103\n'
                                                                   '74.125.193.147'
        })
        with patch.dict(dig.__salt__, {'cmd.run_all': dig_mock}):
            self.assertEqual(dig.A('www.google.com'), ['74.125.193.104',
                                                       '74.125.193.105',
                                                       '74.125.193.99',
                                                       '74.125.193.106',
                                                       '74.125.193.103',
                                                       '74.125.193.147'])

    @skipIf(True, 'Waiting for 2014.1 release')
    def test_aaaa(self):
        dig.__salt__ = {}
        dig_mock = MagicMock(return_value={
            'pid': 25451, 'retcode': 0, 'stderr': '', 'stdout': '2607:f8b0:400f:801::1014'
        })
        with patch.dict(dig.__salt__, {'cmd.run_all': dig_mock}):
            self.assertEqual(dig.AAAA('www.google.com'), ['2607:f8b0:400f:801::1014'])

    @patch('salt.modules.dig.A', MagicMock(return_value=['ns4.google.com.']))
    def test_ns(self):
        dig.__salt__ = {}
        dig_mock = MagicMock(return_value={
            'pid': 26136, 'retcode': 0, 'stderr': '', 'stdout': 'ns4.google.com.'
        })
        with patch.dict(dig.__salt__, {'cmd.run_all': dig_mock}):
            self.assertEqual(dig.NS('google.com'), ['ns4.google.com.'])

    def test_spf(self):
        dig.__salt__ = {}
        dig_mock = MagicMock(return_value={'pid': 26795,
                                           'retcode': 0,
                                           'stderr': '',
                                           'stdout': 'v=spf1'
                                                     ' include:_spf.google.com '
                                                     'ip4:216.73.93.70/31 '
                                                     'ip4:216.73.93.72/31 ~all'})
        with patch.dict(dig.__salt__, {'cmd.run_all': dig_mock}):
            self.assertEqual(dig.SPF('google.com'),
                             ['216.73.93.70/31', '216.73.93.72/31'])

    @skipIf(True, 'Waiting for 2014.1 release')
    def test_spf_redir(self):
        '''
        Test was written after a bug was found when a domain is redirecting the SPF ipv4 range
        '''
        dig.__salt__ = {}
        dig_mock = MagicMock(return_value={'pid': 27282,
                                           'retcode': 0,
                                           'stderr': '',
                                           'stdout': 'v=spf1 a mx '
                                                     'include:_spf.xmission.com ?all'})
        with patch.dict(dig.__salt__, {'cmd.run_all': dig_mock}):
            self.assertEqual(dig.SPF('xmission.com'), ['198.60.22.0/24', '166.70.13.0/24'])

    def test_mx(self):
        dig.__salt__ = {}
        dig_mock = MagicMock(return_value={'pid': 27780,
                                           'retcode': 0,
                                           'stderr': '',
                                           'stdout': '10 aspmx.l.google.com.\n'
                                                     '20 alt1.aspmx.l.google.com.\n'
                                                     '40 alt3.aspmx.l.google.com.\n'
                                                     '50 alt4.aspmx.l.google.com.\n'
                                                     '30 alt2.aspmx.l.google.com.'})
        with patch.dict(dig.__salt__, {'cmd.run_all': dig_mock}):
            self.assertEqual(dig.MX('google.com'), [['10', 'aspmx.l.google.com.'],
                                                     ['20', 'alt1.aspmx.l.google.com.'],
                                                     ['40', 'alt3.aspmx.l.google.com.'],
                                                     ['50', 'alt4.aspmx.l.google.com.'],
                                                     ['30', 'alt2.aspmx.l.google.com.']])
