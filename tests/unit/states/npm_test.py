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
from salt.exceptions import CommandExecutionError

ensure_in_syspath('../../')

# Import Salt Libs
from salt.states import npm

npm.__salt__ = {}
npm.__opts__ = {'test': False}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class NpmTestCase(TestCase):

    '''
    Test cases for salt.states.npm
    '''
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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(NpmTestCase, needs_daemon=False)
