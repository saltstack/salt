'''
Make api awesomeness
'''
# Import Python libs
import inspect

# Import Salt libs
import salt.log  # pylint: disable=W0611
import salt.client
import salt.runner
import salt.wheel
import salt.utils
from salt.exceptions import SaltException, EauthAuthenticationError

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

        New backwards compatible client and fun naming scheme.
        In new scheme low['client'] is the client mode either 'sync' or 'async'.
        Default is 'async'
        If 'wheel' or 'runner' prefixes fun then use associated salt client given
            by prefix in the specified 'sync' or 'async' mode.
        Otherwise use local salt client in the given 'sync' or 'async' mode
        '''

        if not 'client' in low:
            low['client'] = 'async'
            #raise SaltException('No client specified')

        # check for wheel or runner prefix to fun name
        funparts = low.get('fun', '').split('.')
        if len(funparts) > 2 and funparts[0] in ['wheel', 'runner']:
            if low['client'] not in ['sync', 'async']: #client should be only 'sync' or 'async'
                raise SaltException('With fun of "{1}", client must be "sync" or "async" not "{0}".'\
                                    .format(low['client'], low['fun']))

            low['client'] = '{0}_{1}'.format(funparts[0], low['client'])
            low['fun'] = '.'.join(funparts[1:]) #strip prefix


        if not ('token' in low or 'eauth' in low):
            raise EauthAuthenticationError(
                    'No authentication credentials given')

        l_fun = getattr(self, low['client'])
        f_call = salt.utils.format_call(l_fun, low)

        ret = l_fun(*f_call.get('args', ()), **f_call.get('kwargs', {}))
        return ret

    def local_async(self, *args, **kwargs):
        '''
        Wrap LocalClient for running :ref:`execution modules <all-salt.modules>`
        and immediately return the job ID. The results of the job can then be
        retrieved at a later time.

        .. seealso:: :ref:`python-api`
        '''
        local = salt.client.LocalClient(self.opts['conf_file'])
        return local.run_job(*args, **kwargs)

    async = local_async # default async client

    def local_sync(self, *args, **kwargs):
        '''
        Wrap LocalClient for running :ref:`execution modules <all-salt.modules>`

        .. seealso:: :ref:`python-api`
        '''
        local = salt.client.LocalClient(self.opts['conf_file'])
        return local.cmd(*args, **kwargs)

    local = local_sync  # backwards compatible alias
    sync = local_sync # default sync client

    def runner_sync(self, fun, **kwargs):
        '''
        Wrap RunnerClient for executing :ref:`runner modules <all-salt.runners>`
        '''
        runner = salt.runner.RunnerClient(self.opts)
        return runner.low(fun, kwargs)

    runner = runner_sync #backwards compatible alias
    runner_async = runner_sync # until we get an runner_async

    def wheel_sync(self, fun, **kwargs):
        '''
        Wrap Wheel to enable executing :ref:`wheel modules <all-salt.wheel>`
        '''
        kwargs['fun'] = fun
        wheel = salt.wheel.Wheel(self.opts)
        return wheel.master_call(**kwargs)

    wheel = wheel_sync # backwards compatible alias
    wheel_async = wheel_sync # so it works either mode
