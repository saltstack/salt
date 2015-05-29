# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(PkgngTestCase, needs_daemon=False)
