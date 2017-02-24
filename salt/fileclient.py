# -*- coding: utf-8 -*-
'''
Classes that manage file clients
'''
from __future__ import absolute_import

# Import python libs
import contextlib
import logging
import os
import string
import shutil
import ftplib
from tornado.httputil import parse_response_start_line, HTTPInputError

# Import salt libs
from salt.exceptions import (
    CommandExecutionError, MinionError
)
import salt.client
import salt.crypt
import salt.loader
import salt.payload
import salt.transport
import salt.fileserver
import salt.utils
import salt.utils.files
import salt.utils.templates
import salt.utils.url
import salt.utils.gzip_util
import salt.utils.http
import salt.ext.six as six
from salt.utils.locales import sdecode
from salt.utils.openstack.swift import SaltSwift

# pylint: disable=no-name-in-module,import-error
import salt.ext.six.moves.BaseHTTPServer as BaseHTTPServer
from salt.ext.six.moves.urllib.error import HTTPError, URLError
from salt.ext.six.moves.urllib.parse import urlparse, urlunparse
# pylint: enable=no-name-in-module,import-error

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


def decode_dict_keys_to_str(src):
    '''
    Convert top level keys from bytes to strings if possible.
    This is necessary because Python 3 makes a distinction
    between these types.
    '''
    if not six.PY3 or not isinstance(src, dict):
        return src

    output = {}
    for key, val in six.iteritems(src):
        if isinstance(key, bytes):
            try:
                key = key.decode()
            except UnicodeError:
                pass
        output[key] = val
    return output


