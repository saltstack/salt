# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''

# Import Salt Libs
from __future__ import absolute_import
import os
import copy
import traceback

# Import Salt Testing Libs
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import Salt libs
import integration
from salt.output import display_output


class OutputReturnTest(integration.ShellCase):
    '''
    Integration tests to ensure outputters return their expected format.
    Tests against situations where the loader might not be returning the
    right outputter even though it was explicitly requested.
    '''

    def test_output_json(self):
        '''
        Tests the return of json-formatted data
        '''
        expected = ['{', '    "local": true', '}']
        ret = self.run_call('test.ping --out=json')
        self.assertEqual(ret, expected)

    def test_output_nested(self):
        '''
        Tests the return of nested-formatted data
        '''
        expected = ['local:', '    True']
        ret = self.run_call('test.ping --out=nested')
        self.assertEqual(ret, expected)

    def test_output_quiet(self):
        '''
        Tests the return of an out=quiet query
        '''
        expected = []
        ret = self.run_call('test.ping --out=quiet')
        self.assertEqual(ret, expected)

    def test_output_pprint(self):
        '''
        Tests the return of pprint-formatted data
        '''
        expected = ["{'local': True}"]
        ret = self.run_call('test.ping --out=pprint')
        self.assertEqual(ret, expected)

    def test_output_raw(self):
        '''
        Tests the return of raw-formatted data
        '''
        expected = ["{'local': True}"]
        ret = self.run_call('test.ping --out=raw')
        self.assertEqual(ret, expected)

    def test_output_txt(self):
        '''
        Tests the return of txt-formatted data
        '''
        expected = ['local: True']
        ret = self.run_call('test.ping --out=txt')
        self.assertEqual(ret, expected)

    def test_output_yaml(self):
        '''
        Tests the return of yaml-formatted data
        '''
        expected = ['local: true']
        ret = self.run_call('test.ping --out=yaml')
        self.assertEqual(ret, expected)

    def test_output_unicodebad(self):
        '''
        Tests outputter reliability with utf8
        '''
        opts = copy.deepcopy(self.minion_opts)
        opts['output_file'] = os.path.join(
            self.minion_opts['root_dir'], 'outputtest')
        data = {'foo': {'result': False,
                        'aaa': 'azerzaeréééé',
                        'comment': u'ééééàààà'}}
        try:
            # this should not raises UnicodeEncodeError
            display_output(data, opts=self.minion_opts)
            self.assertTrue(True)
        except Exception:
            # display trace in error message for debugging on jenkins
            trace = traceback.format_exc()
            self.assertEqual(trace, '')


if __name__ == '__main__':
    from integration import run_tests
    run_tests(OutputReturnTest)
