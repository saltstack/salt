# -*- coding: utf-8 -*-
'''
This module provides the point of entry for client applications to interface to
salt. The purpose is to have a simplified consistent interface for various
client applications.

.. warning:: This API is not yet public or stable!

    This API exists in its current form as an entry point for Halite only. This
    interface is likely to change without warning. Long-term plans are to make
    this public as a unified interface to Salt's *Client() APIs. Until that
    time please use Salt's *Client() interfaces individually:

    http://docs.saltstack.com/ref/clients/index.html

'''

# Import Python libs
from __future__ import absolute_import
import os

# Import Salt libs
import salt.config
import salt.auth
import salt.client
import salt.runner
import salt.wheel
import salt.utils.args
import salt.utils.event
import salt.syspaths as syspaths
from salt.exceptions import EauthAuthenticationError


def tokenify(cmd, token=None):
    '''
    If token is not None Then assign token to 'token' key of cmd dict
        and return cmd
    Otherwise return cmd
    '''
    if token is not None:
        cmd[u'token'] = token
    return cmd


class APIClient(object):
    '''
    Provide a uniform method of accessing the various client interfaces in Salt
    in the form of low-data data structures. For example:
    '''
    def __init__(self, opts=None, listen=True):
        if not opts:
            opts = salt.config.client_config(
                os.environ.get(
                    u'SALT_MASTER_CONFIG',
                    os.path.join(syspaths.CONFIG_DIR, u'master')
                )
            )
        self.opts = opts
        self.localClient = salt.client.get_local_client(self.opts[u'conf_file'])
        self.runnerClient = salt.runner.RunnerClient(self.opts)
        self.wheelClient = salt.wheel.Wheel(self.opts)
        self.resolver = salt.auth.Resolver(self.opts)
        self.event = salt.utils.event.get_event(
                u'master',
                self.opts[u'sock_dir'],
                self.opts[u'transport'],
                opts=self.opts,
                listen=listen)

    def run(self, cmd):
        '''
        Execute the salt command given by cmd dict.

        cmd is a dictionary of the following form:

        {
            'mode': 'modestring',
            'fun' : 'modulefunctionstring',
            'kwarg': functionkeywordargdictionary,
            'tgt' : 'targetpatternstring',
            'tgt_type' : 'targetpatterntype',
            'ret' : 'returner namestring',
            'timeout': 'functiontimeout',
            'arg' : 'functionpositionalarg sequence',
            'token': 'salttokenstring',
            'username': 'usernamestring',
            'password': 'passwordstring',
            'eauth': 'eauthtypestring',
        }

        Implied by the fun is which client is used to run the command, that is, either
        the master local minion client, the master runner client, or the master wheel client.

        The cmd dict items are as follows:

        mode: either 'sync' or 'async'. Defaults to 'async' if missing
        fun: required. If the function is to be run on the master using either
            a wheel or runner client then the fun: includes either
            'wheel.' or 'runner.' as a prefix and has three parts separated by '.'.
            Otherwise the fun: specifies a module to be run on a minion via the local
            minion client.
            Example:
                fun of 'wheel.config.values' run with master wheel client
                fun of 'runner.manage.status' run with master runner client
                fun of 'test.ping' run with local minion client
                fun of 'wheel.foobar' run with with local minion client not wheel
        kwarg: A dictionary of keyword function parameters to be passed to the eventual
               salt function specified by fun:
        tgt: Pattern string specifying the targeted minions when the implied client is local
        tgt_type: Optional target pattern type string when client is local minion.
            Defaults to 'glob' if missing
        ret: Optional name string of returner when local minion client.
        arg: Optional positional argument string when local minion client
        token: the salt token. Either token: is required or the set of username:,
            password: , and eauth:
        username: the salt username. Required if token is missing.
        password: the user's password. Required if token is missing.
        eauth: the authentication type such as 'pam' or 'ldap'. Required if token is missing

        '''
        cmd = dict(cmd)  # make copy
        client = u'minion'  # default to local minion client
        mode = cmd.get(u'mode', u'async')  # default to 'async'

        # check for wheel or runner prefix to fun name to use wheel or runner client
        funparts = cmd.get(u'fun', u'').split(u'.')
        if len(funparts) > 2 and funparts[0] in [u'wheel', u'runner']:  # master
            client = funparts[0]
            cmd[u'fun'] = u'.'.join(funparts[1:])  # strip prefix

        if not (u'token' in cmd or
                (u'eauth' in cmd and u'password' in cmd and u'username' in cmd)):
            raise EauthAuthenticationError(u'No authentication credentials given')

        executor = getattr(self, u'{0}_{1}'.format(client, mode))
        result = executor(**cmd)
        return result

    def minion_async(self, **kwargs):
        '''
        Wrap LocalClient for running :ref:`execution modules <all-salt.modules>`
        and immediately return the job ID. The results of the job can then be
        retrieved at a later time.

        .. seealso:: :ref:`python-api`
        '''
        return self.localClient.run_job(**kwargs)

    def minion_sync(self, **kwargs):
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

    runner_sync = runner_async  # always runner async, so works in either mode

    def wheel_sync(self, **kwargs):
        '''
        Wrap Wheel to enable executing :ref:`wheel modules <all-salt.wheel>`
        Expects that one of the kwargs is key 'fun' whose value is the namestring
        of the function to call
        '''
        return self.wheelClient.master_call(**kwargs)

    wheel_async = wheel_sync  # always wheel_sync, so it works either mode

    def signature(self, cmd):
        '''
        Convenience function that returns dict of function signature(s) specified by cmd.

        cmd is dict of the form:
        {
            'module' : 'modulestring',
            'tgt' : 'targetpatternstring',
            'tgt_type' : 'targetpatterntype',
            'token': 'salttokenstring',
            'username': 'usernamestring',
            'password': 'passwordstring',
            'eauth': 'eauthtypestring',
        }

        The cmd dict items are as follows:

        module: required. This is either a module or module function name for
            the specified client.
        tgt: Optional pattern string specifying the targeted minions when client
          is 'minion'
        tgt_type: Optional target pattern type string when client is 'minion'.
            Example: 'glob' defaults to 'glob' if missing
        token: the salt token. Either token: is required or the set of username:,
            password: , and eauth:
        username: the salt username. Required if token is missing.
        password: the user's password. Required if token is missing.
        eauth: the authentication type such as 'pam' or 'ldap'. Required if token is missing

        Adds client per the command.
        '''
        cmd[u'client'] = u'minion'
        if len(cmd[u'module'].split(u'.')) > 2 and cmd[u'module'].split(u'.')[0] in [u'runner', u'wheel']:
            cmd[u'client'] = u'master'
        return self._signature(cmd)

    def _signature(self, cmd):
        '''
        Expects everything that signature does and also a client type string.
        client can either be master or minion.
        '''
        result = {}

        client = cmd.get(u'client', u'minion')
        if client == u'minion':
            cmd[u'fun'] = u'sys.argspec'
            cmd[u'kwarg'] = dict(module=cmd[u'module'])
            result = self.run(cmd)
        elif client == u'master':
            parts = cmd[u'module'].split(u'.')
            client = parts[0]
            module = u'.'.join(parts[1:])  # strip prefix
            if client == u'wheel':
                functions = self.wheelClient.functions
            elif client == u'runner':
                functions = self.runnerClient.functions
            result = {u'master': salt.utils.args.argspec_report(functions, module)}
        return result

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
            'expire': expiretimeinfractionalseconds,
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
                u"Authentication failed with {0}.".format(repr(ex)))

        if u'token' not in tokenage:
            raise EauthAuthenticationError(u"Authentication failed with provided credentials.")

        # Grab eauth config for the current backend for the current user
        tokenage_eauth = self.opts[u'external_auth'][tokenage[u'eauth']]
        if tokenage[u'name'] in tokenage_eauth:
            tokenage[u'perms'] = tokenage_eauth[tokenage[u'name']]
        else:
            tokenage[u'perms'] = tokenage_eauth[u'*']

        tokenage[u'user'] = tokenage[u'name']
        tokenage[u'username'] = tokenage[u'name']

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
                u"Token validation failed with {0}.".format(repr(ex)))

        return result

    def get_event(self, wait=0.25, tag=u'', full=False):
        '''
        Get a single salt event.
        If no events are available, then block for up to ``wait`` seconds.
        Return the event if it matches the tag (or ``tag`` is empty)
        Otherwise return None

        If wait is 0 then block forever or until next event becomes available.
        '''
        return self.event.get_event(wait=wait, tag=tag, full=full, auto_reconnect=True)

    def fire_event(self, data, tag):
        '''
        fires event with data and tag
        This only works if api is running with same user permissions as master
        Need to convert this to a master call with appropriate authentication

        '''
        return self.event.fire_event(data, salt.utils.event.tagify(tag, u'wui'))
