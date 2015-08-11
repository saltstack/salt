# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
import salt.config
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)
import os

ensure_in_syspath('../../')

# Import Salt Libs
from salt.states import winrepo

# Globals
winrepo.__salt__ = {}
winrepo.__opts__ = {}


class MockRunnerClient(object):
    '''
        Mock RunnerClient class
    '''
    def __init__(self):
        pass

    class RunnerClient(object):
        '''
            Mock RunnerClient class
        '''
        def __init__(self, master_config):
            '''
                init method
            '''
            pass

        @staticmethod
        def cmd(arg1, arg2):
            '''
                Mock cmd method
            '''
            return []


@patch('salt.states.winrepo.salt.runner', MockRunnerClient)
@skipIf(NO_MOCK, NO_MOCK_REASON)
class WinrepoTestCase(TestCase):
    '''
    Validate the winrepo state
    '''
    def test_genrepo(self):
        '''
        Test to refresh the winrepo.p file of the repository
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': False,
               'comment': ''}
        mock = MagicMock(side_effect=[False, True, True, True, True, True,
                                      True])
        with patch.object(os.path, 'exists', mock):
            ret.update({'comment': '/srv/salt/win/repo is missing'})
            self.assertDictEqual(winrepo.genrepo('salt'), ret)

            mock = MagicMock(return_value={'winrepo_dir': 'salt',
                                           'winrepo_cachefile': 'abc'})
            with patch.object(salt.config, 'master_config', mock):
                mock = MagicMock(return_value=[0, 1, 2, 3, 4, 5, 6, 7, 8])
                with patch.object(os, 'stat', mock):
                    mock = MagicMock(return_value=[])
                    with patch.object(os, 'walk', mock):
                        with patch.dict(winrepo.__opts__, {'test': True}):
                            ret.update({'comment': '', 'result': None})
                            self.assertDictEqual(winrepo.genrepo('salt'), ret)

                        with patch.dict(winrepo.__opts__, {'test': False}):
                            ret.update({'result': True})
                            self.assertDictEqual(winrepo.genrepo('salt'), ret)

                            ret.update({'changes': {'winrepo': []}})
                            self.assertDictEqual(winrepo.genrepo('salt', True),
                                                 ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(WinrepoTestCase, needs_daemon=False)
