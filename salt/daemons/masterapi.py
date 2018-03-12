# -*- coding: utf-8 -*-
'''
This module contains all of the routines needed to set up a master server, this
involves preparing the three listeners and the workers needed by the master.
'''
from __future__ import absolute_import

# Import python libs
import fnmatch
import logging
import os
import re
import time
import stat
import msgpack

# Import salt libs
import salt.crypt
import salt.utils
import salt.cache
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
import salt.utils.args
import salt.utils.atomicfile
import salt.utils.event
import salt.utils.files
import salt.utils.verify
import salt.utils.minions
import salt.utils.gzip_util
import salt.utils.jid
from salt.defaults import DEFAULT_TARGET_DELIM
from salt.pillar import git_pillar
from salt.utils.event import tagify
from salt.exceptions import FileserverConfigError, SaltMasterError

# Import 3rd-party libs
import salt.ext.six as six

try:
    import pwd
    HAS_PWD = True
except ImportError:
    # pwd is not available on windows
    HAS_PWD = False

log = logging.getLogger(__name__)

# Things to do in lower layers:
# only accept valid minion ids


def init_git_pillar(opts):
    '''
    Clear out the ext pillar caches, used when the master starts
    '''
    ret = []
    for opts_dict in [x for x in opts.get('ext_pillar', [])]:
        if 'git' in opts_dict:
            if isinstance(opts_dict['git'], six.string_types):
                # Legacy git pillar code
                try:
                    import git
                except ImportError:
                    return ret
                parts = opts_dict['git'].strip().split()
                try:
                    br = parts[0]
                    loc = parts[1]
                except IndexError:
                    log.critical(
                        'Unable to extract external pillar data: {0}'
                        .format(opts_dict['git'])
                    )
                else:
                    ret.append(
                        git_pillar._LegacyGitPillar(
                            br,
                            loc,
                            opts
                        )
                    )
            else:
                # New git_pillar code
                try:
                    pillar = salt.utils.gitfs.GitPillar(opts)
                    pillar.init_remotes(
                        opts_dict['git'],
                        git_pillar.PER_REMOTE_OVERRIDES,
                        git_pillar.PER_REMOTE_ONLY,
                        git_pillar.GLOBAL_ONLY)
                    ret.append(pillar)
                except FileserverConfigError:
                    if opts.get('git_pillar_verify_config', True):
                        raise
                    else:
                        log.critical('Could not initialize git_pillar')
    return ret


def clean_fsbackend(opts):
    '''
    Clean out the old fileserver backends
    '''
    # Clear remote fileserver backend caches so they get recreated
    for backend in ('git', 'hg', 'svn'):
        if backend in opts['fileserver_backend']:
            env_cache = os.path.join(
                opts['cachedir'],
                '{0}fs'.format(backend),
                'envs.p'
            )
            if os.path.isfile(env_cache):
                log.debug('Clearing {0}fs env cache'.format(backend))
                try:
                    os.remove(env_cache)
                except OSError as exc:
                    log.critical(
                        'Unable to clear env cache file {0}: {1}'
                        .format(env_cache, exc)
                    )

            file_lists_dir = os.path.join(
                opts['cachedir'],
                'file_lists',
                '{0}fs'.format(backend)
            )
            try:
                file_lists_caches = os.listdir(file_lists_dir)
            except OSError:
                continue
            for file_lists_cache in fnmatch.filter(file_lists_caches, '*.p'):
                cache_file = os.path.join(file_lists_dir, file_lists_cache)
                try:
                    os.remove(cache_file)
                except OSError as exc:
                    log.critical(
                        'Unable to file_lists cache file {0}: {1}'
                        .format(cache_file, exc)
                    )


def clean_expired_tokens(opts):
    '''
    Clean expired tokens from the master
    '''
    serializer = salt.payload.Serial(opts)
    for (dirpath, dirnames, filenames) in os.walk(opts['token_dir']):
        for token in filenames:
            token_path = os.path.join(dirpath, token)
            with salt.utils.fopen(token_path, 'rb') as token_file:
                try:
                    token_data = serializer.loads(token_file.read())
                except msgpack.UnpackValueError:
                    # Bad token file or empty. Remove.
                    os.remove(token_path)
                    return
                if 'expire' not in token_data or token_data.get('expire', 0) < time.time():
                    try:
                        os.remove(token_path)
                    except (IOError, OSError):
                        pass


