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
from salt.states import win_path

# Globals
win_path.__salt__ = {}
win_path.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class WinPathTestCase(TestCase):
    '''
        Validate the win_path state
    '''
    def test_absent(self):
        '''
            Test to remove the directory from the SYSTEM path
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': None,
               'comment': ''}
        mock = MagicMock(return_value=False)
        with patch.dict(win_path.__salt__, {"win_path.exists": mock}):
            with patch.dict(win_path.__opts__, {"test": True}):
                ret.update({'comment': 'salt is not in the PATH'})
                self.assertDictEqual(win_path.absent('salt'), ret)

            with patch.dict(win_path.__opts__, {"test": False}):
                mock = MagicMock(return_value=True)
                with patch.dict(win_path.__salt__, {"win_path.remove": mock}):
                    ret.update({'result': True})
                    self.assertDictEqual(win_path.absent('salt'), ret)

    def test_exists(self):
        '''
            Test to add the directory to the system PATH at index location
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': True,
               'comment': ''}
        mock = MagicMock(return_value=['Salt', 'Saltdude'])
        with patch.dict(win_path.__salt__, {"win_path.get_path": mock}):
            mock = MagicMock(side_effect=['Saltdude', 'Saltdude', '/Saltdude',
                                          'Saltdude'])
            with patch.object(win_path, '_normalize_dir', mock):
                ret.update({'comment': 'salt is already present in the'
                            ' PATH at the right location'})
                self.assertDictEqual(win_path.exists('salt', 1), ret)

                self.assertDictEqual(win_path.exists('salt'), ret)

                with patch.dict(win_path.__opts__, {"test": True}):
                    ret.update({'comment': '', 'result': None,
                                'changes': {'added': 'salt will be'
                                            ' added at index 2'}})
                    self.assertDictEqual(win_path.exists('salt'), ret)

                with patch.dict(win_path.__opts__, {"test": False}):
                    mock = MagicMock(return_value=False)
                    with patch.dict(win_path.__salt__, {"win_path.add": mock}):
                        ret.update({'comment': 'salt is already present in the'
                                    ' PATH at the right location',
                                    'result': True, 'changes': {}})
                        self.assertDictEqual(win_path.exists('salt'), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(WinPathTestCase, needs_daemon=False)
