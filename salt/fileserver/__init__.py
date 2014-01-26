# -*- coding: utf-8 -*-
'''
File server pluggable modules and generic backend functions
'''

# Import python libs
import os
import re
import fnmatch
import logging
import time
import errno

# Import salt libs
import salt.loader
import salt.utils

log = logging.getLogger(__name__)


def _lock_cache(w_lock):
    try:
        os.mkdir(w_lock)
    except OSError, e:
        if e.errno != errno.EEXIST:
            raise
        return False
    else:
        log.trace('Lockfile {0} created'.format(w_lock))
        return True


def check_file_list_cache(opts, form, list_cache, w_lock):
    '''
    Checks the cache file to see if there is a new enough file list cache, and
    returns the match (if found, along with booleans used by the fileserver
    backend to determine if the cache needs to be refreshed/written).
    '''
    refresh_cache = False
    save_cache = True
    serial = salt.payload.Serial(opts)
    if not os.path.isfile(list_cache) and _lock_cache(w_lock):
        refresh_cache = True
    else:
        attempt = 0
        while attempt < 11:
            try:
                cache_stat = os.stat(list_cache)
                age = time.time() - cache_stat.st_mtime
                if age < opts.get('fileserver_list_cache_time', 30):
                    # Young enough! Load this sucker up!
                    with salt.utils.fopen(list_cache, 'r') as fp_:
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
    with salt.utils.fopen(list_cache, 'w+') as fp_:
        fp_.write(serial.dumps(data))
        try:
            os.rmdir(w_lock)
        except OSError, e:
            log.trace("Error removing lockfile {0}:  {1}".format(w_lock, e))
        log.trace('Lockfile {0} removed'.format(w_lock))


def check_env_cache(opts, env_cache):
    '''
    Returns cached env names, if present. Otherwise returns None.
    '''
    if not os.path.isfile(env_cache):
        return None
    try:
        with salt.utils.fopen(env_cache, 'r') as fp_:
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
    for saltenv, path_list in path_map.iteritems():
        for path in path_list:
            for directory, dirnames, filenames in os.walk(path):
                for item in filenames:
                    file_path = os.path.join(directory, item)
                    file_map[file_path] = os.path.getmtime(file_path)
    return file_map


def diff_mtime_map(map1, map2):
    '''
    Is there a change to the mtime map? return a boolean
    '''
    # check if the file lists are different
    if cmp(sorted(map1.keys()), sorted(map2.keys())) != 0:
        log.debug('diff_mtime_map: the keys are different')
        return True

    # check if the mtimes are the same
    if cmp(sorted(map1), sorted(map2)) != 0:
        log.debug('diff_mtime_map: the maps are different')
        return True

    # we made it, that means we have no changes
    log.debug('diff_mtime_map: the maps are the same')
    return False


