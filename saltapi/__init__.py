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
        fcall = salt.utils.format_call(l_fun, low)
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
        
