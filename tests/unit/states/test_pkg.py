# -*- coding: utf-8 -*-

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
from salt.ext import six
import salt.states.pkg as pkg


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PkgTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.pkg
    '''
    pkgs = {
        'pkga': {'old': '1.0.1', 'new': '2.0.1'},
        'pkgb': {'old': '1.0.2', 'new': '2.0.2'},
        'pkgc': {'old': '1.0.3', 'new': '2.0.3'}
    }

    def setup_loader_modules(self):
        return {
            pkg: {
                '__grains__': {
                    'os': 'CentOS'
                }
            }
        }

    def test_uptodate_with_changes(self):
        '''
        Test pkg.uptodate with simulated changes
        '''
        list_upgrades = MagicMock(return_value={
            pkgname: pkgver['new'] for pkgname, pkgver in six.iteritems(self.pkgs)
        })
        upgrade = MagicMock(return_value=self.pkgs)
        version = MagicMock(side_effect=lambda pkgname: self.pkgs[pkgname]['old'])

        with patch.dict(pkg.__salt__,
                        {'pkg.list_upgrades': list_upgrades,
                         'pkg.upgrade': upgrade,
                         'pkg.version': version}):

            # Run state with test=false
            with patch.dict(pkg.__opts__, {'test': False}):

                ret = pkg.uptodate('dummy', test=True)
                self.assertTrue(ret['result'])
                self.assertDictEqual(ret['changes'], self.pkgs)

            # Run state with test=true
            with patch.dict(pkg.__opts__, {'test': True}):
                ret = pkg.uptodate('dummy', test=True)
                self.assertIsNone(ret['result'])
                self.assertDictEqual(ret['changes'], self.pkgs)

    def test_uptodate_with_pkgs_with_changes(self):
        '''
        Test pkg.uptodate with simulated changes
        '''

        pkgs = {
            'pkga': {'old': '1.0.1', 'new': '2.0.1'},
            'pkgb': {'old': '1.0.2', 'new': '2.0.2'},
            'pkgc': {'old': '1.0.3', 'new': '2.0.3'}
        }

        list_upgrades = MagicMock(return_value={
            pkgname: pkgver['new'] for pkgname, pkgver in six.iteritems(self.pkgs)
        })
        upgrade = MagicMock(return_value=self.pkgs)
        version = MagicMock(side_effect=lambda pkgname: pkgs[pkgname]['old'])

        with patch.dict(pkg.__salt__,
                        {'pkg.list_upgrades': list_upgrades,
                         'pkg.upgrade': upgrade,
                         'pkg.version': version}):
            # Run state with test=false
            with patch.dict(pkg.__opts__, {'test': False}):
                ret = pkg.uptodate('dummy', test=True, pkgs=[pkgname for pkgname in six.iterkeys(self.pkgs)])
                self.assertTrue(ret['result'])
                self.assertDictEqual(ret['changes'], pkgs)

            # Run state with test=true
            with patch.dict(pkg.__opts__, {'test': True}):
                ret = pkg.uptodate('dummy', test=True, pkgs=[pkgname for pkgname in six.iterkeys(self.pkgs)])
                self.assertIsNone(ret['result'])
                self.assertDictEqual(ret['changes'], pkgs)

    def test_uptodate_no_changes(self):
        '''
        Test pkg.uptodate with no changes
        '''
        list_upgrades = MagicMock(return_value={})
        upgrade = MagicMock(return_value={})

        with patch.dict(pkg.__salt__,
                        {'pkg.list_upgrades': list_upgrades,
                         'pkg.upgrade': upgrade}):

            # Run state with test=false
            with patch.dict(pkg.__opts__, {'test': False}):

                ret = pkg.uptodate('dummy', test=True)
                self.assertTrue(ret['result'])
                self.assertDictEqual(ret['changes'], {})

            # Run state with test=true
            with patch.dict(pkg.__opts__, {'test': True}):
                ret = pkg.uptodate('dummy', test=True)
                self.assertTrue(ret['result'])
                self.assertDictEqual(ret['changes'], {})

    def test_uptodate_with_pkgs_no_changes(self):
        '''
        Test pkg.uptodate with no changes
        '''
        list_upgrades = MagicMock(return_value={})
        upgrade = MagicMock(return_value={})

        with patch.dict(pkg.__salt__,
                        {'pkg.list_upgrades': list_upgrades,
                         'pkg.upgrade': upgrade}):
            # Run state with test=false
            with patch.dict(pkg.__opts__, {'test': False}):
                ret = pkg.uptodate('dummy', test=True, pkgs=[pkgname for pkgname in six.iterkeys(self.pkgs)])
                self.assertTrue(ret['result'])
                self.assertDictEqual(ret['changes'], {})

            # Run state with test=true
            with patch.dict(pkg.__opts__, {'test': True}):
                ret = pkg.uptodate('dummy', test=True, pkgs=[pkgname for pkgname in six.iterkeys(self.pkgs)])
                self.assertTrue(ret['result'])
                self.assertDictEqual(ret['changes'], {})

    def test_uptodate_with_failed_changes(self):
        '''
        Test pkg.uptodate with simulated failed changes
        '''

        pkgs = {
            'pkga': {'old': '1.0.1', 'new': '2.0.1'},
            'pkgb': {'old': '1.0.2', 'new': '2.0.2'},
            'pkgc': {'old': '1.0.3', 'new': '2.0.3'}
        }

        list_upgrades = MagicMock(return_value={
            pkgname: pkgver['new'] for pkgname, pkgver in six.iteritems(self.pkgs)
        })
        upgrade = MagicMock(return_value={})
        version = MagicMock(side_effect=lambda pkgname: pkgs[pkgname]['old'])

        with patch.dict(pkg.__salt__,
                        {'pkg.list_upgrades': list_upgrades,
                         'pkg.upgrade': upgrade,
                         'pkg.version': version}):
            # Run state with test=false
            with patch.dict(pkg.__opts__, {'test': False}):
                ret = pkg.uptodate('dummy', test=True, pkgs=[pkgname for pkgname in six.iterkeys(self.pkgs)])
                self.assertFalse(ret['result'])
                self.assertDictEqual(ret['changes'], {})

            # Run state with test=true
            with patch.dict(pkg.__opts__, {'test': True}):
                ret = pkg.uptodate('dummy', test=True, pkgs=[pkgname for pkgname in six.iterkeys(self.pkgs)])
                self.assertIsNone(ret['result'])
                self.assertDictEqual(ret['changes'], pkgs)
