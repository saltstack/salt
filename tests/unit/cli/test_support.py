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
        for idx, data in enumerate(['', '\x1b[0;36m', self.message, '\x1b[0;0m', '\n']):
            assert self.device.write.call_args_list[idx][0][0] == data

