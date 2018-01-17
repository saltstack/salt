# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Bo Maryniuk <bo@suse.de>`
'''

from __future__ import absolute_import, print_function, unicode_literals
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt libs
import salt.exceptions
import salt.state

try:
    import pytest
except ImportError as err:
    pytest = None


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(pytest is None, 'PyTest is missing')
class SSDPTestCase(TestCase):
    '''
    TestCase for SSDP-related parts.
    '''

    def test_ssdp_base(self):
        '''
        Test SSDP base class main methods.

        :return:
        '''
