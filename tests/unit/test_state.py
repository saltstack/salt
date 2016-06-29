# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
)

# Import Salt libs
from salt import state


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
        state.format_log(ret)
