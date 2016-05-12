class Command(object):
    '''
    The command base class
    '''
    SYNC = 'runner'
    ASYNC = 'runner_async'

    def execute(self, *args, **kwargs):
        '''
        This will be implemented by subclasses
        :return: None
        '''
        pass


class SaltRunnerError(RuntimeError):
    '''
    Represent any errors
    '''
    pass


class RunnerReceiver(object):
    '''
    The receiver for runner class
    '''
    def __init__(self, salt_client=None):
        '''
        Sets the salt client to be used.
        Can be RunnerClient, LocalClient
        or WheelClient depending on the operation.
        :param salt_client: The python client that will be used
        '''
        self.client = salt_client

    def _get_method_name_to_call(self, low):
        '''
        Return the String method name
        :param client: sync or async
        :return: String method name or the empty string
        '''

        methods = {
            Command.SYNC: 'cmd_sync',
            Command.ASYNC: 'cmd_async',
        }
        client = low['client']
        if client not in methods:
            return ''
        return methods[client]

    def _build_low_data(self, low, **kwargs):
        '''
        :param low: the low data passed in
        :return: new dictionary of updated low data
        that has defaults filled in for all parameters
        and auth values. This low data should be in a
        form accepted by RunnerClient
        '''
        low_data = {
            'fun': low['fun'],
            'arg': low.get('arg', []) or [],  # ensure arg is initialized
            'kwarg': low.get('kwarg', {}) or {},  # ensure kwarg is initialized
        }

        if 'token' in kwargs:
            low_data.update({
                'token': kwargs.get('token'),
            })
        elif 'eauth' in kwargs:
            low_data.update({
                'username': kwargs.get('username', ''),
                'password': kwargs.get('password', ''),
                'eauth': kwargs.get('eauth'),
            })
        else:  # Don't have token or eauth, bail!!
            raise SaltRunnerError(
                'Neither token or eauth found! Please set token or eauth and try again.')
        return low_data

    def action(self, low, *args, **kwargs):
        '''
        Calls cmd_* on the client
        :param low: The low data including client
        :return: None
        '''

        def _ignore_args(*args, **kwargs):
            '''
            ignore all arguments
            '''
            pass

        getattr(self.client,
                self._get_method_name_to_call(low),  # can be either cmd_sync or cmd_async
                _ignore_args)(self._build_low_data(low, **kwargs), timeout=10)


class RunnerCommand(Command):
    '''
    Class to represent runner commands
    '''
    REPR_MSGS = ''.join(['RunnerCommand(fun={0}', ', arg={1}', ', kwarg={2}',
                         ', client={3}', ', receiver={4})'])

    def __init__(self,
                 fun='job.list_jobs',
                 arg=None,
                 kwarg=None,
                 receiver=None):
        self.receiver = receiver
        self.client = Command.SYNC
        self.fun = fun
        self.arg = arg
        self.kwarg = kwarg

    def make_async(self):
        '''
        This should execute asynchronously
        '''
        self.client = Command.ASYNC

    def make_sync(self):
        '''
        This should execute synchronously
        '''
        self.client = Command.SYNC

    def execute(self, *args, **kwargs):
        '''
        Calls action on the receiver
        :return: None
        '''
        self.receiver.action({
            'fun': self.fun,
            'arg': self.arg,
            'kwarg': self.kwarg,
            'client': self.client,
        }, *args, **kwargs)

    def __repr__(self):
        return self.REPR_MSGS.format(
            repr(self.fun),
            repr(self.arg),
            repr(self.kwarg),
            repr(self.client),
            repr(self.receiver)
        )


def get_sync_runner_command(fun='job.list_job',
                            arg=None,
                            kwarg=None,
                            client=None
                            ):
    '''
    Commands need to be authenticated
    set (username, password and eauth) as keyword args

    :param fun: Runner module function (string) to call
    :param arg: Positional argument list
    :param kwarg: Dictionary with key value pairs
    :param client: The salt python client to use (RunnerClient).
    :return: RunnerCommand instance
    '''
    return RunnerCommand(
        receiver=RunnerReceiver(salt_client=client),
        fun=fun,
        arg=arg,
        kwarg=kwarg
    )

def get_async_runner_command(fun='job.list_job', arg=None,
                             kwarg=None, client=None):
    '''
    :param fun: Runner module function (string) to call
    :param arg: Positional argument list
    :param kwarg: Dictionary with key value pairs
    :param client: The salt python client to use (RunnerClient).
    :return: RunnerCommand instance
    '''
    cmd = RunnerCommand(
        receiver=RunnerReceiver(salt_client=client),
        fun=fun,
        arg=arg,
        kwarg=kwarg
    )
    cmd.make_async()
    return cmd


class APIClient(object):

    @staticmethod
    def submit_runner_command(command, *args, **kwargs):
        '''
        Executes this command instance
        '''
        command.execute(*args, **kwargs)
