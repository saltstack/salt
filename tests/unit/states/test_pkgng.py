# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt Libs
from salt.states import pkgng

pkgng.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PkgngTestCase(TestCase):
    '''
    Test cases for salt.states.pkgng
    '''
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