def reap_fileserver_cache_dir(cache_base, find_func):
    '''
    Remove unused cache items assuming the cache directory follows a directory convention:

    cache_base -> saltenv -> relpath
    '''
    for saltenv in os.listdir(cache_base):
        env_base = os.path.join(cache_base, saltenv)
        for root, dirs, files in os.walk(env_base):
            # if we have an empty directory, lets cleanup
            # This will only remove the directory on the second time "_reap_cache" is called (which is intentional)
            if len(dirs) == 0 and len(files) == 0:
                os.rmdir(root)
                continue
            # if not, lets check the files in the directory
            for file_ in files:
                file_path = os.path.join(root, file_)
                file_rel_path = os.path.relpath(file_path, env_base)
                try:
                    filename, _, hash_type = file_rel_path.rsplit('.', 2)
                except ValueError:
                    log.warn('Found invalid hash file [{0}] when attempting to reap cache directory.'.format(file_))
                    continue
                # do we have the file?
                ret = find_func(filename, saltenv=saltenv)
                # if we don't actually have the file, lets clean up the cache object
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
        ret = []
        if not back:
            back = self.opts['fileserver_backend']
        if isinstance(back, str):
            back = [back]
        for sub in back:
            if '{0}.envs'.format(sub) in self.servers:
                ret.append(sub)
        return ret

    def update(self, back=None):
        '''
        Update all of the file-servers that support the update function or the
        named fileserver only.
        '''
        back = self._gen_back(back)
        for fsb in back:
            fstr = '{0}.update'.format(fsb)
            if fstr in self.servers:
                log.debug('Updating fileserver cache')
                self.servers[fstr]()

    def envs(self, back=None, sources=False):
        '''
        Return the environments for the named backend or all back-ends
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
        if path.startswith('|'):
            # The path arguments are escaped
            path = path[1:]
        else:
            if '?' in path:
                hcomps = path.split('?')
                path = hcomps[0]
                comps = hcomps[1].split('&')
                for comp in comps:
                    if not '=' in comp:
                        # Invalid option, skip it
                        continue
                    args = comp.split('=', 1)
                    kwargs[args[0]] = args[1]
        if 'env' in kwargs:
            salt.utils.warn_until(
                'Boron',
                'Passing a salt environment should be done using \'saltenv\' '
                'not \'env\'. This functionality will be removed in Salt '
                'Boron.'
            )
            saltenv = kwargs.pop('env')
        elif 'saltenv' in kwargs:
            saltenv = kwargs.pop('saltenv')
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
                'Boron',
                'Passing a salt environment should be done using \'saltenv\' '
                'not \'env\'. This functionality will be removed in Salt '
                'Boron.'
            )
            load['saltenv'] = load.pop('env')

        if 'path' not in load or 'loc' not in load or 'saltenv' not in load:
            return ret
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
                'Boron',
                'Passing a salt environment should be done using \'saltenv\' '
                'not \'env\'. This functionality will be removed in Salt '
                'Boron.'
            )
            load['saltenv'] = load.pop('env')

        if 'path' not in load or 'saltenv' not in load:
            return ''
        fnd = self.find_file(load['path'], load['saltenv'])
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
                'Boron',
                'Passing a salt environment should be done using \'saltenv\' '
                'not \'env\'. This functionality will be removed in Salt '
                'Boron.'
            )
            load['saltenv'] = load.pop('env')

        ret = set()
        if 'saltenv' not in load:
            return []
        for fsb in self._gen_back(None):
            fstr = '{0}.file_list'.format(fsb)
            if fstr in self.servers:
                ret.update(self.servers[fstr](load))
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
                'Boron',
                'Passing a salt environment should be done using \'saltenv\' '
                'not \'env\'. This functionality will be removed in Salt '
                'Boron.'
            )
            load['saltenv'] = load.pop('env')

        ret = set()
        if 'saltenv' not in load:
            return []
        for fsb in self._gen_back(None):
            fstr = '{0}.file_list_emptydirs'.format(fsb)
            if fstr in self.servers:
                ret.update(self.servers[fstr](load))
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
                'Boron',
                'Passing a salt environment should be done using \'saltenv\' '
                'not \'env\'. This functionality will be removed in Salt '
                'Boron.'
            )
            load['saltenv'] = load.pop('env')

        ret = set()
        if 'saltenv' not in load:
            return []
        for fsb in self._gen_back(None):
            fstr = '{0}.dir_list'.format(fsb)
            if fstr in self.servers:
                ret.update(self.servers[fstr](load))
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
                'Boron',
                'Passing a salt environment should be done using \'saltenv\' '
                'not \'env\'. This functionality will be removed in Salt '
                'Boron.'
            )
            load['saltenv'] = load.pop('env')

        ret = {}
        if 'saltenv' not in load:
            return {}
        for fsb in self._gen_back(None):
            symlstr = '{0}.symlink_list'.format(fsb)
            if symlstr in self.servers:
                ret = self.servers[symlstr](load)
        # some *fs do not handle prefix. Ensure it is filtered
        prefix = load.get('prefix', '').strip('/')
        if prefix != '':
            ret = [f for f in ret if f.startswith(prefix)]
        return ret
