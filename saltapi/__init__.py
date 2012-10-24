'''
Make api awesomeness
'''

# Import python libs
#
# Import Salt libs
import salt.utils
import salt.client
import salt.runner

class API(object):
    '''
    '''
    def __init__(self, opts):
        self.opts = opts
        self.local = salt.client.LocalClient(opts['conf_file'])

    def run(self, low):
        '''
        '''
        if not 'client' in low:
            raise SaltException('No client specified')
        l_fun = getattr(self, low['client'])
        fcall = format_call(l_fun, low)
        if 'kwargs' in fcall:
            ret = l_fun(*fcall['args'], **fcall['kwargs'])
        else:
            ret = l_fun(*f_call['args'])
        return ret

    def cmd(
            tgt,
            fun,
            arg=(),
            expr_form='glob',
            ret='',
            timeout=None,
            **kwargs):
        '''
        Wrap running a job
        '''
        return self.local.run_job(
                tgt,
                fun,
                arg,
                expr_form,
                ret,
                timeout,
                **kwargs).get('jid')

    def runner(fun, **kwargs):
        '''
        '''
        runner = salt.runner.RunnerClient(opts)
        return salt.runner.low(fun, kwargs)
        
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
    if isinstance(aspec[0], list):
        arglen = len(aspec[0])
    if isinstance(aspec[3], tuple):
        deflen = len(aspec[3])
    if aspec[2]:
        # This state accepts kwargs
        ret['kwargs'] = {}
        for key in data:
            # Passing kwargs the conflict with args == stack trace
            if key in aspec[0]:
                continue
            ret['kwargs'][key] = data[key]
    kwargs = {}
    for ind in range(arglen - 1, 0, -1):
        minus = arglen - ind
        if deflen - minus > -1:
            kwargs[aspec[0][ind]] = aspec[3][-minus]
    for arg in kwargs:
        if arg in data:
            kwargs[arg] = data[arg]
    for arg in aspec[0]:
        if arg in kwargs:
            ret['args'].append(kwargs[arg])
        else:
            ret['args'].append(data[arg])
    return ret