def clean_pub_auth(opts):
    try:
        auth_cache = os.path.join(opts['cachedir'], 'publish_auth')
        if not os.path.exists(auth_cache):
            return
        else:
            for (dirpath, dirnames, filenames) in os.walk(auth_cache):
                for auth_file in filenames:
                    auth_file_path = os.path.join(dirpath, auth_file)
                    if not os.path.isfile(auth_file_path):
                        continue
                    if (time.time() - os.path.getmtime(auth_file_path) >
                            (opts['keep_jobs'] * 3600)):
                        os.remove(auth_file_path)
    except (IOError, OSError):
        log.error('Unable to delete pub auth file')


def clean_old_jobs(opts):
    '''
    Clean out the old jobs from the job cache
    '''
    # TODO: better way to not require creating the masterminion every time?
    mminion = salt.minion.MasterMinion(
                opts,
                states=False,
                rend=False,
                )
    # If the master job cache has a clean_old_jobs, call it
    fstr = '{0}.clean_old_jobs'.format(opts['master_job_cache'])
    if fstr in mminion.returners:
        mminion.returners[fstr]()


def mk_key(opts, user):
    if HAS_PWD:
        uid = None
        try:
            uid = pwd.getpwnam(user).pw_uid
        except KeyError:
            # User doesn't exist in the system
            if opts['client_acl_verify']:
                return None
    if salt.utils.is_windows():
        # The username may contain '\' if it is in Windows
        # 'DOMAIN\username' format. Fix this for the keyfile path.
        keyfile = os.path.join(
            opts['cachedir'], '.{0}_key'.format(user.replace('\\', '_'))
        )
    else:
        keyfile = os.path.join(
            opts['cachedir'], '.{0}_key'.format(user)
        )

    if os.path.exists(keyfile):
        log.debug('Removing stale keyfile: {0}'.format(keyfile))
        if salt.utils.is_windows() and not os.access(keyfile, os.W_OK):
            # Cannot delete read-only files on Windows.
            os.chmod(keyfile, stat.S_IRUSR | stat.S_IWUSR)
        os.unlink(keyfile)

    key = salt.crypt.Crypticle.generate_key_string()
    with salt.utils.files.set_umask(0o277):
        with salt.utils.fopen(keyfile, 'w+') as fp_:
            fp_.write(key)
    # 600 octal: Read and write access to the owner only.
    # Write access is necessary since on subsequent runs, if the file
    # exists, it needs to be written to again. Windows enforces this.
    os.chmod(keyfile, 0o600)
    if HAS_PWD and uid is not None:
        try:
            os.chown(keyfile, uid, -1)
        except OSError:
            # The master is not being run as root and can therefore not
            # chown the key file
            pass
    return key


def access_keys(opts):
    '''
    A key needs to be placed in the filesystem with permissions 0400 so
    clients are required to run as root.
    '''
    # TODO: Need a way to get all available users for systems not supported by pwd module.
    #       For now users pattern matching will not work for publisher_acl.
    keys = {}
    publisher_acl = opts['publisher_acl']
    acl_users = set(publisher_acl.keys())
    if opts.get('user'):
        acl_users.add(opts['user'])
    acl_users.add(salt.utils.get_user())
    for user in acl_users:
        log.info('Preparing the %s key for local communication', user)
        key = mk_key(opts, user)
        if key is not None:
            keys[user] = key

    # Check other users matching ACL patterns
    if opts['client_acl_verify'] and HAS_PWD:
        log.profile('Beginning pwd.getpwall() call in masterapi access_keys function')
        for user in pwd.getpwall():
            user = user.pw_name
            if user not in keys and salt.utils.check_whitelist_blacklist(user, whitelist=acl_users):
                keys[user] = mk_key(opts, user)
        log.profile('End pwd.getpwall() call in masterapi access_keys function')

    return keys


def fileserver_update(fileserver):
    '''
    Update the fileserver backends, requires that a built fileserver object
    be passed in
    '''
    try:
        if not fileserver.servers:
            log.error(
                'No fileservers loaded, the master will not be able to '
                'serve files to minions'
            )
            raise SaltMasterError('No fileserver backends available')
        fileserver.update()
    except Exception as exc:
        log.error(
            'Exception {0} occurred in file server update'.format(exc),
            exc_info_on_loglevel=logging.DEBUG
        )


