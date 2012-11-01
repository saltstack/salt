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
        f_call = format_call(l_fun, low)

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


### Remove when salt 0.10.5 is released!
def _getargs(func):
    '''
    A small wrapper around getargspec that also supports callable classes
    '''
    if not callable(func):
        raise TypeError('{0} is not a callable'.format(func))

    if inspect.isfunction(func):
        aspec = inspect.getargspec(func)
    elif inspect.ismethod(func):
        aspec = inspect.getargspec(func)
        del aspec.args[0] # self
    elif isinstance(func, object):
        aspec = inspect.getargspec(func.__call__)
        del aspec.args[0]  # self
    else:
        raise TypeError("Cannot inspect argument list for '{0}'".format(func))

    return aspec


def format_call(fun, data):
    '''
    Pass in a function and a dict containing arguments to the function.

    A dict with the keys args and kwargs is returned
    '''
    ret = {}
    ret['args'] = []
    aspec = _getargs(fun)
    arglen = 0
    deflen = 0
    if isinstance(aspec.args, list):
        arglen = len(aspec.args)
    if isinstance(aspec.defaults, tuple):
        deflen = len(aspec.defaults)
    if aspec.keywords:
        # This state accepts kwargs
        ret['kwargs'] = {}
        for key in data:
            # Passing kwargs the conflict with args == stack trace
            if key in aspec.args:
                continue
            ret['kwargs'][key] = data[key]
    kwargs = {}
    for ind in range(arglen - 1, 0, -1):
        minus = arglen - ind
        if deflen - minus > -1:
            kwargs[aspec.args[ind]] = aspec.defaults[-minus]
    for arg in kwargs:
        if arg in data:
            kwargs[arg] = data[arg]
    for arg in aspec.args:
        if arg in kwargs:
            ret['args'].append(kwargs[arg])
        else:
            ret['args'].append(data[arg])
    return ret
