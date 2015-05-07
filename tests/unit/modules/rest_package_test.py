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
from salt.modules import rest_package

# Globals
rest_package.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class RestPkgTestCase(TestCase):
    '''
    Test cases for salt.modules.rest_package
    '''
    def test_list_pkgs(self):
        '''
        Test for list pkgs
        '''
        with patch.dict(rest_package.__opts__, {'proxyobject': MagicMock()}):
            self.assertTrue(rest_package.list_pkgs())

    def test_install(self):
        '''
        Test for install
        '''
        with patch.dict(rest_package.__opts__, {'proxyobject': MagicMock()}):
            self.assertTrue(rest_package.install())

    def test_remove(self):
        '''
        Test for remove
        '''
        with patch.dict(rest_package.__opts__, {'proxyobject': MagicMock()}):
            self.assertTrue(rest_package.remove())

    def test_version(self):
        '''
        Test to return a string representing the package version or
        an empty string if not installed.
        '''
        with patch.dict(rest_package.__opts__, {'proxyobject': MagicMock()}):
            self.assertTrue(rest_package.version('A'))

    def test_installed(self):
        '''
        Test for installed
        '''
        with patch.dict(rest_package.__opts__, {'proxyobject': MagicMock()}):
            with patch.object(rest_package.__opts__['proxyobject'],
                              'package_status',
                              MagicMock(return_value={'ret': 'ret'})):
                self.assertEqual(rest_package.installed('name'), 'ret')

                self.assertTrue(rest_package.installed('name'))

                self.assertFalse(rest_package.installed('name', version='v'))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(RestPkgTestCase, needs_daemon=False)
