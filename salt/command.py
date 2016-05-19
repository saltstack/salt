# encoding: utf-8
'''
Command
=======
Module to encapsulate invocations to Salt's Python clients.
.. versionadded:: Boron

Contains the :py:class:`Command `which is the base class for all
Runner, Local and Wheel commands.

Also exposes the function :py:func:`get_command_for_low_data`
that builds a :py:class:`Command` instance from low data.


Usage
-----
A :py:class:`Command` instance can be obtained by calling
:py:func:`get_command_for_low_data` as shown.

.. code-block:: python

    command = get_command_for_low_data(low)  # low is the dictionary with salt's low data

The class :py:class:`APIClient` has a submit method that allows
the command created above to be submitted for execution.

.. code-block:: python

    command = get_command_for_low_data(low)  # low is the dictionary with salt's low data
    APIClient.submit(command)  # calls runner, wheel or local client

'''

from salt.runner import RunnerClient


class Command(object):
    '''
    The command base class
    '''
    #pylint: disable=too-few-public-methods
    SYNC = 'runner'
    ASYNC = 'runner_async'

    def execute(self, *args, **kwargs):
        '''
        This will be implemented by subclasses
        :return: None
        '''
        pass


class SaltCommandError(RuntimeError):
    '''
    Represent any errors
    '''
    pass


class RunnerReceiver(object):
    '''
    The receiver for runner class
    '''
    #pylint: disable=too-few-public-methods
    def __init__(self, salt_client=None):
        '''
        Sets the salt client to be used.
        Can be :py:class:`RunnerClient`, :py:class:`LocalClient`
        or :py:class:`WheelClient` depending on the operation.
        :param salt_client: The python client that will be used
        '''
        self.client = salt_client

    def _get_method_name_to_call(self, low):
        '''
        Return the String method name
        :param client: sync or async
        :return: String method name or the empty string
        '''
        # pylint: disable=no-self-use
        methods = {
            Command.SYNC: 'cmd_sync',
            Command.ASYNC: 'cmd_async',
        }
        client = low['client']
        if client not in methods:
            return ''
        return methods[client]

    def action(self, low):
        '''
        Calls cmd_* on the client
        :param low: The low data including client
        :return: None
        '''
        getattr(self.client,
                self._get_method_name_to_call(low),  # can be either cmd_sync or cmd_async
                lambda *args, **kwargs: 1+1)(low, timeout=10)


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
                            client=None):
    '''
    :param fun: Runner module function (string) to call
    :param arg: Positional argument list
    :param kwarg: Dictionary with key value pairs
    :param client: The salt python client to use (eg :py:class:`RunnerClient`).
    :return: :py:class:`RunnerCommand` instance
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
    :param client: The salt python client to use (eg :py:class:`RunnerClient`).
    :return: py:class:`RunnerCommand` instance
    '''
    cmd = RunnerCommand(
        receiver=RunnerReceiver(salt_client=client),
        fun=fun,
        arg=arg,
        kwarg=kwarg
    )
    cmd.make_async()
    return cmd


def get_command_for_low_data(low):
    '''
    :param low: Dictionary with Salt's low data
    :return: The :py:class:`Command` instance, ready for execution
    '''
    client = low.get('client', None)
    if not client:
        raise SaltCommandError('Please specify a client!')

    if client.endswith('_async'):
        # TBD: Be able to return _any_ salt python client
        return get_async_runner_command(
            fun=low['fun'],
            client=RunnerClient({}),
            arg=low.get('arg', []),
            kwarg=low.get('kwarg', {}))
    else:
        return get_sync_runner_command(
            fun=low['fun'],
            client=RunnerClient({}),
            arg=low.get('arg', []),
            kwarg=low.get('kwarg', {}))


class APIClient(object):
    '''
    Salt's :py:class:`APIClient` to execute Salt commands.
    '''
    # pylint: disable=too-few-public-methods

    @staticmethod
    def submit_runner_command(command, *args, **kwargs):
        '''
        Executes this command instance
        '''
        command.execute(*args, **kwargs)
