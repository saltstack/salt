# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import
import os
import sys

# Import Salt Testing libs
from integration import TMP_CONF_DIR
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    patch
)


ensure_in_syspath('../')

# Import Salt libs
import salt.state
import salt.exceptions
from salt.utils.odict import OrderedDict


@skipIf(NO_MOCK, NO_MOCK_REASON)
class StateCompilerTestCase(TestCase):
    '''
    TestCase for the state compiler.
    '''

    def test_format_log_non_ascii_character(self):
        '''
        Tests running a non-ascii character through the state.format_log
        function. See Issue #33605.
        '''
        # There is no return to test against as the format_log
        # function doesn't return anything. However, we do want
        # to make sure that the function doesn't stacktrace when
        # called.
        ret = {'changes': {u'Français': {'old': 'something old',
                                         'new': 'something new'}},
               'result': True}
        salt.state.format_log(ret)

    @skipIf(sys.version_info < (2, 7), 'Context manager in assertEquals only available in > Py2.7')
    @patch('salt.state.State._gather_pillar')
    def test_render_error_on_invalid_requisite(self, state_patch):
        '''
        Test that the state compiler correctly deliver a rendering
        exception when a requisite cannot be resolved
        '''
        high_data = {'git': OrderedDict([('pkg', [OrderedDict([('require', [OrderedDict([('file', OrderedDict([('test1', 'test')]))])])]), 'installed', {'order': 10000}]), ('__sls__', u'issue_35226'), ('__env__', 'base')])}
        minion_opts = salt.config.minion_config(os.path.join(TMP_CONF_DIR, 'minion'))
        minion_opts['pillar'] = {'git': OrderedDict([('test1', 'test')])}
        state_obj = salt.state.State(minion_opts)
        with self.assertRaises(salt.exceptions.SaltRenderError):
            state_obj.call_high(high_data)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(StateCompilerTestCase, needs_daemon=False)
