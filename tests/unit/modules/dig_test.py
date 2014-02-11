# -*- coding: utf-8 -*-
'''
    :codauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import MagicMock, patch, call

from salt.modules import dig

@skipIf(not dig.__virtual__(), 'Dig must be installed')
class DigTestCase(TestCase):

    def test_check_ip(self):
        self.assertTrue(dig.check_ip('127.0.0.1'), msg='Not a valid ip address')

    def test_check_ip_ipv6(self):
        self.assertTrue(dig.check_ip('1111:2222:3333:4444:5555:6666:7777:8888'), msg='Not a valid ip address')

    def test_check_ip_neg(self):
        self.assertFalse(dig.check_ip('-127.0.0.1'), msg="Did not detect negative value as invalid")

    def test_check_ip_empty(self):
        self.assertFalse(dig.check_ip(''), msg="Did not detect empty value as invalid")

    def test_A(self):
        dig.__salt__ = {}
        with patch.dict(dig.__salt__, {'cmd.run_all': MagicMock(return_value={'pid': 3656, 'retcode': 0, 'stderr': '', 'stdout': '74.125.193.104\n74.125.193.105\n74.125.193.99\n74.125.193.106\n74.125.193.103\n74.125.193.147'})}):
            self.assertEqual(dig.A('www.google.com'), ['74.125.193.104', '74.125.193.105', '74.125.193.99', '74.125.193.106', '74.125.193.103', '74.125.193.147'])
