# encoding: utf-8
'''
Make api awesomeness
'''
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
import salt.utils
from salt.exceptions import SaltException, EauthAuthenticationError


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

    def run(self, low):
        '''
        Execute the specified function in the specified client by passing the
        lowstate
        '''
        if 'client' not in low:
            raise SaltException('No client specified')

        if not ('token' in low or 'eauth' in low):
            raise EauthAuthenticationError(
                    'No authentication credentials given')

        l_fun = getattr(self, low['client'])
        f_call = salt.utils.format_call(l_fun, low)

        ret = l_fun(*f_call.get('args', ()), **f_call.get('kwargs', {}))
        return ret

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

        Wraps :py:meth:`salt.client.LocalClient.cmd`.

        :return: Returns the result from the execution module
        '''
        local = salt.client.get_local_client(mopts=self.opts)
        return local.cmd(*args, **kwargs)

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

    def runner(self, fun, timeout=None, **kwargs):
        '''
        Run `runner modules <all-salt.runners>` synchronously

        Wraps :py:meth:`salt.runner.RunnerClient.cmd_sync`.

        :return: Returns the result from the runner module
        '''
        kwargs['fun'] = fun
        runner = salt.runner.RunnerClient(self.opts)
        return runner.cmd_sync(kwargs, timeout=timeout)

    def runner_async(self, fun, **kwargs):
        '''
        Run `runner modules <all-salt.runners>` asynchronously

        Wraps :py:meth:`salt.runner.RunnerClient.cmd_async`.

        :return: event data and a job ID for the executed function.
        '''
        kwargs['fun'] = fun
        runner = salt.runner.RunnerClient(self.opts)
        return runner.cmd_async(kwargs)

    def wheel(self, fun, **kwargs):
        '''
        Run :ref:`wheel modules <all-salt.wheel>` synchronously

        Wraps :py:meth:`salt.wheel.WheelClient.master_call`.

        :return: Returns the result from the wheel module
        '''
        kwargs['fun'] = fun
        wheel = salt.wheel.WheelClient(self.opts)
        return wheel.master_call(**kwargs)

    def wheel_async(self, fun, **kwargs):
        '''
        Run :ref:`wheel modules <all-salt.wheel>` asynchronously

        Wraps :py:meth:`salt.wheel.WheelClient.master_call`.

        :return: Returns the result from the wheel module
        '''
        kwargs['fun'] = fun
        wheel = salt.wheel.WheelClient(self.opts)
        return wheel.cmd_async(kwargs)
