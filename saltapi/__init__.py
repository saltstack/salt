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
    Provide a uniform method of accessing the various *Client interfaces in
    Salt in the form of LowData data structures.

    >>> client = APIClient(__opts__)
    >>> lowdata = {'client': 'local', 'tgt': '*', 'fun': 'test.ping', 'arg': ''}
    >>> client.run(lowdata)
    '''
    def __init__(self, opts):
        self.opts = opts

    def run(self, low):
        '''
        Execute the specified function in the specified client by passing the
        LowData
        '''
        # FIXME: the called *Client functions must be consistently
        # asynchronous. this will need to be addressed across the board

        if not 'client' in low:
            raise SaltException('No client specified')

        l_fun = getattr(self, low['client'])
        f_call = salt.utils.format_call(l_fun, low)

        ret = l_fun(*f_call.get('args', ()), **f_call.get('kwargs', {}))
        return ret

    def local(self, *args, **kwargs):
        '''
        Wrap the LocalClient for running execution modules
        '''
        local = salt.client.LocalClient(self.opts['conf_file'])
        return local.cmd(*args, **kwargs)

    def runner(self, fun, **kwargs):
        '''
        Wrap the RunnerClient for executing runner modules
        '''
        runner = salt.runner.RunnerClient(self.opts)
        return runner.low(fun, kwargs)

    def wheel(self, fun, **kwargs):
        '''
        Wrap the Wheel object to enable sending commands via the wheel system
        '''
        kwargs['fun'] = fun
        wheel = salt.wheel.Wheel(self.opts)
        return wheel.master_call(**kwargs)