class AutoKey(object):
    '''
    Implement the methods to run auto key acceptance and rejection
    '''
    def __init__(self, opts):
        self.opts = opts

    def check_permissions(self, filename):
        '''
        Check if the specified filename has correct permissions
        '''
        if salt.utils.is_windows():
            return True

        # After we've ascertained we're not on windows
        try:
            user = self.opts['user']
            pwnam = pwd.getpwnam(user)
            uid = pwnam[2]
            gid = pwnam[3]
            groups = salt.utils.get_gid_list(user, include_default=False)
        except KeyError:
            log.error(
                'Failed to determine groups for user {0}. The user is not '
                'available.\n'.format(
                    user
                )
            )
            return False

        fmode = os.stat(filename)

        if os.getuid() == 0:
            if fmode.st_uid == uid or fmode.st_gid != gid:
                return True
            elif self.opts.get('permissive_pki_access', False) \
                    and fmode.st_gid in groups:
                return True
        else:
            if stat.S_IWOTH & fmode.st_mode:
                # don't allow others to write to the file
                return False

            # check group flags
            if self.opts.get('permissive_pki_access', False) and stat.S_IWGRP & fmode.st_mode:
                return True
            elif stat.S_IWGRP & fmode.st_mode:
                return False

            # check if writable by group or other
            if not (stat.S_IWGRP & fmode.st_mode or
                    stat.S_IWOTH & fmode.st_mode):
                return True

        return False

    def check_signing_file(self, keyid, signing_file):
        '''
        Check a keyid for membership in a signing file
        '''
        if not signing_file or not os.path.exists(signing_file):
            return False

        if not self.check_permissions(signing_file):
            message = 'Wrong permissions for {0}, ignoring content'
            log.warning(message.format(signing_file))
            return False

        with salt.utils.fopen(signing_file, 'r') as fp_:
            for line in fp_:
                line = line.strip()
                if line.startswith('#'):
                    continue
                else:
                    if salt.utils.expr_match(keyid, line):
                        return True
        return False

    def check_autosign_dir(self, keyid):
        '''
        Check a keyid for membership in a autosign directory.
        '''
        autosign_dir = os.path.join(self.opts['pki_dir'], 'minions_autosign')

        # cleanup expired files
        expire_minutes = self.opts.get('autosign_timeout', 120)
        if expire_minutes > 0:
            min_time = time.time() - (60 * int(expire_minutes))
            for root, dirs, filenames in os.walk(autosign_dir):
                for f in filenames:
                    stub_file = os.path.join(autosign_dir, f)
                    mtime = os.path.getmtime(stub_file)
                    if mtime < min_time:
                        log.warning('Autosign keyid expired {0}'.format(stub_file))
                        os.remove(stub_file)

        stub_file = os.path.join(autosign_dir, keyid)
        if not os.path.exists(stub_file):
            return False
        os.remove(stub_file)
        return True

    def check_autoreject(self, keyid):
        '''
        Checks if the specified keyid should automatically be rejected.
        '''
        return self.check_signing_file(
            keyid,
            self.opts.get('autoreject_file', None)
        )

    def check_autosign(self, keyid):
        '''
        Checks if the specified keyid should automatically be signed.
        '''
        if self.opts['auto_accept']:
            return True
        if self.check_signing_file(keyid, self.opts.get('autosign_file', None)):
            return True
        if self.check_autosign_dir(keyid):
            return True
        return False


