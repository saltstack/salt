import unittest
from mock import MagicMock

from command_pattern.command import Command,\
    RunnerCommand,\
    RunnerReceiver, \
    get_async_runner_command, \
    get_sync_runner_command, \
    APIClient, \
    SaltRunnerError


class CommandTestCase(unittest.TestCase):
    def test_command_has_execute_method(self):
        self.assertEqual(hasattr(Command(), 'execute'), True)


class RunnerCommandTestCase(unittest.TestCase):
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
        command.execute(
            username='foo',
            password='bar',
            eauth='ldap')
        runner_client.cmd_sync.assert_called()

    def test_calls_cmd_async_on_execute(self):
        '''
        RunnerCommand().execute should call cmd_sync on the client
        '''
        runner_client = MagicMock()
        runner_client.cmd_async = MagicMock()

        command = RunnerCommand(receiver=RunnerReceiver(salt_client=runner_client))
        command.make_async()
        command.execute(token='123')
        runner_client.cmd_async.assert_called()


class RunnerClientDummy(object):
    '''
    For now these are stand ins for the RunnerClient
    '''
    def cmd_sync(self, low, timeout=10):
        print('Called cmd_sync with low={0} and timeout={1}'.format(low, timeout))

    def cmd_async(self, low, timeout=10):
        print('Called cmd_async with low={0} and timeout={1}'.format(low, timeout))


class RunnerCommandsTestCase(unittest.TestCase):
    def test_can_build_sync_runner_command(self):
        self.assertIsNotNone(get_sync_runner_command())

    def test_can_build_async_runner_command(self):
        self.assertIsNotNone(get_async_runner_command())


class RunnerReceiverTestCase(unittest.TestCase):
    def test_can_set_salt_client(self):
        salt_client = RunnerClientDummy()
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
        recv.action(low={'client': 'runner_async', 'fun': 'foo.bar'}, token='1234')
        salt_client.cmd_async.assert_called()


class APIClientTestCase(unittest.TestCase):
    def test_has_submit_command_method(self):
        '''
        Check that the submit_runner_command method is available
        '''
        self.assertIsNotNone(APIClient.submit_runner_command)

    def test_raises_exception_when_submit_runner_command_is_called_without_auth(self):
        '''
        Test that cmd_sync is called on the
        client that we set
        '''
        with self.assertRaises(SaltRunnerError):
            runner_client = MagicMock()
            runner_client.cmd_sync = MagicMock()
            APIClient.submit_runner_command(get_sync_runner_command(
                    fun='grains.get',
                    arg=['osfullname'],
                    client=runner_client))

        with self.assertRaises(SaltRunnerError):
            runner_client = MagicMock()
            runner_client.cmd_async = MagicMock()
            APIClient.submit_runner_command(get_async_runner_command(
                    fun='grains.get',
                    arg=['osfullname'],
                    client=runner_client))

    def test_it_works_when_submit_runner_command_is_called_with_token(self):
        runner_client = MagicMock()
        runner_client.cmd_async = MagicMock()
        APIClient.submit_runner_command(get_async_runner_command(
                client=runner_client), token=1234567)
        runner_client.cmd_async.assert_called()

        runner_client_sync = MagicMock()
        runner_client_sync.cmd_sync = MagicMock()
        APIClient.submit_runner_command(get_sync_runner_command(
                client=runner_client_sync), token=1234567)
        runner_client_sync.cmd_sync.assert_called()


    def test_it_works_when_submit_runner_command_is_called_with_eauth(self):
        runner_client = MagicMock()
        runner_client.cmd_async = MagicMock()
        APIClient.submit_runner_command(get_async_runner_command(
                client=runner_client), eauth='pam')
        runner_client.cmd_async.assert_called()

        runner_client_sync = MagicMock()
        runner_client_sync.cmd_sync = MagicMock()
        APIClient.submit_runner_command(get_sync_runner_command(
                client=runner_client_sync), eauth='ldap')
        runner_client_sync.cmd_sync.assert_called()

if __name__ == '__main__':
    unittest.main()
