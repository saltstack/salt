# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salt.exceptions import CommandExecutionError
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
from salt.states import timezone

# Globals
timezone.__salt__ = {}
timezone.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class TimezoneTestCase(TestCase):
    '''
        Validate the timezone state
    '''
    def test_system(self):
        '''
            Test to set the timezone for the system.
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': True,
               'comment': ''}
        mock = MagicMock(side_effect=[CommandExecutionError, True, True, True])
        mock1 = MagicMock(side_effect=['local', 'localtime', 'localtime'])
        mock2 = MagicMock(return_value=False)
        with patch.dict(timezone.__salt__, {"timezone.zone_compare": mock,
                                            "timezone.get_hwclock": mock1,
                                            "timezone.set_hwclock": mock2}):
            ret.update({'comment': "Unable to compare desrired timezone"
                        " 'salt' to system timezone: ", 'result': False})
            self.assertDictEqual(timezone.system('salt'), ret)

            ret.update({'comment': 'Timezone salt already set,'
                        ' UTC already set to salt', 'result': True})
            self.assertDictEqual(timezone.system('salt'), ret)

            with patch.dict(timezone.__opts__, {"test": True}):
                ret.update({'comment': 'UTC needs to be set to True',
                            'result': None})
                self.assertDictEqual(timezone.system('salt'), ret)

            with patch.dict(timezone.__opts__, {"test": False}):
                ret.update({'comment': 'Failed to set UTC to True',
                            'result': False})
                self.assertDictEqual(timezone.system('salt'), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(TimezoneTestCase, needs_daemon=False)
