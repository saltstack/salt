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
    NO_MOCK_REASON)

# Import Salt Libs
from salt.states import gnomedesktop


@skipIf(NO_MOCK, NO_MOCK_REASON)
class GnomedesktopTestCase(TestCase):
    '''
    Test cases for salt.states.gnomedesktop
    '''
    # 'wm_preferences' function tests: 1

    def test_wm_preferences(self):
        '''
        Test to sets values in the org.gnome.desktop.wm.preferences schema
        '''
        name = 'salt'

        ret = {'name': name,
               'result': True,
               'comment': '',
               'changes': {}}

        self.assertDictEqual(gnomedesktop.wm_preferences(name), ret)

    # 'desktop_lockdown' function tests: 1

    def test_desktop_lockdown(self):
        '''
        Test to sets values in the org.gnome.desktop.lockdown schema
        '''
        name = 'salt'

        ret = {'name': name,
               'result': True,
               'comment': '',
               'changes': {}}

        self.assertDictEqual(gnomedesktop.desktop_lockdown(name), ret)

    # 'desktop_interface' function tests: 1

    def test_desktop_interface(self):
        '''
        Test to sets values in the org.gnome.desktop.interface schema
        '''
        name = 'salt'

        ret = {'name': name,
               'result': True,
               'comment': '',
               'changes': {}}

        self.assertDictEqual(gnomedesktop.desktop_interface(name), ret)
