# -*- coding: utf-8 -*-
'''
File server pluggable modules and generic backend functions
'''

# Import python libs
import os
import re
import fnmatch
import logging

# Import salt libs
import salt.loader

log = logging.getLogger(__name__)


def generate_mtime_map(path_map):
    '''
    Generate a dict of filename -> mtime
    '''
    file_map = {}
    for env, path_list in path_map.iteritems():
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

    cache_base -> env -> relpath
    '''
    for env in os.listdir(cache_base):
        env_base = os.path.join(cache_base, env)
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
                ret = find_func(filename, env=env)
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

    def find_file(self, path, env, back=None):
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
            env = kwargs.pop('env')
        for fsb in back:
            fstr = '{0}.find_file'.format(fsb)
            if fstr in self.servers:
                fnd = self.servers[fstr](path, env, **kwargs)
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
        if 'path' not in load or 'loc' not in load or 'env' not in load:
            return ret
        fnd = self.find_file(load['path'], load['env'])
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
        if 'path' not in load or 'env' not in load:
            return ''
        fnd = self.find_file(load['path'], load['env'])
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
        ret = set()
        if 'env' not in load:
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
        ret = set()
        if 'env' not in load:
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
        ret = set()
        if 'env' not in load:
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
        ret = {}
        if 'env' not in load:
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
