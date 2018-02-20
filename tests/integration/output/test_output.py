# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''

# Import Salt Libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import traceback

# Import Salt Testing Libs
from tests.support.case import ShellCase
from tests.support.mixins import RUNTIME_VARS

# Import Salt libs
import salt.config
from salt.output import display_output
from salt.ext import six


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
        expected = ["{u'local': True}"] if six.PY2 else ["{'local': True}"]
        ret = self.run_call('test.ping --out=pprint')
        self.assertEqual(ret, expected)

    def test_output_raw(self):
        '''
        Tests the return of raw-formatted data
        '''
        expected = ["{u'local': True}"] if six.PY2 else ["{'local': True}"]
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

    def test_output_highstate(self):
        '''
        Regression tests for the highstate outputter. Calls a basic state with various
        flags. Each comparison should be identical when successful.
        '''
        # Test basic highstate output. No frills.
        expected = ['minion:', '          ID: simple-ping', '    Function: module.run',
                    '        Name: test.ping', '      Result: True',
                    '     Comment: Module function test.ping executed',
                    '     Changes:   ', '              ret:', '                  True',
                    'Summary for minion', 'Succeeded: 1 (changed=1)', 'Failed:    0',
                    'Total states run:     1']
        state_run = self.run_salt('"minion" state.sls simple-ping')

        for expected_item in expected:
            self.assertIn(expected_item, state_run)

        # Test highstate output while also passing --out=highstate.
        # This is a regression test for Issue #29796
        state_run = self.run_salt('"minion" state.sls simple-ping --out=highstate')

        for expected_item in expected:
            self.assertIn(expected_item, state_run)

        # Test highstate output when passing --static and running a state function.
        # See Issue #44556.
        state_run = self.run_salt('"minion" state.sls simple-ping --static')

        for expected_item in expected:
            self.assertIn(expected_item, state_run)

        # Test highstate output when passing --static and --out=highstate.
        # See Issue #44556.
        state_run = self.run_salt('"minion" state.sls simple-ping --static --out=highstate')

        for expected_item in expected:
            self.assertIn(expected_item, state_run)

    def test_output_highstate_falls_back_nested(self):
        '''
        Tests outputter when passing --out=highstate with a non-state call. This should
        fall back to "nested" output.
        '''
        expected = ['minion:', '    True']
        ret = self.run_salt('"minion" test.ping --out=highstate')
        self.assertEqual(ret, expected)

    def test_static_simple(self):
        '''
        Tests passing the --static option with a basic test.ping command. This
        should be the "nested" output.
        '''
        expected = ['minion:', '    True']
        ret = self.run_salt('"minion" test.ping --static')
        self.assertEqual(ret, expected)
