# -*- coding: utf-8 -*-
'''
File server pluggable modules and generic backend functions
'''

# Import python libs
from __future__ import absolute_import
import errno
import fnmatch
import logging
import os
import re
import time

# Import salt libs
import salt.loader
import salt.utils
import salt.utils.locales

# Import 3rd-party libs
import salt.ext.six as six


log = logging.getLogger(__name__)


def _unlock_cache(w_lock):
    '''
    Unlock a FS file/dir based lock
    '''
    if not os.path.exists(w_lock):
        return
    try:
        if os.path.isdir(w_lock):
            os.rmdir(w_lock)
        elif os.path.isfile(w_lock):
            os.unlink(w_lock)
    except (OSError, IOError) as exc:
        log.trace('Error removing lockfile {0}: {1}'.format(w_lock, exc))


def _lock_cache(w_lock):
    try:
        os.mkdir(w_lock)
    except OSError as exc:
        if exc.errno != errno.EEXIST:
            raise
        return False
    else:
        log.trace('Lockfile {0} created'.format(w_lock))
        return True


def wait_lock(lk_fn, dest, wait_timeout=0):
    '''
    If the write lock is there, check to see if the file is actually being
    written. If there is no change in the file size after a short sleep,
    remove the lock and move forward.
    '''
    if not os.path.exists(lk_fn):
        return False
    if not os.path.exists(dest):
        # The dest is not here, sleep for a bit, if the dest is not here yet
        # kill the lockfile and start the write
        time.sleep(1)
        if not os.path.isfile(dest):
            _unlock_cache(lk_fn)
            return False
    timeout = None
    if wait_timeout:
        timeout = time.time() + wait_timeout
    # There is a lock file, the dest is there, stat the dest, sleep and check
    # that the dest is being written, if it is not being written kill the lock
    # file and continue. Also check if the lock file is gone.
    s_count = 0
    s_size = os.stat(dest).st_size
    while True:
        time.sleep(1)
        if not os.path.exists(lk_fn):
            return False
        size = os.stat(dest).st_size
        if size == s_size:
            s_count += 1
            if s_count >= 3:
                # The file is not being written to, kill the lock and proceed
                _unlock_cache(lk_fn)
                return False
        else:
            s_size = size
        if timeout:
            if time.time() > timeout:
                raise ValueError(
                    'Timeout({0}s) for {1} '
                    '(lock: {2}) elapsed'.format(
                        wait_timeout, dest, lk_fn))
    return False


def check_file_list_cache(opts, form, list_cache, w_lock):
    '''
    Checks the cache file to see if there is a new enough file list cache, and
    returns the match (if found, along with booleans used by the fileserver
    backend to determine if the cache needs to be refreshed/written).
    '''
    refresh_cache = False
    save_cache = True
    serial = salt.payload.Serial(opts)
    wait_lock(w_lock, list_cache, 5 * 60)
    if not os.path.isfile(list_cache) and _lock_cache(w_lock):
        refresh_cache = True
    else:
        attempt = 0
        while attempt < 11:
            try:
                if os.path.exists(w_lock):
                    # wait for a filelist lock for max 15min
                    wait_lock(w_lock, list_cache, 15 * 60)
                if os.path.exists(list_cache):
                    # calculate filelist age is possible
                    cache_stat = os.stat(list_cache)
                    age = time.time() - cache_stat.st_mtime
                else:
                    # if filelist does not exists yet, mark it as expired
                    age = opts.get('fileserver_list_cache_time', 30) + 1
                if age < opts.get('fileserver_list_cache_time', 30):
                    # Young enough! Load this sucker up!
                    with salt.utils.fopen(list_cache, 'rb') as fp_:
                        log.trace('Returning file_lists cache data from '
                                  '{0}'.format(list_cache))
                        return serial.load(fp_).get(form, []), False, False
                elif _lock_cache(w_lock):
                    # Set the w_lock and go
                    refresh_cache = True
                    break
            except Exception:
                time.sleep(0.2)
                attempt += 1
                continue
        if attempt > 10:
            save_cache = False
            refresh_cache = True
    return None, refresh_cache, save_cache


def write_file_list_cache(opts, data, list_cache, w_lock):
    '''
    Checks the cache file to see if there is a new enough file list cache, and
    returns the match (if found, along with booleans used by the fileserver
    backend to determine if the cache needs to be refreshed/written).
    '''
    serial = salt.payload.Serial(opts)
    with salt.utils.fopen(list_cache, 'w+b') as fp_:
        fp_.write(serial.dumps(data))
        _unlock_cache(w_lock)
        log.trace('Lockfile {0} removed'.format(w_lock))


