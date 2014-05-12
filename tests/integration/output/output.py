# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''

# Import Python Libs
import os

# Import Salt Libs
import integration

# Import Salt Testing Libs
from salttesting import skipIf
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')


class OutputReturnTest(integration.ShellCase):
    '''
    Integration tests to ensure outputters return their expected format.
    Tests against situations where the loader might not be returning the
    right outputter even though it was explicitly requested.
    '''

    @skipIf(os.geteuid() != 0, 'You must be logged in as root to run this test')
    def test_output_json(self):
        '''
        Tests the return of json-formatted data
        '''
        expected = ['{', '    "local": true', '}']
        ret = self.run_call('test.ping --out=json')
        self.assertEqual(ret, expected)

    @skipIf(os.geteuid() != 0, 'You must be logged in as root to run this test')
    def test_output_nested(self):
        '''
        Tests the return of nested-formatted data
        '''
        expected = ['local:', '    True']
        ret = self.run_call('test.ping --out=nested')
        self.assertEqual(ret, expected)

    @skipIf(os.geteuid() != 0, 'You must be logged in as root to run this test')
    def test_output_quiet(self):
        '''
        Tests the return of an out=quiet query
        '''
        expected = []
        ret = self.run_call('test.ping --out=quiet')
        self.assertEqual(ret, expected)

    @skipIf(os.geteuid() != 0, 'You must be logged in as root to run this test')
    def test_output_pprint(self):
        '''
        Tests the return of pprint-formatted data
        '''
        expected = ["{'local': True}"]
        ret = self.run_call('test.ping --out=pprint')
        self.assertEqual(ret, expected)

    @skipIf(os.geteuid() != 0, 'You must be logged in as root to run this test')
    def test_output_raw(self):
        '''
        Tests the return of raw-formatted data
        '''
        expected = ["{'local': True}"]
        ret = self.run_call('test.ping --out=raw')
        self.assertEqual(ret, expected)

    @skipIf(os.geteuid() != 0, 'You must be logged in as root to run this test')
    def test_output_txt(self):
        '''
        Tests the return of txt-formatted data
        '''
        expected = ['local: True']
        ret = self.run_call('test.ping --out=txt')
        self.assertEqual(ret, expected)

    @skipIf(os.geteuid() != 0, 'You must be logged in as root to run this test')
    def test_output_yaml(self):
        '''
        Tests the return of yaml-formatted data
        '''
        expected = ['local: true']
        ret = self.run_call('test.ping --out=yaml')
        self.assertEqual(ret, expected)
