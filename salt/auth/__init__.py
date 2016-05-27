# -*- coding: utf-8 -*-
'''
Salt's pluggable authentication system

This system allows for authentication to be managed in a module pluggable way
so that any external authentication system can be used inside of Salt
'''

from __future__ import absolute_import

# 1. Create auth loader instance
# 2. Accept arguments as a dict
# 3. Verify with function introspection
# 4. Execute auth function
# 5. Cache auth token with relative data opts['token_dir']
# 6. Interface to verify tokens

# Import python libs
from __future__ import print_function
import os
import collections
import hashlib
import time
import logging
import random
import getpass
from salt.ext.six.moves import input

# Import salt libs
import salt.config
import salt.loader
import salt.transport.client
import salt.utils
import salt.utils.minions
import salt.payload

log = logging.getLogger(__name__)

AUTH_INTERNAL_KEYWORDS = frozenset([
    'client',
    'cmd',
    'eauth',
    'fun',
    'kwarg',
    'match'
])


class LoadAuth(object):
    '''
    Wrap the authentication system to handle peripheral components
    '''
    def __init__(self, opts):
        self.opts = opts
        self.max_fail = 1.0
        self.serial = salt.payload.Serial(opts)
        self.auth = salt.loader.auth(opts)

    def load_name(self, load):
        '''
        Return the primary name associate with the load, if an empty string
        is returned then the load does not match the function
        '''
        if 'eauth' not in load:
            return ''
        fstr = '{0}.auth'.format(load['eauth'])
        if fstr not in self.auth:
            return ''
        fcall = salt.utils.format_call(self.auth[fstr],
                                       load,
                                       expected_extra_kws=AUTH_INTERNAL_KEYWORDS)
        try:
            return fcall['args'][0]
        except IndexError:
            return ''

    def __auth_call(self, load):
        '''
        Return the token and set the cache data for use

        Do not call this directly! Use the time_auth method to overcome timing
        attacks
        '''
        if 'eauth' not in load:
            return False
        fstr = '{0}.auth'.format(load['eauth'])
        if fstr not in self.auth:
            return False
        fcall = salt.utils.format_call(self.auth[fstr],
                                       load,
                                       expected_extra_kws=AUTH_INTERNAL_KEYWORDS)
        try:
            if 'kwargs' in fcall:
                return self.auth[fstr](*fcall['args'], **fcall['kwargs'])
            else:
                return self.auth[fstr](*fcall['args'])
        except Exception as e:
            log.debug('Authentication module threw {0}'.format(e))
            return False

    def time_auth(self, load):
        '''
        Make sure that all failures happen in the same amount of time
        '''
        start = time.time()
        ret = self.__auth_call(load)
        if ret:
            return ret
        f_time = time.time() - start
        if f_time > self.max_fail:
            self.max_fail = f_time
        deviation = self.max_fail / 4
        r_time = random.SystemRandom().uniform(
                self.max_fail - deviation,
                self.max_fail + deviation
                )
        while start + r_time > time.time():
            time.sleep(0.001)
        return False

    def get_groups(self, load):
        '''
        Read in a load and return the groups a user is a member of
        by asking the appropriate provider
        '''
        if 'eauth' not in load:
            return False
        fstr = '{0}.groups'.format(load['eauth'])
        if fstr not in self.auth:
            return False
        fcall = salt.utils.format_call(self.auth[fstr],
                                       load,
                                       expected_extra_kws=AUTH_INTERNAL_KEYWORDS)
        try:
            return self.auth[fstr](*fcall['args'], **fcall['kwargs'])
        except IndexError:
            return False
        except Exception:
            return None

    def _allow_custom_expire(self, load):
        '''
        Return bool if requesting user is allowed to set custom expire
        '''
        expire_override = self.opts.get('token_expire_user_override', False)

        if expire_override is True:
            return True

        if isinstance(expire_override, collections.Mapping):
            expire_whitelist = expire_override.get(load['eauth'], [])
            if isinstance(expire_whitelist, collections.Iterable):
                if load.get('username') in expire_whitelist:
                    return True

        return False

    def mk_token(self, load):
        '''
        Run time_auth and create a token. Return False or the token
        '''
        ret = self.time_auth(load)
        if ret is False:
            return {}
        fstr = '{0}.auth'.format(load['eauth'])
        hash_type = getattr(hashlib, self.opts.get('hash_type', 'md5'))
        tok = str(hash_type(os.urandom(512)).hexdigest())
        t_path = os.path.join(self.opts['token_dir'], tok)
        while os.path.isfile(t_path):
            tok = str(hash_type(os.urandom(512)).hexdigest())
            t_path = os.path.join(self.opts['token_dir'], tok)
        fcall = salt.utils.format_call(self.auth[fstr],
                                       load,
                                       expected_extra_kws=AUTH_INTERNAL_KEYWORDS)

        if self._allow_custom_expire(load):
            token_expire = load.pop('token_expire', self.opts['token_expire'])
        else:
            _ = load.pop('token_expire', None)
            token_expire = self.opts['token_expire']

        tdata = {'start': time.time(),
                 'expire': time.time() + token_expire,
                 'name': fcall['args'][0],
                 'eauth': load['eauth'],
                 'token': tok}

        if 'groups' in load:
            tdata['groups'] = load['groups']

        with salt.utils.fopen(t_path, 'w+b') as fp_:
            fp_.write(self.serial.dumps(tdata))
        return tdata

    def get_tok(self, tok):
        '''
        Return the name associated with the token, or False if the token is
        not valid
        '''
        t_path = os.path.join(self.opts['token_dir'], tok)
        if not os.path.isfile(t_path):
            return {}
        with salt.utils.fopen(t_path, 'rb') as fp_:
            tdata = self.serial.loads(fp_.read())
        rm_tok = False
        if 'expire' not in tdata:
            # invalid token, delete it!
            rm_tok = True
        if tdata.get('expire', '0') < time.time():
            rm_tok = True
        if rm_tok:
            try:
                os.remove(t_path)
                return {}
            except (IOError, OSError):
                pass
        return tdata