def check_env_cache(opts, env_cache):
    '''
    Returns cached env names, if present. Otherwise returns None.
    '''
    if not os.path.isfile(env_cache):
        return None
    try:
        with salt.utils.fopen(env_cache, 'rb') as fp_:
            log.trace('Returning env cache data from {0}'.format(env_cache))
            serial = salt.payload.Serial(opts)
            return serial.load(fp_)
    except (IOError, OSError):
        pass
    return None


def generate_mtime_map(path_map):
    '''
    Generate a dict of filename -> mtime
    '''
    file_map = {}
    for saltenv, path_list in six.iteritems(path_map):
        for path in path_list:
            for directory, dirnames, filenames in os.walk(path):
                for item in filenames:
                    try:
                        file_path = os.path.join(directory, item)
                        file_map[file_path] = os.path.getmtime(file_path)
                    except (OSError, IOError):
                        # skip dangling symlinks
                        log.info(
                            'Failed to get mtime on {0}, '
                            'dangling symlink ?'.format(file_path))
                        continue
    return file_map


def diff_mtime_map(map1, map2):
    '''
    Is there a change to the mtime map? return a boolean
    '''
    # check if the mtimes are the same
    if sorted(map1) != sorted(map2):
        #log.debug('diff_mtime_map: the maps are different')
        return True

    # we made it, that means we have no changes
    #log.debug('diff_mtime_map: the maps are the same')
    return False


def reap_fileserver_cache_dir(cache_base, find_func):
    '''
    Remove unused cache items assuming the cache directory follows a directory
    convention:

    cache_base -> saltenv -> relpath
    '''
    for saltenv in os.listdir(cache_base):
        env_base = os.path.join(cache_base, saltenv)
        for root, dirs, files in os.walk(env_base):
            # if we have an empty directory, lets cleanup
            # This will only remove the directory on the second time
            # "_reap_cache" is called (which is intentional)
            if len(dirs) == 0 and len(files) == 0:
                # only remove if empty directory is older than 60s
                if time.time() - os.path.getctime(root) > 60:
                    os.rmdir(root)
                continue
            # if not, lets check the files in the directory
            for file_ in files:
                file_path = os.path.join(root, file_)
                file_rel_path = os.path.relpath(file_path, env_base)
                try:
                    filename, _, hash_type = file_rel_path.rsplit('.', 2)
                except ValueError:
                    log.warning((
                        'Found invalid hash file [{0}] when attempting to reap'
                        ' cache directory.'
                    ).format(file_))
                    continue
                # do we have the file?
                ret = find_func(filename, saltenv=saltenv)
                # if we don't actually have the file, lets clean up the cache
                # object
                if ret['path'] == '':
                    os.unlink(file_path)


def is_file_ignored(opts, fname):
    '''
    If file_ignore_regex or file_ignore_glob were given in config,
    compare the given file path against all of them and return True
    on the first match.
    '''
    if opts['file_ignore_regex']:
        for regex in opts['file_ignore_regex']:
            if re.search(regex, fname):
                log.debug(
                    'File matching file_ignore_regex. Skipping: {0}'.format(
                        fname
                    )
                )
                return True

    if opts['file_ignore_glob']:
        for glob in opts['file_ignore_glob']:
            if fnmatch.fnmatch(fname, glob):
                log.debug(
                    'File matching file_ignore_glob. Skipping: {0}'.format(
                        fname
                    )
                )
                return True
    return False


def clear_lock(clear_func, role, remote=None, lock_type='update'):
    '''
    Function to allow non-fileserver functions to clear update locks

    clear_func
        A function reference. This function will be run (with the ``remote``
        param as an argument) to clear the lock, and must return a 2-tuple of
        lists, one containing messages describing successfully cleared locks,
        and one containing messages describing errors encountered.

    role
        What type of lock is being cleared (gitfs, git_pillar, etc.). Used
        solely for logging purposes.

    remote
        Optional string which should be used in ``func`` to pattern match so
        that a subset of remotes can be targeted.

    lock_type : update
        Which type of lock to clear

    Returns the return data from ``clear_func``.
    '''
    msg = 'Clearing {0} lock for {1} remotes'.format(lock_type, role)
    if remote:
        msg += ' matching {0}'.format(remote)
    log.debug(msg)
    return clear_func(remote=remote, lock_type=lock_type)


