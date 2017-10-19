# -*- coding: utf-8 -*-
'''
Classes that manage file clients
'''
from __future__ import absolute_import

# Import python libs
import contextlib
import errno
import logging
import os
import string
import shutil
import ftplib
from tornado.httputil import parse_response_start_line, HTTPHeaders, HTTPInputError

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
import salt.utils.files
import salt.utils.gzip_util
import salt.utils.hashutils
import salt.utils.http
import salt.utils.path
import salt.utils.platform
import salt.utils.stringutils
import salt.utils.templates
import salt.utils.url
import salt.utils.versions
from salt.utils.locales import sdecode
from salt.utils.openstack.swift import SaltSwift

# pylint: disable=no-name-in-module,import-error
from salt.ext import six
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
    client = opts.get(u'file_client', u'remote')
    if pillar and client == u'local':
        client = u'pillar'
    return {
        u'remote': RemoteClient,
        u'local': FSClient,
        u'pillar': LocalClient,
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
        self.__init__(state[u'opts'])

    def __getstate__(self):
        return {u'opts': self.opts}

    def _check_proto(self, path):
        '''
        Make sure that this path is intended for the salt master and trim it
        '''
        if not path.startswith(u'salt://'):
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
    def _cache_loc(self, path, saltenv=u'base', cachedir=None):
        '''
        Return the local location to cache the file, cache dirs will be made
        '''
        cachedir = self.get_cachedir(cachedir)
        dest = salt.utils.path.join(cachedir,
                                    u'files',
                                    saltenv,
                                    path)
        destdir = os.path.dirname(dest)
        cumask = os.umask(63)

        # remove destdir if it is a regular file to avoid an OSError when
        # running os.makedirs below
        if os.path.isfile(destdir):
            os.remove(destdir)

        # ensure destdir exists
        try:
            os.makedirs(destdir)
        except OSError as exc:
            if exc.errno != errno.EEXIST:  # ignore if it was there already
                raise

        yield dest
        os.umask(cumask)

    def get_cachedir(self, cachedir=None):
        if cachedir is None:
            cachedir = self.opts[u'cachedir']
        elif not os.path.isabs(cachedir):
            cachedir = os.path.join(self.opts[u'cachedir'], cachedir)
        return cachedir

    def get_file(self,
                 path,
                 dest=u'',
                 makedirs=False,
                 saltenv=u'base',
                 gzip=None,
                 cachedir=None):
        '''
        Copies a file from the local files or master depending on
        implementation
        '''
        raise NotImplementedError

    def file_list_emptydirs(self, saltenv=u'base', prefix=u''):
        '''
        List the empty dirs
        '''
        raise NotImplementedError

    def cache_file(self, path, saltenv=u'base', cachedir=None, source_hash=None):
        '''
        Pull a file down from the file server and store it in the minion
        file cache
        '''
        return self.get_url(
            path, u'', True, saltenv, cachedir=cachedir, source_hash=source_hash)

    def cache_files(self, paths, saltenv=u'base', cachedir=None):
        '''
        Download a list of files stored on the master and put them in the
        minion file cache
        '''
        ret = []
        if isinstance(paths, six.string_types):
            paths = paths.split(u',')
        for path in paths:
            ret.append(self.cache_file(path, saltenv, cachedir=cachedir))
        return ret

    def cache_master(self, saltenv=u'base', cachedir=None):
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

    def cache_dir(self, path, saltenv=u'base', include_empty=False,
                  include_pat=None, exclude_pat=None, cachedir=None):
        '''
        Download all of the files in a subdir of the master
        '''
        ret = []

        path = self._check_proto(sdecode(path))
        # We want to make sure files start with this *directory*, use
        # '/' explicitly because the master (that's generating the
        # list of files) only runs on POSIX
        if not path.endswith(u'/'):
            path = path + u'/'

        log.info(
            u'Caching directory \'%s\' for environment \'%s\'', path, saltenv
        )
        # go through the list of all files finding ones that are in
        # the target directory and caching them
        for fn_ in self.file_list(saltenv):
            fn_ = sdecode(fn_)
            if fn_.strip() and fn_.startswith(path):
                if salt.utils.stringutils.check_include_exclude(
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
            cachedir = self.get_cachedir(cachedir)

            dest = salt.utils.path.join(cachedir, u'files', saltenv)
            for fn_ in self.file_list_emptydirs(saltenv):
                fn_ = sdecode(fn_)
                if fn_.startswith(path):
                    minion_dir = u'{0}/{1}'.format(dest, fn_)
                    if not os.path.isdir(minion_dir):
                        os.makedirs(minion_dir)
                    ret.append(minion_dir)
        return ret

    def cache_local_file(self, path, **kwargs):
        '''
        Cache a local file on the minion in the localfiles cache
        '''
        dest = os.path.join(self.opts[u'cachedir'], u'localfiles',
                            path.lstrip(u'/'))
        destdir = os.path.dirname(dest)

        if not os.path.isdir(destdir):
            os.makedirs(destdir)

        shutil.copyfile(path, dest)
        return dest

    def file_local_list(self, saltenv=u'base'):
        '''
        List files in the local minion files and localfiles caches
        '''
        filesdest = os.path.join(self.opts[u'cachedir'], u'files', saltenv)
        localfilesdest = os.path.join(self.opts[u'cachedir'], u'localfiles')

        fdest = self._file_local_list(filesdest)
        ldest = self._file_local_list(localfilesdest)
        return sorted(fdest.union(ldest))

    def file_list(self, saltenv=u'base', prefix=u''):
        '''
        This function must be overwritten
        '''
        return []

    def dir_list(self, saltenv=u'base', prefix=u''):
        '''
        This function must be overwritten
        '''
        return []

    def symlink_list(self, saltenv=u'base', prefix=u''):
        '''
        This function must be overwritten
        '''
        return {}

    def is_cached(self, path, saltenv=u'base', cachedir=None):
        '''
        Returns the full path to a file if it is cached locally on the minion
        otherwise returns a blank string
        '''
        if path.startswith(u'salt://'):
            path, senv = salt.utils.url.parse(path)
            if senv:
                saltenv = senv

        escaped = True if salt.utils.url.is_escaped(path) else False

        # also strip escape character '|'
        localsfilesdest = os.path.join(
            self.opts[u'cachedir'], u'localfiles', path.lstrip(u'|/'))
        filesdest = os.path.join(
            self.opts[u'cachedir'], u'files', saltenv, path.lstrip(u'|/'))
        extrndest = self._extrn_path(path, saltenv, cachedir=cachedir)

        if os.path.exists(filesdest):
            return salt.utils.url.escape(filesdest) if escaped else filesdest
        elif os.path.exists(localsfilesdest):
            return salt.utils.url.escape(localsfilesdest) \
                if escaped \
                else localsfilesdest
        elif os.path.exists(extrndest):
            return extrndest

        return u''

    def list_states(self, saltenv):
        '''
        Return a list of all available sls modules on the master for a given
        environment
        '''

        limit_traversal = self.opts.get(u'fileserver_limit_traversal', False)
        states = []

        if limit_traversal:
            if saltenv not in self.opts[u'file_roots']:
                log.warning(
                    u'During an attempt to list states for saltenv \'%s\', '
                    u'the environment could not be found in the configured '
                    u'file roots', saltenv
                )
                return states
            for path in self.opts[u'file_roots'][saltenv]:
                for root, dirs, files in os.walk(path, topdown=True):
                    log.debug(
                        u'Searching for states in dirs %s and files %s',
                        dirs, files
                    )
                    if not [filename.endswith(u'.sls') for filename in files]:
                        #  Use shallow copy so we don't disturb the memory used by os.walk. Otherwise this breaks!
                        del dirs[:]
                    else:
                        for found_file in files:
                            stripped_root = os.path.relpath(root, path)
                            if salt.utils.platform.is_windows():
                                stripped_root = stripped_root.replace(u'\\', u'/')
                            stripped_root = stripped_root.replace(u'/', u'.')
                            if found_file.endswith((u'.sls')):
                                if found_file.endswith(u'init.sls'):
                                    if stripped_root.endswith(u'.'):
                                        stripped_root = stripped_root.rstrip(u'.')
                                    states.append(stripped_root)
                                else:
                                    if not stripped_root.endswith(u'.'):
                                        stripped_root += u'.'
                                    if stripped_root.startswith(u'.'):
                                        stripped_root = stripped_root.lstrip(u'.')
                                    states.append(stripped_root + found_file[:-4])
        else:
            for path in self.file_list(saltenv):
                if salt.utils.platform.is_windows():
                    path = path.replace(u'\\', u'/')
                if path.endswith(u'.sls'):
                    # is an sls module!
                    if path.endswith(u'/init.sls'):
                        states.append(path.replace(u'/', u'.')[:-9])
                    else:
                        states.append(path.replace(u'/', u'.')[:-4])
        return states

    def get_state(self, sls, saltenv, cachedir=None):
        '''
        Get a state file from the master and store it in the local minion
        cache; return the location of the file
        '''
        if u'.' in sls:
            sls = sls.replace(u'.', u'/')
        sls_url = salt.utils.url.create(sls + u'.sls')
        init_url = salt.utils.url.create(sls + u'/init.sls')
        for path in [sls_url, init_url]:
            dest = self.cache_file(path, saltenv, cachedir=cachedir)
            if dest:
                return {u'source': path, u'dest': dest}
        return {}

    def get_dir(self, path, dest=u'', saltenv=u'base', gzip=None,
                cachedir=None):
        '''
        Get a directory recursively from the salt-master
        '''
        ret = []
        # Strip trailing slash
        path = self._check_proto(path).rstrip(u'/')
        # Break up the path into a list containing the bottom-level directory
        # (the one being recursively copied) and the directories preceding it
        separated = path.rsplit(u'/', 1)
        if len(separated) != 2:
            # No slashes in path. (This means all files in saltenv will be
            # copied)
            prefix = u''
        else:
            prefix = separated[0]

        # Copy files from master
        for fn_ in self.file_list(saltenv, prefix=path):
            # Prevent files in "salt://foobar/" (or salt://foo.sh) from
            # matching a path of "salt://foo"
            try:
                if fn_[len(path)] != u'/':
                    continue
            except IndexError:
                continue
            # Remove the leading directories from path to derive
            # the relative path on the minion.
            minion_relpath = fn_[len(prefix):].lstrip(u'/')
            ret.append(
               self.get_file(
                  salt.utils.url.create(fn_),
                  u'{0}/{1}'.format(dest, minion_relpath),
                  True, saltenv, gzip
               )
            )
        # Replicate empty dirs from master
        try:
            for fn_ in self.file_list_emptydirs(saltenv, prefix=path):
                # Prevent an empty dir "salt://foobar/" from matching a path of
                # "salt://foo"
                try:
                    if fn_[len(path)] != u'/':
                        continue
                except IndexError:
                    continue
                # Remove the leading directories from path to derive
                # the relative path on the minion.
                minion_relpath = fn_[len(prefix):].lstrip(u'/')
                minion_mkdir = u'{0}/{1}'.format(dest, minion_relpath)
                if not os.path.isdir(minion_mkdir):
                    os.makedirs(minion_mkdir)
                ret.append(minion_mkdir)
        except TypeError:
            pass
        ret.sort()
        return ret

    def get_url(self, url, dest, makedirs=False, saltenv=u'base',
                no_cache=False, cachedir=None, source_hash=None):
        '''
        Get a single file from a URL.
        '''
        url_data = urlparse(url)
        url_scheme = url_data.scheme
        url_path = os.path.join(
                url_data.netloc, url_data.path).rstrip(os.sep)

        # If dest is a directory, rewrite dest with filename
        if dest is not None \
                and (os.path.isdir(dest) or dest.endswith((u'/', u'\\'))):
            if url_data.query or len(url_data.path) > 1 and not url_data.path.endswith(u'/'):
                strpath = url.split(u'/')[-1]
            else:
                strpath = u'index.html'

            if salt.utils.platform.is_windows():
                strpath = salt.utils.path.sanitize_win_path(strpath)

            dest = os.path.join(dest, strpath)

        if url_scheme and url_scheme.lower() in string.ascii_lowercase:
            url_path = u':'.join((url_scheme, url_path))
            url_scheme = u'file'

        if url_scheme in (u'file', u''):
            # Local filesystem
            if not os.path.isabs(url_path):
                raise CommandExecutionError(
                    u'Path \'{0}\' is not absolute'.format(url_path)
                )
            if dest is None:
                with salt.utils.files.fopen(url_path, u'r') as fp_:
                    data = fp_.read()
                return data
            return url_path

        if url_scheme == u'salt':
            result = self.get_file(url, dest, makedirs, saltenv, cachedir=cachedir)
            if result and dest is None:
                with salt.utils.files.fopen(result, u'r') as fp_:
                    data = fp_.read()
                return data
            return result

        if dest:
            destdir = os.path.dirname(dest)
            if not os.path.isdir(destdir):
                if makedirs:
                    os.makedirs(destdir)
                else:
                    return u''
        elif not no_cache:
            dest = self._extrn_path(url, saltenv, cachedir=cachedir)
            if source_hash is not None:
                try:
                    source_hash = source_hash.split('=')[-1]
                    form = salt.utils.files.HASHES_REVMAP[len(source_hash)]
                    if salt.utils.hashutils.get_hash(dest, form) == source_hash:
                        log.debug(
                            'Cached copy of %s (%s) matches source_hash %s, '
                            'skipping download', url, dest, source_hash
                        )
                        return dest
                except (AttributeError, KeyError, IOError, OSError):
                    pass
            destdir = os.path.dirname(dest)
            if not os.path.isdir(destdir):
                os.makedirs(destdir)

        if url_data.scheme == u's3':
            try:
                def s3_opt(key, default=None):
                    '''
                    Get value of s3.<key> from Minion config or from Pillar
                    '''
                    if u's3.' + key in self.opts:
                        return self.opts[u's3.' + key]
                    try:
                        return self.opts[u'pillar'][u's3'][key]
                    except (KeyError, TypeError):
                        return default
                self.utils[u's3.query'](method=u'GET',
                                       bucket=url_data.netloc,
                                       path=url_data.path[1:],
                                       return_bin=False,
                                       local_file=dest,
                                       action=None,
                                       key=s3_opt(u'key'),
                                       keyid=s3_opt(u'keyid'),
                                       service_url=s3_opt(u'service_url'),
                                       verify_ssl=s3_opt(u'verify_ssl', True),
                                       location=s3_opt(u'location'),
                                       path_style=s3_opt(u'path_style', False),
                                       https_enable=s3_opt(u'https_enable', True))
                return dest
            except Exception as exc:
                raise MinionError(
                    u'Could not fetch from {0}. Exception: {1}'.format(url, exc)
                )
        if url_data.scheme == u'ftp':
            try:
                ftp = ftplib.FTP()
                ftp.connect(url_data.hostname, url_data.port)
                ftp.login(url_data.username, url_data.password)
                with salt.utils.files.fopen(dest, u'wb') as fp_:
                    ftp.retrbinary(u'RETR {0}'.format(url_data.path), fp_.write)
                ftp.quit()
                return dest
            except Exception as exc:
                raise MinionError(u'Could not retrieve {0} from FTP server. Exception: {1}'.format(url, exc))

        if url_data.scheme == u'swift':
            try:
                def swift_opt(key, default):
                    '''
                    Get value of <key> from Minion config or from Pillar
                    '''
                    if key in self.opts:
                        return self.opts[key]
                    try:
                        return self.opts[u'pillar'][key]
                    except (KeyError, TypeError):
                        return default

                swift_conn = SaltSwift(swift_opt(u'keystone.user', None),
                                       swift_opt(u'keystone.tenant', None),
                                       swift_opt(u'keystone.auth_url', None),
                                       swift_opt(u'keystone.password', None))

                swift_conn.get_object(url_data.netloc,
                                      url_data.path[1:],
                                      dest)
                return dest
            except Exception:
                raise MinionError(u'Could not fetch from {0}'.format(url))

        get_kwargs = {}
        if url_data.username is not None \
                and url_data.scheme in (u'http', u'https'):
            netloc = url_data.netloc
            at_sign_pos = netloc.rfind(u'@')
            if at_sign_pos != -1:
                netloc = netloc[at_sign_pos + 1:]
            fixed_url = urlunparse(
                (url_data.scheme, netloc, url_data.path,
                 url_data.params, url_data.query, url_data.fragment))
            get_kwargs[u'auth'] = (url_data.username, url_data.password)
        else:
            fixed_url = url

        destfp = None
        try:
            # Tornado calls streaming_callback on redirect response bodies.
            # But we need streaming to support fetching large files (> RAM
            # avail). Here we are working around this by disabling recording
            # the body for redirections. The issue is fixed in Tornado 4.3.0
            # so on_header callback could be removed when we'll deprecate
            # Tornado<4.3.0. See #27093 and #30431 for details.

            # Use list here to make it writable inside the on_header callback.
            # Simple bool doesn't work here: on_header creates a new local
            # variable instead. This could be avoided in Py3 with 'nonlocal'
            # statement. There is no Py2 alternative for this.
            #
            # write_body[0] is used by the on_chunk callback to tell it whether
            #   or not we need to write the body of the request to disk. For
            #   30x redirects we set this to False because we don't want to
            #   write the contents to disk, as we will need to wait until we
            #   get to the redirected URL.
            #
            # write_body[1] will contain a tornado.httputil.HTTPHeaders
            #   instance that we will use to parse each header line. We
            #   initialize this to False, and after we parse the status line we
            #   will replace it with the HTTPHeaders instance. If/when we have
            #   found the encoding used in the request, we set this value to
            #   False to signify that we are done parsing.
            #
            # write_body[2] is where the encoding will be stored
            write_body = [None, False, None]

            def on_header(hdr):
                if write_body[1] is not False and write_body[2] is None:
                    if not hdr.strip() and 'Content-Type' not in write_body[1]:
                        # If write_body[0] is True, then we are not following a
                        # redirect (initial response was a 200 OK). So there is
                        # no need to reset write_body[0].
                        if write_body[0] is not True:
                            # We are following a redirect, so we need to reset
                            # write_body[0] so that we properly follow it.
                            write_body[0] = None
                        # We don't need the HTTPHeaders object anymore
                        write_body[1] = False
                        return
                    # Try to find out what content type encoding is used if
                    # this is a text file
                    write_body[1].parse_line(hdr)  # pylint: disable=no-member
                    if u'Content-Type' in write_body[1]:
                        content_type = write_body[1].get(u'Content-Type')  # pylint: disable=no-member
                        if not content_type.startswith(u'text'):
                            write_body[1] = write_body[2] = False
                        else:
                            encoding = u'utf-8'
                            fields = content_type.split(u';')
                            for field in fields:
                                if u'encoding' in field:
                                    encoding = field.split(u'encoding=')[-1]
                            write_body[2] = encoding
                            # We have found our encoding. Stop processing headers.
                            write_body[1] = False

                        # If write_body[0] is False, this means that this
                        # header is a 30x redirect, so we need to reset
                        # write_body[0] to None so that we parse the HTTP
                        # status code from the redirect target. Additionally,
                        # we need to reset write_body[2] so that we inspect the
                        # headers for the Content-Type of the URL we're
                        # following.
                        if write_body[0] is write_body[1] is False:
                            write_body[0] = write_body[2] = None

                # Check the status line of the HTTP request
                if write_body[0] is None:
                    try:
                        hdr = parse_response_start_line(hdr)
                    except HTTPInputError:
                        # Not the first line, do nothing
                        return
                    write_body[0] = hdr.code not in [301, 302, 303, 307]
                    write_body[1] = HTTPHeaders()

            if no_cache:
                result = []

                def on_chunk(chunk):
                    if write_body[0]:
                        if write_body[2]:
                            chunk = chunk.decode(write_body[2])
                        result.append(chunk)
            else:
                dest_tmp = u"{0}.part".format(dest)
                # We need an open filehandle to use in the on_chunk callback,
                # that's why we're not using a with clause here.
                destfp = salt.utils.files.fopen(dest_tmp, u'wb')  # pylint: disable=resource-leakage

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
            if u'handle' not in query:
                raise MinionError(u'Error: {0} reading {1}'.format(query[u'error'], url))
            if no_cache:
                if write_body[2]:
                    return u''.join(result)
                return six.b(u'').join(result)
            else:
                destfp.close()
                destfp = None
                salt.utils.files.rename(dest_tmp, dest)
                return dest
        except HTTPError as exc:
            raise MinionError(u'HTTP error {0} reading {1}: {3}'.format(
                exc.code,
                url,
                *BaseHTTPServer.BaseHTTPRequestHandler.responses[exc.code]))
        except URLError as exc:
            raise MinionError(u'Error reading {0}: {1}'.format(url, exc.reason))
        finally:
            if destfp is not None:
                destfp.close()

    def get_template(
            self,
            url,
            dest,
            template=u'jinja',
            makedirs=False,
            saltenv=u'base',
            cachedir=None,
            **kwargs):
        '''
        Cache a file then process it as a template
        '''
        if u'env' in kwargs:
            # "env" is not supported; Use "saltenv".
            kwargs.pop(u'env')

        kwargs[u'saltenv'] = saltenv
        url_data = urlparse(url)
        sfn = self.cache_file(url, saltenv, cachedir=cachedir)
        if not os.path.exists(sfn):
            return u''
        if template in salt.utils.templates.TEMPLATE_REGISTRY:
            data = salt.utils.templates.TEMPLATE_REGISTRY[template](
                sfn,
                **kwargs
            )
        else:
            log.error(
                u'Attempted to render template with unavailable engine %s',
                template
            )
            return u''
        if not data[u'result']:
            # Failed to render the template
            log.error(u'Failed to render template with error: %s', data[u'data'])
            return u''
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
                salt.utils.files.safe_rm(data[u'data'])
                return u''
        shutil.move(data[u'data'], dest)
        return dest

    def _extrn_path(self, url, saltenv, cachedir=None):
        '''
        Return the extrn_filepath for a given url
        '''
        url_data = urlparse(url)
        if salt.utils.platform.is_windows():
            netloc = salt.utils.path.sanitize_win_path(url_data.netloc)
        else:
            netloc = url_data.netloc

        # Strip user:pass from URLs
        netloc = netloc.split(u'@')[-1]

        if cachedir is None:
            cachedir = self.opts[u'cachedir']
        elif not os.path.isabs(cachedir):
            cachedir = os.path.join(self.opts[u'cachedir'], cachedir)

        if url_data.query:
            file_name = u'-'.join([url_data.path, url_data.query])
        else:
            file_name = url_data.path

        return salt.utils.path.join(
            cachedir,
            u'extrn_files',
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

    def _find_file(self, path, saltenv=u'base'):
        '''
        Locate the file path
        '''
        fnd = {u'path': u'',
               u'rel': u''}

        if saltenv not in self.opts[u'file_roots']:
            return fnd
        if salt.utils.url.is_escaped(path):
            # The path arguments are escaped
            path = salt.utils.url.unescape(path)
        for root in self.opts[u'file_roots'][saltenv]:
            full = os.path.join(root, path)
            if os.path.isfile(full):
                fnd[u'path'] = full
                fnd[u'rel'] = path
                return fnd
        return fnd

    def get_file(self,
                 path,
                 dest=u'',
                 makedirs=False,
                 saltenv=u'base',
                 gzip=None,
                 cachedir=None):
        '''
        Copies a file from the local files directory into :param:`dest`
        gzip compression settings are ignored for local files
        '''
        path = self._check_proto(path)
        fnd = self._find_file(path, saltenv)
        fnd_path = fnd.get(u'path')
        if not fnd_path:
            return u''

        return fnd_path

    def file_list(self, saltenv=u'base', prefix=u''):
        '''
        Return a list of files in the given environment
        with optional relative prefix path to limit directory traversal
        '''
        ret = []
        if saltenv not in self.opts[u'file_roots']:
            return ret
        prefix = prefix.strip(u'/')
        for path in self.opts[u'file_roots'][saltenv]:
            for root, dirs, files in os.walk(
                os.path.join(path, prefix), followlinks=True
            ):
                # Don't walk any directories that match file_ignore_regex or glob
                dirs[:] = [d for d in dirs if not salt.fileserver.is_file_ignored(self.opts, d)]
                for fname in files:
                    relpath = os.path.relpath(os.path.join(root, fname), path)
                    ret.append(sdecode(relpath))
        return ret

    def file_list_emptydirs(self, saltenv=u'base', prefix=u''):
        '''
        List the empty dirs in the file_roots
        with optional relative prefix path to limit directory traversal
        '''
        ret = []
        prefix = prefix.strip(u'/')
        if saltenv not in self.opts[u'file_roots']:
            return ret
        for path in self.opts[u'file_roots'][saltenv]:
            for root, dirs, files in os.walk(
                os.path.join(path, prefix), followlinks=True
            ):
                # Don't walk any directories that match file_ignore_regex or glob
                dirs[:] = [d for d in dirs if not salt.fileserver.is_file_ignored(self.opts, d)]
                if len(dirs) == 0 and len(files) == 0:
                    ret.append(sdecode(os.path.relpath(root, path)))
        return ret

    def dir_list(self, saltenv=u'base', prefix=u''):
        '''
        List the dirs in the file_roots
        with optional relative prefix path to limit directory traversal
        '''
        ret = []
        if saltenv not in self.opts[u'file_roots']:
            return ret
        prefix = prefix.strip(u'/')
        for path in self.opts[u'file_roots'][saltenv]:
            for root, dirs, files in os.walk(
                os.path.join(path, prefix), followlinks=True
            ):
                ret.append(sdecode(os.path.relpath(root, path)))
        return ret

    def __get_file_path(self, path, saltenv=u'base'):
        '''
        Return either a file path or the result of a remote find_file call.
        '''
        try:
            path = self._check_proto(path)
        except MinionError as err:
            # Local file path
            if not os.path.isfile(path):
                log.warning(
                    u'specified file %s is not present to generate hash: %s',
                    path, err
                )
                return None
            else:
                return path
        return self._find_file(path, saltenv)

    def hash_file(self, path, saltenv=u'base'):
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
            fnd_path = fnd[u'path']
        except TypeError:
            # Local file path
            fnd_path = fnd

        hash_type = self.opts.get(u'hash_type', u'md5')
        ret[u'hsum'] = salt.utils.hashutils.get_hash(fnd_path, form=hash_type)
        ret[u'hash_type'] = hash_type
        return ret

    def hash_and_stat_file(self, path, saltenv=u'base'):
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
            fnd_path = fnd[u'path']
            fnd_stat = fnd.get(u'stat')
        except TypeError:
            # Local file path
            fnd_path = fnd
            try:
                fnd_stat = list(os.stat(fnd_path))
            except Exception:
                fnd_stat = None

        hash_type = self.opts.get(u'hash_type', u'md5')
        ret[u'hsum'] = salt.utils.hashutils.get_hash(fnd_path, form=hash_type)
        ret[u'hash_type'] = hash_type
        return ret, fnd_stat

    def list_env(self, saltenv=u'base'):
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
        for saltenv in self.opts[u'file_roots']:
            ret.append(saltenv)
        return ret

    def master_tops(self):
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
        if hasattr(self.channel, u'auth'):
            self.auth = self.channel.auth
        else:
            self.auth = u''

    def _refresh_channel(self):
        '''
        Reset the channel, in the event of an interruption
        '''
        self.channel = salt.transport.Channel.factory(self.opts)
        return self.channel

    def get_file(self,
                 path,
                 dest=u'',
                 makedirs=False,
                 saltenv=u'base',
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

        if not salt.utils.platform.is_windows():
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
        if hash_server == u'':
            log.debug(
                u'Could not find file \'%s\' in saltenv \'%s\'',
                path, saltenv
            )
            return False

        # If dest is a directory, rewrite dest with filename
        if dest is not None \
                and (os.path.isdir(dest) or dest.endswith((u'/', u'\\'))):
            dest = os.path.join(dest, os.path.basename(path))
            log.debug(
                u'In saltenv \'%s\', \'%s\' is a directory. Changing dest to '
                u'\'%s\'', saltenv, os.path.dirname(dest), dest
            )

        # Hash compare local copy with master and skip download
        # if no difference found.
        dest2check = dest
        if not dest2check:
            rel_path = self._check_proto(path)

            log.debug(
                u'In saltenv \'%s\', looking at rel_path \'%s\' to resolve '
                u'\'%s\'', saltenv, rel_path, path
            )
            with self._cache_loc(
                    rel_path, saltenv, cachedir=cachedir) as cache_dest:
                dest2check = cache_dest

        log.debug(
            u'In saltenv \'%s\', ** considering ** path \'%s\' to resolve '
            u'\'%s\'', saltenv, dest2check, path
        )

        if dest2check and os.path.isfile(dest2check):
            if not salt.utils.platform.is_windows():
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
                return dest2check

        log.debug(
            u'Fetching file from saltenv \'%s\', ** attempting ** \'%s\'',
            saltenv, path
        )
        d_tries = 0
        transport_tries = 0
        path = self._check_proto(path)
        load = {u'path': path,
                u'saltenv': saltenv,
                u'cmd': u'_serve_file'}
        if gzip:
            gzip = int(gzip)
            load[u'gzip'] = gzip

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
            fn_ = salt.utils.files.fopen(dest, u'wb+')  # pylint: disable=resource-leakage
        else:
            log.debug(u'No dest file found')

        while True:
            if not fn_:
                load[u'loc'] = 0
            else:
                load[u'loc'] = fn_.tell()
            data = self.channel.send(load, raw=True)
            if six.PY3:
                # Sometimes the source is local (eg when using
                # 'salt.fileserver.FSChan'), in which case the keys are
                # already strings. Sometimes the source is remote, in which
                # case the keys are bytes due to raw mode. Standardize on
                # strings for the top-level keys to simplify things.
                data = decode_dict_keys_to_str(data)
            try:
                if not data[u'data']:
                    if not fn_ and data[u'dest']:
                        # This is a 0 byte file on the master
                        with self._cache_loc(
                                data[u'dest'],
                                saltenv,
                                cachedir=cachedir) as cache_dest:
                            dest = cache_dest
                            with salt.utils.files.fopen(cache_dest, u'wb+') as ofile:
                                ofile.write(data[u'data'])
                    if u'hsum' in data and d_tries < 3:
                        # Master has prompted a file verification, if the
                        # verification fails, re-download the file. Try 3 times
                        d_tries += 1
                        hsum = salt.utils.hashutils.get_hash(dest, salt.utils.stringutils.to_str(data.get(u'hash_type', b'md5')))  # future lint: disable=non-unicode-string
                        if hsum != data[u'hsum']:
                            log.warning(
                                u'Bad download of file %s, attempt %d of 3',
                                path, d_tries
                            )
                            continue
                    break
                if not fn_:
                    with self._cache_loc(
                            data[u'dest'],
                            saltenv,
                            cachedir=cachedir) as cache_dest:
                        dest = cache_dest
                        # If a directory was formerly cached at this path, then
                        # remove it to avoid a traceback trying to write the file
                        if os.path.isdir(dest):
                            salt.utils.files.rm_rf(dest)
                        fn_ = salt.utils.files.fopen(dest, u'wb+')
                if data.get(u'gzip', None):
                    data = salt.utils.gzip_util.uncompress(data[u'data'])
                else:
                    data = data[u'data']
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
                    u'Data transport is broken, got: %s, type: %s, '
                    u'exception: %s, attempt %d of 3',
                    data, data_type, exc, transport_tries
                )
                self._refresh_channel()
                if transport_tries > 3:
                    log.error(
                        u'Data transport is broken, got: %s, type: %s, '
                        u'exception: %s, retry attempts exhausted',
                        data, data_type, exc
                    )
                    break

        if fn_:
            fn_.close()
            log.info(
                u'Fetching file from saltenv \'%s\', ** done ** \'%s\'',
                saltenv, path
            )
        else:
            log.debug(
                u'In saltenv \'%s\', we are ** missing ** the file \'%s\'',
                saltenv, path
            )

        return dest

    def file_list(self, saltenv=u'base', prefix=u''):
        '''
        List the files on the master
        '''
        load = {u'saltenv': saltenv,
                u'prefix': prefix,
                u'cmd': u'_file_list'}

        return [sdecode(fn_) for fn_ in self.channel.send(load)]

    def file_list_emptydirs(self, saltenv=u'base', prefix=u''):
        '''
        List the empty dirs on the master
        '''
        load = {u'saltenv': saltenv,
                u'prefix': prefix,
                u'cmd': u'_file_list_emptydirs'}
        self.channel.send(load)

    def dir_list(self, saltenv=u'base', prefix=u''):
        '''
        List the dirs on the master
        '''
        load = {u'saltenv': saltenv,
                u'prefix': prefix,
                u'cmd': u'_dir_list'}
        return self.channel.send(load)

    def symlink_list(self, saltenv=u'base', prefix=u''):
        '''
        List symlinked files and dirs on the master
        '''
        load = {u'saltenv': saltenv,
                u'prefix': prefix,
                u'cmd': u'_symlink_list'}
        return self.channel.send(load)

    def __hash_and_stat_file(self, path, saltenv=u'base'):
        '''
        Common code for hashing and stating files
        '''
        try:
            path = self._check_proto(path)
        except MinionError as err:
            if not os.path.isfile(path):
                log.warning(
                    u'specified file %s is not present to generate hash: %s',
                    path, err
                )
                return {}, None
            else:
                ret = {}
                hash_type = self.opts.get(u'hash_type', u'md5')
                ret[u'hsum'] = salt.utils.hashutils.get_hash(path, form=hash_type)
                ret[u'hash_type'] = hash_type
                return ret
        load = {u'path': path,
                u'saltenv': saltenv,
                u'cmd': u'_file_hash'}
        return self.channel.send(load)

    def hash_file(self, path, saltenv=u'base'):
        '''
        Return the hash of a file, to get the hash of a file on the salt
        master file server prepend the path with salt://<file on server>
        otherwise, prepend the file with / for a local file.
        '''
        return self.__hash_and_stat_file(path, saltenv)

    def hash_and_stat_file(self, path, saltenv=u'base'):
        '''
        The same as hash_file, but also return the file's mode, or None if no
        mode data is present.
        '''
        hash_result = self.hash_file(path, saltenv)
        try:
            path = self._check_proto(path)
        except MinionError as err:
            if not os.path.isfile(path):
                return hash_result, None
            else:
                try:
                    return hash_result, list(os.stat(path))
                except Exception:
                    return hash_result, None
        load = {'path': path,
                'saltenv': saltenv,
                'cmd': '_file_find'}
        fnd = self.channel.send(load)
        try:
            stat_result = fnd.get('stat')
        except AttributeError:
            stat_result = None
        return hash_result, stat_result

    def list_env(self, saltenv=u'base'):
        '''
        Return a list of the files in the file server's specified environment
        '''
        load = {u'saltenv': saltenv,
                u'cmd': u'_file_list'}
        return self.channel.send(load)

    def envs(self):
        '''
        Return a list of available environments
        '''
        load = {u'cmd': u'_file_envs'}
        return self.channel.send(load)

    def master_opts(self):
        '''
        Return the master opts data
        '''
        load = {u'cmd': u'_master_opts'}
        return self.channel.send(load)

    def master_tops(self):
        '''
        Return the metadata derived from the master_tops system
        '''
        load = {u'cmd': u'_master_tops',
                u'id': self.opts[u'id'],
                u'opts': self.opts}
        if self.auth:
            load[u'tok'] = self.auth.gen_token(u'salt')
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
