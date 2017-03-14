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
    def __init__(self, opts, ckminions=None):
        self.opts = opts
        self.max_fail = 1.0
        self.serial = salt.payload.Serial(opts)
        self.auth = salt.loader.auth(opts)
        self.ckminions = ckminions or salt.utils.minions.CkMinions(opts)

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

    def __get_acl(self, load):
        '''
        Returns ACL for a specific user.
        Returns None if eauth doesn't provide any for the user. I. e. None means: use acl declared
        in master config.
        '''
        if 'eauth' not in load:
            return None
        fstr = '{0}.acl'.format(load['eauth'])
        if fstr not in self.auth:
            return None
        fcall = salt.utils.format_call(self.auth[fstr],
                                       load,
                                       expected_extra_kws=AUTH_INTERNAL_KEYWORDS)
        try:
            return self.auth[fstr](*fcall['args'], **fcall['kwargs'])
        except Exception as e:
            log.debug('Authentication module threw {0}'.format(e))
            return None

    def __process_acl(self, load, auth_list):
        '''
        Allows eauth module to modify the access list right before it'll be applied to the request.
        For example ldap auth module expands entries
        '''
        if 'eauth' not in load:
            return auth_list
        fstr = '{0}.process_acl'.format(load['eauth'])
        if fstr not in self.auth:
            return auth_list
        try:
            return self.auth[fstr](auth_list, self.opts)
        except Exception as e:
            log.debug('Authentication module threw {0}'.format(e))
            return auth_list

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
        if not self.authenticate_eauth(load):
            return {}
        fstr = '{0}.auth'.format(load['eauth'])
        hash_type = getattr(hashlib, self.opts.get('hash_type', 'md5'))
        tok = str(hash_type(os.urandom(512)).hexdigest())
        t_path = os.path.join(self.opts['token_dir'], tok)
        while os.path.isfile(t_path):
            tok = str(hash_type(os.urandom(512)).hexdigest())
            t_path = os.path.join(self.opts['token_dir'], tok)

        if self._allow_custom_expire(load):
            token_expire = load.pop('token_expire', self.opts['token_expire'])
        else:
            _ = load.pop('token_expire', None)
            token_expire = self.opts['token_expire']

        tdata = {'start': time.time(),
                 'expire': time.time() + token_expire,
                 'name': self.load_name(load),
                 'eauth': load['eauth'],
                 'token': tok}

        acl_ret = self.__get_acl(load)
        if acl_ret is not None:
            tdata['auth_list'] = acl_ret

        if 'groups' in load:
            tdata['groups'] = load['groups']

        try:
            with salt.utils.fopen(t_path, 'w+b') as fp_:
                fp_.write(self.serial.dumps(tdata))
        except (IOError, OSError):
            log.warning('Authentication failure: can not write token file "{0}".'.format(t_path))
            return {}
        return tdata

    def get_tok(self, tok):
        '''
        Return the name associated with the token, or False if the token is
        not valid
        '''
        t_path = os.path.join(self.opts['token_dir'], tok)
        if not os.path.isfile(t_path):
            return {}
        try:
            with salt.utils.fopen(t_path, 'rb') as fp_:
                tdata = self.serial.loads(fp_.read())
        except (IOError, OSError):
            log.warning('Authentication failure: can not read token file "{0}".'.format(t_path))
            return {}
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

    def authenticate_token(self, load):
        '''
        Authenticate a user by the token specified in load.
        Return the token object or False if auth failed.
        '''
        token = self.get_tok(load['token'])

        # Bail if the token is empty or if the eauth type specified is not allowed
        if not token or token['eauth'] not in self.opts['external_auth']:
            log.warning('Authentication failure of type "token" occurred.')
            return False

        return token

    def authenticate_eauth(self, load):
        '''
        Authenticate a user by the external auth module specified in load.
        Return True on success or False on failure.
        '''
        if 'eauth' not in load:
            log.warning('Authentication failure of type "eauth" occurred.')
            return False

        if load['eauth'] not in self.opts['external_auth']:
            # The eauth system is not enabled, fail
            log.warning('Authentication failure of type "eauth" occurred.')
            return False

        # Perform the actual authentication. If we fail here, do not
        # continue.
        if not self.time_auth(load):
            log.warning('Authentication failure of type "eauth" occurred.')
            return False

        return True

    def authenticate_key(self, load):
        '''
        Authenticate a user by the key passed in load.
        Return the effective user id (name) if it's differ from the specified one (for sudo).
        If the effective user id is the same as passed one return True on success or False on
        failure.
        '''
        auth_key = load.pop('key')
        if not auth_key:
            log.warning('Authentication failure of type "user" occurred.')
            return False
        if 'user' in load:
            auth_user = AuthUser(load['user'])
            if auth_user.is_sudo():
                # If someone sudos check to make sure there is no ACL's around their username
                if auth_key != self.key[self.opts.get('user', 'root')]:
                    log.warning('Authentication failure of type "user" occurred.')
                    return False
                return auth_user.sudo_name()
            elif load['user'] == self.opts.get('user', 'root') or load['user'] == 'root':
                if auth_key != self.key[self.opts.get('user', 'root')]:
                    log.warning('Authentication failure of type "user" occurred.')
                    return False
            elif auth_user.is_running_user():
                if auth_key != self.key.get(load['user']):
                    log.warning('Authentication failure of type "user" occurred.')
                    return False
            elif auth_key == self.key.get('root'):
                pass
            else:
                if load['user'] in self.key:
                    # User is authorised, check key and check perms
                    if auth_key != self.key[load['user']]:
                        log.warning('Authentication failure of type "user" occurred.')
                        return False
                    return load['user']
                else:
                    log.warning('Authentication failure of type "user" occurred.')
                    return False
        else:
            if auth_key != self.key[salt.utils.get_user()]:
                log.warning('Authentication failure of type "other" occurred.')
                return False
        return True

    def get_auth_list(self, load):
        '''
        Retrieve access list for the user specified in load.
        The list is built by eauth module or from master eauth configuration.
        Return None if current configuration doesn't provide any ACL for the user. Return an empty
        list if the user has no rights to execute anything on this master and returns non-empty list
        if user is allowed to execute particular functions.
        '''
        # Get acl from eauth module.
        auth_list = self.__get_acl(load)
        if auth_list is not None:
            return auth_list

        name = self.load_name(load)  # The username we are attempting to auth with
        groups = self.get_groups(load)  # The groups this user belongs to
        if groups is None or groups is False:
            groups = []
        group_perm_keys = [item for item in self.opts['external_auth'][load['eauth']] if item.endswith('%')]  # The configured auth groups

        # First we need to know if the user is allowed to proceed via any of their group memberships.
        group_auth_match = False
        for group_config in group_perm_keys:
            group_config = group_config.rstrip('%')
            for group in groups:
                if group == group_config:
                    group_auth_match = True
        # If a group_auth_match is set it means only that we have a
        # user which matches at least one or more of the groups defined
        # in the configuration file.

        external_auth_in_db = False
        for entry in self.opts['external_auth'][load['eauth']]:
            if entry.startswith('^'):
                external_auth_in_db = True
                break

        # If neither a catchall, a named membership or a group
        # membership is found, there is no need to continue. Simply
        # deny the user access.
        if not ((name in self.opts['external_auth'][load['eauth']]) |
                ('*' in self.opts['external_auth'][load['eauth']]) |
                group_auth_match | external_auth_in_db):
            # Auth successful, but no matching user found in config
            log.warning('Authentication failure of type "eauth" occurred.')
            return None

        # We now have an authenticated session and it is time to determine
        # what the user has access to.
        auth_list = []
        if name in self.opts['external_auth'][load['eauth']]:
            auth_list = self.opts['external_auth'][load['eauth']][name]
        elif '*' in self.opts['external_auth'][load['eauth']]:
            auth_list = self.opts['external_auth'][load['eauth']]['*']
        if group_auth_match:
            auth_list = self.ckminions.fill_auth_list_from_groups(
                    self.opts['external_auth'][load['eauth']],
                    groups,
                    auth_list)

        auth_list = self.__process_acl(load, auth_list)

        log.trace("Compiled auth_list: {0}".format(auth_list))

        return auth_list


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
            auth_data['ldap'] = salt.auth.ldap.__expand_ldap_entries(auth_data['ldap'])
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

    def sudo_name(self):
        '''
        Returns the username of the sudoer, i.e. self.user without the
        'sudo_' prefix.
        '''
        return self.user.split('_', 1)[-1]