class Authorize(object):
    '''
    The authorization engine used by EAUTH
    '''
    def __init__(self, opts, load, loadauth=None):
        self.opts = salt.config.master_config(opts['conf_file'])
        self.load = load
        self.ckminions = salt.utils.minions.CkMinions(opts)
        if loadauth is None:
            self.loadauth = LoadAuth(opts)
        else:
            self.loadauth = loadauth

    @property
    def auth_data(self):
        '''
        Gather and create the authorization data sets

        We're looking at several constructs here.

        Standard eauth: allow jsmith to auth via pam, and execute any command
        on server web1
        external_auth:
          pam:
            jsmith:
              - web1:
                - .*

        Django eauth: Import the django library, dynamically load the Django
        model called 'model'.  That model returns a data structure that
        matches the above for standard eauth.  This is what determines
        who can do what to which machines

        django:
          ^model:
            <stuff returned from django>

        Active Directory Extended:

        Users in the AD group 'webadmins' can run any command on server1
        Users in the AD group 'webadmins' can run test.ping and service.restart
        on machines that have a computer object in the AD 'webservers' OU
        Users in the AD group 'webadmins' can run commands defined in the
        custom attribute (custom attribute not implemented yet, this is for
        future use)
          ldap:
             webadmins%:  <all users in the AD 'webadmins' group>
               - server1:
                   - .*
               - ldap(OU=webservers,dc=int,dc=bigcompany,dc=com):
                  - test.ping
                  - service.restart
               - ldap(OU=Domain Controllers,dc=int,dc=bigcompany,dc=com):
                 - allowed_fn_list_attribute^
        '''
        auth_data = self.opts['external_auth']
        merge_lists = self.opts['pillar_merge_lists']

        if 'django' in auth_data and '^model' in auth_data['django']:
            auth_from_django = salt.auth.django.retrieve_auth_entries()
            auth_data = salt.utils.dictupdate.merge(auth_data,
                                                    auth_from_django,
                                                    strategy='list',
                                                    merge_lists=merge_lists)

        if 'ldap' in auth_data and __opts__.get('auth.ldap.activedirectory', False):
            auth_data['ldap'] = salt.auth.ldap.expand_ldap_entries(auth_data['ldap'])
            log.debug(auth_data['ldap'])

        #for auth_back in self.opts.get('external_auth_sources', []):
        #    fstr = '{0}.perms'.format(auth_back)
        #    if fstr in self.loadauth.auth:
        #        auth_data.append(getattr(self.loadauth.auth)())
        return auth_data

    def token(self, adata, load):
        '''
        Determine if token auth is valid and yield the adata
        '''
        try:
            token = self.loadauth.get_tok(load['token'])
        except Exception as exc:
            log.error(
                'Exception occurred when generating auth token: {0}'.format(
                    exc
                )
            )
            yield {}
        if not token:
            log.warning('Authentication failure of type "token" occurred.')
            yield {}
        for sub_auth in adata:
            for sub_adata in adata:
                if token['eauth'] not in adata:
                    continue
            if not ((token['name'] in adata[token['eauth']]) |
                    ('*' in adata[token['eauth']])):
                continue
            yield {'sub_auth': sub_auth, 'token': token}
        yield {}

    def eauth(self, adata, load):
        '''
        Determine if the given eauth is valid and yield the adata
        '''
        for sub_auth in [adata]:
            if load['eauth'] not in sub_auth:
                continue
            try:
                name = self.loadauth.load_name(load)
                if not ((name in sub_auth[load['eauth']]) |
                        ('*' in sub_auth[load['eauth']])):
                    continue
                if not self.loadauth.time_auth(load):
                    continue
            except Exception as exc:
                log.error(
                    'Exception occurred while authenticating: {0}'.format(exc)
                )
                continue
            yield {'sub_auth': sub_auth, 'name': name}
        yield {}

    def rights_check(self, form, sub_auth, name, load, eauth=None):
        '''
        Read in the access system to determine if the validated user has
        requested rights
        '''
        if load.get('eauth'):
            sub_auth = sub_auth[load['eauth']]
        good = self.ckminions.any_auth(
                form,
                sub_auth[name] if name in sub_auth else sub_auth['*'],
                load.get('fun', None),
                load.get('arg', None),
                load.get('tgt', None),
                load.get('tgt_type', 'glob'))
        if not good:
            # Accept find_job so the CLI will function cleanly
            if load.get('fun', '') != 'saltutil.find_job':
                return good
        return good

    def rights(self, form, load):
        '''
        Determine what type of authentication is being requested and pass
        authorization

        Note: this will check that the user has at least one right that will let
        him execute "load", this does not deal with conflicting rules
        '''

        adata = self.auth_data
        good = False
        if load.get('token', False):
            for sub_auth in self.token(self.auth_data, load):
                if sub_auth:
                    if self.rights_check(
                            form,
                            self.auth_data[sub_auth['token']['eauth']],
                            sub_auth['token']['name'],
                            load,
                            sub_auth['token']['eauth']):
                        return True
            log.warning(
                'Authentication failure of type "token" occurred.'
            )
        elif load.get('eauth'):
            for sub_auth in self.eauth(self.auth_data, load):
                if sub_auth:
                    if self.rights_check(
                            form,
                            sub_auth['sub_auth'],
                            sub_auth['name'],
                            load,
                            load['eauth']):
                        return True
            log.warning(
                'Authentication failure of type "eauth" occurred.'
            )
        return False


