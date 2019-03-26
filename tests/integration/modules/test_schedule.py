# Import Python libs

import logging

# Import Salt Testing libs
from tests.support.case import ModuleCase

log = logging.getLogger(__name__)


class ScheduleModuleTest(ModuleCase):
    """
    Test the schedule module
    """

    def test_schedule_list(self):
        """
        schedule.list
        """
        expected = {"schedule": {}}
        ret = self.run_function("schedule.list")
        self.assertEqual(ret, expected)

    def test_schedule_reload(self):
        """
        schedule.list
        """
        expected = {"comment": [], "result": True}
        ret = self.run_function("schedule.reload")
        self.assertEqual(ret, expected)
