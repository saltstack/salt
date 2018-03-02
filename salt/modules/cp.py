# -*- coding: utf-8 -*-
'''
Minion side functions for salt-cp
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import base64
import errno
import os
import logging
import fnmatch

# Import salt libs
import salt.minion
import salt.fileclient
import salt.utils.files
import salt.utils.gzip_util
import salt.utils.locales
import salt.utils.path
import salt.utils.templates
import salt.utils.url
import salt.crypt
import salt.transport
from salt.exceptions import CommandExecutionError
from salt.ext.six.moves.urllib.parse import urlparse as _urlparse  # pylint: disable=import-error,no-name-in-module

# Import 3rd-party libs
from salt.ext import six

log = logging.getLogger(__name__)

__proxyenabled__ = ['*']


def _auth():
    '''
    Return the auth object
    '''
    if 'auth' not in __context__:
        __context__['auth'] = salt.crypt.SAuth(__opts__)
    return __context__['auth']


def _gather_pillar(pillarenv, pillar_override):
    '''
    Whenever a state run starts, gather the pillar data fresh
    '''
    pillar = salt.pillar.get_pillar(
        __opts__,
        __grains__,
        __opts__['id'],
        __opts__['saltenv'],
        pillar_override=pillar_override,
        pillarenv=pillarenv
    )
    ret = pillar.compile_pillar()
    if pillar_override and isinstance(pillar_override, dict):
        ret.update(pillar_override)
    return ret


def recv(files, dest):
    '''
    Used with salt-cp, pass the files dict, and the destination.

    This function receives small fast copy files from the master via salt-cp.
    It does not work via the CLI.
    '''
    ret = {}
    for path, data in six.iteritems(files):
        if os.path.basename(path) == os.path.basename(dest) \
                and not os.path.isdir(dest):
            final = dest
        elif os.path.isdir(dest):
            final = os.path.join(dest, os.path.basename(path))
        elif os.path.isdir(os.path.dirname(dest)):
            final = dest
        else:
            return 'Destination unavailable'

        try:
            with salt.utils.files.fopen(final, 'w+') as fp_:
                fp_.write(data)
            ret[final] = True
        except IOError:
            ret[final] = False

    return ret


def recv_chunked(dest, chunk, append=False, compressed=True, mode=None):
    '''
    This function receives files copied to the minion using ``salt-cp`` and is
    not intended to be used directly on the CLI.
    '''
    if 'retcode' not in __context__:
        __context__['retcode'] = 0

    def _error(msg):
        __context__['retcode'] = 1
        return msg

    if chunk is None:
        # dest is an empty dir and needs to be created
        try:
            os.makedirs(dest)
        except OSError as exc:
            if exc.errno == errno.EEXIST:
                if os.path.isfile(dest):
                    return 'Path exists and is a file'
            else:
                return _error(exc.__str__())
        return True

    chunk = base64.b64decode(chunk)

    open_mode = 'ab' if append else 'wb'
    try:
        fh_ = salt.utils.files.fopen(dest, open_mode)  # pylint: disable=W8470
    except (IOError, OSError) as exc:
        if exc.errno != errno.ENOENT:
            # Parent dir does not exist, we need to create it
            return _error(exc.__str__())
        try:
            os.makedirs(os.path.dirname(dest))
        except (IOError, OSError) as makedirs_exc:
            # Failed to make directory
            return _error(makedirs_exc.__str__())
        fh_ = salt.utils.files.fopen(dest, open_mode)  # pylint: disable=W8470

    try:
        # Write the chunk to disk
        fh_.write(salt.utils.gzip_util.uncompress(chunk) if compressed
                  else chunk)
    except (IOError, OSError) as exc:
        # Write failed
        return _error(exc.__str__())
    else:
        # Write successful
        if not append and mode is not None:
            # If this is the first chunk we're writing, set the mode
            #log.debug('Setting mode for %s to %s', dest, oct(mode))
            log.debug('Setting mode for %s to %s', dest, mode)
            try:
                os.chmod(dest, mode)
            except OSError:
                return _error(exc.__str__())
        return True
    finally:
        try:
            fh_.close()
        except AttributeError:
            pass


def _mk_client():
    '''
    Create a file client and add it to the context.

    Each file client needs to correspond to a unique copy
    of the opts dictionary, therefore it's hashed by the
    id of the __opts__ dict
    '''
    if 'cp.fileclient_{0}'.format(id(__opts__)) not in __context__:
        __context__['cp.fileclient_{0}'.format(id(__opts__))] = \
                salt.fileclient.get_file_client(__opts__)


def _client():
    '''
    Return a client, hashed by the list of masters
    '''
    _mk_client()
    return __context__['cp.fileclient_{0}'.format(id(__opts__))]


def _render_filenames(path, dest, saltenv, template, **kw):
    '''
    Process markup in the :param:`path` and :param:`dest` variables (NOT the
    files under the paths they ultimately point to) according to the markup
    format provided by :param:`template`.
    '''
    if not template:
        return (path, dest)

    # render the path as a template using path_template_engine as the engine
    if template not in salt.utils.templates.TEMPLATE_REGISTRY:
        raise CommandExecutionError(
            'Attempted to render file paths with unavailable engine '
            '{0}'.format(template)
        )

    kwargs = {}
    kwargs['salt'] = __salt__
    if 'pillarenv' in kw or 'pillar' in kw:
        pillarenv = kw.get('pillarenv', __opts__.get('pillarenv'))
        kwargs['pillar'] = _gather_pillar(pillarenv, kw.get('pillar'))
    else:
        kwargs['pillar'] = __pillar__
    kwargs['grains'] = __grains__
    kwargs['opts'] = __opts__
    kwargs['saltenv'] = saltenv

    def _render(contents):
        '''
        Render :param:`contents` into a literal pathname by writing it to a
        temp file, rendering that file, and returning the result.
        '''
        # write out path to temp file
        tmp_path_fn = salt.utils.files.mkstemp()
        with salt.utils.files.fopen(tmp_path_fn, 'w+') as fp_:
            fp_.write(salt.utils.stringutils.to_str(contents))
        data = salt.utils.templates.TEMPLATE_REGISTRY[template](
            tmp_path_fn,
            to_str=True,
            **kwargs
        )
        salt.utils.files.safe_rm(tmp_path_fn)
        if not data['result']:
            # Failed to render the template
            raise CommandExecutionError(
                'Failed to render file path with error: {0}'.format(
                    data['data']
                )
            )
        else:
            return data['data']

    path = _render(path)
    dest = _render(dest)
    return (path, dest)


def get_file(path,
             dest,
             saltenv='base',
             makedirs=False,
             template=None,
             gzip=None,
             **kwargs):
    '''
    .. versionchanged:: 2018.3.0
        ``dest`` can now be a directory

    Used to get a single file from the salt master

    CLI Example:

    .. code-block:: bash

        salt '*' cp.get_file salt://path/to/file /minion/dest

    Template rendering can be enabled on both the source and destination file
    names like so:

    .. code-block:: bash

        salt '*' cp.get_file "salt://{{grains.os}}/vimrc" /etc/vimrc template=jinja

    This example would instruct all Salt minions to download the vimrc from a
    directory with the same name as their os grain and copy it to /etc/vimrc

    For larger files, the cp.get_file module also supports gzip compression.
    Because gzip is CPU-intensive, this should only be used in scenarios where
    the compression ratio is very high (e.g. pretty-printed JSON or YAML
    files).

    Use the *gzip* named argument to enable it.  Valid values are 1..9, where 1
    is the lightest compression and 9 the heaviest.  1 uses the least CPU on
    the master (and minion), 9 uses the most.

    There are two ways of defining the fileserver environment (a.k.a.
    ``saltenv``) from which to retrieve the file. One is to use the ``saltenv``
    parameter, and the other is to use a querystring syntax in the ``salt://``
    URL. The below two examples are equivalent:

    .. code-block:: bash

        salt '*' cp.get_file salt://foo/bar.conf /etc/foo/bar.conf saltenv=config
        salt '*' cp.get_file salt://foo/bar.conf?saltenv=config /etc/foo/bar.conf

    .. note::
        It may be necessary to quote the URL when using the querystring method,
        depending on the shell being used to run the command.
    '''
    (path, dest) = _render_filenames(path, dest, saltenv, template, **kwargs)

    path, senv = salt.utils.url.split_env(path)
    if senv:
        saltenv = senv

    if not hash_file(path, saltenv):
        return ''
    else:
        return _client().get_file(
                path,
                dest,
                makedirs,
                saltenv,
                gzip)


def get_template(path,
                 dest,
                 template='jinja',
                 saltenv='base',
                 makedirs=False,
                 **kwargs):
    '''
    Render a file as a template before setting it down.
    Warning, order is not the same as in fileclient.cp for
    non breaking old API.

    CLI Example:

    .. code-block:: bash

        salt '*' cp.get_template salt://path/to/template /minion/dest
    '''
    if 'salt' not in kwargs:
        kwargs['salt'] = __salt__
    if 'pillar' not in kwargs:
        kwargs['pillar'] = __pillar__
    if 'grains' not in kwargs:
        kwargs['grains'] = __grains__
    if 'opts' not in kwargs:
        kwargs['opts'] = __opts__
    return _client().get_template(
            path,
            dest,
            template,
            makedirs,
            saltenv,
            **kwargs)


def get_dir(path, dest, saltenv='base', template=None, gzip=None, **kwargs):
    '''
    Used to recursively copy a directory from the salt master

    CLI Example:

    .. code-block:: bash

        salt '*' cp.get_dir salt://path/to/dir/ /minion/dest

    get_dir supports the same template and gzip arguments as get_file.
    '''
    (path, dest) = _render_filenames(path, dest, saltenv, template, **kwargs)

    return _client().get_dir(path, dest, saltenv, gzip)


def get_url(path, dest='', saltenv='base', makedirs=False, source_hash=None):
    '''
    .. versionchanged:: 2018.3.0
        ``dest`` can now be a directory

    Used to get a single file from a URL.

    path
        A URL to download a file from. Supported URL schemes are: ``salt://``,
        ``http://``, ``https://``, ``ftp://``, ``s3://``, ``swift://`` and
        ``file://`` (local filesystem). If no scheme was specified, this is
        equivalent of using ``file://``.
        If a ``file://`` URL is given, the function just returns absolute path
        to that file on a local filesystem.
        The function returns ``False`` if Salt was unable to fetch a file from
        a ``salt://`` URL.

    dest
        The default behaviour is to write the fetched file to the given
        destination path. If this parameter is omitted or set as empty string
        (``''``), the function places the remote file on the local filesystem
        inside the Minion cache directory and returns the path to that file.

        .. note::

            To simply return the file contents instead, set destination to
            ``None``. This works with ``salt://``, ``http://``, ``https://``
            and ``file://`` URLs. The files fetched by ``http://`` and
            ``https://`` will not be cached.

    saltenv : base
        Salt fileserver envrionment from which to retrieve the file. Ignored if
        ``path`` is not a ``salt://`` URL.

    source_hash
        If ``path`` is an http(s) or ftp URL and the file exists in the
        minion's file cache, this option can be passed to keep the minion from
        re-downloading the file if the cached copy matches the specified hash.

        .. versionadded:: 2018.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' cp.get_url salt://my/file /tmp/this_file_is_mine
        salt '*' cp.get_url http://www.slashdot.org /tmp/index.html
    '''
    if isinstance(dest, six.string_types):
        result = _client().get_url(
            path, dest, makedirs, saltenv, source_hash=source_hash)
    else:
        result = _client().get_url(
            path, None, makedirs, saltenv, no_cache=True, source_hash=source_hash)
    if not result:
        log.error('Unable to fetch file %s from saltenv %s.', path, saltenv)
    return result


def get_file_str(path, saltenv='base'):
    '''
    Download a file from a URL to the Minion cache directory and return the
    contents of that file

    Returns ``False`` if Salt was unable to cache a file from a URL.

    CLI Example:

    .. code-block:: bash

        salt '*' cp.get_file_str salt://my/file
    '''
    fn_ = cache_file(path, saltenv)
    if isinstance(fn_, six.string_types):
        try:
            with salt.utils.files.fopen(fn_, 'r') as fp_:
                return fp_.read()
        except IOError:
            return False
    return fn_


def cache_file(path, saltenv='base', source_hash=None):
    '''
    Used to cache a single file on the Minion

    Returns the location of the new cached file on the Minion

    source_hash
        If ``name`` is an http(s) or ftp URL and the file exists in the
        minion's file cache, this option can be passed to keep the minion from
        re-downloading the file if the cached copy matches the specified hash.

        .. versionadded:: 2018.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' cp.cache_file salt://path/to/file

    There are two ways of defining the fileserver environment (a.k.a.
    ``saltenv``) from which to cache the file. One is to use the ``saltenv``
    parameter, and the other is to use a querystring syntax in the ``salt://``
    URL. The below two examples are equivalent:

    .. code-block:: bash

        salt '*' cp.cache_file salt://foo/bar.conf saltenv=config
        salt '*' cp.cache_file salt://foo/bar.conf?saltenv=config

    If the path being cached is a ``salt://`` URI, and the path does not exist,
    then ``False`` will be returned.

    .. note::
        It may be necessary to quote the URL when using the querystring method,
        depending on the shell being used to run the command.
    '''
    path = salt.utils.locales.sdecode(path)
    saltenv = salt.utils.locales.sdecode(saltenv)

    contextkey = '{0}_|-{1}_|-{2}'.format('cp.cache_file', path, saltenv)

    path_is_remote = _urlparse(path).scheme in ('http', 'https', 'ftp')
    try:
        if path_is_remote and contextkey in __context__:
            # Prevent multiple caches in the same salt run. Affects remote URLs
            # since the master won't know their hash, so the fileclient
            # wouldn't be able to prevent multiple caches if we try to cache
            # the remote URL more than once.
            if os.path.isfile(__context__[contextkey]):
                return __context__[contextkey]
            else:
                # File is in __context__ but no longer exists in the minion
                # cache, get rid of the context key and re-cache below.
                # Accounts for corner case where file is removed from minion
                # cache between cp.cache_file calls in the same salt-run.
                __context__.pop(contextkey)
    except AttributeError:
        pass

    path, senv = salt.utils.url.split_env(path)
    if senv:
        saltenv = senv

    result = _client().cache_file(path, saltenv, source_hash=source_hash)
    if not result:
        log.error(
            'Unable to cache file \'%s\' from saltenv \'%s\'.',
            path, saltenv
        )
    if path_is_remote:
        # Cache was successful, store the result in __context__ to prevent
        # multiple caches (see above).
        __context__[contextkey] = result
    return result


def cache_files(paths, saltenv='base'):
    '''
    Used to gather many files from the Master, the gathered files will be
    saved in the minion cachedir reflective to the paths retrieved from the
    Master

    CLI Example:

    .. code-block:: bash

        salt '*' cp.cache_files salt://pathto/file1,salt://pathto/file1

    There are two ways of defining the fileserver environment (a.k.a.
    ``saltenv``) from which to cache the files. One is to use the ``saltenv``
    parameter, and the other is to use a querystring syntax in the ``salt://``
    URL. The below two examples are equivalent:

    .. code-block:: bash

        salt '*' cp.cache_files salt://foo/bar.conf,salt://foo/baz.conf saltenv=config
        salt '*' cp.cache_files salt://foo/bar.conf?saltenv=config,salt://foo/baz.conf?saltenv=config

    The querystring method is less useful when all files are being cached from
    the same environment, but is a good way of caching files from multiple
    different environments in the same command. For example, the below command
    will cache the first file from the ``config1`` environment, and the second
    one from the ``config2`` environment.

    .. code-block:: bash

        salt '*' cp.cache_files salt://foo/bar.conf?saltenv=config1,salt://foo/bar.conf?saltenv=config2

    .. note::
        It may be necessary to quote the URL when using the querystring method,
        depending on the shell being used to run the command.
    '''
    return _client().cache_files(paths, saltenv)


def cache_dir(path, saltenv='base', include_empty=False, include_pat=None,
              exclude_pat=None):
    '''
    Download and cache everything under a directory from the master


    include_pat : None
        Glob or regex to narrow down the files cached from the given path. If
        matching with a regex, the regex must be prefixed with ``E@``,
        otherwise the expression will be interpreted as a glob.

        .. versionadded:: 2014.7.0

    exclude_pat : None
        Glob or regex to exclude certain files from being cached from the given
        path. If matching with a regex, the regex must be prefixed with ``E@``,
        otherwise the expression will be interpreted as a glob.

        .. note::

            If used with ``include_pat``, files matching this pattern will be
            excluded from the subset of files defined by ``include_pat``.

        .. versionadded:: 2014.7.0


    CLI Examples:

    .. code-block:: bash

        salt '*' cp.cache_dir salt://path/to/dir
        salt '*' cp.cache_dir salt://path/to/dir include_pat='E@*.py$'
    '''
    return _client().cache_dir(
        path, saltenv, include_empty, include_pat, exclude_pat
    )


def cache_master(saltenv='base'):
    '''
    Retrieve all of the files on the master and cache them locally

    CLI Example:

    .. code-block:: bash

        salt '*' cp.cache_master
    '''
    return _client().cache_master(saltenv)


def cache_local_file(path):
    '''
    Cache a local file on the minion in the localfiles cache

    CLI Example:

    .. code-block:: bash

        salt '*' cp.cache_local_file /etc/hosts
    '''
    if not os.path.exists(path):
        return ''

    path_cached = is_cached(path)

    # If the file has already been cached, return the path
    if path_cached:
        path_hash = hash_file(path)
        path_cached_hash = hash_file(path_cached)

        if path_hash['hsum'] == path_cached_hash['hsum']:
            return path_cached

    # The file hasn't been cached or has changed; cache it
    return _client().cache_local_file(path)


def list_states(saltenv='base'):
    '''
    List all of the available state modules in an environment

    CLI Example:

    .. code-block:: bash

        salt '*' cp.list_states
    '''
    return _client().list_states(saltenv)


def list_master(saltenv='base', prefix=''):
    '''
    List all of the files stored on the master

    CLI Example:

    .. code-block:: bash

        salt '*' cp.list_master
    '''
    return _client().file_list(saltenv, prefix)


def list_master_dirs(saltenv='base', prefix=''):
    '''
    List all of the directories stored on the master

    CLI Example:

    .. code-block:: bash

        salt '*' cp.list_master_dirs
    '''
    return _client().dir_list(saltenv, prefix)


def list_master_symlinks(saltenv='base', prefix=''):
    '''
    List all of the symlinks stored on the master

    CLI Example:

    .. code-block:: bash

        salt '*' cp.list_master_symlinks
    '''
    return _client().symlink_list(saltenv, prefix)


def list_minion(saltenv='base'):
    '''
    List all of the files cached on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' cp.list_minion
    '''
    return _client().file_local_list(saltenv)


def is_cached(path, saltenv='base'):
    '''
    Return a boolean if the given path on the master has been cached on the
    minion

    CLI Example:

    .. code-block:: bash

        salt '*' cp.is_cached salt://path/to/file
    '''
    return _client().is_cached(path, saltenv)


def hash_file(path, saltenv='base'):
    '''
    Return the hash of a file, to get the hash of a file on the
    salt master file server prepend the path with salt://<file on server>
    otherwise, prepend the file with / for a local file.

    CLI Example:

    .. code-block:: bash

        salt '*' cp.hash_file salt://path/to/file
    '''
    path, senv = salt.utils.url.split_env(path)
    if senv:
        saltenv = senv

    return _client().hash_file(path, saltenv)


def stat_file(path, saltenv='base', octal=True):
    '''
    Return the permissions of a file, to get the permissions of a file on the
    salt master file server prepend the path with salt://<file on server>
    otherwise, prepend the file with / for a local file.

    CLI Example:

    .. code-block:: bash

        salt '*' cp.stat_file salt://path/to/file
    '''
    path, senv = salt.utils.url.split_env(path)
    if senv:
        saltenv = senv

    stat = _client().hash_and_stat_file(path, saltenv)[1]
    if stat is None:
        return stat
    return salt.utils.files.st_mode_to_octal(stat[0]) if octal is True else stat[0]


def push(path, keep_symlinks=False, upload_path=None, remove_source=False):
    '''
    WARNING Files pushed to the master will have global read permissions..

    Push a file from the minion up to the master, the file will be saved to
    the salt master in the master's minion files cachedir
    (defaults to ``/var/cache/salt/master/minions/minion-id/files``)

    Since this feature allows a minion to push a file up to the master server
    it is disabled by default for security purposes. To enable, set
    ``file_recv`` to ``True`` in the master configuration file, and restart the
    master.

    keep_symlinks
        Keep the path value without resolving its canonical form

    upload_path
        Provide a different path inside the master's minion files cachedir

    remove_source
        Remove the source file on the minion

        .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' cp.push /etc/fstab
        salt '*' cp.push /etc/system-release keep_symlinks=True
        salt '*' cp.push /etc/fstab upload_path='/new/path/fstab'
        salt '*' cp.push /tmp/filename remove_source=True
    '''
    log.debug('Trying to copy \'%s\' to master', path)
    if '../' in path or not os.path.isabs(path):
        log.debug('Path must be absolute, returning False')
        return False
    if not keep_symlinks:
        path = os.path.realpath(path)
    if not os.path.isfile(path):
        log.debug('Path failed os.path.isfile check, returning False')
        return False
    auth = _auth()

    if upload_path:
        if '../' in upload_path:
            log.debug('Path must be absolute, returning False')
            log.debug('Bad path: %s', upload_path)
            return False
        load_path = upload_path.lstrip(os.sep)
    else:
        load_path = path.lstrip(os.sep)
    # Normalize the path. This does not eliminate
    # the possibility that relative entries will still be present
    load_path_normal = os.path.normpath(load_path)

    # If this is Windows and a drive letter is present, remove it
    load_path_split_drive = os.path.splitdrive(load_path_normal)[1]

    # Finally, split the remaining path into a list for delivery to the master
    load_path_list = [_f for _f in load_path_split_drive.split(os.sep) if _f]

    load = {'cmd': '_file_recv',
            'id': __opts__['id'],
            'path': load_path_list,
            'tok': auth.gen_token(b'salt')}
    channel = salt.transport.Channel.factory(__opts__)
    with salt.utils.files.fopen(path, 'rb') as fp_:
        init_send = False
        while True:
            load['loc'] = fp_.tell()
            load['data'] = fp_.read(__opts__['file_buffer_size'])
            if not load['data'] and init_send:
                if remove_source:
                    try:
                        salt.utils.files.rm_rf(path)
                        log.debug('Removing source file \'%s\'', path)
                    except IOError:
                        log.error('cp.push failed to remove file \'%s\'', path)
                        return False
                return True
            ret = channel.send(load)
            if not ret:
                log.error('cp.push Failed transfer failed. Ensure master has '
                          '\'file_recv\' set to \'True\' and that the file '
                          'is not larger than the \'file_recv_size_max\' '
                          'setting on the master.')
                return ret
            init_send = True


def push_dir(path, glob=None, upload_path=None):
    '''
    Push a directory from the minion up to the master, the files will be saved
    to the salt master in the master's minion files cachedir (defaults to
    ``/var/cache/salt/master/minions/minion-id/files``).  It also has a glob
    for matching specific files using globbing.

    .. versionadded:: 2014.7.0

    Since this feature allows a minion to push files up to the master server it
    is disabled by default for security purposes. To enable, set ``file_recv``
    to ``True`` in the master configuration file, and restart the master.

    upload_path
        Provide a different path and directory name inside the master's minion
        files cachedir

    CLI Example:

    .. code-block:: bash

        salt '*' cp.push /usr/lib/mysql
        salt '*' cp.push /usr/lib/mysql upload_path='/newmysql/path'
        salt '*' cp.push_dir /etc/modprobe.d/ glob='*.conf'
    '''
    if '../' in path or not os.path.isabs(path):
        return False
    tmpupload_path = upload_path
    path = os.path.realpath(path)
    if os.path.isfile(path):
        return push(path, upload_path=upload_path)
    else:
        filelist = []
        for root, _, files in salt.utils.path.os_walk(path):
            filelist += [os.path.join(root, tmpfile) for tmpfile in files]
        if glob is not None:
            filelist = [fi for fi in filelist if fnmatch.fnmatch(os.path.basename(fi), glob)]
        if not filelist:
            return False
        for tmpfile in filelist:
            if upload_path and tmpfile.startswith(path):
                tmpupload_path = os.path.join(os.path.sep,
                                              upload_path.strip(os.path.sep),
                                              tmpfile.replace(path, '')
                                              .strip(os.path.sep))
            ret = push(tmpfile, upload_path=tmpupload_path)
            if not ret:
                return ret
    return True