class RemoteFuncs(object):
    '''
    Funcitons made available to minions, this class includes the raw routines
    post validation that make up the minion access to the master
    '''
    def __init__(self, opts):
        self.opts = opts
        self.event = salt.utils.event.get_event(
                'master',
                self.opts['sock_dir'],
                self.opts['transport'],
                opts=self.opts,
                listen=False)
        self.serial = salt.payload.Serial(opts)
        self.ckminions = salt.utils.minions.CkMinions(opts)
        # Create the tops dict for loading external top data
        self.tops = salt.loader.tops(self.opts)
        # Make a client
        self.local = salt.client.get_local_client(mopts=self.opts)
        # Create the master minion to access the external job cache
        self.mminion = salt.minion.MasterMinion(
                self.opts,
                states=False,
                rend=False)
        self.__setup_fileserver()
        self.cache = salt.cache.factory(opts)

    def __setup_fileserver(self):
        '''
        Set the local file objects from the file server interface
        '''
        fs_ = salt.fileserver.Fileserver(self.opts)
        self._serve_file = fs_.serve_file
        self._file_find = fs_._find_file
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
        return self.ckminions.auth_check(
                perms,
                load['fun'],
                load['arg'],
                load['tgt'],
                load.get('tgt_type', 'glob'),
                publish_validate=True)

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
        mopts['top_file_merging_strategy'] = self.opts['top_file_merging_strategy']
        mopts['env_order'] = self.opts['env_order']
        mopts['default_top'] = self.opts['default_top']
        if load.get('env_only'):
            return mopts
        mopts['renderer'] = self.opts['renderer']
        mopts['failhard'] = self.opts['failhard']
        mopts['state_top'] = self.opts['state_top']
        mopts['state_top_saltenv'] = self.opts['state_top_saltenv']
        mopts['nodegroups'] = self.opts['nodegroups']
        mopts['state_auto_order'] = self.opts['state_auto_order']
        mopts['state_events'] = self.opts['state_events']
        mopts['state_aggregate'] = self.opts['state_aggregate']
        mopts['jinja_lstrip_blocks'] = self.opts['jinja_lstrip_blocks']
        mopts['jinja_trim_blocks'] = self.opts['jinja_trim_blocks']
        return mopts

    def _ext_nodes(self, load, skip_verify=False):
        '''
        Return the results from an external node classifier if one is
        specified
        '''
        if not skip_verify:
            if 'id' not in load:
                log.error('Received call for external nodes without an id')
                return {}
            if not salt.utils.verify.valid_id(self.opts, load['id']):
                return {}
        # Evaluate all configured master_tops interfaces

        opts = {}
        grains = {}
        ret = {}

        if 'opts' in load:
            opts = load['opts']
            if 'grains' in load['opts']:
                grains = load['opts']['grains']
        for fun in self.tops:
            if fun not in self.opts.get('master_tops', {}):
                continue
            try:
                ret = salt.utils.dictupdate.merge(ret, self.tops[fun](opts=opts, grains=grains), merge_lists=True)
            except Exception as exc:
                # If anything happens in the top generation, log it and move on
                log.error(
                    'Top function {0} failed with error {1} for minion '
                    '{2}'.format(
                        fun, exc, load['id']
                    )
                )
        return ret

    def _mine_get(self, load, skip_verify=False):
        '''
        Gathers the data from the specified minions' mine
        '''
        if not skip_verify:
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
        expr_form = load.get('expr_form')
        if expr_form is not None and 'tgt_type' not in load:
            salt.utils.warn_until(
                u'Neon',
                u'_mine_get: minion {0} uses pre-Nitrogen API key '
                u'"expr_form". Accepting for backwards compatibility '
                u'but this is not guaranteed '
                u'after the Neon release'.format(load['id'])
            )
            match_type = expr_form
        else:
            match_type = load.get('tgt_type', 'glob')
        if match_type.lower() == 'pillar':
            match_type = 'pillar_exact'
        if match_type.lower() == 'compound':
            match_type = 'compound_pillar_exact'
        checker = salt.utils.minions.CkMinions(self.opts)
        minions = checker.check_minions(
                load['tgt'],
                match_type,
                greedy=False
                )
        for minion in minions:
            fdata = self.cache.fetch('minions/{0}'.format(minion), 'mine')
            if isinstance(fdata, dict):
                fdata = fdata.get(load['fun'])
                if fdata:
                    ret[minion] = fdata
        return ret

    def _mine(self, load, skip_verify=False):
        '''
        Return the mine data
        '''
        if not skip_verify:
            if 'id' not in load or 'data' not in load:
                return False
        if self.opts.get('minion_data_cache', False) or self.opts.get('enforce_mine_cache', False):
            cbank = 'minions/{0}'.format(load['id'])
            ckey = 'mine'
            if not load.get('clear', False):
                data = self.cache.fetch(cbank, ckey)
                if isinstance(data, dict):
                    data.update(load['data'])
                    load['data'] = data
            self.cache.store(cbank, ckey, load['data'])
        return True

    def _mine_delete(self, load):
        '''
        Allow the minion to delete a specific function from its own mine
        '''
        if 'id' not in load or 'fun' not in load:
            return False
        if self.opts.get('minion_data_cache', False) or self.opts.get('enforce_mine_cache', False):
            cbank = 'minions/{0}'.format(load['id'])
            ckey = 'mine'
            try:
                data = self.cache.fetch(cbank, ckey)
                if not isinstance(data, dict):
                    return False
                if load['fun'] in data:
                    del data[load['fun']]
                    self.cache.store(cbank, ckey, data)
            except OSError:
                return False
        return True

    def _mine_flush(self, load, skip_verify=False):
        '''
        Allow the minion to delete all of its own mine contents
        '''
        if not skip_verify and 'id' not in load:
            return False
        if self.opts.get('minion_data_cache', False) or self.opts.get('enforce_mine_cache', False):
            return self.cache.flush('minions/{0}'.format(load['id']), 'mine')
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
        if not salt.utils.verify.valid_id(self.opts, load['id']):
            return False
        file_recv_max_size = 1024*1024 * self.opts['file_recv_max_size']

        if 'loc' in load and load['loc'] < 0:
            log.error('Invalid file pointer: load[loc] < 0')
            return False

        if len(load['data']) + load.get('loc', 0) > file_recv_max_size:
            log.error(
                'Exceeding file_recv_max_size limit: {0}'.format(
                    file_recv_max_size
                )
            )
            return False
        # Normalize Windows paths
        normpath = load['path']
        if ':' in normpath:
            # make sure double backslashes are normalized
            normpath = normpath.replace('\\', '/')
            normpath = os.path.normpath(normpath)
        cpath = os.path.join(
            self.opts['cachedir'],
            'minions',
            load['id'],
            'files',
            normpath)
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
#        pillar = salt.pillar.Pillar(
        log.debug('Master _pillar using ext: {0}'.format(load.get('ext')))
        pillar = salt.pillar.get_pillar(
                self.opts,
                load['grains'],
                load['id'],
                load.get('saltenv', load.get('env')),
                load.get('ext'),
                self.mminion.functions,
                pillar_override=load.get('pillar_override', {}))
        pillar_dirs = {}
        data = pillar.compile_pillar(pillar_dirs=pillar_dirs)
        if self.opts.get('minion_data_cache', False):
            self.cache.store('minions/{0}'.format(load['id']),
                             'data',
                             {'grains': load['grains'], 'pillar': data})
            if self.opts.get('minion_data_cache_events') is True:
                self.event.fire_event('Minion data cache refresh', tagify(load['id'], 'refresh', 'minion'))
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
                if 'data' in event:
                    event_data = event['data']
                else:
                    event_data = event
                self.event.fire_event(event_data, event['tag'])  # old dup event
                if load.get('pretag') is not None:
                    self.event.fire_event(event_data, tagify(event['tag'], base=load['pretag']))
        else:
            tag = load['tag']
            self.event.fire_event(load, tag)
        return True

    def _return(self, load):
        '''
        Handle the return data sent from the minions
        '''
        # Generate EndTime
        endtime = salt.utils.jid.jid_to_time(salt.utils.jid.gen_jid())
        # If the return data is invalid, just ignore it
        if any(key not in load for key in ('return', 'jid', 'id')):
            return False

        if load['jid'] == 'req':
            # The minion is returning a standalone job, request a jobid
            prep_fstr = '{0}.prep_jid'.format(self.opts['master_job_cache'])
            load['jid'] = self.mminion.returners[prep_fstr](nocache=load.get('nocache', False))

            # save the load, since we don't have it
            saveload_fstr = '{0}.save_load'.format(self.opts['master_job_cache'])
            self.mminion.returners[saveload_fstr](load['jid'], load)
        log.info('Got return from {id} for job {jid}'.format(**load))
        self.event.fire_event(load, load['jid'])  # old dup event
        self.event.fire_event(load, tagify([load['jid'], 'ret', load['id']], 'job'))
        self.event.fire_ret_load(load)
        if not self.opts['job_cache'] or self.opts.get('ext_job_cache'):
            return

        fstr = '{0}.update_endtime'.format(self.opts['master_job_cache'])
        if (self.opts.get('job_cache_store_endtime')
                and fstr in self.mminion.returners):
            self.mminion.returners[fstr](load['jid'], endtime)

        fstr = '{0}.returner'.format(self.opts['master_job_cache'])
        self.mminion.returners[fstr](load)

    def _syndic_return(self, load):
        '''
        Receive a syndic minion return and format it to look like returns from
        individual minions.
        '''
        # Verify the load
        if any(key not in load for key in ('return', 'jid', 'id')):
            return None
        # if we have a load, save it
        if 'load' in load:
            fstr = '{0}.save_load'.format(self.opts['master_job_cache'])
            self.mminion.returners[fstr](load['jid'], load['load'])

        # Format individual return loads
        for key, item in six.iteritems(load['return']):
            ret = {'jid': load['jid'],
                   'id': key,
                   'return': item}
            if 'out' in load:
                ret['out'] = load['out']
            self._return(ret)

    def minion_runner(self, load):
        '''
        Execute a runner from a minion, return the runner's function data
        '''
        if 'peer_run' not in self.opts:
            return {}
        if not isinstance(self.opts['peer_run'], dict):
            return {}
        if any(key not in load for key in ('fun', 'arg', 'id')):
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
            # The minion is not who it says it is!
            # We don't want to listen to it!
            log.warning(
                    'Minion id {0} is not who it says it is!'.format(
                    load['id']
                    )
            )
            return {}
        # Prepare the runner object
        opts = {}
        opts.update(self.opts)
        opts.update({'fun': load['fun'],
                'arg': salt.utils.args.parse_input(
                    load['arg'],
                    no_parse=load.get('no_parse', [])),
                'id': load['id'],
                'doc': False,
                'conf_file': self.opts['conf_file']})
        runner = salt.runner.Runner(opts)
        return runner.run()

    def pub_ret(self, load, skip_verify=False):
        '''
        Request the return data from a specific jid, only allowed
        if the requesting minion also initialted the execution.
        '''
        if not skip_verify and any(key not in load for key in ('jid', 'id')):
            return {}
        else:
            auth_cache = os.path.join(
                    self.opts['cachedir'],
                    'publish_auth')
            if not os.path.isdir(auth_cache):
                os.makedirs(auth_cache)
            jid_fn = os.path.join(auth_cache, load['jid'])
            with salt.utils.fopen(jid_fn, 'r') as fp_:
                if not load['id'] == fp_.read():
                    return {}

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
        if not self.__verify_minion_publish(load):
            return {}
        # Set up the publication payload
        pub_load = {
            'fun': load['fun'],
            'arg': salt.utils.args.parse_input(
                load['arg'],
                no_parse=load.get('no_parse', [])),
            'tgt_type': load.get('tgt_type', 'glob'),
            'tgt': load['tgt'],
            'ret': load['ret'],
            'id': load['id'],
        }
        if 'tgt_type' in load:
            if load['tgt_type'].startswith('node'):
                if load['tgt'] in self.opts['nodegroups']:
                    pub_load['tgt'] = self.opts['nodegroups'][load['tgt']]
                    pub_load['tgt_type'] = 'compound'
                else:
                    return {}
            else:
                pub_load['tgt_type'] = load['tgt_type']
        ret = {}
        ret['jid'] = self.local.cmd_async(**pub_load)
        ret['minions'] = self.ckminions.check_minions(
                load['tgt'],
                pub_load['tgt_type'])
        auth_cache = os.path.join(
                self.opts['cachedir'],
                'publish_auth')
        if not os.path.isdir(auth_cache):
            os.makedirs(auth_cache)
        jid_fn = os.path.join(auth_cache, str(ret['jid']))
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
            'arg': salt.utils.args.parse_input(
                load['arg'],
                no_parse=load.get('no_parse', [])),
            'tgt_type': load.get('tgt_type', 'glob'),
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
                log.warning(msg)
                return {}
        if 'timeout' in load:
            try:
                pub_load['timeout'] = int(load['timeout'])
            except ValueError:
                msg = 'Failed to parse timeout value: {0}'.format(
                        load['timeout'])
                log.warning(msg)
                return {}
        if 'tgt_type' in load:
            if load['tgt_type'].startswith('node'):
                if load['tgt'] in self.opts['nodegroups']:
                    pub_load['tgt'] = self.opts['nodegroups'][load['tgt']]
                    pub_load['tgt_type'] = 'compound'
                else:
                    return {}
            else:
                pub_load['tgt_type'] = load['tgt_type']
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
        for key, val in six.iteritems(self.local.get_cache_returns(ret['__jid__'])):
            if key not in ret:
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
        keyapi.delete_key(load['id'],
                          preserve_minions=load.get('preserve_minion_cache',
                                                         False))
        return True


