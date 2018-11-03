# -*- coding: utf-8 -*-
'''
    :codeauthor: Bo Maryniuk <bo@maryniuk.net>
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import patch, NO_MOCK, NO_MOCK_REASON
from salt.modules import saltsupport

try:
    import pytest
except ImportError:
    pytest = None


@skipIf(not bool(pytest), 'Pytest required')
@skipIf(NO_MOCK, NO_MOCK_REASON)
class SaltSupportModuleTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.support::SaltSupportModule
    '''
    def setup_loader_modules(self):
        return {saltsupport: {}}


@skipIf(not bool(pytest), 'Pytest required')
@skipIf(NO_MOCK, NO_MOCK_REASON)
class LogCollectorTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.support::LogCollector
    '''
    def setup_loader_modules(self):
        return {saltsupport: {}}

