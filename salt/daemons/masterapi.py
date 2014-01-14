# -*- coding: utf-8 -*-
'''
This module contains all of the routines needed to set up a master server, this
involves preparing the three listeners and the workers needed by the master.
'''

# Import python libs
import os
import re
import logging
import getpass


# Import salt libs
import salt.crypt
import salt.utils
import salt.client
import salt.payload
import salt.pillar
import salt.state
import salt.runner
import salt.auth
import salt.wheel
import salt.minion
import salt.search
import salt.key
import salt.fileserver
import salt.utils.atomicfile
import salt.utils.event
import salt.utils.verify
import salt.utils.minions
import salt.utils.gzip_util
from salt.utils.event import tagify

log = logging.getLogger(__name__)

# Things to do in lower layers:
# only accept valid minion ids


class RemoteFuncs(object):
    '''
    Funcitons made available to minions, this class includes the raw routines
    post validation that make up the minion access to the master
    '''
    def __init__(self, opts):
        self.opts = opts
        self.event = salt.utils.event.MasterEvent(self.opts['sock_dir'])
        self.serial = salt.payload.Serial(opts)
        self.ckminions = salt.utils.minions.CkMinions(opts)
        # Create the tops dict for loading external top data
        self.tops = salt.loader.tops(self.opts)
        # Make a client
        self.local = salt.client.LocalClient(self.opts['conf_file'])
        # Create the master minion to access the external job cache
        self.mminion = salt.minion.MasterMinion(
                self.opts,
                states=False,
                rend=False)
        self.__setup_fileserver()

    def __setup_fileserver(self):
        '''
        Set the local file objects from the file server interface
        '''
        fs_ = salt.fileserver.Fileserver(self.opts)
        self._serve_file = fs_.serve_file
        self._file_hash = fs_.file_hash
        self._file_list = fs_.file_list
        self._file_list_emptydirs = fs_.file_list_emptydirs
        self._dir_list = fs_.dir_list
        self._symlink_list = fs_.symlink_list
        self._file_envs = fs_.envs

    def __verify_minion_publish(self, load):
        '''
        Verify that the passed information authorized a minion to execute
        '''
        # Verify that the load is valid
        if 'peer' not in self.opts:
            return False
        if not isinstance(self.opts['peer'], dict):
            return False
        if any(key not in load for key in ('fun', 'arg', 'tgt', 'ret', 'id')):
            return False
        # If the command will make a recursive publish don't run
        if re.match('publish.*', load['fun']):
            return False
        # Check the permissions for this minion
        perms = []
        for match in self.opts['peer']:
            if re.match(match, load['id']):
                # This is the list of funcs/modules!
                if isinstance(self.opts['peer'][match], list):
                    perms.extend(self.opts['peer'][match])
        if ',' in load['fun']:
            # 'arg': [['cat', '/proc/cpuinfo'], [], ['foo']]
            load['fun'] = load['fun'].split(',')
            arg_ = []
            for arg in load['arg']:
                arg_.append(arg.split())
            load['arg'] = arg_
        good = self.ckminions.auth_check(
                perms,
                load['fun'],
                load['tgt'],
                load.get('tgt_type', 'glob'))
        if not good:
            return False
        return True

    def _master_opts(self, load):
        '''
        Return the master options to the minion
        '''
        mopts = {}
        file_roots = {}
        envs = self._file_envs()
        for saltenv in envs:
            if saltenv not in file_roots:
                file_roots[saltenv] = []
        mopts['file_roots'] = file_roots
        if load.get('env_only'):
            return mopts
        mopts['renderer'] = self.opts['renderer']
        mopts['failhard'] = self.opts['failhard']
        mopts['state_top'] = self.opts['state_top']
        mopts['nodegroups'] = self.opts['nodegroups']
        mopts['state_auto_order'] = self.opts['state_auto_order']
        mopts['state_events'] = self.opts['state_events']
        mopts['jinja_lstrip_blocks'] = self.opts['jinja_lstrip_blocks']
        mopts['jinja_trim_blocks'] = self.opts['jinja_trim_blocks']
        return mopts

    def _mine_get(self, load):
        '''
        Gathers the data from the specified minions' mine
        '''
        if any(key not in load for key in ('id', 'tgt', 'fun')):
            return {}
        if 'mine_get' in self.opts:
            # If master side acl defined.
            if not isinstance(self.opts['mine_get'], dict):
                return {}
            perms = set()
            for match in self.opts['mine_get']:
                if re.match(match, load['id']):
                    if isinstance(self.opts['mine_get'][match], list):
                        perms.update(self.opts['mine_get'][match])
            if not any(re.match(perm, load['fun']) for perm in perms):
                return {}
        ret = {}
        if not salt.utils.verify.valid_id(self.opts, load['id']):
            return ret
        checker = salt.utils.minions.CkMinions(self.opts)
        minions = checker.check_minions(
                load['tgt'],
                load.get('expr_form', 'glob')
                )
        for minion in minions:
            mine = os.path.join(
                    self.opts['cachedir'],
                    'minions',
                    minion,
                    'mine.p')
            try:
                with salt.utils.fopen(mine) as fp_:
                    fdata = self.serial.load(fp_).get(load['fun'])
                    if fdata:
                        ret[minion] = fdata
            except Exception:
                continue
        return ret

    def _mine(self, load):
        '''
        Return the mine data
        '''
        if 'id' not in load or 'data' not in load:
            return False
        if self.opts.get('minion_data_cache', False) or self.opts.get('enforce_mine_cache', False):
            cdir = os.path.join(self.opts['cachedir'], 'minions', load['id'])
            if not os.path.isdir(cdir):
                os.makedirs(cdir)
            datap = os.path.join(cdir, 'mine.p')
            if not load.get('clear', False):
                if os.path.isfile(datap):
                    with salt.utils.fopen(datap, 'r') as fp_:
                        new = self.serial.load(fp_)
                    if isinstance(new, dict):
                        new.update(load['data'])
                        load['data'] = new
            with salt.utils.fopen(datap, 'w+') as fp_:
                fp_.write(self.serial.dumps(load['data']))
        return True

    def _mine_delete(self, load):
        '''
        Allow the minion to delete a specific function from its own mine
        '''
        if 'id' not in load or 'fun' not in load:
            return False
        if self.opts.get('minion_data_cache', False) or self.opts.get('enforce_mine_cache', False):
            cdir = os.path.join(self.opts['cachedir'], 'minions', load['id'])
            if not os.path.isdir(cdir):
                return True
            datap = os.path.join(cdir, 'mine.p')
            if os.path.isfile(datap):
                try:
                    with salt.utils.fopen(datap, 'r') as fp_:
                        mine_data = self.serial.load(fp_)
                    if isinstance(mine_data, dict):
                        if mine_data.pop(load['fun'], False):
                            with salt.utils.fopen(datap, 'w+') as fp_:
                                fp_.write(self.serial.dumps(mine_data))
                except OSError:
                    return False
        return True

    def _mine_flush(self, load):
        '''
        Allow the minion to delete all of its own mine contents
        '''
        if 'id' not in load:
            return False
        if self.opts.get('minion_data_cache', False) or self.opts.get('enforce_mine_cache', False):
            cdir = os.path.join(self.opts['cachedir'], 'minions', load['id'])
            if not os.path.isdir(cdir):
                return True
            datap = os.path.join(cdir, 'mine.p')
            if os.path.isfile(datap):
                try:
                    os.remove(datap)
                except OSError:
                    return False
        return True

    def _file_recv(self, load):
        '''
        Allows minions to send files to the master, files are sent to the
        master file cache
        '''
        if any(key not in load for key in ('id', 'path', 'loc')):
            return False
        if not self.opts['file_recv'] or os.path.isabs(load['path']):
            return False
        if os.path.isabs(load['path']) or '../' in load['path']:
            # Can overwrite master files!!
            return False
        file_recv_max_size = 1024*1024 * self.opts.get('file_recv_max_size', 100)
        if len(load['data']) + load.get('loc', 0) > file_recv_max_size:
            log.error(
                'Exceeding file_recv_max_size limit: {0}'.format(
                    file_recv_max_size
                )
            )
            return False
        cpath = os.path.join(
                self.opts['cachedir'],
                'minions',
                load['id'],
                'files',
                load['path'])
        cdir = os.path.dirname(cpath)
        if not os.path.isdir(cdir):
            try:
                os.makedirs(cdir)
            except os.error:
                pass
        if os.path.isfile(cpath) and load['loc'] != 0:
            mode = 'ab'
        else:
            mode = 'wb'
        with salt.utils.fopen(cpath, mode) as fp_:
            if load['loc']:
                fp_.seek(load['loc'])
            fp_.write(load['data'])
        return True

    def _pillar(self, load):
        '''
        Return the pillar data for the minion
        '''
        if any(key not in load for key in ('id', 'grains')):
            return False
        pillar = salt.pillar.Pillar(
                self.opts,
                load['grains'],
                load['id'],
                load.get('saltenv', load.get('env')),
                load.get('ext'),
                self.mminion.functions)
        data = pillar.compile_pillar()
        if self.opts.get('minion_data_cache', False):
            cdir = os.path.join(self.opts['cachedir'], 'minions', load['id'])
            if not os.path.isdir(cdir):
                os.makedirs(cdir)
            datap = os.path.join(cdir, 'data.p')
            with salt.utils.fopen(datap, 'w+') as fp_:
                fp_.write(
                        self.serial.dumps(
                            {'grains': load['grains'],
                             'pillar': data})
                            )
        return data

    def _minion_event(self, load):
        '''
        Receive an event from the minion and fire it on the master event
        interface
        '''
        if 'id' not in load:
            return False
        if 'events' not in load and ('tag' not in load or 'data' not in load):
            return False
        if 'events' in load:
            for event in load['events']:
                self.event.fire_event(event, event['tag'])  # old dup event
                if load.get('pretag') is not None:
                    self.event.fire_event(event, tagify(event['tag'], base=load['pretag']))
        else:
            tag = load['tag']
            self.event.fire_event(load, tag)
        return True

    def _return(self, load):
        '''
        Handle the return data sent from the minions
        '''
        # If the return data is invalid, just ignore it
        if any(key not in load for key in ('return', 'jid', 'id')):
            return False
        if load['jid'] == 'req':
        # The minion is returning a standalone job, request a jobid
            load['jid'] = salt.utils.prep_jid(
                    self.opts['cachedir'],
                    self.opts['hash_type'],
                    load.get('nocache', False))
        log.info('Got return from {id} for job {jid}'.format(**load))
        self.event.fire_event(load, load['jid'])  # old dup event
        self.event.fire_event(load, tagify([load['jid'], 'ret', load['id']], 'job'))
        self.event.fire_ret_load(load)
        if self.opts['master_ext_job_cache']:
            fstr = '{0}.returner'.format(self.opts['master_ext_job_cache'])
            self.mminion.returners[fstr](load)
            return
        if not self.opts['job_cache'] or self.opts.get('ext_job_cache'):
            return
        jid_dir = salt.utils.jid_dir(
                load['jid'],
                self.opts['cachedir'],
                self.opts['hash_type']
                )
        if not os.path.isdir(jid_dir):
            log.error(
                'An inconsistency occurred, a job was received with a job id '
                'that is not present on the master: {jid}'.format(**load)
            )
            return False
        if os.path.exists(os.path.join(jid_dir, 'nocache')):
            return
        hn_dir = os.path.join(jid_dir, load['id'])
        if not os.path.isdir(hn_dir):
            os.makedirs(hn_dir)
        # Otherwise the minion has already returned this jid and it should
        # be dropped
        else:
            log.error(
                'An extra return was detected from minion {0}, please verify '
                'the minion, this could be a replay attack'.format(
                    load['id']
                )
            )
            return False

        self.serial.dump(
            load['return'],
            # Use atomic open here to avoid the file being read before it's
            # completely written to. Refs #1935
            salt.utils.atomicfile.atomic_open(
                os.path.join(hn_dir, 'return.p'), 'w+'
            )
        )
        if 'out' in load:
            self.serial.dump(
                load['out'],
                # Use atomic open here to avoid the file being read before
                # it's completely written to. Refs #1935
                salt.utils.atomicfile.atomic_open(
                    os.path.join(hn_dir, 'out.p'), 'w+'
                )
            )

    def _syndic_return(self, load):
        '''
        Receive a syndic minion return and format it to look like returns from
        individual minions.
        '''
        # Verify the load
        if any(key not in load for key in ('return', 'jid', 'id')):
            return None
        # set the write flag
        jid_dir = salt.utils.jid_dir(
                load['jid'],
                self.opts['cachedir'],
                self.opts['hash_type']
                )
        if not os.path.isdir(jid_dir):
            os.makedirs(jid_dir)
            if 'load' in load:
                with salt.utils.fopen(os.path.join(jid_dir, '.load.p'), 'w+') as fp_:
                    self.serial.dump(load['load'], fp_)
        wtag = os.path.join(jid_dir, 'wtag_{0}'.format(load['id']))
        try:
            with salt.utils.fopen(wtag, 'w+') as fp_:
                fp_.write('')
        except (IOError, OSError):
            log.error(
                'Failed to commit the write tag for the syndic return, are '
                'permissions correct in the cache dir: {0}?'.format(
                    self.opts['cachedir']
                )
            )
            return False

        # Format individual return loads
        for key, item in load['return'].items():
            ret = {'jid': load['jid'],
                   'id': key,
                   'return': item}
            if 'out' in load:
                ret['out'] = load['out']
            self._return(ret)
        if os.path.isfile(wtag):
            os.remove(wtag)

    def minion_runner(self, load):
        '''
        Execute a runner from a minion, return the runner's function data
        '''
        if 'peer_run' not in self.opts:
            return {}
        if not isinstance(self.opts['peer_run'], dict):
            return {}
        if any(key not in load for key in ('fun', 'arg', 'id', 'tok')):
            return {}
        perms = set()
        for match in self.opts['peer_run']:
            if re.match(match, load['id']):
                # This is the list of funcs/modules!
                if isinstance(self.opts['peer_run'][match], list):
                    perms.update(self.opts['peer_run'][match])
        good = False
        for perm in perms:
            if re.match(perm, load['fun']):
                good = True
        if not good:
            return {}
        # Prepare the runner object
        opts = {'fun': load['fun'],
                'arg': load['arg'],
                'id': load['id'],
                'doc': False,
                'conf_file': self.opts['conf_file']}
        opts.update(self.opts)
        runner = salt.runner.Runner(opts)
        return runner.run()

    def pub_ret(self, load):
        '''
        Request the return data from a specific jid, only allowed
        if the requesting minion also initialted the execution.
        '''
        if any(key not in load for key in ('jid', 'id', 'tok')):
            return {}
        # Check that this minion can access this data
        auth_cache = os.path.join(
                self.opts['cachedir'],
                'publish_auth')
        if not os.path.isdir(auth_cache):
            os.makedirs(auth_cache)
        jid_fn = os.path.join(auth_cache, load['jid'])
        with salt.utils.fopen(jid_fn, 'r') as fp_:
            if not load['id'] == fp_.read():
                return {}
        # Grab the latest and return
        return self.local.get_cache_returns(load['jid'])

    def minion_pub(self, load):
        '''
        Publish a command initiated from a minion, this method executes minion
        restrictions so that the minion publication will only work if it is
        enabled in the config.
        The configuration on the master allows minions to be matched to
        salt functions, so the minions can only publish allowed salt functions
        The config will look like this:
        peer:
            .*:
                - .*
        This configuration will enable all minions to execute all commands.
        peer:
            foo.example.com:
                - test.*
        This configuration will only allow the minion foo.example.com to
        execute commands from the test module
        '''
        # Set up the publication payload
        pub_load = {
            'fun': load['fun'],
            'arg': load['arg'],
            'expr_form': load.get('tgt_type', 'glob'),
            'tgt': load['tgt'],
            'ret': load['ret'],
            'id': load['id'],
        }
        if 'tgt_type' in load:
            if load['tgt_type'].startswith('node'):
                if load['tgt'] in self.opts['nodegroups']:
                    pub_load['tgt'] = self.opts['nodegroups'][load['tgt']]
                    pub_load['expr_form_type'] = 'compound'
                    pub_load['expr_form'] = load['tgt_type']
                else:
                    return {}
            else:
                pub_load['expr_form'] = load['tgt_type']
        ret = {}
        ret['jid'] = self.local.cmd_async(**pub_load)
        ret['minions'] = self.ckminions.check_minions(
                load['tgt'],
                pub_load['expr_form'])
        auth_cache = os.path.join(
                self.opts['cachedir'],
                'publish_auth')
        if not os.path.isdir(auth_cache):
            os.makedirs(auth_cache)
        jid_fn = os.path.join(auth_cache, ret['jid'])
        with salt.utils.fopen(jid_fn, 'w+') as fp_:
            fp_.write(load['id'])
        return ret

    def minion_publish(self, load):
        '''
        Publish a command initiated from a minion, this method executes minion
        restrictions so that the minion publication will only work if it is
        enabled in the config.
        The configuration on the master allows minions to be matched to
        salt functions, so the minions can only publish allowed salt functions
        The config will look like this:
        peer:
            .*:
                - .*
        This configuration will enable all minions to execute all commands.
        peer:
            foo.example.com:
                - test.*
        This configuration will only allow the minion foo.example.com to
        execute commands from the test module
        '''
        if not self.__verify_minion_publish(load):
            return {}
        # Set up the publication payload
        pub_load = {
            'fun': load['fun'],
            'arg': load['arg'],
            'expr_form': load.get('tgt_type', 'glob'),
            'tgt': load['tgt'],
            'ret': load['ret'],
            'id': load['id'],
        }
        if 'tmo' in load:
            try:
                pub_load['timeout'] = int(load['tmo'])
            except ValueError:
                msg = 'Failed to parse timeout value: {0}'.format(
                        load['tmo'])
                log.warn(msg)
                return {}
        if 'timeout' in load:
            try:
                pub_load['timeout'] = int(load['timeout'])
            except ValueError:
                msg = 'Failed to parse timeout value: {0}'.format(
                        load['tmo'])
                log.warn(msg)
                return {}
        if 'tgt_type' in load:
            if load['tgt_type'].startswith('node'):
                if load['tgt'] in self.opts['nodegroups']:
                    pub_load['tgt'] = self.opts['nodegroups'][load['tgt']]
                    pub_load['expr_form_type'] = 'compound'
                else:
                    return {}
            else:
                pub_load['expr_form'] = load['tgt_type']
        pub_load['raw'] = True
        ret = {}
        for minion in self.local.cmd_iter(**pub_load):
            if load.get('form', '') == 'full':
                data = minion
                if 'jid' in minion:
                    ret['__jid__'] = minion['jid']
                data['ret'] = data.pop('return')
                ret[minion['id']] = data
            else:
                ret[minion['id']] = minion['return']
                if 'jid' in minion:
                    ret['__jid__'] = minion['jid']
        for key, val in self.local.get_cache_returns(ret['__jid__']).items():
            if not key in ret:
                ret[key] = val
        if load.get('form', '') != 'full':
            ret.pop('__jid__')
        return ret

    def revoke_auth(self, load):
        '''
        Allow a minion to request revocation of its own key
        '''
        if 'id' not in load:
            return False
        keyapi = salt.key.Key(self.opts)
        keyapi.delete_key(load['id'])
        return True


