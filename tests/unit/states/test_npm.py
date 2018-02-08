# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

from salt.exceptions import CommandExecutionError

# Import Salt Libs
import salt.states.npm as npm


@skipIf(NO_MOCK, NO_MOCK_REASON)
class NpmTestCase(TestCase, LoaderModuleMockMixin):

    '''
    Test cases for salt.states.npm
    '''
    def setup_loader_modules(self):
        return {npm: {'__opts__': {'test': False}}}

    # 'installed' function tests: 1

    def test_installed(self):
        '''
        Test to verify that the given package is installed
        and is at the correct version.
        '''
        name = 'coffee-script'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {}}

        mock_err = MagicMock(side_effect=CommandExecutionError)
        mock_dict = MagicMock(return_value={name: {'version': '1.2'}})
        with patch.dict(npm.__salt__, {'npm.list': mock_err}):
            comt = ("Error looking up 'coffee-script': ")
            ret.update({'comment': comt})
            self.assertDictEqual(npm.installed(name), ret)

        with patch.dict(npm.__salt__, {'npm.list': mock_dict,
                                       'npm.install': mock_err}):
            with patch.dict(npm.__opts__, {'test': True}):
                comt = ("Package(s) 'coffee-script' "
                        "satisfied by coffee-script@1.2")
                ret.update({'comment': comt, 'result': True})
                self.assertDictEqual(npm.installed(name), ret)

            with patch.dict(npm.__opts__, {'test': False}):
                comt = ("Package(s) 'coffee-script' "
                        "satisfied by coffee-script@1.2")
                ret.update({'comment': comt, 'result': True})
                self.assertDictEqual(npm.installed(name), ret)

                comt = ("Error installing 'n, p, m': ")
                ret.update({'comment': comt, 'result': False})
                self.assertDictEqual(npm.installed(name, 'npm'), ret)

                with patch.dict(npm.__salt__, {'npm.install': mock_dict}):
                    comt = ("Package(s) 'n, p, m' successfully installed")
                    ret.update({'comment': comt, 'result': True,
                                'changes': {'new': ['n', 'p', 'm'], 'old': []}})
                    self.assertDictEqual(npm.installed(name, 'npm'), ret)

    # 'removed' function tests: 1

    def test_removed(self):
        '''
        Test to verify that the given package is not installed.
        '''
        name = 'coffee-script'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {}}

        mock_err = MagicMock(side_effect=[CommandExecutionError, {},
                                          {name: ''}, {name: ''}])
        mock_t = MagicMock(return_value=True)
        with patch.dict(npm.__salt__, {'npm.list': mock_err,
                                       'npm.uninstall': mock_t}):
            comt = ("Error uninstalling 'coffee-script': ")
            ret.update({'comment': comt})
            self.assertDictEqual(npm.removed(name), ret)

            comt = ("Package 'coffee-script' is not installed")
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(npm.removed(name), ret)

            with patch.dict(npm.__opts__, {'test': True}):
                comt = ("Package 'coffee-script' is set to be removed")
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(npm.removed(name), ret)

            with patch.dict(npm.__opts__, {'test': False}):
                comt = ("Package 'coffee-script' was successfully removed")
                ret.update({'comment': comt, 'result': True,
                            'changes': {name: 'Removed'}})
                self.assertDictEqual(npm.removed(name), ret)

    # 'bootstrap' function tests: 1

    def test_bootstrap(self):
        '''
        Test to bootstraps a node.js application.
        '''
        name = 'coffee-script'

        ret = {'name': name,
               'result': False,
               'comment': '',
               'changes': {}}

        mock_err = MagicMock(side_effect=[CommandExecutionError, False, True])
        with patch.dict(npm.__salt__, {'npm.install': mock_err}):
            comt = ("Error Bootstrapping 'coffee-script': ")
            ret.update({'comment': comt})
            self.assertDictEqual(npm.bootstrap(name), ret)

            comt = ('Directory is already bootstrapped')
            ret.update({'comment': comt, 'result': True})
            self.assertDictEqual(npm.bootstrap(name), ret)

            comt = ('Directory was successfully bootstrapped')
            ret.update({'comment': comt, 'result': True,
                        'changes': {name: 'Bootstrapped'}})
            self.assertDictEqual(npm.bootstrap(name), ret)

    # 'bootstrap' function tests: 1

    def test_cache_cleaned(self):
        '''
        Test to verify that the npm cache is cleaned.
        '''
        name = 'coffee-script'

        pkg_ret = {
            'name': name,
            'result': False,
            'comment': '',
            'changes': {}
        }
        ret = {
            'name': None,
            'result': False,
            'comment': '',
            'changes': {}
        }

        mock_list = MagicMock(return_value=['~/.npm', '~/.npm/{0}/'.format(name)])
        mock_cache_clean_success = MagicMock(return_value=True)
        mock_cache_clean_failure = MagicMock(return_value=False)
        mock_err = MagicMock(side_effect=CommandExecutionError)

        with patch.dict(npm.__salt__, {'npm.cache_list': mock_err}):
            comt = ('Error looking up cached packages: ')
            ret.update({'comment': comt})
            self.assertDictEqual(npm.cache_cleaned(), ret)

        with patch.dict(npm.__salt__, {'npm.cache_list': mock_err}):
            comt = ("Error looking up cached {0}: ".format(name))
            pkg_ret.update({'comment': comt})
            self.assertDictEqual(npm.cache_cleaned(name), pkg_ret)

        mock_data = {'npm.cache_list': mock_list, 'npm.cache_clean': MagicMock()}
        with patch.dict(npm.__salt__, mock_data):
            non_cached_pkg = 'salt'
            comt = ('Package {0} is not in the cache'.format(non_cached_pkg))
            pkg_ret.update({'name': non_cached_pkg, 'result': True, 'comment': comt})
            self.assertDictEqual(npm.cache_cleaned(non_cached_pkg), pkg_ret)
            pkg_ret.update({'name': name})

            with patch.dict(npm.__opts__, {'test': True}):
                comt = ('Cached packages set to be removed')
                ret.update({'result': None, 'comment': comt})
                self.assertDictEqual(npm.cache_cleaned(), ret)

            with patch.dict(npm.__opts__, {'test': True}):
                comt = ('Cached {0} set to be removed'.format(name))
                pkg_ret.update({'result': None, 'comment': comt})
                self.assertDictEqual(npm.cache_cleaned(name), pkg_ret)

            with patch.dict(npm.__opts__, {'test': False}):
                comt = ('Cached packages successfully removed')
                ret.update({'result': True, 'comment': comt,
                            'changes': {'cache': 'Removed'}})
                self.assertDictEqual(npm.cache_cleaned(), ret)

            with patch.dict(npm.__opts__, {'test': False}):
                comt = ('Cached {0} successfully removed'.format(name))
                pkg_ret.update({'result': True, 'comment': comt,
                            'changes': {name: 'Removed'}})
                self.assertDictEqual(npm.cache_cleaned(name), pkg_ret)

        mock_data = {'npm.cache_list': mock_list, 'npm.cache_clean': MagicMock(return_value=False)}
        with patch.dict(npm.__salt__, mock_data):
            with patch.dict(npm.__opts__, {'test': False}):
                comt = ('Error cleaning cached packages')
                ret.update({'result': False, 'comment': comt})
                ret['changes'] = {}
                self.assertDictEqual(npm.cache_cleaned(), ret)

            with patch.dict(npm.__opts__, {'test': False}):
                comt = ('Error cleaning cached {0}'.format(name))
                pkg_ret.update({'result': False, 'comment': comt})
                pkg_ret['changes'] = {}
                self.assertDictEqual(npm.cache_cleaned(name), pkg_ret)
