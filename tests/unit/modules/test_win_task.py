import pytest
import salt.modules.win_task as win_task
import salt.utils.platform
from tests.support.unit import TestCase, skipIf


@skipIf(not salt.utils.platform.is_windows(), "System is not Windows")
@pytest.mark.destructive_test
class WinTaskTestCase(TestCase):
    """
    Test cases for salt.modules.win_task
    """

    def test_repeat_interval(self):
        task_name = "SaltTest1"
        try:
            ret = win_task.create_task(
                task_name,
                user_name="System",
                force=True,
                action_type="Execute",
                cmd="c:\\salt\\salt-call.bat",
                trigger_type="Daily",
                trigger_enabled=True,
                repeat_duration="30 minutes",
                repeat_interval="30 minutes",
            )
            self.assertTrue(ret)

            ret = win_task.info(task_name)
            self.assertEqual(ret["triggers"][0]["trigger_type"], "Daily")
        finally:
            ret = win_task.delete_task(task_name)
            self.assertTrue(ret)

    def test_repeat_interval_and_indefinitely(self):
        task_name = "SaltTest2"
        try:
            ret = win_task.create_task(
                task_name,
                user_name="System",
                force=True,
                action_type="Execute",
                cmd="c:\\salt\\salt-call.bat",
                trigger_type="Daily",
                trigger_enabled=True,
                repeat_duration="Indefinitely",
                repeat_interval="30 minutes",
            )
            self.assertTrue(ret)

            ret = win_task.info(task_name)
            self.assertEqual(ret["triggers"][0]["trigger_type"], "Daily")
        finally:
            ret = win_task.delete_task(task_name)
            self.assertTrue(ret)
