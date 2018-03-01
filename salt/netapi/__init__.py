# encoding: utf-8
'''
Make api awesomeness
'''
from __future__ import absolute_import, print_function, unicode_literals
# Import Python libs
import inspect
import os

# Import Salt libs
import salt.log  # pylint: disable=W0611
import salt.client
import salt.config
import salt.runner
import salt.syspaths
import salt.wheel
import salt.utils.args
import salt.client.ssh.client
import salt.exceptions

# Import third party libs
from salt.ext import six


class NetapiClient(object):
    '''
    Provide a uniform method of accessing the various client interfaces in Salt
    in the form of low-data data structures. For example:

    >>> client = NetapiClient(__opts__)
    >>> lowstate = {'client': 'local', 'tgt': '*', 'fun': 'test.ping', 'arg': ''}
    >>> client.run(lowstate)
    '''

    def __init__(self, opts):
        self.opts = opts

    def _is_master_running(self):
        '''
        Perform a lightweight check to see if the master daemon is running

        Note, this will return an invalid success if the master crashed or was
        not shut down cleanly.
        '''
        if self.opts['transport'] == 'tcp':
            ipc_file = 'publish_pull.ipc'
        else:
            ipc_file = 'workers.ipc'
        return os.path.exists(os.path.join(
            self.opts['sock_dir'],
            ipc_file))

    def run(self, low):
        '''
        Execute the specified function in the specified client by passing the
        lowstate
        '''
        # Eauth currently requires a running daemon and commands run through
        # this method require eauth so perform a quick check to raise a
        # more meaningful error.
        if not self._is_master_running():
            raise salt.exceptions.SaltDaemonNotRunning(
                    'Salt Master is not available.')

        if low.get('client') not in CLIENTS:
            raise salt.exceptions.SaltInvocationError(
                    'Invalid client specified: \'{0}\''.format(low.get('client')))

        if not ('token' in low or 'eauth' in low) and low['client'] != 'ssh':
            raise salt.exceptions.EauthAuthenticationError(
                    'No authentication credentials given')

        l_fun = getattr(self, low['client'])
        f_call = salt.utils.args.format_call(l_fun, low)
        return l_fun(*f_call.get('args', ()), **f_call.get('kwargs', {}))

    def local_async(self, *args, **kwargs):
        '''
        Run :ref:`execution modules <all-salt.modules>` asynchronously

        Wraps :py:meth:`salt.client.LocalClient.run_job`.

        :return: job ID
        '''
        local = salt.client.get_local_client(mopts=self.opts)
        return local.run_job(*args, **kwargs)

    def local(self, *args, **kwargs):
        '''
        Run :ref:`execution modules <all-salt.modules>` synchronously

        See :py:meth:`salt.client.LocalClient.cmd` for all available
        parameters.

        Sends a command from the master to the targeted minions. This is the
        same interface that Salt's own CLI uses. Note the ``arg`` and ``kwarg``
        parameters are sent down to the minion(s) and the given function,
        ``fun``, is called with those parameters.

        :return: Returns the result from the execution module
        '''
        local = salt.client.get_local_client(mopts=self.opts)
        return local.cmd(*args, **kwargs)

    def local_subset(self, *args, **kwargs):
        '''
        Run :ref:`execution modules <all-salt.modules>` against subsets of minions

        .. versionadded:: 2016.3.0

        Wraps :py:meth:`salt.client.LocalClient.cmd_subset`
        '''
        local = salt.client.get_local_client(mopts=self.opts)
        return local.cmd_subset(*args, **kwargs)

    def local_batch(self, *args, **kwargs):
        '''
        Run :ref:`execution modules <all-salt.modules>` against batches of minions

        .. versionadded:: 0.8.4

        Wraps :py:meth:`salt.client.LocalClient.cmd_batch`

        :return: Returns the result from the exeuction module for each batch of
            returns
        '''
        local = salt.client.get_local_client(mopts=self.opts)
        return local.cmd_batch(*args, **kwargs)

    def ssh(self, *args, **kwargs):
        '''
        Run salt-ssh commands synchronously

        Wraps :py:meth:`salt.client.ssh.client.SSHClient.cmd_sync`.

        :return: Returns the result from the salt-ssh command
        '''
        ssh_client = salt.client.ssh.client.SSHClient(mopts=self.opts,
                                                      disable_custom_roster=True)
        return ssh_client.cmd_sync(kwargs)

    def runner(self, fun, timeout=None, full_return=False, **kwargs):
        '''
        Run `runner modules <all-salt.runners>` synchronously

        Wraps :py:meth:`salt.runner.RunnerClient.cmd_sync`.

        Note that runner functions must be called using keyword arguments.
        Positional arguments are not supported.

        :return: Returns the result from the runner module
        '''
        kwargs['fun'] = fun
        runner = salt.runner.RunnerClient(self.opts)
        return runner.cmd_sync(kwargs, timeout=timeout, full_return=full_return)

    def runner_async(self, fun, **kwargs):
        '''
        Run `runner modules <all-salt.runners>` asynchronously

        Wraps :py:meth:`salt.runner.RunnerClient.cmd_async`.

        Note that runner functions must be called using keyword arguments.
        Positional arguments are not supported.

        :return: event data and a job ID for the executed function.
        '''
        kwargs['fun'] = fun
        runner = salt.runner.RunnerClient(self.opts)
        return runner.cmd_async(kwargs)

    def wheel(self, fun, **kwargs):
        '''
        Run :ref:`wheel modules <all-salt.wheel>` synchronously

        Wraps :py:meth:`salt.wheel.WheelClient.master_call`.

        Note that wheel functions must be called using keyword arguments.
        Positional arguments are not supported.

        :return: Returns the result from the wheel module
        '''
        kwargs['fun'] = fun
        wheel = salt.wheel.WheelClient(self.opts)
        return wheel.cmd_sync(kwargs)

    def wheel_async(self, fun, **kwargs):
        '''
        Run :ref:`wheel modules <all-salt.wheel>` asynchronously

        Wraps :py:meth:`salt.wheel.WheelClient.master_call`.

        Note that wheel functions must be called using keyword arguments.
        Positional arguments are not supported.

        :return: Returns the result from the wheel module
        '''
        kwargs['fun'] = fun
        wheel = salt.wheel.WheelClient(self.opts)
        return wheel.cmd_async(kwargs)

CLIENTS = [
    name for name, _
    in inspect.getmembers(NetapiClient, predicate=inspect.ismethod if six.PY2 else None)
    if not (name == 'run' or name.startswith('_'))
]