class LocalFuncs(object):
    '''
    Set up methods for use only from the local system
    '''
    # The ClearFuncs object encapsulates the functions that can be executed in
    # the clear:
    # publish (The publish from the LocalClient)
    # _auth
    def __init__(self, opts, key):
        self.opts = opts
        self.serial = salt.payload.Serial(opts)
        self.key = key
        # Create the event manager
        self.event = salt.utils.event.get_event(
                'master',
                self.opts['sock_dir'],
                self.opts['transport'],
                opts=self.opts,
                listen=False)
        # Make a client
        self.local = salt.client.get_local_client(mopts=self.opts)
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
        if 'token' in load:
            auth_type = 'token'
            err_name = 'TokenAuthenticationError'
            token = self.loadauth.authenticate_token(load)
            if not token:
                return dict(error=dict(name=err_name,
                                       message='Authentication failure of type "token" occurred.'))
            username = token['name']
            auth_list = self.loadauth.get_auth_list(load, token)
        else:
            auth_type = 'eauth'
            err_name = 'EauthAuthenticationError'
            username = load.get('username', 'UNKNOWN')
            if not self.loadauth.authenticate_eauth(load):
                return dict(error=dict(name=err_name,
                                       message=('Authentication failure of type "eauth" occurred '
                                                'for user {0}.').format(username)))
            auth_list = self.loadauth.get_auth_list(load)

        if not self.ckminions.runner_check(auth_list, load['fun']):
            return dict(error=dict(name=err_name,
                                   message=('Authentication failure of type "{0}" occurred '
                                            'for user {1}.').format(auth_type, username)))

        try:
            fun = load.pop('fun')
            runner_client = salt.runner.RunnerClient(self.opts)
            return runner_client.async(fun,
                                       load.get('kwarg', {}),
                                       username)
        except Exception as exc:
            log.error('Exception occurred while '
                    'introspecting {0}: {1}'.format(fun, exc))
            return dict(error=dict(name=exc.__class__.__name__,
                                   args=exc.args,
                                   message=str(exc)))

    def wheel(self, load):
        '''
        Send a master control function back to the wheel system
        '''
        # All wheel ops pass through eauth
        if 'token' in load:
            auth_type = 'token'
            err_name = 'TokenAuthenticationError'
            token = self.loadauth.authenticate_token(load)
            if not token:
                return dict(error=dict(name=err_name,
                                       message='Authentication failure of type "token" occurred.'))
            username = token['name']
            auth_list = self.loadauth.get_auth_list(load, token)
        elif 'eauth' in load:
            auth_type = 'eauth'
            err_name = 'EauthAuthenticationError'
            username = load.get('username', 'UNKNOWN')
            if not self.loadauth.authenticate_eauth(load):
                return dict(error=dict(name=err_name,
                                       message=('Authentication failure of type "eauth" occurred for '
                                                'user {0}.').format(username)))
            auth_list = self.loadauth.get_auth_list(load)
        else:
            auth_type = 'user'
            err_name = 'UserAuthenticationError'
            username = load.get('username', 'UNKNOWN')
            if not self.loadauth.authenticate_key(load, self.key):
                return dict(error=dict(name=err_name,
                                       message=('Authentication failure of type "user" occurred for '
                                                'user {0}.').format(username)))

        if auth_type != 'user':
            if not self.ckminions.wheel_check(auth_list, load['fun']):
                return dict(error=dict(name=err_name,
                                       message=('Authentication failure of type "{0}" occurred for '
                                                'user {1}.').format(auth_type, username)))

        # Authenticated. Do the job.
        jid = salt.utils.jid.gen_jid()
        fun = load.pop('fun')
        tag = tagify(jid, prefix='wheel')
        data = {'fun': "wheel.{0}".format(fun),
                'jid': jid,
                'tag': tag,
                'user': username}
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
            data['return'] = 'Exception occurred in wheel {0}: {1}: {2}'.format(
                                        fun,
                                        exc.__class__.__name__,
                                        exc,
                                        )
            data['success'] = False
            self.event.fire_event(data, tagify([jid, 'ret'], 'wheel'))
            return {'tag': tag,
                    'data': data}

    def mk_token(self, load):
        '''
        Create and return an authentication token, the clear load needs to
        contain the eauth key and the needed authentication creds.
        '''
        token = self.loadauth.mk_token(load)
        if not token:
            log.warning('Authentication failure of type "eauth" occurred.')
            return ''
        return token

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

        publisher_acl = salt.acl.PublisherACL(self.opts['publisher_acl_blacklist'])

        if publisher_acl.user_is_blacklisted(load['user']) or \
                publisher_acl.cmd_is_blacklisted(load['fun']):
            log.error(
                '{user} does not have permissions to run {function}. Please '
                'contact your local administrator if you believe this is in '
                'error.\n'.format(
                    user=load['user'],
                    function=load['fun']
                )
            )
            return ''

        # Retrieve the minions list
        delimiter = load.get('kwargs', {}).get('delimiter', DEFAULT_TARGET_DELIM)
        minions = self.ckminions.check_minions(
            load['tgt'],
            load.get('tgt_type', 'glob'),
            delimiter
        )

        # Check for external auth calls
        if extra.get('token', False):
            # Authenticate
            token = self.loadauth.authenticate_token(extra)
            if not token:
                return ''

            # Get acl from eauth module.
            auth_list = self.loadauth.get_auth_list(extra, token)

            # Authorize the request
            if not self.ckminions.auth_check(
                    auth_list,
                    load['fun'],
                    load['arg'],
                    load['tgt'],
                    load.get('tgt_type', 'glob'),
                    minions=minions,
                    # always accept find_job
                    whitelist=['saltutil.find_job'],
                    ):
                log.warning('Authentication failure of type "token" occurred.')
                return ''
            load['user'] = token['name']
            log.debug('Minion tokenized user = "{0}"'.format(load['user']))
        elif 'eauth' in extra:
            # Authenticate.
            if not self.loadauth.authenticate_eauth(extra):
                return ''

            # Get acl from eauth module.
            auth_list = self.loadauth.get_auth_list(extra)

            # Authorize the request
            if not self.ckminions.auth_check(
                    auth_list,
                    load['fun'],
                    load['arg'],
                    load['tgt'],
                    load.get('tgt_type', 'glob'),
                    minions=minions,
                    # always accept find_job
                    whitelist=['saltutil.find_job'],
                    ):
                log.warning('Authentication failure of type "eauth" occurred.')
                return ''
            load['user'] = self.loadauth.load_name(extra)  # The username we are attempting to auth with
        # Verify that the caller has root on master
        else:
            auth_ret = self.loadauth.authenticate_key(load, self.key)
            if auth_ret is False:
                return ''

            if auth_ret is not True:
                if salt.auth.AuthUser(load['user']).is_sudo():
                    if not self.opts['sudo_acl'] or not self.opts['publisher_acl']:
                        auth_ret = True

            if auth_ret is not True:
                auth_list = salt.utils.get_values_of_matching_keys(
                        self.opts['publisher_acl'],
                        auth_ret)
                if not auth_list:
                    log.warning(
                        'Authentication failure of type "user" occurred.'
                    )
                    return ''

                if not self.ckminions.auth_check(
                        auth_list,
                        load['fun'],
                        load['arg'],
                        load['tgt'],
                        load.get('tgt_type', 'glob'),
                        minions=minions,
                        # always accept find_job
                        whitelist=['saltutil.find_job'],
                        ):
                    log.warning('Authentication failure of type "user" occurred.')
                    return ''

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
            fstr = '{0}.prep_jid'.format(self.opts['master_job_cache'])
            load['jid'] = self.mminion.returners[fstr](nocache=extra.get('nocache', False))
        self.event.fire_event({'minions': minions}, load['jid'])

        new_job_load = {
                'jid': load['jid'],
                'tgt_type': load['tgt_type'],
                'tgt': load['tgt'],
                'user': load['user'],
                'fun': load['fun'],
                'arg': salt.utils.args.parse_input(
                    load['arg'],
                    no_parse=load.get('no_parse', [])),
                'minions': minions,
            }

        # Announce the job on the event bus
        self.event.fire_event(new_job_load, 'new_job')  # old dup event
        self.event.fire_event(new_job_load, tagify([load['jid'], 'new'], 'job'))

        # Save the invocation information
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

        # always write out to the master job cache
        try:
            fstr = '{0}.save_load'.format(self.opts['master_job_cache'])
            self.mminion.returners[fstr](load['jid'], load)
        except KeyError:
            log.critical(
                'The specified returner used for the master job cache '
                '"{0}" does not have a save_load function!'.format(
                    self.opts['master_job_cache']
                )
            )
        except Exception:
            log.critical(
                'The specified returner threw a stack trace:\n',
                exc_info=True
            )
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
            'arg': salt.utils.args.parse_input(
                load['arg'],
                no_parse=load.get('no_parse', [])),
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

        if 'kwargs' in load:
            if 'ret_config' in load['kwargs']:
                pub_load['ret_config'] = load['kwargs'].get('ret_config')

            if 'metadata' in load['kwargs']:
                pub_load['metadata'] = load['kwargs'].get('metadata')

            if 'ret_kwargs' in load['kwargs']:
                pub_load['ret_kwargs'] = load['kwargs'].get('ret_kwargs')

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

        return {'ret': {
                    'jid': load['jid'],
                    'minions': minions
                    },
                'pub': pub_load
                }
