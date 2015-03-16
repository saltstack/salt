# -*- coding: utf-8 -*-
'''
Classes that manage file clients
'''

# Import python libs
import contextlib
import logging
import hashlib
import os
import shutil
import requests

# Import salt libs
from salt.exceptions import (
    CommandExecutionError, MinionError, SaltReqTimeoutError
)
import salt.client
import salt.crypt
import salt.loader
import salt.payload
import salt.transport
import salt.fileserver
import salt.utils
import salt.utils.templates
import salt.utils.gzip_util
from salt._compat import (
    URLError, HTTPError, BaseHTTPServer, urlparse, urlunparse)
from salt.utils.openstack.swift import SaltSwift

log = logging.getLogger(__name__)


def get_file_client(opts, pillar=False):
    '''
    Read in the ``file_client`` option and return the correct type of file
    server
    '''
    client = opts.get('file_client', 'remote')
    if pillar and client == 'local':
        client = 'pillar'
    return {
        'remote': RemoteClient,
        'local': FSClient,
        'pillar': LocalClient,
    }.get(client, RemoteClient)(opts)


class Client(object):
    '''
    Base class for Salt file interactions
    '''
    def __init__(self, opts):
        self.opts = opts
        self.serial = salt.payload.Serial(self.opts)

    def _check_proto(self, path):
        '''
        Make sure that this path is intended for the salt master and trim it
        '''
        if not path.startswith('salt://'):
            raise MinionError('Unsupported path: {0}'.format(path))
        return path[7:]

    def _file_local_list(self, dest):
        '''
        Helper util to return a list of files in a directory
        '''
        if os.path.isdir(dest):
            destdir = dest
        else:
            destdir = os.path.dirname(dest)

        filelist = set()

        for root, dirs, files in os.walk(destdir, followlinks=True):
            for name in files:
                path = os.path.join(root, name)
                filelist.add(path)

        return filelist

    @contextlib.contextmanager
    def _cache_loc(self, path, saltenv='base', env=None):
        '''
        Return the local location to cache the file, cache dirs will be made
        '''
        if env is not None:
            salt.utils.warn_until(
                'Boron',
                'Passing a salt environment should be done using \'saltenv\' '
                'not \'env\'. This functionality will be removed in Salt '
                'Boron.'
            )
            # Backwards compatibility
            saltenv = env

        dest = os.path.join(self.opts['cachedir'],
                            'files',
                            saltenv,
                            path)
        destdir = os.path.dirname(dest)
        cumask = os.umask(63)
        if not os.path.isdir(destdir):
            # remove destdir if it is a regular file to avoid an OSError when
            # running os.makedirs below
            if os.path.isfile(destdir):
                os.remove(destdir)
            os.makedirs(destdir)
        yield dest
        os.umask(cumask)

    def get_file(self,
                 path,
                 dest='',
                 makedirs=False,
                 saltenv='base',
                 gzip=None,
                 env=None):
        '''
        Copies a file from the local files or master depending on
        implementation
        '''
        raise NotImplementedError

    def file_list_emptydirs(self, saltenv='base', prefix='', env=None):
        '''
        List the empty dirs
        '''
        raise NotImplementedError

    def cache_file(self, path, saltenv='base', env=None):
        '''
        Pull a file down from the file server and store it in the minion
        file cache
        '''
        if env is not None:
            salt.utils.warn_until(
                'Boron',
                'Passing a salt environment should be done using \'saltenv\' '
                'not \'env\'. This functionality will be removed in Salt '
                'Boron.'
            )
            # Backwards compatibility
            saltenv = env

        return self.get_url(path, '', True, saltenv)

    def cache_files(self, paths, saltenv='base', env=None):
        '''
        Download a list of files stored on the master and put them in the
        minion file cache
        '''
        if env is not None:
            salt.utils.warn_until(
                'Boron',
                'Passing a salt environment should be done using \'saltenv\' '
                'not \'env\'. This functionality will be removed in Salt '
                'Boron.'
            )
            # Backwards compatibility
            saltenv = env

        ret = []
        if isinstance(paths, str):
            paths = paths.split(',')
        for path in paths:
            ret.append(self.cache_file(path, saltenv))
        return ret

    def cache_master(self, saltenv='base', env=None):
        '''
        Download and cache all files on a master in a specified environment
        '''
        if env is not None:
            salt.utils.warn_until(
                'Boron',
                'Passing a salt environment should be done using \'saltenv\' '
                'not \'env\'. This functionality will be removed in Salt '
                'Boron.'
            )
            # Backwards compatibility
            saltenv = env

        ret = []
        for path in self.file_list(saltenv):
            ret.append(self.cache_file('salt://{0}'.format(path), saltenv))
        return ret

    def cache_dir(self, path, saltenv='base', include_empty=False,
                  include_pat=None, exclude_pat=None, env=None):
        '''
        Download all of the files in a subdir of the master
        '''
        if env is not None:
            salt.utils.warn_until(
                'Boron',
                'Passing a salt environment should be done using \'saltenv\' '
                'not \'env\'. This functionality will be removed in Salt '
                'Boron.'
            )
            # Backwards compatibility
            saltenv = env

        ret = []

        path = self._check_proto(path)
        # We want to make sure files start with this *directory*, use
        # '/' explicitly because the master (that's generating the
        # list of files) only runs on POSIX
        if not path.endswith('/'):
            path = path + '/'

        log.info(
            'Caching directory {0!r} for environment {1!r}'.format(
                path, saltenv
            )
        )
        # go through the list of all files finding ones that are in
        # the target directory and caching them
        for fn_ in self.file_list(saltenv):
            if fn_.strip() and fn_.startswith(path):
                if salt.utils.check_include_exclude(
                        fn_, include_pat, exclude_pat):
                    fn_ = self.cache_file('salt://' + fn_, saltenv)
                    if fn_:
                        ret.append(fn_)

        if include_empty:
            # Break up the path into a list containing the bottom-level
            # directory (the one being recursively copied) and the directories
            # preceding it
            # separated = string.rsplit(path, '/', 1)
            # if len(separated) != 2:
            #     # No slashes in path. (So all files in saltenv will be copied)
            #     prefix = ''
            # else:
            #     prefix = separated[0]
            dest = salt.utils.path_join(
                self.opts['cachedir'],
                'files',
                saltenv
            )
            for fn_ in self.file_list_emptydirs(saltenv):
                if fn_.startswith(path):
                    minion_dir = '{0}/{1}'.format(dest, fn_)
                    if not os.path.isdir(minion_dir):
                        os.makedirs(minion_dir)
                    ret.append(minion_dir)
        return ret

    def cache_local_file(self, path, **kwargs):
        '''
        Cache a local file on the minion in the localfiles cache
        '''
        dest = os.path.join(self.opts['cachedir'], 'localfiles',
                            path.lstrip('/'))
        destdir = os.path.dirname(dest)

        if not os.path.isdir(destdir):
            os.makedirs(destdir)

        shutil.copyfile(path, dest)
        return dest

    def file_local_list(self, saltenv='base', env=None):
        '''
        List files in the local minion files and localfiles caches
        '''
        if env is not None:
            salt.utils.warn_until(
                'Boron',
                'Passing a salt environment should be done using \'saltenv\' '
                'not \'env\'. This functionality will be removed in Salt '
                'Boron.'
            )
            # Backwards compatibility
            saltenv = env

        filesdest = os.path.join(self.opts['cachedir'], 'files', saltenv)
        localfilesdest = os.path.join(self.opts['cachedir'], 'localfiles')

        fdest = self._file_local_list(filesdest)
        ldest = self._file_local_list(localfilesdest)
        return sorted(fdest.union(ldest))

    def file_list(self, saltenv='base', prefix='', env=None):
        '''
        This function must be overwritten
        '''
        if env is not None:
            salt.utils.warn_until(
                'Boron',
                'Passing a salt environment should be done using \'saltenv\' '
                'not \'env\'. This functionality will be removed in Salt '
                'Boron.'
            )
            # Backwards compatibility
            saltenv = env

        return []

    def dir_list(self, saltenv='base', prefix='', env=None):
        '''
        This function must be overwritten
        '''
        if env is not None:
            salt.utils.warn_until(
                'Boron',
                'Passing a salt environment should be done using \'saltenv\' '
                'not \'env\'. This functionality will be removed in Salt '
                'Boron.'
            )
            # Backwards compatibility
            saltenv = env

        return []

    def symlink_list(self, saltenv='base', prefix='', env=None):
        '''
        This function must be overwritten
        '''
        if env is not None:
            salt.utils.warn_until(
                'Boron',
                'Passing a salt environment should be done using \'saltenv\' '
                'not \'env\'. This functionality will be removed in Salt '
                'Boron.'
            )
            # Backwards compatibility
            saltenv = env

        return {}

    def is_cached(self, path, saltenv='base', env=None):
        '''
        Returns the full path to a file if it is cached locally on the minion
        otherwise returns a blank string
        '''
        if env is not None:
            salt.utils.warn_until(
                'Boron',
                'Passing a salt environment should be done using \'saltenv\' '
                'not \'env\'. This functionality will be removed in Salt '
                'Boron.'
            )
            # Backwards compatibility
            saltenv = env

        localsfilesdest = os.path.join(
            self.opts['cachedir'], 'localfiles', path.lstrip('/'))
        filesdest = os.path.join(
            self.opts['cachedir'], 'files', saltenv, path.lstrip('salt://'))

        if os.path.exists(filesdest):
            return filesdest
        elif os.path.exists(localsfilesdest):
            return localsfilesdest

        return ''

    def list_states(self, saltenv):
        '''
        Return a list of all available sls modules on the master for a given
        environment
        '''

        limit_traversal = self.opts.get('fileserver_limit_traversal', False)
        states = []

        if limit_traversal:
            if saltenv not in self.opts['file_roots']:
                log.warning(
                    'During an attempt to list states for saltenv {0!r}, '
                    'the environment could not be found in the configured '
                    'file roots'.format(saltenv)
                )
                return states
            for path in self.opts['file_roots'][saltenv]:
                for root, dirs, files in os.walk(path, topdown=True):
                    log.debug('Searching for states in dirs {0} and files '
                              '{1}'.format(dirs, files))
                    if not [filename.endswith('.sls') for filename in files]:
                        #  Use shallow copy so we don't disturb the memory used by os.walk. Otherwise this breaks!
                        del dirs[:]
                    else:
                        for found_file in files:
                            stripped_root = os.path.relpath(root, path).replace('/', '.')
                            if salt.utils.is_windows():
                                stripped_root = stripped_root.replace('\\', '/')
                            if found_file.endswith(('.sls')):
                                if found_file.endswith('init.sls'):
                                    if stripped_root.endswith('.'):
                                        stripped_root = stripped_root.rstrip('.')
                                    states.append(stripped_root)
                                else:
                                    if not stripped_root.endswith('.'):
                                        stripped_root += '.'
                                    if stripped_root.startswith('.'):
                                        stripped_root = stripped_root.lstrip('.')
                                    states.append(stripped_root + found_file[:-4])
        else:
            for path in self.file_list(saltenv):
                if salt.utils.is_windows():
                    path = path.replace('\\', '/')
                if path.endswith('.sls'):
                    # is an sls module!
                    if path.endswith('{0}init.sls'.format('/')):
                        states.append(path.replace('/', '.')[:-9])
                    else:
                        states.append(path.replace('/', '.')[:-4])
        return states

    def get_state(self, sls, saltenv):
        '''
        Get a state file from the master and store it in the local minion
        cache return the location of the file
        '''
        if '.' in sls:
            sls = sls.replace('.', '/')
        for path in ['salt://{0}.sls'.format(sls),
                     '/'.join(['salt:/', sls, 'init.sls'])]:
            dest = self.cache_file(path, saltenv)
            if dest:
                return {'source': path, 'dest': dest}
        return {}

    def get_dir(self, path, dest='', saltenv='base', gzip=None, env=None):
        '''
        Get a directory recursively from the salt-master
        '''
        if env is not None:
            salt.utils.warn_until(
                'Boron',
                'Passing a salt environment should be done using \'saltenv\' '
                'not \'env\'. This functionality will be removed in Salt '
                'Boron.'
            )
            # Backwards compatibility
            saltenv = env

        ret = []
        # Strip trailing slash
        path = self._check_proto(path).rstrip('/')
        # Break up the path into a list containing the bottom-level directory
        # (the one being recursively copied) and the directories preceding it
        separated = path.rsplit('/', 1)
        if len(separated) != 2:
            # No slashes in path. (This means all files in env will be copied)
            prefix = ''
        else:
            prefix = separated[0]

        # Copy files from master
        for fn_ in self.file_list(saltenv):
            if fn_.startswith(path):
                # Prevent files in "salt://foobar/" (or salt://foo.sh) from
                # matching a path of "salt://foo"
                try:
                    if fn_[len(path)] != '/':
                        continue
                except IndexError:
                    continue
                # Remove the leading directories from path to derive
                # the relative path on the minion.
                minion_relpath = fn_[len(prefix):].lstrip('/')
                ret.append(
                    self.get_file(
                        'salt://{0}'.format(fn_),
                        '{0}/{1}'.format(dest, minion_relpath),
                        True, saltenv, gzip
                    )
                )
        # Replicate empty dirs from master
        try:
            for fn_ in self.file_list_emptydirs(saltenv):
                if fn_.startswith(path):
                    # Prevent an empty dir "salt://foobar/" from matching a path of
                    # "salt://foo"
                    try:
                        if fn_[len(path)] != '/':
                            continue
                    except IndexError:
                        continue
                    # Remove the leading directories from path to derive
                    # the relative path on the minion.
                    minion_relpath = fn_[len(prefix):].lstrip('/')
                    minion_mkdir = '{0}/{1}'.format(dest, minion_relpath)
                    if not os.path.isdir(minion_mkdir):
                        os.makedirs(minion_mkdir)
                    ret.append(minion_mkdir)
        except TypeError:
            pass
        ret.sort()
        return ret

    def get_url(self, url, dest, makedirs=False, saltenv='base', env=None):
        '''
        Get a single file from a URL.
        '''
        if env is not None:
            salt.utils.warn_until(
                'Boron',
                'Passing a salt environment should be done using \'saltenv\' '
                'not \'env\'. This functionality will be removed in Salt '
                'Boron.'
            )
            # Backwards compatibility
            saltenv = env

        url_data = urlparse(url)

        if url_data.scheme in ('file', ''):
            # Local filesystem
            if not os.path.isabs(url_data.path):
                raise CommandExecutionError(
                    'Path {0!r} is not absolute'.format(url_data.path)
                )
            return url_data.path

        if url_data.scheme == 'salt':
            return self.get_file(url, dest, makedirs, saltenv)
        if dest:
            destdir = os.path.dirname(dest)
            if not os.path.isdir(destdir):
                if makedirs:
                    os.makedirs(destdir)
                else:
                    return ''
        else:
            if salt.utils.is_windows():
                netloc = salt.utils.sanitize_win_path_string(url_data.netloc)
            else:
                netloc = url_data.netloc
            dest = salt.utils.path_join(
                self.opts['cachedir'],
                'extrn_files',
                saltenv,
                netloc,
                url_data.path
            )
            destdir = os.path.dirname(dest)
            if not os.path.isdir(destdir):
                os.makedirs(destdir)

        if url_data.scheme == 's3':
            try:
                salt.utils.s3.query(method='GET',
                                    bucket=url_data.netloc,
                                    path=url_data.path[1:],
                                    return_bin=False,
                                    local_file=dest,
                                    action=None,
                                    key=self.opts.get('s3.key', None),
                                    keyid=self.opts.get('s3.keyid', None),
                                    service_url=self.opts.get('s3.service_url',
                                                              None),
                                    verify_ssl=self.opts.get('s3.verify_ssl',
                                                              True))
                return dest
            except Exception:
                raise MinionError('Could not fetch from {0}'.format(url))

        if url_data.scheme == 'swift':
            try:
                swift_conn = SaltSwift(self.opts.get('keystone.user', None),
                                             self.opts.get('keystone.tenant', None),
                                             self.opts.get('keystone.auth_url', None),
                                             self.opts.get('keystone.password', None))
                swift_conn.get_object(url_data.netloc,
                                      url_data.path[1:],
                                      dest)
                return dest
            except Exception:
                raise MinionError('Could not fetch from {0}'.format(url))

        get_kwargs = {}
        if url_data.username is not None \
                and url_data.scheme in ('http', 'https'):
            _, netloc = url_data.netloc.split('@', 1)
            fixed_url = urlunparse(
                (url_data.scheme, netloc, url_data.path,
                 url_data.params, url_data.query, url_data.fragment))
            get_kwargs['auth'] = (url_data.username, url_data.password)
        else:
            fixed_url = url
        try:
            if requests.__version__[0] == '0':
                # 'stream' was called 'prefetch' before 1.0, with flipped meaning
                get_kwargs['prefetch'] = False
            else:
                get_kwargs['stream'] = True
            response = requests.get(fixed_url, **get_kwargs)
            response.raise_for_status()
            with salt.utils.fopen(dest, 'wb') as destfp:
                for chunk in response.iter_content(chunk_size=32*1024):
                    destfp.write(chunk)
            return dest
        except HTTPError as exc:
            raise MinionError('HTTP error {0} reading {1}: {3}'.format(
                exc.code,
                url,
                *BaseHTTPServer.BaseHTTPRequestHandler.responses[exc.code]))
        except URLError as exc:
            raise MinionError('Error reading {0}: {1}'.format(url, exc.reason))

    def get_template(
            self,
            url,
            dest,
            template='jinja',
            makedirs=False,
            saltenv='base',
            env=None,
            **kwargs):
        '''
        Cache a file then process it as a template
        '''
        if env is not None:
            salt.utils.warn_until(
                'Boron',
                'Passing a salt environment should be done using \'saltenv\' '
                'not \'env\'. This functionality will be removed in Salt '
                'Boron.'
            )
            # Backwards compatibility
            saltenv = env

        kwargs['saltenv'] = saltenv
        url_data = urlparse(url)
        sfn = self.cache_file(url, saltenv)
        if not os.path.exists(sfn):
            return ''
        if template in salt.utils.templates.TEMPLATE_REGISTRY:
            data = salt.utils.templates.TEMPLATE_REGISTRY[template](
                sfn,
                **kwargs
            )
        else:
            log.error('Attempted to render template with unavailable engine '
                      '{0}'.format(template))
            return ''
        if not data['result']:
            # Failed to render the template
            log.error(
                'Failed to render template with error: {0}'.format(
                    data['data']
                )
            )
            return ''
        if not dest:
            # No destination passed, set the dest as an extrn_files cache
            dest = salt.utils.path_join(
                self.opts['cachedir'],
                'extrn_files',
                saltenv,
                url_data.netloc,
                url_data.path
            )
            # If Salt generated the dest name, create any required dirs
            makedirs = True

        destdir = os.path.dirname(dest)
        if not os.path.isdir(destdir):
            if makedirs:
                os.makedirs(destdir)
            else:
                salt.utils.safe_rm(data['data'])
                return ''
        shutil.move(data['data'], dest)
        return dest


