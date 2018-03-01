# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rahul Handay <rahulha@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.exceptions import CommandExecutionError
import salt.states.timezone as timezone


@skipIf(NO_MOCK, NO_MOCK_REASON)
class TimezoneTestCase(TestCase, LoaderModuleMockMixin):
    '''
        Validate the timezone state
    '''
    def setup_loader_modules(self):
        return {timezone: {}}

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
            ret.update({'comment': "Unable to compare desired timezone"
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
