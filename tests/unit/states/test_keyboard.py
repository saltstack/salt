# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt Libs
import salt.states.keyboard as keyboard


@skipIf(NO_MOCK, NO_MOCK_REASON)
class KeyboardTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.keyboard
    '''
    def setup_loader_modules(self):
        return {keyboard: {}}

    # 'system' function tests: 1

    def test_system(self):
        '''
        Test to set the keyboard layout for the system.
        '''
        name = 'salt'

        ret = {'name': name,
               'result': True,
               'comment': '',
               'changes': {}}

        mock = MagicMock(side_effect=[name, '', '', ''])
        mock_t = MagicMock(side_effect=[True, False])
        with patch.dict(keyboard.__salt__, {'keyboard.get_sys': mock,
                                            'keyboard.set_sys': mock_t}):
            comt = ('System layout {0} already set'.format(name))
            ret.update({'comment': comt})
            self.assertDictEqual(keyboard.system(name), ret)

            with patch.dict(keyboard.__opts__, {'test': True}):
                comt = ('System layout {0} needs to be set'.format(name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(keyboard.system(name), ret)

            with patch.dict(keyboard.__opts__, {'test': False}):
                comt = ('Set system keyboard layout {0}'.format(name))
                ret.update({'comment': comt, 'result': True,
                            'changes': {'layout': name}})
                self.assertDictEqual(keyboard.system(name), ret)

                comt = ('Failed to set system keyboard layout')
                ret.update({'comment': comt, 'result': False, 'changes': {}})
                self.assertDictEqual(keyboard.system(name), ret)

    # 'xorg' function tests: 1

    def test_xorg(self):
        '''
        Test to set the keyboard layout for XOrg.
        '''
        name = 'salt'

        ret = {'name': name,
               'result': True,
               'comment': '',
               'changes': {}}

        mock = MagicMock(side_effect=[name, '', '', ''])
        mock_t = MagicMock(side_effect=[True, False])
        with patch.dict(keyboard.__salt__, {'keyboard.get_x': mock,
                                            'keyboard.set_x': mock_t}):
            comt = ('XOrg layout {0} already set'.format(name))
            ret.update({'comment': comt})
            self.assertDictEqual(keyboard.xorg(name), ret)

            with patch.dict(keyboard.__opts__, {'test': True}):
                comt = ('XOrg layout {0} needs to be set'.format(name))
                ret.update({'comment': comt, 'result': None})
                self.assertDictEqual(keyboard.xorg(name), ret)

            with patch.dict(keyboard.__opts__, {'test': False}):
                comt = ('Set XOrg keyboard layout {0}'.format(name))
                ret.update({'comment': comt, 'result': True,
                            'changes': {'layout': name}})
                self.assertDictEqual(keyboard.xorg(name), ret)

                comt = ('Failed to set XOrg keyboard layout')
                ret.update({'comment': comt, 'result': False, 'changes': {}})
                self.assertDictEqual(keyboard.xorg(name), ret)
