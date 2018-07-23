# -*- coding: utf-8 -*-
'''
    :codeauthor: Bo Maryniuk <bo@suse.de>
'''

from __future__ import absolute_import, print_function, unicode_literals

from tests.support.unit import skipIf, TestCase
from tests.support.mock import MagicMock, patch, NO_MOCK, NO_MOCK_REASON

from salt.cli.support.console import IndentOutput

try:
    import pytest
except ImportError:
    pytest = None


@skipIf(not bool(pytest), 'Pytest needs to be installed')
@skipIf(NO_MOCK, NO_MOCK_REASON)
class SaltSupportTestCase(TestCase):
    '''
    Unit Tests for the salt-support.
    '''

    def test_console_indent_output(self):
        '''
        Test console indent output.
        '''
        message = 'Stubborn processes on dumb terminal'
        device = MagicMock()
        iout = IndentOutput(device=device)
        iout.put(message)
        assert device.write.called
        assert device.write.call_count == 5
        for idx, data in enumerate(['', '\x1b[0;36m', message, '\x1b[0;0m', '\n']):
            assert device.write.call_args_list[idx][0][0] == data
