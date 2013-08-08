'''
This module provides the point of entry for client applications to interface to salt.
The purpose is to have a simplified consistent interface for various client applications

'''
# Import Python libs
import inspect

# Import Salt libs
import salt.auth
import salt.client
import salt.runner
import salt.wheel
import salt.utils
from salt.exceptions import SaltException, EauthAuthenticationError

def tokenify(low, token=None):
    '''
    If token is not None Then assign token to 'token' key of lowstate cmd dict
        low and return low
    Otherwise return low
    '''
    if token is not None:
        low['token'] = token
    return low


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
        self.local = salt.client.LocalClient(self.opts['conf_file'])
        self.runner = salt.runner.RunnerClient(self.opts)
        self.wheel = salt.wheel.Wheel(self.opts)
        self.auth = salt.auth.LoadAuth(self.opts)
        self.event = salt.utils.event.SaltEvent('master', self.opts['sock_dir'])

    def run(self, low):
        '''
        Execute the specified function in the specified client by passing the
        lowstate cmd
        
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
        return self.local.run_job(*args, **kwargs)
    
    async = local_async # default async client

    def local_sync(self, *args, **kwargs):
        '''
        Wrap LocalClient for running :ref:`execution modules <all-salt.modules>`

        .. seealso:: :ref:`python-api`
        '''
        return self.local.cmd(*args, **kwargs)
    
    local = local_sync  # backwards compatible alias
    sync = local_sync # default sync client

    def runner_sync(self, fun, **kwargs):
        '''
        Wrap RunnerClient for executing :ref:`runner modules <all-salt.runners>`
        '''
        return self.runner.low(fun, kwargs)
    
    runner = runner_sync #backwards compatible alias
    runner_async = runner_sync # until we get an runner_async

    def wheel_sync(self, fun, **kwargs):
        '''
        Wrap Wheel to enable executing :ref:`wheel modules <all-salt.wheel>`
        '''
        kwargs['fun'] = fun
        return self.wheel.master_call(**kwargs)
    
    wheel = wheel_sync # backwards compatible alias
    wheel_async = wheel_sync # so it works either mode
    
    def create_token(self, creds):
        '''
        Create token with creds.
        Token authorizes salt access if successful authentication
        with the credentials in creds.
        creds format is as follows:
        
        {
            'username': 'namestring',
            'password': 'passwordstring',
            'eauth': 'eauthtypestring',
        }
        
        examples of valid eauth type strings: 'pam' or 'ldap'
        
        Returns dictionary of token information with the following format:
        
        {
            'token': 'tokenstring',
            'start': starttimeinfractionalseconds,
            'expire': expiretimeinfactionalseconds,
            'name': 'usernamestring',
            'user': 'usernamestring',
            'username': 'usernamestring',
            'eauth': 'eauthtypestring',
            'perms: permslistofstrings,
        }
        The perms list provides those parts of salt for which the user is authorised
        to execute.
        example perms list:
        [
            "grains.*",
            "status.*",
            "sys.*",
            "test.*"
        ]
        
        '''
        try:
            tokenage = self.auth.mk_token(creds)
        except IOError as ex:
            if ex.errno == 13:
                raise  #should raise permissions error here
        
            
        if not 'token' in tokenage:
            raise EauthAuthenticationError("Authentication failed with provided credentials.") 
            
        # Grab eauth config for the current backend for the current user
        if tokenage['name'] in self.opts['external_auth'][tokenage['eauth']]:
            tokenage['perms'] = self.opts['external_auth'][tokenage['eauth']][tokenage['name']]
        else:
            tokenage['perms'] = self.opts['external_auth'][tokenage['eauth']]['*']
        
        tokenage['user'] = tokenage['name']
        tokenage['username'] = tokenage['name']
        
        return tokenage
    
    def get_next_event(self, wait=0.25, tag='', full=False):
        '''
        Returns next available event with tag tag from event bus
        If any within wait seconds
        Otherwise return None
        
        If tag is empty then return events for all tags
        If full then add tag field to returned data
        
        If wait is 0 then block forever or until next event becomes available.
        '''
        return (self.event.get_event(wait=wait, tag=tag, full=full))  