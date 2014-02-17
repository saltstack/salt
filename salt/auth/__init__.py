# -*- coding: utf-8 -*-
'''
Salt's pluggable authentication system

This system allows for authentication to be managed in a module pluggable way
so that any external authentication system can be used inside of Salt
'''

# 1. Create auth loader instance
# 2. Accept arguments as a dict
# 3. Verify with function introspection
# 4. Execute auth function
# 5. Cache auth token with relative data opts['token_dir']
# 6. Interface to verify tokens

# Import python libs
from __future__ import print_function
import os
import hashlib
import time
import logging
import random
import getpass

# Import salt libs
import salt.config
import salt.loader
import salt.utils
import salt.utils.minions
import salt.payload

log = logging.getLogger(__name__)


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
        fcall = salt.utils.format_call(self.auth[fstr], load)
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
        fcall = salt.utils.format_call(self.auth[fstr], load)
        try:
            if 'kwargs' in fcall:
                return self.auth[fstr](*fcall['args'], **fcall['kwargs'])
            else:
                return self.auth[fstr](*fcall['args'])
        except Exception as exc:
            err = 'Authentication module threw an exception: {0}'.format(exc)
            log.critical(err)
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
        r_time = random.uniform(
                self.max_fail - deviation,
                self.max_fail + deviation
                )
        while start + r_time > time.time():
            time.sleep(0.001)
        return False

    def mk_token(self, load):
        '''
        Run time_auth and create a token. Return False or the token
        '''
        ret = self.time_auth(load)
        if ret is False:
            return {}
        fstr = '{0}.auth'.format(load['eauth'])
        tok = str(hashlib.md5(os.urandom(512)).hexdigest())
        t_path = os.path.join(self.opts['token_dir'], tok)
        while os.path.isfile(t_path):
            tok = hashlib.md5(os.urandom(512)).hexdigest()
            t_path = os.path.join(self.opts['token_dir'], tok)
        fcall = salt.utils.format_call(self.auth[fstr], load)
        tdata = {'start': time.time(),
                 'expire': time.time() + self.opts['token_expire'],
                 'name': fcall['args'][0],
                 'eauth': load['eauth'],
                 'token': tok}
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

    def auth_data(self):
        '''
        Gather and create the autorization data sets
        '''
        auth_data = self.opts['external_auth']
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
        '''
        adata = self.auth_data()
        good = False
        if load.get('token', False):
            good = False
            for sub_auth in self.token(adata, load):
                if sub_auth:
                    if self.rights_check(
                            form,
                            adata[sub_auth['token']['eauth']],
                            sub_auth['token']['name'],
                            load,
                            sub_auth['token']['eauth']):
                        good = True
            if not good:
                log.warning(
                    'Authentication failure of type "token" occurred.'
                )
                return False
        elif load.get('eauth'):
            good = False
            for sub_auth in self.eauth(adata, load):
                if sub_auth:
                    if self.rights_check(
                            form,
                            sub_auth['sub_auth'],
                            sub_auth['name'],
                            load,
                            load['eauth']):
                        good = True
            if not good:
                log.warning(
                    'Authentication failure of type "eauth" occurred.'
                )
                return False
        return good


class Resolver(object):
    '''
    The class used to resolve options for the command line and for generic
    interactive interfaces
    '''
    def __init__(self, opts):
        self.opts = opts
        self.auth = salt.loader.auth(opts)

    def _send_token_request(self, load):
        sreq = salt.payload.SREQ(
            'tcp://{0[interface]}:{0[ret_port]}'.format(self.opts),
            )
        tdata = sreq.send('clear', load)
        return tdata

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
                ret[arg] = raw_input('{0}: '.format(arg))
        for kwarg, default in args['kwargs'].items():
            if kwarg in self.opts:
                ret['kwarg'] = self.opts[kwarg]
            else:
                ret[kwarg] = raw_input('{0} [{1}]: '.format(kwarg, default))

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
        try:
            oldmask = os.umask(0177)
            with salt.utils.fopen(self.opts['token_file'], 'w+') as fp_:
                fp_.write(tdata['token'])
            os.umask(oldmask)
        except (IOError, OSError):
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
