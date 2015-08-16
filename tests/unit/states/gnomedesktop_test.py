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
    NO_MOCK_REASON)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(GnomedesktopTestCase, needs_daemon=False)