class Client(object):
    '''
    Base class for Salt file interactions
    '''
    def __init__(self, opts):
        self.opts = opts
        self.utils = salt.loader.utils(self.opts)
        self.serial = salt.payload.Serial(self.opts)

    # Add __setstate__ and __getstate__ so that the object may be
    # deep copied. It normally can't be deep copied because its
    # constructor requires an 'opts' parameter.
    # The TCP transport needs to be able to deep copy this class
    # due to 'salt.utils.context.ContextDict.clone'.
    def __setstate__(self, state):
        # This will polymorphically call __init__
        # in the derived class.
        self.__init__(state['opts'])

    def __getstate__(self):
        return {'opts': self.opts}

    def _check_proto(self, path):
        '''
        Make sure that this path is intended for the salt master and trim it
        '''
        if not path.startswith('salt://'):
            raise MinionError(u'Unsupported path: {0}'.format(path))
        file_path, saltenv = salt.utils.url.parse(path)
        return file_path

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
    def _cache_loc(self, path, saltenv='base', cachedir=None):
        '''
        Return the local location to cache the file, cache dirs will be made
        '''
        if cachedir is None:
            cachedir = self.opts['cachedir']
        elif not os.path.isabs(cachedir):
            cachedir = os.path.join(self.opts['cachedir'], cachedir)

        dest = salt.utils.path_join(cachedir,
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
                 cachedir=None):
        '''
        Copies a file from the local files or master depending on
        implementation
        '''
        raise NotImplementedError

    def file_list_emptydirs(self, saltenv='base', prefix=''):
        '''
        List the empty dirs
        '''
        raise NotImplementedError

    def cache_file(self, path, saltenv='base', cachedir=None):
        '''
        Pull a file down from the file server and store it in the minion
        file cache
        '''
        return self.get_url(path, '', True, saltenv, cachedir=cachedir)

    def cache_files(self, paths, saltenv='base', cachedir=None):
        '''
        Download a list of files stored on the master and put them in the
        minion file cache
        '''
        ret = []
        if isinstance(paths, str):
            paths = paths.split(',')
        for path in paths:
            ret.append(self.cache_file(path, saltenv, cachedir=cachedir))
        return ret

    def cache_master(self, saltenv='base', cachedir=None):
        '''
        Download and cache all files on a master in a specified environment
        '''
        ret = []
        for path in self.file_list(saltenv):
            ret.append(
                self.cache_file(
                    salt.utils.url.create(path), saltenv, cachedir=cachedir)
            )
        return ret

    def cache_dir(self, path, saltenv='base', include_empty=False,
                  include_pat=None, exclude_pat=None, cachedir=None):
        '''
        Download all of the files in a subdir of the master
        '''
        ret = []

        path = self._check_proto(sdecode(path))
        # We want to make sure files start with this *directory*, use
        # '/' explicitly because the master (that's generating the
        # list of files) only runs on POSIX
        if not path.endswith('/'):
            path = path + '/'

        log.info(
            'Caching directory \'{0}\' for environment \'{1}\''.format(
                path, saltenv
            )
        )
        # go through the list of all files finding ones that are in
        # the target directory and caching them
        for fn_ in self.file_list(saltenv):
            fn_ = sdecode(fn_)
            if fn_.strip() and fn_.startswith(path):
                if salt.utils.check_include_exclude(
                        fn_, include_pat, exclude_pat):
                    fn_ = self.cache_file(
                        salt.utils.url.create(fn_), saltenv, cachedir=cachedir)
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
            if cachedir is None:
                cachedir = self.opts['cachedir']
            elif not os.path.isabs(cachedir):
                cachedir = os.path.join(self.opts['cachedir'], cachedir)

            dest = salt.utils.path_join(cachedir, 'files', saltenv)
            for fn_ in self.file_list_emptydirs(saltenv):
                fn_ = sdecode(fn_)
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

    def file_local_list(self, saltenv='base'):
        '''
        List files in the local minion files and localfiles caches
        '''
        filesdest = os.path.join(self.opts['cachedir'], 'files', saltenv)
        localfilesdest = os.path.join(self.opts['cachedir'], 'localfiles')

        fdest = self._file_local_list(filesdest)
        ldest = self._file_local_list(localfilesdest)
        return sorted(fdest.union(ldest))

    def file_list(self, saltenv='base', prefix=''):
        '''
        This function must be overwritten
        '''
        return []

    def dir_list(self, saltenv='base', prefix=''):
        '''
        This function must be overwritten
        '''
        return []

    def symlink_list(self, saltenv='base', prefix=''):
        '''
        This function must be overwritten
        '''
        return {}

    def is_cached(self, path, saltenv='base', cachedir=None):
        '''
        Returns the full path to a file if it is cached locally on the minion
        otherwise returns a blank string
        '''
        if path.startswith('salt://'):
            path, senv = salt.utils.url.parse(path)
            if senv:
                saltenv = senv

        escaped = True if salt.utils.url.is_escaped(path) else False

        # also strip escape character '|'
        localsfilesdest = os.path.join(
            self.opts['cachedir'], 'localfiles', path.lstrip('|/'))
        filesdest = os.path.join(
            self.opts['cachedir'], 'files', saltenv, path.lstrip('|/'))
        extrndest = self._extrn_path(path, saltenv, cachedir=cachedir)

        if os.path.exists(filesdest):
            return salt.utils.url.escape(filesdest) if escaped else filesdest
        elif os.path.exists(localsfilesdest):
            return salt.utils.url.escape(localsfilesdest) \
                if escaped \
                else localsfilesdest
        elif os.path.exists(extrndest):
            return extrndest

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
                    'During an attempt to list states for saltenv \'{0}\', '
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
                            stripped_root = os.path.relpath(root, path)
                            if salt.utils.is_windows():
                                stripped_root = stripped_root.replace('\\', '/')
                            stripped_root = stripped_root.replace('/', '.')
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

    def get_state(self, sls, saltenv, cachedir=None):
        '''
        Get a state file from the master and store it in the local minion
        cache; return the location of the file
        '''
        if '.' in sls:
            sls = sls.replace('.', '/')
        sls_url = salt.utils.url.create(sls + '.sls')
        init_url = salt.utils.url.create(sls + '/init.sls')
        for path in [sls_url, init_url]:
            dest = self.cache_file(path, saltenv, cachedir=cachedir)
            if dest:
                return {'source': path, 'dest': dest}
        return {}

    def get_dir(self, path, dest='', saltenv='base', gzip=None,
                cachedir=None):
        '''
        Get a directory recursively from the salt-master
        '''
        ret = []
        # Strip trailing slash
        path = self._check_proto(path).rstrip('/')
        # Break up the path into a list containing the bottom-level directory
        # (the one being recursively copied) and the directories preceding it
        separated = path.rsplit('/', 1)
        if len(separated) != 2:
            # No slashes in path. (This means all files in saltenv will be
            # copied)
            prefix = ''
        else:
            prefix = separated[0]

        # Copy files from master
        for fn_ in self.file_list(saltenv, prefix=path):
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
                  salt.utils.url.create(fn_),
                  '{0}/{1}'.format(dest, minion_relpath),
                  True, saltenv, gzip
               )
            )
        # Replicate empty dirs from master
        try:
            for fn_ in self.file_list_emptydirs(saltenv, prefix=path):
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

    def get_url(self, url, dest, makedirs=False, saltenv='base',
                no_cache=False, cachedir=None):
        '''
        Get a single file from a URL.
        '''
        url_data = urlparse(url)
        url_scheme = url_data.scheme
        url_path = os.path.join(
                url_data.netloc, url_data.path).rstrip(os.sep)

        if url_scheme and url_scheme.lower() in string.ascii_lowercase:
            url_path = ':'.join((url_scheme, url_path))
            url_scheme = 'file'

        if url_scheme in ('file', ''):
            # Local filesystem
            if not os.path.isabs(url_path):
                raise CommandExecutionError(
                    'Path \'{0}\' is not absolute'.format(url_path)
                )
            if dest is None:
                with salt.utils.fopen(url_path, 'r') as fp_:
                    data = fp_.read()
                return data
            return url_path

        if url_scheme == 'salt':
            result = self.get_file(url, dest, makedirs, saltenv, cachedir=cachedir)
            if result and dest is None:
                with salt.utils.fopen(result, 'r') as fp_:
                    data = fp_.read()
                return data
            return result

        if dest:
            destdir = os.path.dirname(dest)
            if not os.path.isdir(destdir):
                if makedirs:
                    os.makedirs(destdir)
                else:
                    return ''
        elif not no_cache:
            dest = self._extrn_path(url, saltenv, cachedir=cachedir)
            destdir = os.path.dirname(dest)
            if not os.path.isdir(destdir):
                os.makedirs(destdir)

        if url_data.scheme == 's3':
            try:
                def s3_opt(key, default=None):
                    '''Get value of s3.<key> from Minion config or from Pillar'''
                    if 's3.' + key in self.opts:
                        return self.opts['s3.' + key]
                    try:
                        return self.opts['pillar']['s3'][key]
                    except (KeyError, TypeError):
                        return default
                self.utils['s3.query'](method='GET',
                                       bucket=url_data.netloc,
                                       path=url_data.path[1:],
                                       return_bin=False,
                                       local_file=dest,
                                       action=None,
                                       key=s3_opt('key'),
                                       keyid=s3_opt('keyid'),
                                       service_url=s3_opt('service_url'),
                                       verify_ssl=s3_opt('verify_ssl', True),
                                       location=s3_opt('location'))
                return dest
            except Exception as exc:
                raise MinionError(
                    'Could not fetch from {0}. Exception: {1}'.format(url, exc)
                )
        if url_data.scheme == 'ftp':
            try:
                ftp = ftplib.FTP()
                ftp.connect(url_data.hostname, url_data.port)
                ftp.login(url_data.username, url_data.password)
                with salt.utils.fopen(dest, 'wb') as fp_:
                    ftp.retrbinary('RETR {0}'.format(url_data.path), fp_.write)
                ftp.quit()
                return dest
            except Exception as exc:
                raise MinionError('Could not retrieve {0} from FTP server. Exception: {1}'.format(url, exc))

        if url_data.scheme == 'swift':
            try:
                def swift_opt(key, default):
                    '''Get value of <key> from Minion config or from Pillar'''
                    if key in self.opts:
                        return self.opts[key]
                    try:
                        return self.opts['pillar'][key]
                    except (KeyError, TypeError):
                        return default

                swift_conn = SaltSwift(swift_opt('keystone.user', None),
                                       swift_opt('keystone.tenant', None),
                                       swift_opt('keystone.auth_url', None),
                                       swift_opt('keystone.password', None))

                swift_conn.get_object(url_data.netloc,
                                      url_data.path[1:],
                                      dest)
                return dest
            except Exception:
                raise MinionError('Could not fetch from {0}'.format(url))

        get_kwargs = {}
        if url_data.username is not None \
                and url_data.scheme in ('http', 'https'):
            netloc = url_data.netloc
            at_sign_pos = netloc.rfind('@')
            if at_sign_pos != -1:
                netloc = netloc[at_sign_pos + 1:]
            fixed_url = urlunparse(
                (url_data.scheme, netloc, url_data.path,
                 url_data.params, url_data.query, url_data.fragment))
            get_kwargs['auth'] = (url_data.username, url_data.password)
        else:
            fixed_url = url

        destfp = None
        try:
            # Tornado calls streaming_callback on redirect response bodies.
            # But we need streaming to support fetching large files (> RAM avail).
            # Here we working this around by disabling recording the body for redirections.
            # The issue is fixed in Tornado 4.3.0 so on_header callback could be removed
            # when we'll deprecate Tornado<4.3.0.
            # See #27093 and #30431 for details.

            # Use list here to make it writable inside the on_header callback. Simple bool doesn't
            # work here: on_header creates a new local variable instead. This could be avoided in
            # Py3 with 'nonlocal' statement. There is no Py2 alternative for this.
            write_body = [False]

            def on_header(hdr):
                try:
                    hdr = parse_response_start_line(hdr)
                except HTTPInputError:
                    # Not the first line, do nothing
                    return
                write_body[0] = hdr.code not in [301, 302, 303, 307]

            if no_cache:
                result = []

                def on_chunk(chunk):
                    if write_body[0]:
                        result.append(chunk)
            else:
                dest_tmp = "{0}.part".format(dest)
                # We need an open filehandle to use in the on_chunk callback,
                # that's why we're not using a with clause here.
                destfp = salt.utils.fopen(dest_tmp, 'wb')

                def on_chunk(chunk):
                    if write_body[0]:
                        destfp.write(chunk)

            query = salt.utils.http.query(
                fixed_url,
                stream=True,
                streaming_callback=on_chunk,
                header_callback=on_header,
                username=url_data.username,
                password=url_data.password,
                opts=self.opts,
                **get_kwargs
            )
            if 'handle' not in query:
                raise MinionError('Error: {0} reading {1}'.format(query['error'], url))
            if no_cache:
                return six.b('').join(result)
            else:
                destfp.close()
                destfp = None
                salt.utils.files.rename(dest_tmp, dest)
                return dest
        except HTTPError as exc:
            raise MinionError('HTTP error {0} reading {1}: {3}'.format(
                exc.code,
                url,
                *BaseHTTPServer.BaseHTTPRequestHandler.responses[exc.code]))
        except URLError as exc:
            raise MinionError('Error reading {0}: {1}'.format(url, exc.reason))
        finally:
            if destfp is not None:
                destfp.close()

    def get_template(
            self,
            url,
            dest,
            template='jinja',
            makedirs=False,
            saltenv='base',
            cachedir=None,
            **kwargs):
        '''
        Cache a file then process it as a template
        '''
        if 'env' in kwargs:
            salt.utils.warn_until(
                'Oxygen',
                'Parameter \'env\' has been detected in the argument list.  This '
                'parameter is no longer used and has been replaced by \'saltenv\' '
                'as of Salt 2016.11.0.  This warning will be removed in Salt Oxygen.'
                )
            kwargs.pop('env')

        kwargs['saltenv'] = saltenv
        url_data = urlparse(url)
        sfn = self.cache_file(url, saltenv, cachedir=cachedir)
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
            dest = self._extrn_path(url, saltenv, cachedir=cachedir)
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

    def _extrn_path(self, url, saltenv, cachedir=None):
        '''
        Return the extn_filepath for a given url
        '''
        url_data = urlparse(url)
        if salt.utils.is_windows():
            netloc = salt.utils.sanitize_win_path_string(url_data.netloc)
        else:
            netloc = url_data.netloc

        # Strip user:pass from URLs
        netloc = netloc.split('@')[-1]

        if cachedir is None:
            cachedir = self.opts['cachedir']
        elif not os.path.isabs(cachedir):
            cachedir = os.path.join(self.opts['cachedir'], cachedir)

        if url_data.query:
            file_name = '-'.join([url_data.path, url_data.query])
        else:
            file_name = url_data.path

        return salt.utils.path_join(
            cachedir,
            'extrn_files',
            saltenv,
            netloc,
            file_name
        )


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
        if salt.utils.url.is_escaped(path):
            # The path arguments are escaped
            path = salt.utils.url.unescape(path)
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
                 cachedir=None):
        '''
        Copies a file from the local files directory into :param:`dest`
        gzip compression settings are ignored for local files
        '''
        path = self._check_proto(path)
        fnd = self._find_file(path, saltenv)
        fnd_path = fnd.get('path')
        if not fnd_path:
            return ''

        try:
            fnd_mode = fnd.get('stat', [])[0]
        except (IndexError, TypeError):
            fnd_mode = None

        if not salt.utils.is_windows():
            if fnd_mode is not None:
                try:
                    if os.stat(dest).st_mode != fnd_mode:
                        try:
                            os.chmod(dest, fnd_mode)
                        except OSError as exc:
                            log.warning('Failed to chmod %s: %s', dest, exc)
                except Exception:
                    pass

        return fnd_path

    def file_list(self, saltenv='base', prefix=''):
        '''
        Return a list of files in the given environment
        with optional relative prefix path to limit directory traversal
        '''
        ret = []
        if saltenv not in self.opts['file_roots']:
            return ret
        prefix = prefix.strip('/')
        for path in self.opts['file_roots'][saltenv]:
            for root, dirs, files in os.walk(
                os.path.join(path, prefix), followlinks=True
            ):
                # Don't walk any directories that match file_ignore_regex or glob
                dirs[:] = [d for d in dirs if not salt.fileserver.is_file_ignored(self.opts, d)]
                for fname in files:
                    relpath = os.path.relpath(os.path.join(root, fname), path)
                    ret.append(sdecode(relpath))
        return ret

    def file_list_emptydirs(self, saltenv='base', prefix=''):
        '''
        List the empty dirs in the file_roots
        with optional relative prefix path to limit directory traversal
        '''
        ret = []
        prefix = prefix.strip('/')
        if saltenv not in self.opts['file_roots']:
            return ret
        for path in self.opts['file_roots'][saltenv]:
            for root, dirs, files in os.walk(
                os.path.join(path, prefix), followlinks=True
            ):
                # Don't walk any directories that match file_ignore_regex or glob
                dirs[:] = [d for d in dirs if not salt.fileserver.is_file_ignored(self.opts, d)]
                if len(dirs) == 0 and len(files) == 0:
                    ret.append(sdecode(os.path.relpath(root, path)))
        return ret

    def dir_list(self, saltenv='base', prefix=''):
        '''
        List the dirs in the file_roots
        with optional relative prefix path to limit directory traversal
        '''
        ret = []
        if saltenv not in self.opts['file_roots']:
            return ret
        prefix = prefix.strip('/')
        for path in self.opts['file_roots'][saltenv]:
            for root, dirs, files in os.walk(
                os.path.join(path, prefix), followlinks=True
            ):
                ret.append(sdecode(os.path.relpath(root, path)))
        return ret

    def __get_file_path(self, path, saltenv='base'):
        '''
        Return either a file path or the result of a remote find_file call.
        '''
        try:
            path = self._check_proto(path)
        except MinionError as err:
            # Local file path
            if not os.path.isfile(path):
                msg = 'specified file {0} is not present to generate hash: {1}'
                log.warning(msg.format(path, err))
                return None
            else:
                return path
        return self._find_file(path, saltenv)

    def hash_file(self, path, saltenv='base'):
        '''
        Return the hash of a file, to get the hash of a file in the file_roots
        prepend the path with salt://<file on server> otherwise, prepend the
        file with / for a local file.
        '''
        ret = {}
        fnd = self.__get_file_path(path, saltenv)
        if fnd is None:
            return ret

        try:
            # Remote file path (self._find_file() invoked)
            fnd_path = fnd['path']
        except TypeError:
            # Local file path
            fnd_path = fnd

        hash_type = self.opts.get('hash_type', 'md5')
        ret['hsum'] = salt.utils.get_hash(fnd_path, form=hash_type)
        ret['hash_type'] = hash_type
        return ret

    def hash_and_stat_file(self, path, saltenv='base'):
        '''
        Return the hash of a file, to get the hash of a file in the file_roots
        prepend the path with salt://<file on server> otherwise, prepend the
        file with / for a local file.

        Additionally, return the stat result of the file, or None if no stat
        results were found.
        '''
        ret = {}
        fnd = self.__get_file_path(path, saltenv)
        if fnd is None:
            return ret, None

        try:
            # Remote file path (self._find_file() invoked)
            fnd_path = fnd['path']
            fnd_stat = fnd.get('stat')
        except TypeError:
            # Local file path
            fnd_path = fnd
            try:
                fnd_stat = list(os.stat(fnd_path))
            except Exception:
                fnd_stat = None

        hash_type = self.opts.get('hash_type', 'md5')
        ret['hsum'] = salt.utils.get_hash(fnd_path, form=hash_type)
        ret['hash_type'] = hash_type
        return ret, fnd_stat

    def list_env(self, saltenv='base'):
        '''
        Return a list of the files in the file server's specified environment
        '''
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

    def _refresh_channel(self):
        '''
        Reset the channel, in the event of an interruption
        '''
        self.channel = salt.transport.Channel.factory(self.opts)
        return self.channel

    def get_file(self,
                 path,
                 dest='',
                 makedirs=False,
                 saltenv='base',
                 gzip=None,
                 cachedir=None):
        '''
        Get a single file from the salt-master
        path must be a salt server location, aka, salt://path/to/file, if
        dest is omitted, then the downloaded file will be placed in the minion
        cache
        '''
        path, senv = salt.utils.url.split_env(path)
        if senv:
            saltenv = senv

        if not salt.utils.is_windows():
            hash_server, stat_server = self.hash_and_stat_file(path, saltenv)
            try:
                mode_server = stat_server[0]
            except (IndexError, TypeError):
                mode_server = None
        else:
            hash_server = self.hash_file(path, saltenv)
            mode_server = None

        # Check if file exists on server, before creating files and
        # directories
        if hash_server == '':
            log.debug(
                'Could not find file \'%s\' in saltenv \'%s\'',
                path, saltenv
            )
            return False

        # Hash compare local copy with master and skip download
        # if no difference found.
        dest2check = dest
        if not dest2check:
            rel_path = self._check_proto(path)

            log.debug(
                'In saltenv \'%s\', looking at rel_path \'%s\' to resolve '
                '\'%s\'', saltenv, rel_path, path
            )
            with self._cache_loc(
                    rel_path, saltenv, cachedir=cachedir) as cache_dest:
                dest2check = cache_dest

        log.debug(
            'In saltenv \'%s\', ** considering ** path \'%s\' to resolve '
            '\'%s\'', saltenv, dest2check, path
        )

        if dest2check and os.path.isfile(dest2check):
            if not salt.utils.is_windows():
                hash_local, stat_local = \
                    self.hash_and_stat_file(dest2check, saltenv)
                try:
                    mode_local = stat_local[0]
                except (IndexError, TypeError):
                    mode_local = None
            else:
                hash_local = self.hash_file(dest2check, saltenv)
                mode_local = None

            if hash_local == hash_server:
                if not salt.utils.is_windows():
                    if mode_server is None:
                        log.debug('No file mode available for \'%s\'', path)
                    elif mode_local is None:
                        log.debug(
                            'No file mode available for \'%s\'',
                            dest2check
                        )
                    else:
                        if mode_server == mode_local:
                            log.info(
                                'Fetching file from saltenv \'%s\', '
                                '** skipped ** latest already in cache '
                                '\'%s\', mode up-to-date', saltenv, path
                            )
                        else:
                            try:
                                os.chmod(dest2check, mode_server)
                                log.info(
                                    'Fetching file from saltenv \'%s\', '
                                    '** updated ** latest already in cache, '
                                    '\'%s\', mode updated from %s to %s',
                                    saltenv,
                                    path,
                                    salt.utils.st_mode_to_octal(mode_local),
                                    salt.utils.st_mode_to_octal(mode_server)
                                )
                            except OSError as exc:
                                log.warning(
                                    'Failed to chmod %s: %s', dest2check, exc
                                )
                    # We may not have been able to check/set the mode, but we
                    # don't want to re-download the file because of a failure
                    # in mode checking. Return the cached path.
                    return dest2check
                else:
                    log.info(
                        'Fetching file from saltenv \'%s\', ** skipped ** '
                        'latest already in cache \'%s\'', saltenv, path
                    )
                    return dest2check

        log.debug(
            'Fetching file from saltenv \'%s\', ** attempting ** \'%s\'',
            saltenv, path
        )
        d_tries = 0
        transport_tries = 0
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
            # We need an open filehandle here, that's why we're not using a
            # with clause:
            fn_ = salt.utils.fopen(dest, 'wb+')
        else:
            log.debug('No dest file found')

        while True:
            if not fn_:
                load['loc'] = 0
            else:
                load['loc'] = fn_.tell()
            data = self.channel.send(load, raw=True)
            if six.PY3:
                # Sometimes the source is local (eg when using
                # 'salt.filesystem.FSChan'), in which case the keys are
                # already strings. Sometimes the source is remote, in which
                # case the keys are bytes due to raw mode. Standardize on
                # strings for the top-level keys to simplify things.
                data = decode_dict_keys_to_str(data)
            try:
                if not data['data']:
                    if not fn_ and data['dest']:
                        # This is a 0 byte file on the master
                        with self._cache_loc(
                                data['dest'],
                                saltenv,
                                cachedir=cachedir) as cache_dest:
                            dest = cache_dest
                            with salt.utils.fopen(cache_dest, 'wb+') as ofile:
                                ofile.write(data['data'])
                    if 'hsum' in data and d_tries < 3:
                        # Master has prompted a file verification, if the
                        # verification fails, re-download the file. Try 3 times
                        d_tries += 1
                        hsum = salt.utils.get_hash(dest, salt.utils.to_str(data.get('hash_type', b'md5')))
                        if hsum != data['hsum']:
                            log.warning(
                                'Bad download of file %s, attempt %d of 3',
                                path, d_tries
                            )
                            continue
                    break
                if not fn_:
                    with self._cache_loc(
                            data['dest'],
                            saltenv,
                            cachedir=cachedir) as cache_dest:
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
                if six.PY3 and isinstance(data, str):
                    data = data.encode()
                fn_.write(data)
            except (TypeError, KeyError) as exc:
                try:
                    data_type = type(data).__name__
                except AttributeError:
                    # Shouldn't happen, but don't let this cause a traceback.
                    data_type = str(type(data))
                transport_tries += 1
                log.warning(
                    'Data transport is broken, got: %s, type: %s, '
                    'exception: %s, attempt %d of 3',
                    data, data_type, exc, transport_tries
                )
                self._refresh_channel()
                if transport_tries > 3:
                    log.error(
                        'Data transport is broken, got: %s, type: %s, '
                        'exception: %s, retry attempts exhausted',
                        data, data_type, exc
                    )
                    break

        if fn_:
            fn_.close()
            log.info(
                'Fetching file from saltenv \'%s\', ** done ** \'%s\'',
                saltenv, path
            )
        else:
            log.debug(
                'In saltenv \'%s\', we are ** missing ** the file \'%s\'',
                saltenv, path
            )

        if not salt.utils.is_windows():
            if mode_server is not None:
                try:
                    if os.stat(dest).st_mode != mode_server:
                        try:
                            os.chmod(dest, mode_server)
                            log.info(
                                'Fetching file from saltenv \'%s\', '
                                '** done ** \'%s\', mode set to %s',
                                saltenv,
                                path,
                                salt.utils.st_mode_to_octal(mode_server)
                            )
                        except OSError:
                            log.warning('Failed to chmod %s: %s', dest, exc)
                except OSError:
                    pass
        return dest

    def file_list(self, saltenv='base', prefix=''):
        '''
        List the files on the master
        '''
        load = {'saltenv': saltenv,
                'prefix': prefix,
                'cmd': '_file_list'}

        return [sdecode(fn_) for fn_ in self.channel.send(load)]

    def file_list_emptydirs(self, saltenv='base', prefix=''):
        '''
        List the empty dirs on the master
        '''
        load = {'saltenv': saltenv,
                'prefix': prefix,
                'cmd': '_file_list_emptydirs'}
        self.channel.send(load)

    def dir_list(self, saltenv='base', prefix=''):
        '''
        List the dirs on the master
        '''
        load = {'saltenv': saltenv,
                'prefix': prefix,
                'cmd': '_dir_list'}
        return self.channel.send(load)

    def symlink_list(self, saltenv='base', prefix=''):
        '''
        List symlinked files and dirs on the master
        '''
        load = {'saltenv': saltenv,
                'prefix': prefix,
                'cmd': '_symlink_list'}
        return self.channel.send(load)

    def __hash_and_stat_file(self, path, saltenv='base'):
        '''
        Common code for hashing and stating files
        '''
        try:
            path = self._check_proto(path)
        except MinionError as err:
            if not os.path.isfile(path):
                msg = 'specified file {0} is not present to generate hash: {1}'
                log.warning(msg.format(path, err))
                return {}
            else:
                ret = {}
                hash_type = self.opts.get('hash_type', 'md5')
                ret['hsum'] = salt.utils.get_hash(path, form=hash_type)
                ret['hash_type'] = hash_type
                return ret, list(os.stat(path))
        load = {'path': path,
                'saltenv': saltenv,
                'cmd': '_file_hash_and_stat'}
        return self.channel.send(load)

    def hash_file(self, path, saltenv='base'):
        '''
        Return the hash of a file, to get the hash of a file on the salt
        master file server prepend the path with salt://<file on server>
        otherwise, prepend the file with / for a local file.
        '''
        return self.__hash_and_stat_file(path, saltenv)[0]

    def hash_and_stat_file(self, path, saltenv='base'):
        '''
        The same as hash_file, but also return the file's mode, or None if no
        mode data is present.
        '''
        return self.__hash_and_stat_file(path, saltenv)

    def list_env(self, saltenv='base'):
        '''
        Return a list of the files in the file server's specified environment
        '''
        load = {'saltenv': saltenv,
                'cmd': '_file_list'}
        return self.channel.send(load)

    def envs(self):
        '''
        Return a list of available environments
        '''
        load = {'cmd': '_file_envs'}
        return self.channel.send(load)

    def master_opts(self):
        '''
        Return the master opts data
        '''
        load = {'cmd': '_master_opts'}
        return self.channel.send(load)

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
        return self.channel.send(load)


class FSClient(RemoteClient):
    '''
    A local client that uses the RemoteClient but substitutes the channel for
    the FSChan object
    '''
    def __init__(self, opts):  # pylint: disable=W0231
        Client.__init__(self, opts)  # pylint: disable=W0233
        self.channel = salt.fileserver.FSChan(opts)
        self.auth = DumbAuth()


class DumbAuth(object):
    '''
    The dumbauth class is used to stub out auth calls fired from the FSClient
    subsystem
    '''
    def gen_token(self, clear_tok):
        return clear_tok
