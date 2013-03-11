'''
Make api awesomeness
'''
# Import Python libs
import inspect

# Import Salt libs
import salt.client
import salt.runner
import salt.wheel
import salt.utils
from salt.exceptions import SaltException

class APIClient(object):
    '''
    Provide a uniform method of accessing the various client interfaces in Salt
    in the form of low-data data structures. For example:

    >>> client = APIClient(__opts__)
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
        if not 'client' in low:
            raise SaltException('No client specified')

        l_fun = getattr(self, low['client'])
        f_call = salt.utils.format_call(l_fun, low)

        ret = l_fun(*f_call.get('args', ()), **f_call.get('kwargs', {}))
        return ret

    def local_async(self, *args, **kwargs):
        '''
        Wrap LocalClient for running :ref:`execution modules <all-salt.modules>`
        and immediately return the job ID. The results of the job can then be
        retrieved at a later time.
        '''
        local = salt.client.LocalClient(self.opts['conf_file'])
        return local.run_job(*args, **kwargs)

    def local(self, *args, **kwargs):
        '''
        Wrap LocalClient for running :ref:`execution modules <all-salt.modules>`
        '''
        local = salt.client.LocalClient(self.opts['conf_file'])
        return local.cmd(*args, **kwargs)

    def runner(self, fun, **kwargs):
        '''
        Wrap RunnerClient for executing :ref:`runner modules <all-salt.runners>`
        '''
        runner = salt.runner.RunnerClient(self.opts)
        return runner.low(fun, kwargs)

    def wheel(self, fun, **kwargs):
        '''
        Wrap Wheel to enable executing :ref:`wheel modules <all-salt.wheel>`
        '''
        kwargs['fun'] = fun
        wheel = salt.wheel.Wheel(self.opts)
        return wheel.master_call(**kwargs)