class LocalFuncs(object):
    '''
    Set up methods for use only from the local system
    '''
    # The ClearFuncs object encapsulates the functions that can be executed in
    # the clear:
    # publish (The publish from the LocalClient)
    # _auth
    def __init__(self, opts, key, master_key):
        self.opts = opts
        self.serial = salt.payload.Serial(opts)
        self.key = key
        self.master_key = master_key
        # Create the event manager
        self.event = salt.utils.event.MasterEvent(self.opts['sock_dir'])
        # Make a client
        self.local = salt.client.LocalClient(self.opts['conf_file'])
        # Make an minion checker object
        self.ckminions = salt.utils.minions.CkMinions(opts)
        # Make an Auth object
        self.loadauth = salt.auth.LoadAuth(opts)
        # Stand up the master Minion to access returner data
        self.mminion = salt.minion.MasterMinion(
                self.opts,
                states=False,
                rend=False)
        # Make a wheel object
        self.wheel_ = salt.wheel.Wheel(opts)

    def runner(self, load):
        '''
        Send a master control function back to the runner system
        '''
        # All runner ops pass through eauth
        if 'token' in load:
            try:
                token = self.loadauth.get_tok(load['token'])
            except Exception as exc:
                msg = 'Exception occurred when generating auth token: {0}'.format(
                        exc)
                log.error(msg)
                return dict(error=dict(name='TokenAuthenticationError',
                                       message=msg))
            if not token:
                msg = 'Authentication failure of type "token" occurred.'
                log.warning(msg)
                return dict(error=dict(name='TokenAuthenticationError',
                                       message=msg))
            if token['eauth'] not in self.opts['external_auth']:
                msg = 'Authentication failure of type "token" occurred.'
                log.warning(msg)
                return dict(error=dict(name='TokenAuthenticationError',
                                       message=msg))
            if token['name'] not in self.opts['external_auth'][token['eauth']]:
                msg = 'Authentication failure of type "token" occurred.'
                log.warning(msg)
                return dict(error=dict(name='TokenAuthenticationError',
                                       message=msg))
            good = self.ckminions.runner_check(
                    self.opts['external_auth'][token['eauth']][token['name']] if token['name'] in self.opts['external_auth'][token['eauth']] else self.opts['external_auth'][token['eauth']]['*'],
                    load['fun'])
            if not good:
                msg = ('Authentication failure of type "token" occurred for '
                       'user {0}.').format(token['name'])
                log.warning(msg)
                return dict(error=dict(name='TokenAuthenticationError',
                                       message=msg))

            try:
                fun = load.pop('fun')
                runner_client = salt.runner.RunnerClient(self.opts)
                return runner_client.async(
                        fun,
                        load.get('kwarg', {}),
                        token['name'])
            except Exception as exc:
                log.error('Exception occurred while '
                        'introspecting {0}: {1}'.format(fun, exc))
                return dict(error=dict(name=exc.__class__.__name__,
                                       args=exc.args,
                                       message=exc.message))

        if 'eauth' not in load:
            msg = ('Authentication failure of type "eauth" occurred for '
                   'user {0}.').format(load.get('username', 'UNKNOWN'))
            log.warning(msg)
            return dict(error=dict(name='EauthAuthenticationError',
                                   message=msg))
        if load['eauth'] not in self.opts['external_auth']:
            # The eauth system is not enabled, fail
            msg = ('Authentication failure of type "eauth" occurred for '
                   'user {0}.').format(load.get('username', 'UNKNOWN'))
            log.warning(msg)
            return dict(error=dict(name='EauthAuthenticationError',
                                   message=msg))

        try:
            name = self.loadauth.load_name(load)
            if not ((name in self.opts['external_auth'][load['eauth']]) | ('*' in self.opts['external_auth'][load['eauth']])):
                msg = ('Authentication failure of type "eauth" occurred for '
                       'user {0}.').format(load.get('username', 'UNKNOWN'))
                log.warning(msg)
                return dict(error=dict(name='EauthAuthenticationError',
                                       message=msg))
            if not self.loadauth.time_auth(load):
                msg = ('Authentication failure of type "eauth" occurred for '
                       'user {0}.').format(load.get('username', 'UNKNOWN'))
                log.warning(msg)
                return dict(error=dict(name='EauthAuthenticationError',
                                       message=msg))
            good = self.ckminions.runner_check(
                    self.opts['external_auth'][load['eauth']][name] if name in self.opts['external_auth'][load['eauth']] else self.opts['external_auth'][load['eauth']]['*'],
                    load['fun'])
            if not good:
                msg = ('Authentication failure of type "eauth" occurred for '
                       'user {0}.').format(load.get('username', 'UNKNOWN'))
                log.warning(msg)
                return dict(error=dict(name='EauthAuthenticationError',
                                       message=msg))

            try:
                fun = load.pop('fun')
                runner_client = salt.runner.RunnerClient(self.opts)
                return runner_client.async(fun,
                                           load.get('kwarg', {}),
                                           load.get('username', 'UNKNOWN'))
            except Exception as exc:
                log.error('Exception occurred while '
                        'introspecting {0}: {1}'.format(fun, exc))
                return dict(error=dict(name=exc.__class__.__name__,
                                       args=exc.args,
                                       message=exc.message))

        except Exception as exc:
            log.error(
                'Exception occurred in the runner system: {0}'.format(exc)
            )
            return dict(error=dict(name=exc.__class__.__name__,
                                   args=exc.args,
                                   message=exc.message))

    def wheel(self, load):
        '''
        Send a master control function back to the wheel system
        '''
        # All wheel ops pass through eauth
        if 'token' in load:
            try:
                token = self.loadauth.get_tok(load['token'])
            except Exception as exc:
                msg = 'Exception occurred when generating auth token: {0}'.format(
                        exc)
                log.error(msg)
                return dict(error=dict(name='TokenAuthenticationError',
                                       message=msg))
            if not token:
                msg = 'Authentication failure of type "token" occurred.'
                log.warning(msg)
                return dict(error=dict(name='TokenAuthenticationError',
                                       message=msg))
            if token['eauth'] not in self.opts['external_auth']:
                msg = 'Authentication failure of type "token" occurred.'
                log.warning(msg)
                return dict(error=dict(name='TokenAuthenticationError',
                                       message=msg))
            if token['name'] not in self.opts['external_auth'][token['eauth']]:
                msg = 'Authentication failure of type "token" occurred.'
                log.warning(msg)
                return dict(error=dict(name='TokenAuthenticationError',
                                       message=msg))
            good = self.ckminions.wheel_check(
                    self.opts['external_auth'][token['eauth']][token['name']]
                        if token['name'] in self.opts['external_auth'][token['eauth']]
                        else self.opts['external_auth'][token['eauth']]['*'],
                    load['fun'])
            if not good:
                msg = ('Authentication failure of type "token" occurred for '
                       'user {0}.').format(token['name'])
                log.warning(msg)
                return dict(error=dict(name='TokenAuthenticationError',
                                       message=msg))

            jid = salt.utils.gen_jid()
            fun = load.pop('fun')
            tag = tagify(jid, prefix='wheel')
            data = {'fun': "wheel.{0}".format(fun),
                    'jid': jid,
                    'tag': tag,
                    'user': token['name']}
            try:
                self.event.fire_event(data, tagify([jid, 'new'], 'wheel'))
                ret = self.wheel_.call_func(fun, **load)
                data['return'] = ret
                data['success'] = True
                self.event.fire_event(data, tagify([jid, 'ret'], 'wheel'))
                return {'tag': tag,
                        'data': data}
            except Exception as exc:
                log.error(exc)
                log.error('Exception occurred while '
                        'introspecting {0}: {1}'.format(fun, exc))
                data['return'] = 'Exception occured in wheel {0}: {1}: {2}'.format(
                                            fun,
                                            exc.__class__.__name__,
                                            exc,
                                            )
                data['success'] = False
                self.event.fire_event(data, tagify([jid, 'ret'], 'wheel'))
                return {'tag': tag,
                        'data': data}

        if 'eauth' not in load:
            msg = ('Authentication failure of type "eauth" occurred for '
                   'user {0}.').format(load.get('username', 'UNKNOWN'))
            log.warning(msg)
            return dict(error=dict(name='EauthAuthenticationError',
                                       message=msg))
        if load['eauth'] not in self.opts['external_auth']:
            # The eauth system is not enabled, fail
            msg = ('Authentication failure of type "eauth" occurred for '
                   'user {0}.').format(load.get('username', 'UNKNOWN'))
            log.warning(msg)
            return dict(error=dict(name='EauthAuthenticationError',
                                       message=msg))

        try:
            name = self.loadauth.load_name(load)
            if not ((name in self.opts['external_auth'][load['eauth']]) |
                    ('*' in self.opts['external_auth'][load['eauth']])):
                msg = ('Authentication failure of type "eauth" occurred for '
                       'user {0}.').format(load.get('username', 'UNKNOWN'))
                log.warning(msg)
                return dict(error=dict(name='EauthAuthenticationError',
                                       message=msg))
            if not self.loadauth.time_auth(load):
                msg = ('Authentication failure of type "eauth" occurred for '
                       'user {0}.').format(load.get('username', 'UNKNOWN'))
                log.warning(msg)
                return dict(error=dict(name='EauthAuthenticationError',
                                       message=msg))
            good = self.ckminions.wheel_check(
                    self.opts['external_auth'][load['eauth']][name]
                        if name in self.opts['external_auth'][load['eauth']]
                        else self.opts['external_auth'][token['eauth']]['*'],
                    load['fun'])
            if not good:
                msg = ('Authentication failure of type "eauth" occurred for '
                       'user {0}.').format(load.get('username', 'UNKNOWN'))
                log.warning(msg)
                return dict(error=dict(name='EauthAuthenticationError',
                                       message=msg))

            jid = salt.utils.gen_jid()
            fun = load.pop('fun')
            tag = tagify(jid, prefix='wheel')
            data = {'fun': "wheel.{0}".format(fun),
                    'jid': jid,
                    'tag': tag,
                    'user': load.get('username', 'UNKNOWN')}
            try:
                self.event.fire_event(data, tagify([jid, 'new'], 'wheel'))
                ret = self.wheel_.call_func(fun, **load)
                data['return'] = ret
                data['success'] = True
                self.event.fire_event(data, tagify([jid, 'ret'], 'wheel'))
                return {'tag': tag,
                        'data': data}
            except Exception as exc:
                log.error('Exception occurred while '
                        'introspecting {0}: {1}'.format(fun, exc))
                data['return'] = 'Exception occured in wheel {0}: {1}: {2}'.format(
                                            fun,
                                            exc.__class__.__name__,
                                            exc,
                                            )
                self.event.fire_event(data, tagify([jid, 'ret'], 'wheel'))
                return {'tag': tag,
                        'data': data}

        except Exception as exc:
            log.error(
                'Exception occurred in the wheel system: {0}'.format(exc)
            )
            return dict(error=dict(name=exc.__class__.__name__,
                                   args=exc.args,
                                   message=exc.message))

    def mk_token(self, load):
        '''
        Create and return an authentication token, the clear load needs to
        contain the eauth key and the needed authentication creds.
        '''
        if 'eauth' not in load:
            log.warning('Authentication failure of type "eauth" occurred.')
            return ''
        if load['eauth'] not in self.opts['external_auth']:
            # The eauth system is not enabled, fail
            log.warning('Authentication failure of type "eauth" occurred.')
            return ''
        try:
            name = self.loadauth.load_name(load)
            if not ((name in self.opts['external_auth'][load['eauth']]) |
                    ('*' in self.opts['external_auth'][load['eauth']])):
                log.warning('Authentication failure of type "eauth" occurred.')
                return ''
            if not self.loadauth.time_auth(load):
                log.warning('Authentication failure of type "eauth" occurred.')
                return ''
            return self.loadauth.mk_token(load)
        except Exception as exc:
            log.error(
                'Exception occurred while authenticating: {0}'.format(exc)
            )
            return ''

    def get_token(self, load):
        '''
        Return the name associated with a token or False if the token is invalid
        '''
        if 'token' not in load:
            return False
        return self.loadauth.get_tok(load['token'])

    def publish(self, load):
        '''
        This method sends out publications to the minions, it can only be used
        by the LocalClient.
        '''
        extra = load.get('kwargs', {})

        # check blacklist/whitelist
        good = True
        # Check if the user is blacklisted
        for user_re in self.opts['client_acl_blacklist'].get('users', []):
            if re.match(user_re, load['user']):
                good = False
                break

        # check if the cmd is blacklisted
        for module_re in self.opts['client_acl_blacklist'].get('modules', []):
            # if this is a regular command, its a single function
            if type(load['fun']) == str:
                funs_to_check = [load['fun']]
            # if this a compound function
            else:
                funs_to_check = load['fun']
            for fun in funs_to_check:
                if re.match(module_re, fun):
                    good = False
                    break

        if good is False:
            log.error(
                '{user} does not have permissions to run {function}. Please '
                'contact your local administrator if you believe this is in '
                'error.\n'.format(
                    user=load['user'],
                    function=load['fun']
                )
            )
            return ''
        # to make sure we don't step on anyone else's toes
        del good

        # Check for external auth calls
        if extra.get('token', False):
            # A token was passed, check it
            try:
                token = self.loadauth.get_tok(extra['token'])
            except Exception as exc:
                log.error(
                    'Exception occurred when generating auth token: {0}'.format(
                        exc
                    )
                )
                return ''
            if not token:
                log.warning('Authentication failure of type "token" occurred.')
                return ''
            if token['eauth'] not in self.opts['external_auth']:
                log.warning('Authentication failure of type "token" occurred.')
                return ''
            if not ((token['name'] in self.opts['external_auth'][token['eauth']]) |
                    ('*' in self.opts['external_auth'][token['eauth']])):
                log.warning('Authentication failure of type "token" occurred.')
                return ''
            good = self.ckminions.auth_check(
                    self.opts['external_auth'][token['eauth']][token['name']]
                        if token['name'] in self.opts['external_auth'][token['eauth']]
                        else self.opts['external_auth'][token['eauth']]['*'],
                    load['fun'],
                    load['tgt'],
                    load.get('tgt_type', 'glob'))
            if not good:
                # Accept find_job so the CLI will function cleanly
                if load['fun'] != 'saltutil.find_job':
                    log.warning(
                        'Authentication failure of type "token" occurred.'
                    )
                    return ''
            load['user'] = token['name']
            log.debug('Minion tokenized user = "{0}"'.format(load['user']))
        elif 'eauth' in extra:
            if extra['eauth'] not in self.opts['external_auth']:
                # The eauth system is not enabled, fail
                log.warning(
                    'Authentication failure of type "eauth" occurred.'
                )
                return ''
            try:
                name = self.loadauth.load_name(extra)
                if not ((name in self.opts['external_auth'][extra['eauth']]) |
                        ('*' in self.opts['external_auth'][extra['eauth']])):
                    log.warning(
                        'Authentication failure of type "eauth" occurred.'
                    )
                    return ''
                if not self.loadauth.time_auth(extra):
                    log.warning(
                        'Authentication failure of type "eauth" occurred.'
                    )
                    return ''
            except Exception as exc:
                log.error(
                    'Exception occurred while authenticating: {0}'.format(exc)
                )
                return ''
            good = self.ckminions.auth_check(
                    self.opts['external_auth'][extra['eauth']][name]
                        if name in self.opts['external_auth'][extra['eauth']]
                        else self.opts['external_auth'][extra['eauth']]['*'],
                    load['fun'],
                    load['tgt'],
                    load.get('tgt_type', 'glob'))
            if not good:
                # Accept find_job so the CLI will function cleanly
                if load['fun'] != 'saltutil.find_job':
                    log.warning(
                        'Authentication failure of type "eauth" occurred.'
                    )
                    return ''
            load['user'] = name
        # Verify that the caller has root on master
        elif 'user' in load:
            if load['user'].startswith('sudo_'):
                # If someone can sudo, allow them to act as root
                if load.get('key', 'invalid') == self.key.get('root'):
                    load.pop('key')
                elif load.pop('key') != self.key[self.opts.get('user', 'root')]:
                    log.warning(
                        'Authentication failure of type "user" occurred.'
                    )
                    return ''
            elif load['user'] == self.opts.get('user', 'root'):
                if load.pop('key') != self.key[self.opts.get('user', 'root')]:
                    log.warning(
                        'Authentication failure of type "user" occurred.'
                    )
                    return ''
            elif load['user'] == 'root':
                if load.pop('key') != self.key.get(self.opts.get('user', 'root')):
                    log.warning(
                        'Authentication failure of type "user" occurred.'
                    )
                    return ''
            elif load['user'] == getpass.getuser():
                if load.pop('key') != self.key.get(load['user']):
                    log.warning(
                        'Authentication failure of type "user" occurred.'
                    )
                    return ''
            else:
                if load['user'] in self.key:
                    # User is authorised, check key and check perms
                    if load.pop('key') != self.key[load['user']]:
                        log.warning(
                            'Authentication failure of type "user" occurred.'
                        )
                        return ''
                    if load['user'] not in self.opts['client_acl']:
                        log.warning(
                            'Authentication failure of type "user" occurred.'
                        )
                        return ''
                    good = self.ckminions.auth_check(
                            self.opts['client_acl'][load['user']],
                            load['fun'],
                            load['tgt'],
                            load.get('tgt_type', 'glob'))
                    if not good:
                        # Accept find_job so the CLI will function cleanly
                        if load['fun'] != 'saltutil.find_job':
                            log.warning(
                                'Authentication failure of type "user" '
                                'occurred.'
                            )
                            return ''
                else:
                    log.warning(
                        'Authentication failure of type "user" occurred.'
                    )
                    return ''
        else:
            if load.pop('key') != self.key[getpass.getuser()]:
                log.warning(
                    'Authentication failure of type "other" occurred.'
                )
                return ''
        # Retrieve the minions list
        minions = self.ckminions.check_minions(
                load['tgt'],
                load.get('tgt_type', 'glob')
                )
        # If we order masters (via a syndic), don't short circuit if no minions
        # are found
        if not self.opts.get('order_masters'):
            # Check for no minions
            if not minions:
                return {
                    'enc': 'clear',
                    'load': {
                        'jid': None,
                        'minions': minions
                    }
                }
        # Retrieve the jid
        if not load['jid']:
            load['jid'] = salt.utils.prep_jid(
                    self.opts['cachedir'],
                    self.opts['hash_type'],
                    extra.get('nocache', False)
                    )
        self.event.fire_event({'minions': minions}, load['jid'])
        jid_dir = salt.utils.jid_dir(
                load['jid'],
                self.opts['cachedir'],
                self.opts['hash_type']
                )

        new_job_load = {
                'jid': load['jid'],
                'tgt_type': load['tgt_type'],
                'tgt': load['tgt'],
                'user': load['user'],
                'fun': load['fun'],
                'arg': load['arg'],
                'minions': minions,
            }

        # Announce the job on the event bus
        self.event.fire_event(new_job_load, 'new_job')  # old dup event
        self.event.fire_event(new_job_load, tagify([load['jid'], 'new'], 'job'))

        # Verify the jid dir
        if not os.path.isdir(jid_dir):
            os.makedirs(jid_dir)
        # Save the invocation information
        self.serial.dump(
                load,
                salt.utils.fopen(os.path.join(jid_dir, '.load.p'), 'w+')
                )
        # save the minions to a cache so we can see in the UI
        self.serial.dump(
                minions,
                salt.utils.fopen(os.path.join(jid_dir, '.minions.p'), 'w+')
                )
        if self.opts['ext_job_cache']:
            try:
                fstr = '{0}.save_load'.format(self.opts['ext_job_cache'])
                self.mminion.returners[fstr](load['jid'], load)
            except KeyError:
                log.critical(
                    'The specified returner used for the external job cache '
                    '"{0}" does not have a save_load function!'.format(
                        self.opts['ext_job_cache']
                    )
                )
            except Exception:
                log.critical(
                    'The specified returner threw a stack trace:\n',
                    exc_info=True
                )
        # Set up the payload
        payload = {'enc': 'aes'}
        # Altering the contents of the publish load is serious!! Changes here
        # break compatibility with minion/master versions and even tiny
        # additions can have serious implications on the performance of the
        # publish commands.
        #
        # In short, check with Thomas Hatch before you even think about
        # touching this stuff, we can probably do what you want to do another
        # way that won't have a negative impact.
        pub_load = {
            'fun': load['fun'],
            'arg': load['arg'],
            'tgt': load['tgt'],
            'jid': load['jid'],
            'ret': load['ret'],
        }

        if 'id' in extra:
            pub_load['id'] = extra['id']
        if 'tgt_type' in load:
            pub_load['tgt_type'] = load['tgt_type']
        if 'to' in load:
            pub_load['to'] = load['to']

        if 'user' in load:
            log.info(
                'User {user} Published command {fun} with jid {jid}'.format(
                    **load
                )
            )
            pub_load['user'] = load['user']
        else:
            log.info(
                'Published command {fun} with jid {jid}'.format(
                    **load
                )
            )
        log.debug('Published command details {0}'.format(pub_load))

        return {
            'enc': 'clear',
            'load': {
                'jid': load['jid'],
                'minions': minions
            }
        }
