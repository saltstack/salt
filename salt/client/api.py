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
        self.localClient = salt.client.LocalClient(self.opts['conf_file'])
        self.runnerClient = salt.runner.RunnerClient(self.opts)
        self.wheelClient = salt.wheel.Wheel(self.opts)
        self.resolver = salt.auth.Resolver(self.opts)
        self.event = salt.utils.event.SaltEvent('master', self.opts['sock_dir'])

    def run(self, cmd):
        '''
        Execute the salt command given by cmd dict.
        
        cmd is a dictionary of the following form:
        
        {
            'mode': 'modestring',
            'fun' : 'modulefunctionstring',
            'kwarg': functionkeywordargdictionary,
            'tgt' : 'targetpatternstring',
            'expr_form' : 'targetpatterntype',
            'ret' : 'returner namestring',
            'timeout': 'functiontimeout',
            'arg' : 'functionpositionalarg sequence',
            'token': 'salttokenstring',
            'username': 'usernamestring',
            'password': 'passwordstring',
            'eauth': 'eauthtypestring',
        }
        
        Implied by the fun is which client is used to run the command, that is, either
        the local minion client, the master runner client, or the master wheel client.
        
        The cmd dict items are as follows:
        
        mode: either 'sync' or 'async'. Defaults to 'async' if missing
        fun: required. If the function is to be run on the master using either
            a wheel or runner client then the fun: includes either
            'wheel.' or 'runner.' as a prefix and has three parts separated by '.'.
            Otherwise the fun: specifies a module to be run on a minion via the local
            client.
            Example:
                fun of  'wheel.config.values' run with master wheel client
                fun or 'wheel.foobar' run with with minion local client
                fun of 'test.ping' run with minion local client
                fun of 'runnner.manage.status' run with master runner client
                    tgt,
        kwarg: A dictionary of keyword function parameters to be passed to the eventual
               salt function specificed by fun:
        tgt: Pattern string specifying the targeted minions when the implied client is local
        expr_form: Optional target pattern type string when client is local.
            Example: 'glob' defaults to 'glob' if missing
        ret: Optional name string of returner when local client.
        arg: Optional positional argument string when local client      
        token: the salt token. Either token: is required or the set of username:,
            password: , and eauth:
        username: the salt username. Required if token is missing.
        password: the user's password. Required if token is missing.
        eauth: the authentication type such as 'pam' or 'ldap'. Required if token is missing
        
        '''
        client = 'local' #default to minion local client
        mode = cmd.get('mode', 'async') #default to 'async'
        
        # check for wheel or runner prefix to fun name to use wheel or runner client
        funparts = cmd.get('fun', '').split('.') 
        if len(funparts) > 2 and funparts[0] in ['wheel', 'runner']: #master 
            client = funparts[0]
            cmd['fun'] = '.'.join(funparts[1:]) #strip prefix
            
        if not ('token' in cmd  or
                ('eauth' in cmd and 'password' in cmd and 'username' in cmd) ):
            raise EauthAuthenticationError('No authentication credentials given')
        
        executor = getattr(self, '{0}_{1}'.format(client, mode))
        

        ret = executor(**cmd)
        return ret

    def local_async(self, **kwargs):
        '''
        Wrap LocalClient for running :ref:`execution modules <all-salt.modules>`
        and immediately return the job ID. The results of the job can then be
        retrieved at a later time.

        .. seealso:: :ref:`python-api`
        '''
        return self.localClient.run_job(**kwargs)
    
    async = local_async # default async client

    def local_sync(self, *args, **kwargs):
        '''
        Wrap LocalClient for running :ref:`execution modules <all-salt.modules>`

        .. seealso:: :ref:`python-api`
        '''
        return self.localClient.cmd(**kwargs)
    
    def runner_async(self, **kwargs):
        '''
        Wrap RunnerClient for executing :ref:`runner modules <all-salt.runners>`
        Expects that one of the kwargs is key 'fun' whose value is the namestring
        of the function to call
        '''
        return self.runnerClient.master_call(**kwargs)
    
    runner_sync = runner_async # always runner async, so works in either mode

    def wheel_sync(self, **kwargs):
        '''
        Wrap Wheel to enable executing :ref:`wheel modules <all-salt.wheel>`
        Expects that one of the kwargs is key 'fun' whose value is the namestring
        of the function to call
        '''
        return self.wheelClient.master_call(**kwargs)
    
    wheel_async = wheel_sync # always wheel_sync, so it works either mode
    
    def signatures(self, **kwargs):
        '''
        Returns dict of function signatures for the specified fun.
        
        '''
        return {}
    
    
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
            tokenage = self.resolver.mk_token(creds)
        except Exception as ex:
            raise EauthAuthenticationError(
                "Authentication failed with {0}.".format(repr(ex)))
            
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

    def verify_token(self, token):
        '''
        If token is valid Then returns user name associated with token
        Else False.
        '''
        try:
            result = self.resolver.get_token(token)
        except Exception as ex:
            raise EauthAuthenticationError(
                "Token validation failed with {0}.".format(repr(ex)))
        
        return result
    
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