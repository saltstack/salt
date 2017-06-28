# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt Libs
import salt.states.pkgng as pkgng


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PkgngTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.pkgng
    '''
    def setup_loader_modules(self):
        return {pkgng: {}}

    # 'update_packaging_site' function tests: 1

    def test_update_packaging_site(self):
        '''
        Test to execute update_packaging_site.
        '''
        name = "http://192.168.0.2"

        ret = {'name': name,
               'result': True,
               'comment': '',
               'changes': {}}

        mock_t = MagicMock(return_value=True)
        with patch.dict(pkgng.__salt__, {'pkgng.update_package_site': mock_t}):
            self.assertDictEqual(pkgng.update_packaging_site(name), ret)