class LocalClient(Client):
    '''
    Use the local_roots option to parse a local file root
    '''
    def __init__(self, opts):
        Client.__init__(self, opts)

    def _find_file(self, path, saltenv='base'):
        '''
        Locate the file path
        '''
        fnd = {'path': '',
               'rel': ''}

        if saltenv not in self.opts['file_roots']:
            return fnd
        if path.startswith('|'):
            # The path arguments are escaped
            path = path[1:]
        for root in self.opts['file_roots'][saltenv]:
            full = os.path.join(root, path)
            if os.path.isfile(full):
                fnd['path'] = full
                fnd['rel'] = path
                return fnd
        return fnd

    def get_file(self,
                 path,
                 dest='',
                 makedirs=False,
                 saltenv='base',
                 gzip=None,
                 env=None):
        '''
        Copies a file from the local files directory into :param:`dest`
        gzip compression settings are ignored for local files
        '''
        if env is not None:
            salt.utils.warn_until(
                'Boron',
                'Passing a salt environment should be done using \'saltenv\' '
                'not \'env\'. This functionality will be removed in Salt '
                'Boron.'
            )
            # Backwards compatibility
            saltenv = env

        path = self._check_proto(path)
        fnd = self._find_file(path, saltenv)
        if not fnd['path']:
            return ''
        return fnd['path']

    def file_list(self, saltenv='base', prefix='', env=None):
        '''
        Return a list of files in the given environment
        with optional relative prefix path to limit directory traversal
        '''
        if env is not None:
            salt.utils.warn_until(
                'Boron',
                'Passing a salt environment should be done using \'saltenv\' '
                'not \'env\'. This functionality will be removed in Salt '
                'Boron.'
            )
            # Backwards compatibility
            saltenv = env

        ret = []
        if saltenv not in self.opts['file_roots']:
            return ret
        prefix = prefix.strip('/')
        for path in self.opts['file_roots'][saltenv]:
            for root, dirs, files in os.walk(
                os.path.join(path, prefix), followlinks=True
            ):
                for fname in files:
                    ret.append(
                        os.path.relpath(
                            os.path.join(root, fname),
                            path
                        )
                    )
        return ret

    def file_list_emptydirs(self, saltenv='base', prefix='', env=None):
        '''
        List the empty dirs in the file_roots
        with optional relative prefix path to limit directory traversal
        '''
        if env is not None:
            salt.utils.warn_until(
                'Boron',
                'Passing a salt environment should be done using \'saltenv\' '
                'not \'env\'. This functionality will be removed in Salt '
                'Boron.'
            )
            # Backwards compatibility
            saltenv = env

        ret = []
        prefix = prefix.strip('/')
        if saltenv not in self.opts['file_roots']:
            return ret
        for path in self.opts['file_roots'][saltenv]:
            for root, dirs, files in os.walk(
                os.path.join(path, prefix), followlinks=True
            ):
                if len(dirs) == 0 and len(files) == 0:
                    ret.append(os.path.relpath(root, path))
        return ret

    def dir_list(self, saltenv='base', prefix='', env=None):
        '''
        List the dirs in the file_roots
        with optional relative prefix path to limit directory traversal
        '''
        if env is not None:
            salt.utils.warn_until(
                'Boron',
                'Passing a salt environment should be done using \'saltenv\' '
                'not \'env\'. This functionality will be removed in Salt '
                'Boron.'
            )
            # Backwards compatibility
            saltenv = env

        ret = []
        if saltenv not in self.opts['file_roots']:
            return ret
        prefix = prefix.strip('/')
        for path in self.opts['file_roots'][saltenv]:
            for root, dirs, files in os.walk(
                os.path.join(path, prefix), followlinks=True
            ):
                ret.append(os.path.relpath(root, path))
        return ret

    def hash_file(self, path, saltenv='base', env=None):
        '''
        Return the hash of a file, to get the hash of a file in the file_roots
        prepend the path with salt://<file on server> otherwise, prepend the
        file with / for a local file.
        '''
        if env is not None:
            salt.utils.warn_until(
                'Boron',
                'Passing a salt environment should be done using \'saltenv\' '
                'not \'env\'. This functionality will be removed in Salt '
                'Boron.'
            )
            # Backwards compatibility
            saltenv = env

        ret = {}
        try:
            path = self._check_proto(path)
        except MinionError:
            if not os.path.isfile(path):
                err = 'Specified file {0} is not present to generate hash'
                log.warning(err.format(path))
                return ret
            else:
                opts_hash_type = self.opts.get('hash_type', 'md5')
                hash_type = getattr(hashlib, opts_hash_type)
                ret['hsum'] = salt.utils.get_hash(
                    path, form=hash_type)
                ret['hash_type'] = opts_hash_type
                return ret
        path = self._find_file(path, saltenv)['path']
        if not path:
            return {}
        ret = {}
        ret['hsum'] = salt.utils.get_hash(path, self.opts['hash_type'])
        ret['hash_type'] = self.opts['hash_type']
        return ret

    def list_env(self, saltenv='base', env=None):
        '''
        Return a list of the files in the file server's specified environment
        '''
        if env is not None:
            salt.utils.warn_until(
                'Boron',
                'Passing a salt environment should be done using \'saltenv\' '
                'not \'env\'. This functionality will be removed in Salt '
                'Boron.'
            )
            # Backwards compatibility
            saltenv = env

        return self.file_list(saltenv)

    def master_opts(self):
        '''
        Return the master opts data
        '''
        return self.opts

    def envs(self):
        '''
        Return the available environments
        '''
        ret = []
        for saltenv in self.opts['file_roots']:
            ret.append(saltenv)
        return ret

    def ext_nodes(self):
        '''
        Originally returned information via the external_nodes subsystem.
        External_nodes was deprecated and removed in
        2014.1.6 in favor of master_tops (which had been around since pre-0.17).
             salt-call --local state.show_top
        ends up here, but master_tops has not been extended to support
        show_top in a completely local environment yet.  It's worth noting
        that originally this fn started with
            if 'external_nodes' not in opts: return {}
        So since external_nodes is gone now, we are just returning the
        empty dict.
        '''
        return {}