class Resolver(object):
    '''
    The class used to resolve options for the command line and for generic
    interactive interfaces
    '''
    def __init__(self, opts):
        self.opts = opts
        self.auth = salt.loader.auth(opts)

    def _send_token_request(self, load):
        if self.opts['transport'] in ('zeromq', 'tcp'):
            master_uri = 'tcp://' + salt.utils.ip_bracket(self.opts['interface']) + \
                         ':' + str(self.opts['ret_port'])
            channel = salt.transport.client.ReqChannel.factory(self.opts,
                                                                crypt='clear',
                                                                master_uri=master_uri)
            return channel.send(load)

        elif self.opts['transport'] == 'raet':
            channel = salt.transport.client.ReqChannel.factory(self.opts)
            channel.dst = (None, None, 'local_cmd')
            return channel.send(load)

    def cli(self, eauth):
        '''
        Execute the CLI options to fill in the extra data needed for the
        defined eauth system
        '''
        ret = {}
        if not eauth:
            print('External authentication system has not been specified')
            return ret
        fstr = '{0}.auth'.format(eauth)
        if fstr not in self.auth:
            print(('The specified external authentication system "{0}" is '
                   'not available').format(eauth))
            return ret

        args = salt.utils.arg_lookup(self.auth[fstr])
        for arg in args['args']:
            if arg in self.opts:
                ret[arg] = self.opts[arg]
            elif arg.startswith('pass'):
                ret[arg] = getpass.getpass('{0}: '.format(arg))
            else:
                ret[arg] = input('{0}: '.format(arg))
        for kwarg, default in list(args['kwargs'].items()):
            if kwarg in self.opts:
                ret['kwarg'] = self.opts[kwarg]
            else:
                ret[kwarg] = input('{0} [{1}]: '.format(kwarg, default))

        # Use current user if empty
        if 'username' in ret and not ret['username']:
            ret['username'] = salt.utils.get_user()

        return ret

    def token_cli(self, eauth, load):
        '''
        Create the token from the CLI and request the correct data to
        authenticate via the passed authentication mechanism
        '''
        load['cmd'] = 'mk_token'
        load['eauth'] = eauth
        tdata = self._send_token_request(load)
        if 'token' not in tdata:
            return tdata
        oldmask = os.umask(0o177)
        try:
            with salt.utils.fopen(self.opts['token_file'], 'w+') as fp_:
                fp_.write(tdata['token'])
        except (IOError, OSError):
            pass
        finally:
            os.umask(oldmask)
        return tdata

    def mk_token(self, load):
        '''
        Request a token from the master
        '''
        load['cmd'] = 'mk_token'
        tdata = self._send_token_request(load)
        return tdata

    def get_token(self, token):
        '''
        Request a token from the master
        '''
        load = {}
        load['token'] = token
        load['cmd'] = 'get_token'
        tdata = self._send_token_request(load)
        return tdata


class AuthUser(object):
    '''
    Represents a user requesting authentication to the salt master
    '''

    def __init__(self, user):
        '''
        Instantiate an AuthUser object.

        Takes a user to reprsent, as a string.
        '''
        self.user = user

    def is_sudo(self):
        '''
        Determines if the user is running with sudo

        Returns True if the user is running with sudo and False if the
        user is not running with sudo
        '''
        return self.user.startswith('sudo_')

    def is_running_user(self):
        '''
        Determines if the user is the same user as the one running
        this process

        Returns True if the user is the same user as the one running
        this process and False if not.
        '''
        return self.user == salt.utils.get_user()