class Fileserver(object):
    '''
    Create a fileserver wrapper object that wraps the fileserver functions and
    iterates over them to execute the desired function within the scope of the
    desired fileserver backend.
    '''
    def __init__(self, opts):
        self.opts = opts
        self.servers = salt.loader.fileserver(opts, opts['fileserver_backend'])

    def _gen_back(self, back):
        '''
        Return the backend list
        '''
        if not back:
            back = self.opts['fileserver_backend']
        else:
            try:
                back = back.split(',')
            except AttributeError:
                back = six.text_type(back).split(',')

        ret = []
        if not isinstance(back, list):
            return ret

        try:
            subtract_only = all((x.startswith('-') for x in back))
        except AttributeError:
            pass
        else:
            if subtract_only:
                # Only subtracting backends from enabled ones
                ret = self.opts['fileserver_backend']
                for sub in back:
                    if '{0}.envs'.format(sub[1:]) in self.servers:
                        ret.remove(sub[1:])
                    elif '{0}.envs'.format(sub[1:-2]) in self.servers:
                        ret.remove(sub[1:-2])
                return ret

        for sub in back:
            if '{0}.envs'.format(sub) in self.servers:
                ret.append(sub)
            elif '{0}.envs'.format(sub[:-2]) in self.servers:
                ret.append(sub[:-2])
        return ret

    def master_opts(self, load):
        '''
        Simplify master opts
        '''
        return self.opts

    def update_opts(self):
        # This fix func monkey patching by pillar
        for name, func in self.servers.items():
            try:
                if '__opts__' in func.__globals__:
                    func.__globals__['__opts__'].update(self.opts)
            except AttributeError:
                pass

    def clear_cache(self, back=None):
        '''
        Clear the cache of all of the fileserver backends that support the
        clear_cache function or the named backend(s) only.
        '''
        back = self._gen_back(back)
        cleared = []
        errors = []
        for fsb in back:
            fstr = '{0}.clear_cache'.format(fsb)
            if fstr in self.servers:
                log.debug('Clearing {0} fileserver cache'.format(fsb))
                failed = self.servers[fstr]()
                if failed:
                    errors.extend(failed)
                else:
                    cleared.append(
                        'The {0} fileserver cache was successfully cleared'
                        .format(fsb)
                    )
        return cleared, errors

    def lock(self, back=None, remote=None):
        '''
        ``remote`` can either be a dictionary containing repo configuration
        information, or a pattern. If the latter, then remotes for which the URL
        matches the pattern will be locked.
        '''
        back = self._gen_back(back)
        locked = []
        errors = []
        for fsb in back:
            fstr = '{0}.lock'.format(fsb)
            if fstr in self.servers:
                msg = 'Setting update lock for {0} remotes'.format(fsb)
                if remote:
                    if not isinstance(remote, six.string_types):
                        errors.append(
                            'Badly formatted remote pattern \'{0}\''
                            .format(remote)
                        )
                        continue
                    else:
                        msg += ' matching {0}'.format(remote)
                log.debug(msg)
                good, bad = self.servers[fstr](remote=remote)
                locked.extend(good)
                errors.extend(bad)
        return locked, errors

    def clear_lock(self, back=None, remote=None):
        '''
        Clear the update lock for the enabled fileserver backends

        back
            Only clear the update lock for the specified backend(s). The
            default is to clear the lock for all enabled backends

        remote
            If specified, then any remotes which contain the passed string will
            have their lock cleared.
        '''
        back = self._gen_back(back)
        cleared = []
        errors = []
        for fsb in back:
            fstr = '{0}.clear_lock'.format(fsb)
            if fstr in self.servers:
                good, bad = clear_lock(self.servers[fstr],
                                       fsb,
                                       remote=remote)
                cleared.extend(good)
                errors.extend(bad)
        return cleared, errors

    def update(self, back=None):
        '''
        Update all of the enabled fileserver backends which support the update
        function, or
        '''
        back = self._gen_back(back)
        for fsb in back:
            fstr = '{0}.update'.format(fsb)
            if fstr in self.servers:
                log.debug('Updating {0} fileserver cache'.format(fsb))
                self.servers[fstr]()

    def envs(self, back=None, sources=False):
        '''
        Return the environments for the named backend or all backends
        '''
        back = self._gen_back(back)
        ret = set()
        if sources:
            ret = {}
        for fsb in back:
            fstr = '{0}.envs'.format(fsb)
            if sources:
                ret[fsb] = self.servers[fstr]()
            else:
                ret.update(self.servers[fstr]())
        if sources:
            return ret
        return list(ret)

    def init(self, back=None):
        '''
        Initialize the backend, only do so if the fs supports an init function
        '''
        back = self._gen_back(back)
        for fsb in back:
            fstr = '{0}.init'.format(fsb)
            if fstr in self.servers:
                self.servers[fstr]()

    def find_file(self, path, saltenv, back=None):
        '''
        Find the path and return the fnd structure, this structure is passed
        to other backend interfaces.
        '''
        back = self._gen_back(back)
        kwargs = {}
        fnd = {'path': '',
               'rel': ''}
        if os.path.isabs(path):
            return fnd
        if '../' in path:
            return fnd
        if salt.utils.url.is_escaped(path):
            # don't attempt to find URL query arguements in the path
            path = salt.utils.url.unescape(path)
        else:
            if '?' in path:
                hcomps = path.split('?')
                path = hcomps[0]
                comps = hcomps[1].split('&')
                for comp in comps:
                    if '=' not in comp:
                        # Invalid option, skip it
                        continue
                    args = comp.split('=', 1)
                    kwargs[args[0]] = args[1]

        if 'env' in kwargs:
            salt.utils.warn_until(
                'Oxygen',
                'Parameter \'env\' has been detected in the argument list.  This '
                'parameter is no longer used and has been replaced by \'saltenv\' '
                'as of Salt Carbon.  This warning will be removed in Salt Oxygen.'
                )
            kwargs.pop('env')
        if 'saltenv' in kwargs:
            saltenv = kwargs.pop('saltenv')

        if not isinstance(saltenv, six.string_types):
            saltenv = six.text_type(saltenv)

        for fsb in back:
            fstr = '{0}.find_file'.format(fsb)
            if fstr in self.servers:
                fnd = self.servers[fstr](path, saltenv, **kwargs)
                if fnd.get('path'):
                    fnd['back'] = fsb
                    return fnd
        return fnd

    def serve_file(self, load):
        '''
        Serve up a chunk of a file
        '''
        ret = {'data': '',
               'dest': ''}

        if 'env' in load:
            salt.utils.warn_until(
                'Oxygen',
                'Parameter \'env\' has been detected in the argument list.  This '
                'parameter is no longer used and has been replaced by \'saltenv\' '
                'as of Salt Carbon.  This warning will be removed in Salt Oxygen.'
                )
            load.pop('env')

        if 'path' not in load or 'loc' not in load or 'saltenv' not in load:
            return ret
        if not isinstance(load['saltenv'], six.string_types):
            load['saltenv'] = six.text_type(load['saltenv'])

        fnd = self.find_file(load['path'], load['saltenv'])
        if not fnd.get('back'):
            return ret
        fstr = '{0}.serve_file'.format(fnd['back'])
        if fstr in self.servers:
            return self.servers[fstr](load, fnd)
        return ret

    def file_hash(self, load):
        '''
        Return the hash of a given file
        '''
        if 'env' in load:
            salt.utils.warn_until(
                'Oxygen',
                'Parameter \'env\' has been detected in the argument list.  This '
                'parameter is no longer used and has been replaced by \'saltenv\' '
                'as of Salt Carbon.  This warning will be removed in Salt Oxygen.'
                )
            load.pop('env')

        if 'path' not in load or 'saltenv' not in load:
            return ''
        if not isinstance(load['saltenv'], six.string_types):
            load['saltenv'] = six.text_type(load['saltenv'])

        fnd = self.find_file(salt.utils.locales.sdecode(load['path']),
                load['saltenv'])
        if not fnd.get('back'):
            return ''
        fstr = '{0}.file_hash'.format(fnd['back'])
        if fstr in self.servers:
            return self.servers[fstr](load, fnd)
        return ''

    def file_list(self, load):
        '''
        Return a list of files from the dominant environment
        '''
        if 'env' in load:
            salt.utils.warn_until(
                'Oxygen',
                'Parameter \'env\' has been detected in the argument list.  This '
                'parameter is no longer used and has been replaced by \'saltenv\' '
                'as of Salt Carbon.  This warning will be removed in Salt Oxygen.'
                )
            load.pop('env')

        ret = set()
        if 'saltenv' not in load:
            return []
        if not isinstance(load['saltenv'], six.string_types):
            load['saltenv'] = six.text_type(load['saltenv'])

        for fsb in self._gen_back(load.pop('fsbackend', None)):
            fstr = '{0}.file_list'.format(fsb)
            if fstr in self.servers:
                ret.update(self.servers[fstr](load))
        # upgrade all set elements to a common encoding
        ret = [salt.utils.locales.sdecode(f) for f in ret]
        # some *fs do not handle prefix. Ensure it is filtered
        prefix = load.get('prefix', '').strip('/')
        if prefix != '':
            ret = [f for f in ret if f.startswith(prefix)]
        return sorted(ret)

    def file_list_emptydirs(self, load):
        '''
        List all emptydirs in the given environment
        '''
        if 'env' in load:
            salt.utils.warn_until(
                'Oxygen',
                'Parameter \'env\' has been detected in the argument list.  This '
                'parameter is no longer used and has been replaced by \'saltenv\' '
                'as of Salt Carbon.  This warning will be removed in Salt Oxygen.'
                )
            load.pop('env')

        ret = set()
        if 'saltenv' not in load:
            return []
        if not isinstance(load['saltenv'], six.string_types):
            load['saltenv'] = six.text_type(load['saltenv'])

        for fsb in self._gen_back(None):
            fstr = '{0}.file_list_emptydirs'.format(fsb)
            if fstr in self.servers:
                ret.update(self.servers[fstr](load))
        # upgrade all set elements to a common encoding
        ret = [salt.utils.locales.sdecode(f) for f in ret]
        # some *fs do not handle prefix. Ensure it is filtered
        prefix = load.get('prefix', '').strip('/')
        if prefix != '':
            ret = [f for f in ret if f.startswith(prefix)]
        return sorted(ret)

    def dir_list(self, load):
        '''
        List all directories in the given environment
        '''
        if 'env' in load:
            salt.utils.warn_until(
                'Oxygen',
                'Parameter \'env\' has been detected in the argument list.  This '
                'parameter is no longer used and has been replaced by \'saltenv\' '
                'as of Salt Carbon.  This warning will be removed in Salt Oxygen.'
                )
            load.pop('env')

        ret = set()
        if 'saltenv' not in load:
            return []
        if not isinstance(load['saltenv'], six.string_types):
            load['saltenv'] = six.text_type(load['saltenv'])

        for fsb in self._gen_back(load.pop('fsbackend', None)):
            fstr = '{0}.dir_list'.format(fsb)
            if fstr in self.servers:
                ret.update(self.servers[fstr](load))
        # upgrade all set elements to a common encoding
        ret = [salt.utils.locales.sdecode(f) for f in ret]
        # some *fs do not handle prefix. Ensure it is filtered
        prefix = load.get('prefix', '').strip('/')
        if prefix != '':
            ret = [f for f in ret if f.startswith(prefix)]
        return sorted(ret)

    def symlink_list(self, load):
        '''
        Return a list of symlinked files and dirs
        '''
        if 'env' in load:
            salt.utils.warn_until(
                'Oxygen',
                'Parameter \'env\' has been detected in the argument list.  This '
                'parameter is no longer used and has been replaced by \'saltenv\' '
                'as of Salt Carbon.  This warning will be removed in Salt Oxygen.'
                )
            load.pop('env')

        ret = {}
        if 'saltenv' not in load:
            return {}
        if not isinstance(load['saltenv'], six.string_types):
            load['saltenv'] = six.text_type(load['saltenv'])

        for fsb in self._gen_back(load.pop('fsbackend', None)):
            symlstr = '{0}.symlink_list'.format(fsb)
            if symlstr in self.servers:
                ret = self.servers[symlstr](load)
        # upgrade all set elements to a common encoding
        ret = dict([
            (salt.utils.locales.sdecode(x), salt.utils.locales.sdecode(y)) for x, y in ret.items()
        ])
        # some *fs do not handle prefix. Ensure it is filtered
        prefix = load.get('prefix', '').strip('/')
        if prefix != '':
            ret = dict([
                (x, y) for x, y in six.iteritems(ret) if x.startswith(prefix)
            ])
        return ret


class FSChan(object):
    '''
    A class that mimics the transport channels allowing for local access to
    to the fileserver class class structure
    '''
    def __init__(self, opts, **kwargs):
        self.opts = opts
        self.kwargs = kwargs
        self.fs = Fileserver(self.opts)
        self.fs.init()
        self.fs.update()
        self.cmd_stub = {'ext_nodes': {}}

    def send(self, load, tries=None, timeout=None, raw=False):  # pylint: disable=unused-argument
        '''
        Emulate the channel send method, the tries and timeout are not used
        '''
        if 'cmd' not in load:
            log.error('Malformed request, no cmd: {0}'.format(load))
            return {}
        cmd = load['cmd'].lstrip('_')
        if cmd in self.cmd_stub:
            return self.cmd_stub[cmd]
        if cmd == 'file_envs':
            return self.fs.envs()
        if not hasattr(self.fs, cmd):
            log.error('Malformed request, invalid cmd: {0}'.format(load))
            return {}
        return getattr(self.fs, cmd)(load)
