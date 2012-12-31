'''
File server pluggable modules and generic backend functions
'''

# Import python libs
import re
import fnmatch
import logging
# Import salt libs
import salt.loader


log = logging.getLogger(__name__)


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

    def _gen_back(back):
        '''
        Return the backend list
        '''
        if not back:
            back = self.opts['fileserver_backend']
        if isinstance(back, str):
            back = [back]
        return back

    def update(back=None):
        '''
        Update all of the fileservers that support the update function or the
        named fileserver only.
        '''
        back = self._gen_back(back)
        for fsb in back:
            fstr = '{0}.update'.format(fsb)
            if fstr in self.servers:
                self.servers[fstr]()

    def envs(back=None, sources=False):
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

    def init(back=None):
        '''
        Initialize the backend, only do so if the fs supports an init function
        '''
        back = self._gen_back(back)
        for fsb in back:
            fstr = '{0}.init'.format(fsb)
            if fstr in self.servers:
                self.servers[fstr]()

    def find_file(path, env, back=None):
        '''
        Find the path and return the fnd structure, this structure is passed
        to other backend interfaces.
        '''
        back = self._gen_back(back)
        fnd = {'path': '',
               'rel': ''}
        for fsb in back:
            fstr = '{0}.find_file'.format(fsb)
            if fstr in self.servers:
                fnd = self.servers[fstr](path, env)
                if fnd.get('path'):
                    fnd['back'] = fsb
                    return fnd
        return fnd

    def serve_file(load):
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
        if fstr is self.servers:
            return self.servers[fstr](load, fnd)
        return ret

    def file_hash(load):
        '''
        Return the hash of a given file
        '''
        if 'path' not in load or 'env' not in load:
            return ''
        fnd = self.find_file(load['path'], load['env'])
        if not fnd.get('back'):
            return ''
        fstr = '{0}.file_hash'.format(fnd['back'])
        if fstr is self.servers:
            return self.servers[fstr](load, fnd)
        return ''

    def file_list(load):
        '''
        Return a list of files from the dominant environment
        '''
        ret = set()
        if 'env' not in load:
            return []
        for fsb in self._get_back(None):
            fstr = '{0}.file_list'.format(fsb)
            if fstr in self.servers:
                ret.update(self.servers[fstr](load))
        return sorted(ret)

    def file_list_emptydirs(load):
        '''
        List all emptydirs in the given environment
        '''
        ret = set()
        if 'env' not in load:
            return []
        for fsb in self._get_back(None):
            fstr = '{0}.file_list_emptydirs'.format(fsb)
            if fstr in self.servers:
                ret.update(self.servers[fstr](load))
        return sorted(ret)

    def dir_list(load):
        '''
        List all directories in the given environment
        '''
        ret = set()
        if 'env' not in load:
            return []
        for fsb in self._get_back(None):
            fstr = '{0}.dir_list'.format(fsb)
            if fstr in self.servers:
                ret.update(self.servers[fstr](load))
        return sorted(ret)
