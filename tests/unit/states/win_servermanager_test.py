# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

ensure_in_syspath('../../')

# Import Salt Libs
from salt.states import win_servermanager

# Globals
win_servermanager.__salt__ = {}
win_servermanager.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class WinServermanagerTestCase(TestCase):
    '''
        Validate the win_servermanager state
    '''
    def test_installed(self):
        '''
            Test to install the windows feature
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': True,
               'comment': ''}
        mock = MagicMock(side_effect=['salt', 'stack', 'stack'])
        mock1 = MagicMock(return_value={'Success': True})
        with patch.dict(win_servermanager.__salt__,
                        {"win_servermanager.list_installed": mock,
                         "win_servermanager.install": mock1}):
            ret.update({'comment': 'The feature salt is already installed'})
            self.assertDictEqual(win_servermanager.installed('salt'), ret)

            with patch.dict(win_servermanager.__opts__, {"test": True}):
                ret.update({'changes': {'feature':
                                        'salt will be installed'
                                        ' recurse=False'}, 'result': None,
                            'comment': ''})
                self.assertDictEqual(win_servermanager.installed('salt'), ret)

                with patch.dict(win_servermanager.__opts__, {"test": False}):
                    ret.update({'changes': {'feature': {'Success': True}},
                                'result': True, 'comment': 'Installed salt'})
                    self.assertDictEqual(win_servermanager.installed('salt'),
                                         ret)

    def test_removed(self):
        '''
            Test to remove the windows feature
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': True,
               'comment': ''}
        mock = MagicMock(side_effect=['stack', 'salt', 'salt'])
        mock1 = MagicMock(return_value={'Success': True})
        with patch.dict(win_servermanager.__salt__,
                        {"win_servermanager.list_installed": mock,
                         "win_servermanager.remove": mock1}):
            ret.update({'comment': 'The feature salt is not installed'})
            self.assertDictEqual(win_servermanager.removed('salt'), ret)

            with patch.dict(win_servermanager.__opts__, {"test": True}):
                ret.update({'changes': {'feature':
                                        'salt will be removed'},
                            'result': None, 'comment': ''})
                self.assertDictEqual(win_servermanager.removed('salt'), ret)

                with patch.dict(win_servermanager.__opts__, {"test": False}):
                    ret.update({'changes': {'feature': {'Success': True}},
                                'result': True})
                    self.assertDictEqual(win_servermanager.removed('salt'),
                                         ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(WinServermanagerTestCase, needs_daemon=False)
