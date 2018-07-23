# -*- coding: utf-8 -*-
'''
    :codeauthor: Bo Maryniuk <bo@suse.de>
'''

from __future__ import absolute_import, print_function, unicode_literals

from tests.support.unit import skipIf, TestCase
from tests.support.mock import MagicMock, patch, NO_MOCK, NO_MOCK_REASON

from salt.cli.support.console import IndentOutput
from salt.utils.color import get_colors

try:
    import pytest
except ImportError:
    pytest = None


@skipIf(not bool(pytest), 'Pytest needs to be installed')
@skipIf(NO_MOCK, NO_MOCK_REASON)
class SaltSupportIndentOutputTestCase(TestCase):
    '''
    Unit Tests for the salt-support indent output.
    '''

    def setUp(self):
        '''
        Setup test
        :return:
        '''

        self.message = 'Stubborn processes on dumb terminal'
        self.device = MagicMock()
        self.iout = IndentOutput(device=self.device)
        self.colors = get_colors()

    def tearDown(self):
        '''
        Remove instances after test run
        :return:
        '''
        del self.message
        del self.device
        del self.iout

    def test_standard_output(self):
        '''
        Test console standard output.
        '''
        self.iout.put(self.message)
        assert self.device.write.called
        assert self.device.write.call_count == 5
        for idx, data in enumerate(['', str(self.colors['CYAN']), self.message, str(self.colors['ENDC']), '\n']):
            assert self.device.write.call_args_list[idx][0][0] == data

    def test_indent_output(self):
        '''
        Test indent distance.
        :return:
        '''
        self.iout.put(self.message, indent=10)
        for idx, data in enumerate([' ' * 10, str(self.colors['CYAN']), self.message, str(self.colors['ENDC']), '\n']):
            assert self.device.write.call_args_list[idx][0][0] == data

