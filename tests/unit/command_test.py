# encoding: utf-8
from __future__ import absolute_import

from salttesting import TestCase
from salttesting.mock import MagicMock

from salt.command import Command,\
    RunnerCommand,\
    RunnerReceiver, \
    get_async_runner_command, \
    get_sync_runner_command, \
    APIClient, \
    SaltCommandError, \
    get_command_for_low_data


class CommandTestCase(TestCase):
    def test_command_has_execute_method(self):
        self.assertEqual(hasattr(Command(), 'execute'), True)


class RunnerCommandTestCase(TestCase):
    def test_command_has_execute_method(self):
        '''
        Commands must implement execute
        '''
        self.assertEqual(hasattr(RunnerCommand(), 'execute'), True)

    def test_repr_return_data(self):
        '''
        Make sure __repr__ returns
        useful info about this command's low data
        '''
        fun = 'job.list_job'
        arg = [123456]
        kwarg = {'ext_source': 'source'}
        receiver = RunnerReceiver()

        msg = RunnerCommand.REPR_MSGS.format(fun, arg, kwarg, Command.SYNC, receiver)

        self.assertTrue(Command.SYNC in msg)
        self.assertTrue(fun in msg)
        self.assertTrue(str(receiver) in msg)
        self.assertTrue(str(arg) in msg)
        self.assertTrue(str(kwarg) in msg)

    def test_execute_calls_recievers_action_method(self):
        '''
        The execute method of RunnerCommand needs
        to call action method of RunnerReceiver.
        '''
        mock = RunnerReceiver()
        mock.action = MagicMock()

        command = RunnerCommand(receiver=mock)
        command.execute()
        mock.action.assert_called()

    def test_make_async_sets_async_client(self):
        command = RunnerCommand(receiver=RunnerReceiver())
        command.make_async()

        self.assertEqual(command.client, Command.ASYNC)

    def test_make_sync_sets_runner_client(self):
        command = RunnerCommand(receiver=RunnerReceiver())
        self.assertEqual(command.client, Command.SYNC)

        command.make_async()
        command.make_sync()
        self.assertEqual(command.client, Command.SYNC)

    def test_calls_cmd_sync_on_execute(self):
        '''
        RunnerCommand().execute should call cmd_sync on the client
        '''
        runner_client = MagicMock()
        runner_client.cmd_sync = MagicMock()

        command = get_sync_runner_command(client=runner_client)
        command.execute()
        runner_client.cmd_sync.assert_called()

    def test_calls_cmd_async_on_execute(self):
        '''
        RunnerCommand().execute should call cmd_sync on the client
        '''
        runner_client = MagicMock()
        runner_client.cmd_async = MagicMock()

        command = RunnerCommand(receiver=RunnerReceiver(salt_client=runner_client))
        command.make_async()
        command.execute()
        runner_client.cmd_async.assert_called()


class RunnerCommandsTestCase(TestCase):
    def test_can_build_sync_runner_command(self):
        self.assertIsNotNone(get_sync_runner_command())

    def test_can_build_async_runner_command(self):
        self.assertIsNotNone(get_async_runner_command())


class RunnerReceiverTestCase(TestCase):
    def test_can_set_salt_client(self):
        salt_client = {}
        recv = RunnerReceiver(salt_client=salt_client)
        self.assertEqual(salt_client, recv.client)

    def action_calls_cmd_sync(self):
        salt_client = MagicMock()
        salt_client.cmd_sync = MagicMock()

        recv = RunnerReceiver(salt_client=salt_client)
        recv.action()
        salt_client.cmd_sync.assert_called()

    def test_action_calls_cmd_async(self):
        salt_client = MagicMock()
        salt_client.cmd_async = MagicMock()
        recv = RunnerReceiver(salt_client=salt_client)
        recv.action(low={'client': 'runner_async', 'fun': 'foo.bar'})
        salt_client.cmd_async.assert_called()


class APIClientTestCase(TestCase):
    def test_has_submit_command_method(self):
        '''
        Check that the submit_runner_command method is available
        '''
        self.assertIsNotNone(APIClient.submit_runner_command)

    def test_it_calls_execute_on_command(self):
        command = MagicMock()
        command.execute = MagicMock()
        APIClient.submit_runner_command(command)
        command.execute.assert_called()


class CommandForLowDataTestCase(TestCase):
    def test_returns_command_for_low_data(self):
        low = {
            'client': 'runner',
            'fun': 'foo.bar',
            'arg': [],
            'kwarg': {}
        }
        self.assertIsInstance(get_command_for_low_data(low), Command)

    def test_raises_error_if_client_not_specified(self):
        low = {
            'fun': 'foo.bar',
            'arg': [],
            'kwarg': {}
        }
        with self.assertRaises(SaltCommandError):
            get_command_for_low_data(low)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(CommandTestCase, needs_daemon=False)
    run_tests(RunnerCommandTestCase, needs_daemon=False)
    run_tests(RunnerCommandsTestCase, needs_daemon=False)
    run_tests(RunnerReceiverTestCase, needs_daemon=False)
    run_tests(APIClientTestCase, needs_daemon=False)
    run_tests(CommandForLowDataTestCase, needs_daemon=False)
