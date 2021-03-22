import pytest
import salt.modules.win_task as task
import salt.utils.platform
from salt.exceptions import CommandExecutionError
from tests.support.case import ModuleCase
from tests.support.unit import skipIf


@skipIf(not salt.utils.platform.is_windows(), "windows test only")
class WinTasksTest(ModuleCase):
    """
    Tests for salt.modules.win_task.
    """

    @pytest.mark.destructive_test
    def test_adding_task_with_xml(self):
        """
        Test adding a task using xml
        """
        xml_text = r"""
        <Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
          <RegistrationInfo>
            <Date>2015-06-12T15:59:35.691983</Date>
            <Author>System</Author>
          </RegistrationInfo>
          <Triggers>
            <LogonTrigger>
              <Enabled>true</Enabled>
              <Delay>PT30S</Delay>
            </LogonTrigger>
          </Triggers>
          <Principals>
            <Principal id="Author">
              <UserId>System</UserId>
              <LogonType>InteractiveToken</LogonType>
              <RunLevel>HighestAvailable</RunLevel>
            </Principal>
          </Principals>
          <Settings>
            <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
            <DisallowStartIfOnBatteries>true</DisallowStartIfOnBatteries>
            <StopIfGoingOnBatteries>true</StopIfGoingOnBatteries>
            <AllowHardTerminate>true</AllowHardTerminate>
            <StartWhenAvailable>false</StartWhenAvailable>
            <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
            <IdleSettings>
              <StopOnIdleEnd>true</StopOnIdleEnd>
              <RestartOnIdle>false</RestartOnIdle>
            </IdleSettings>
            <AllowStartOnDemand>true</AllowStartOnDemand>
            <Enabled>true</Enabled>
            <Hidden>false</Hidden>
            <RunOnlyIfIdle>false</RunOnlyIfIdle>
            <WakeToRun>false</WakeToRun>
            <ExecutionTimeLimit>P3D</ExecutionTimeLimit>
            <Priority>4</Priority>
          </Settings>
          <Actions Context="Author">
            <Exec>
              <Command>echo</Command>
              <Arguments>"hello"</Arguments>
            </Exec>
          </Actions>
        </Task>
        """
        self.assertEqual(
            self.run_function("task.create_task_from_xml", "foo", xml_text=xml_text),
            True,
        )
        all_tasks = self.run_function("task.list_tasks")
        self.assertIn("foo", all_tasks)

    @pytest.mark.destructive_test
    def test_adding_task_with_invalid_xml(self):
        """
        Test adding a task using a malformed xml
        """
        xml_text = r"""<Malformed"""
        with self.assertRaises(CommandExecutionError):
            task.create_task_from_xml("foo", xml_text=xml_text)
