# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.unit import skipIf
from tests.support.helpers import destructiveTest

# Import Salt Libs
import salt.utils.platform

# All test will add to a log in some way.
# Because of this they all most be destructive test.
@destructiveTest
@skipIf(not salt.utils.platform.is_windows(), 'Tests for only Windows')
class WinEventViewerTest(ModuleCase):

    def test_get_events_filter(self):
        '''
        test get_events_filter
        '''

        self.run_function('win_event_viewer.get_events_filter', ('System',
                                                                 'target_computer=None',
                                                                 'all_requirements=True',
                                                                 'eventID=1',
                                                                 'sid=None'), timeout=180)

    def test_get_number_of_events(self):
        '''
        test get_number_of_events
        '''

        ret = self.run_function('win_event_viewer.get_number_of_events', ('System',), timeout=180)
        self.assertEqual(int(ret), abs(int(ret)))

    def test_log_event(self):
        '''
        test log_event
        '''

        self.run_function('win_event_viewer.log_event', ('Salt_Test', '101',), timeout=180)