class RemoteClient(Client):
    '''
    Interact with the salt master file server.
    '''
    def __init__(self, opts):
        Client.__init__(self, opts)
        self.channel = salt.transport.Channel.factory(self.opts)
        if hasattr(self.channel, 'auth'):
            self.auth = self.channel.auth
        else:
            self.auth = ''

    def _get_channel(self):
        '''
        Return the right channel
        '''
        if self.auth:
            return self.channel
        return salt.transport.Channel.factory(self.opts)

    def get_file(self,
                 path,
                 dest='',
                 makedirs=False,
                 saltenv='base',
                 gzip=None,
                 env=None):
        '''
        Get a single file from the salt-master
        path must be a salt server location, aka, salt://path/to/file, if
        dest is omitted, then the downloaded file will be placed in the minion
        cache
        '''
        if env is not None:
            salt.utils.warn_until(
                'Boron',
                'Passing a salt environment should be done using \'saltenv\' '
                'not \'env\'. This functionality will be removed in Salt '
                'Boron.'
            )
            # Backwards compatibility
            saltenv = env

        # Hash compare local copy with master and skip download
        # if no diference found.
        dest2check = dest
        if not dest2check:
            rel_path = self._check_proto(path)
            with self._cache_loc(rel_path, saltenv) as cache_dest:
                dest2check = cache_dest

        if dest2check and os.path.isfile(dest2check):
            hash_local = self.hash_file(dest2check, saltenv)
            hash_server = self.hash_file(path, saltenv)
            if hash_local == hash_server:
                log.info(
                    'Fetching file from saltenv {0!r}, ** skipped ** '
                    'latest already in cache {1!r}'.format(
                        saltenv, path
                    )
                )
                return dest2check

        log.debug(
            'Fetching file from saltenv {0!r}, ** attempting ** {1!r}'.format(
                saltenv, path
            )
        )
        d_tries = 0
        path = self._check_proto(path)
        load = {'path': path,
                'saltenv': saltenv,
                'cmd': '_serve_file'}
        if gzip:
            gzip = int(gzip)
            load['gzip'] = gzip

        fn_ = None
        if dest:
            destdir = os.path.dirname(dest)
            if not os.path.isdir(destdir):
                if makedirs:
                    os.makedirs(destdir)
                else:
                    return False
            fn_ = salt.utils.fopen(dest, 'wb+')
        while True:
            if not fn_:
                load['loc'] = 0
            else:
                load['loc'] = fn_.tell()
            data = self.channel.send(load)
            if 'data' not in data:
                log.error('Data is {0}'.format(data))
            if not data['data']:
                if not fn_ and data['dest']:
                    # This is a 0 byte file on the master
                    with self._cache_loc(data['dest'], saltenv) as cache_dest:
                        dest = cache_dest
                        with salt.utils.fopen(cache_dest, 'wb+') as ofile:
                            ofile.write(data['data'])
                if 'hsum' in data and d_tries < 3:
                    # Master has prompted a file verification, if the
                    # verification fails, re-download the file. Try 3 times
                    d_tries += 1
                    hsum = salt.utils.get_hash(dest, data.get('hash_type', 'md5'))
                    if hsum != data['hsum']:
                        log.warn('Bad download of file {0}, attempt {1} '
                                 'of 3'.format(path, d_tries))
                        continue
                break
            if not fn_:
                with self._cache_loc(data['dest'], saltenv) as cache_dest:
                    dest = cache_dest
                    # If a directory was formerly cached at this path, then
                    # remove it to avoid a traceback trying to write the file
                    if os.path.isdir(dest):
                        salt.utils.rm_rf(dest)
                    fn_ = salt.utils.fopen(dest, 'wb+')
            if data.get('gzip', None):
                data = salt.utils.gzip_util.uncompress(data['data'])
            else:
                data = data['data']
            fn_.write(data)
        if fn_:
            fn_.close()
            log.info(
                'Fetching file from saltenv {0!r}, ** done ** {1!r}'.format(
                    saltenv, path
                )
            )
        return dest

    def file_list(self, saltenv='base', prefix='', env=None):
        '''
        List the files on the master
        '''
        if env is not None:
            salt.utils.warn_until(
                'Boron',
                'Passing a salt environment should be done using \'saltenv\' '
                'not \'env\'. This functionality will be removed in Salt '
                'Boron.'
            )
            # Backwards compatibility
            saltenv = env

        load = {'saltenv': saltenv,
                'prefix': prefix,
                'cmd': '_file_list'}
        try:
            channel = self._get_channel()
            return channel.send(load)
        except SaltReqTimeoutError:
            return ''

    def file_list_emptydirs(self, saltenv='base', prefix='', env=None):
        '''
        List the empty dirs on the master
        '''
        if env is not None:
            salt.utils.warn_until(
                'Boron',
                'Passing a salt environment should be done using \'saltenv\' '
                'not \'env\'. This functionality will be removed in Salt '
                'Boron.'
            )
            # Backwards compatibility
            saltenv = env

        load = {'saltenv': saltenv,
                'prefix': prefix,
                'cmd': '_file_list_emptydirs'}
        try:
            channel = self._get_channel()
            channel.send(load)
        except SaltReqTimeoutError:
            return ''

    def dir_list(self, saltenv='base', prefix='', env=None):
        '''
        List the dirs on the master
        '''
        if env is not None:
            salt.utils.warn_until(
                'Boron',
                'Passing a salt environment should be done using \'saltenv\' '
                'not \'env\'. This functionality will be removed in Salt '
                'Boron.'
            )
            # Backwards compatibility
            saltenv = env

        load = {'saltenv': saltenv,
                'prefix': prefix,
                'cmd': '_dir_list'}
        try:
            channel = self._get_channel()
            return channel.send(load)
        except SaltReqTimeoutError:
            return ''

    def symlink_list(self, saltenv='base', prefix='', env=None):
        '''
        List symlinked files and dirs on the master
        '''
        load = {'saltenv': saltenv,
                'prefix': prefix,
                'cmd': '_symlink_list'}
        try:
            channel = self._get_channel()
            return channel.send(load)
        except SaltReqTimeoutError:
            return ''

    def hash_file(self, path, saltenv='base', env=None):
        '''
        Return the hash of a file, to get the hash of a file on the salt
        master file server prepend the path with salt://<file on server>
        otherwise, prepend the file with / for a local file.
        '''
        if env is not None:
            salt.utils.warn_until(
                'Boron',
                'Passing a salt environment should be done using \'saltenv\' '
                'not \'env\'. This functionality will be removed in Salt '
                'Boron.'
            )
            # Backwards compatibility
            saltenv = env

        try:
            path = self._check_proto(path)
        except MinionError:
            if not os.path.isfile(path):
                err = 'Specified file {0} is not present to generate hash'
                log.warning(err.format(path))
                return {}
            else:
                ret = {}
                hash_type = self.opts.get('hash_type', 'md5')
                ret['hsum'] = salt.utils.get_hash(
                    path, form=hash_type, chunk_size=4096)
                ret['hash_type'] = hash_type
                return ret
        load = {'path': path,
                'saltenv': saltenv,
                'cmd': '_file_hash'}
        try:
            channel = self._get_channel()
            return channel.send(load)
        except SaltReqTimeoutError:
            return ''

    def list_env(self, saltenv='base', env=None):
        '''
        Return a list of the files in the file server's specified environment
        '''
        if env is not None:
            salt.utils.warn_until(
                'Boron',
                'Passing a salt environment should be done using \'saltenv\' '
                'not \'env\'. This functionality will be removed in Salt '
                'Boron.'
            )
            # Backwards compatibility
            saltenv = env

        load = {'saltenv': saltenv,
                'cmd': '_file_list'}
        try:
            channel = self._get_channel()
            return channel.send(load)
        except SaltReqTimeoutError:
            return ''

    def envs(self):
        '''
        Return a list of available environments
        '''
        load = {'cmd': '_file_envs'}
        try:
            channel = self._get_channel()
            return channel.send(load)
        except SaltReqTimeoutError:
            return ''

    def master_opts(self):
        '''
        Return the master opts data
        '''
        load = {'cmd': '_master_opts'}
        try:
            channel = self._get_channel()
            return channel.send(load)
        except SaltReqTimeoutError:
            return ''

    def ext_nodes(self):
        '''
        Return the metadata derived from the external nodes system on the
        master.
        '''
        load = {'cmd': '_ext_nodes',
                'id': self.opts['id'],
                'opts': self.opts}
        if self.auth:
            load['tok'] = self.auth.gen_token('salt')
        try:
            channel = self._get_channel()
            return channel.send(load)
        except SaltReqTimeoutError:
            return ''


class FSClient(RemoteClient):
    '''
    A local client that uses the RemoteClient but substitutes the channel for
    the FSChan object
    '''
    def __init__(self, opts):  # pylint: disable=W0231
        self.opts = opts
        self.channel = salt.fileserver.FSChan(opts)
        self.auth = DumbAuth()


class DumbAuth(object):
    '''
    The dumbauth class is used to stub out auth calls fired from the FSClient
    subsystem
    '''
    def gen_token(self, clear_tok):
        return clear_tok
