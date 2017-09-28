# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''

# Import Salt Libs
from __future__ import absolute_import
import os
import traceback

# Import Salt Testing Libs
from tests.support.case import ShellCase
from tests.support.mixins import RUNTIME_VARS

# Import Salt libs
import salt.config
from salt.output import display_output


class OutputReturnTest(ShellCase):
    '''
    Integration tests to ensure outputters return their expected format.
    Tests against situations where the loader might not be returning the
    right outputter even though it was explicitly requested.
    '''

    def test_output_json(self):
        '''
        Tests the return of json-formatted data
        '''
        ret = self.run_call('test.ping --out=json')
        self.assertIn('{', ret)
        self.assertIn('"local": true', ''.join(ret))
        self.assertIn('}', ''.join(ret))

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
        opts = salt.config.minion_config(os.path.join(RUNTIME_VARS.TMP_CONF_DIR, 'minion'))
        opts['output_file'] = os.path.join(
            RUNTIME_VARS.TMP,
            'outputtest'
        )
        data = {'foo': {'result': False,
                        'aaa': 'azerzaeréééé',
                        'comment': u'ééééàààà'}}
        try:
            # this should not raises UnicodeEncodeError
            display_output(data, opts=opts)
        except Exception:
            # display trace in error message for debugging on jenkins
            trace = traceback.format_exc()
            sentinel = object()
            old_max_diff = getattr(self, 'maxDiff', sentinel)
            try:
                self.maxDiff = None
                self.assertEqual(trace, '')
            finally:
                if old_max_diff is sentinel:
                    delattr(self, 'maxDiff')
                else:
                    self.maxDiff = old_max_diff
