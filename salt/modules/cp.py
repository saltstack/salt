# -*- coding: utf-8 -*-
'''
Minion side functions for salt-cp
'''

# Import python libs
import os
import logging
import fnmatch

# Import salt libs
import salt.minion
import salt.fileclient
import salt.utils
import salt.crypt
import salt.transport
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)


def _auth():
    '''
    Return the auth object
    '''
    if 'auth' not in __context__:
        __context__['auth'] = salt.crypt.SAuth(__opts__)
    return __context__['auth']


def recv(files, dest):
    '''
    Used with salt-cp, pass the files dict, and the destination.

    This function receives small fast copy files from the master via salt-cp.
    It does not work via the CLI.
    '''
    ret = {}
    for path, data in files.items():
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
            salt.utils.fopen(final, 'w+').write(data)
            ret[final] = True
        except IOError:
            ret[final] = False

    return ret


def _mk_client():
    '''
    Create a file client and add it to the context
    '''
    if 'cp.fileclient' not in __context__:
        __context__['cp.fileclient'] = \
                salt.fileclient.get_file_client(__opts__)


def _render_filenames(path, dest, saltenv, template):
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
    kwargs['pillar'] = __pillar__
    kwargs['grains'] = __grains__
    kwargs['opts'] = __opts__
    kwargs['saltenv'] = saltenv

    def _render(contents):
        # write out path to temp file
        tmp_path_fn = salt.utils.mkstemp()
        with salt.utils.fopen(tmp_path_fn, 'w+') as fp_:
            fp_.write(contents)
        data = salt.utils.templates.TEMPLATE_REGISTRY[template](
            tmp_path_fn,
            to_str=True,
            **kwargs
        )
        salt.utils.safe_rm(tmp_path_fn)
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
             env=None):
    '''
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
    '''
    if env is not None:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        # Backwards compatibility
        saltenv = env

    (path, dest) = _render_filenames(path, dest, saltenv, template)

    if not hash_file(path, saltenv):
        return ''
    else:
        _mk_client()
        return __context__['cp.fileclient'].get_file(
                path,
                dest,
                makedirs,
                saltenv,
                gzip)


def get_template(path,
                 dest,
                 template='jinja',
                 saltenv='base',
                 env=None,
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
    if env is not None:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        # Backwards compatibility
        saltenv = env

    _mk_client()
    if 'salt' not in kwargs:
        kwargs['salt'] = __salt__
    if 'pillar' not in kwargs:
        kwargs['pillar'] = __pillar__
    if 'grains' not in kwargs:
        kwargs['grains'] = __grains__
    if 'opts' not in kwargs:
        kwargs['opts'] = __opts__
    return __context__['cp.fileclient'].get_template(
            path,
            dest,
            template,
            makedirs,
            saltenv,
            **kwargs)


def get_dir(path, dest, saltenv='base', template=None, gzip=None, env=None):
    '''
    Used to recursively copy a directory from the salt master

    CLI Example:

    .. code-block:: bash

        salt '*' cp.get_dir salt://path/to/dir/ /minion/dest

    get_dir supports the same template and gzip arguments as get_file.
    '''
    if env is not None:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        # Backwards compatibility
        saltenv = env

    (path, dest) = _render_filenames(path, dest, saltenv, template)

    _mk_client()
    return __context__['cp.fileclient'].get_dir(path, dest, saltenv, gzip)


def get_url(path, dest, saltenv='base', env=None):
    '''
    Used to get a single file from a URL.

    CLI Example:

    .. code-block:: bash

        salt '*' cp.get_url salt://my/file /tmp/mine
        salt '*' cp.get_url http://www.slashdot.org /tmp/index.html
    '''
    if env is not None:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        # Backwards compatibility
        saltenv = env

    _mk_client()
    return __context__['cp.fileclient'].get_url(path, dest, False, saltenv)


def get_file_str(path, saltenv='base', env=None):
    '''
    Return the contents of a file from a URL

    CLI Example:

    .. code-block:: bash

        salt '*' cp.get_file_str salt://my/file
    '''
    if env is not None:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        # Backwards compatibility
        saltenv = env

    fn_ = cache_file(path, saltenv)
    with salt.utils.fopen(fn_, 'r') as fp_:
        data = fp_.read()
    return data


def cache_file(path, saltenv='base', env=None):
    '''
    Used to cache a single file on the salt-minion
    Returns the location of the new cached file on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' cp.cache_file salt://path/to/file
    '''
    if env is not None:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        # Backwards compatibility
        saltenv = env

    _mk_client()
    if path.startswith('salt://|'):
        # Strip pipe. Windows doesn't allow pipes in filenames
        path = 'salt://{0}'.format(path[8:])
    env_splitter = '?saltenv='
    if '?env=' in path:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using '
            '\'saltenv\' not \'env\'. This functionality will be '
            'removed in Salt Boron.'
        )
        env_splitter = '?env='
    try:
        path, saltenv = path.split(env_splitter)
    except ValueError:
        pass
    result = __context__['cp.fileclient'].cache_file(path, saltenv)
    if not result:
        log.error(
            'Unable to cache file {0!r} from saltenv {1!r}.'.format(
                path, saltenv
            )
        )
    return result


def cache_files(paths, saltenv='base', env=None):
    '''
    Used to gather many files from the master, the gathered files will be
    saved in the minion cachedir reflective to the paths retrieved from the
    master.

    CLI Example:

    .. code-block:: bash

        salt '*' cp.cache_files salt://pathto/file1,salt://pathto/file1
    '''
    if env is not None:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        # Backwards compatibility
        saltenv = env

    _mk_client()
    return __context__['cp.fileclient'].cache_files(paths, saltenv)


def cache_dir(path, saltenv='base', include_empty=False, include_pat=None,
              exclude_pat=None, env=None):
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
    if env is not None:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        # Backwards compatibility
        saltenv = env

    _mk_client()
    return __context__['cp.fileclient'].cache_dir(
        path, saltenv, include_empty, include_pat, exclude_pat
    )


def cache_master(saltenv='base', env=None):
    '''
    Retrieve all of the files on the master and cache them locally

    CLI Example:

    .. code-block:: bash

        salt '*' cp.cache_master
    '''
    if env is not None:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        # Backwards compatibility
        saltenv = env

    _mk_client()
    return __context__['cp.fileclient'].cache_master(saltenv)


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
    _mk_client()
    return __context__['cp.fileclient'].cache_local_file(path)


def list_states(saltenv='base', env=None):
    '''
    List all of the available state modules in an environment

    CLI Example:

    .. code-block:: bash

        salt '*' cp.list_states
    '''
    if env is not None:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        # Backwards compatibility
        saltenv = env

    _mk_client()
    return __context__['cp.fileclient'].list_states(saltenv)


def list_master(saltenv='base', prefix='', env=None):
    '''
    List all of the files stored on the master

    CLI Example:

    .. code-block:: bash

        salt '*' cp.list_master
    '''
    if env is not None:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        # Backwards compatibility
        saltenv = env

    _mk_client()
    return __context__['cp.fileclient'].file_list(saltenv, prefix)


def list_master_dirs(saltenv='base', prefix='', env=None):
    '''
    List all of the directories stored on the master

    CLI Example:

    .. code-block:: bash

        salt '*' cp.list_master_dirs
    '''
    if env is not None:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        # Backwards compatibility
        saltenv = env

    _mk_client()
    return __context__['cp.fileclient'].dir_list(saltenv, prefix)


def list_master_symlinks(saltenv='base', prefix='', env=None):
    '''
    List all of the symlinks stored on the master

    CLI Example:

    .. code-block:: bash

        salt '*' cp.list_master_symlinks
    '''
    if env is not None:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        # Backwards compatibility
        saltenv = env

    _mk_client()
    return __context__['cp.fileclient'].symlink_list(saltenv, prefix)


def list_minion(saltenv='base', env=None):
    '''
    List all of the files cached on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' cp.list_minion
    '''
    if env is not None:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        # Backwards compatibility
        saltenv = env

    _mk_client()
    return __context__['cp.fileclient'].file_local_list(saltenv)


def is_cached(path, saltenv='base', env=None):
    '''
    Return a boolean if the given path on the master has been cached on the
    minion

    CLI Example:

    .. code-block:: bash

        salt '*' cp.is_cached salt://path/to/file
    '''
    if env is not None:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        # Backwards compatibility
        saltenv = env

    _mk_client()
    return __context__['cp.fileclient'].is_cached(path, saltenv)


def hash_file(path, saltenv='base', env=None):
    '''
    Return the hash of a file, to get the hash of a file on the
    salt master file server prepend the path with salt://<file on server>
    otherwise, prepend the file with / for a local file.

    CLI Example:

    .. code-block:: bash

        salt '*' cp.hash_file salt://path/to/file
    '''
    if env is not None:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        # Backwards compatibility
        saltenv = env

    _mk_client()
    return __context__['cp.fileclient'].hash_file(path, saltenv)


def push(path):
    '''
    Push a file from the minion up to the master, the file will be saved to
    the salt master in the master's minion files cachedir
    (defaults to ``/var/cache/salt/master/minions/minion-id/files``)

    Since this feature allows a minion to push a file up to the master server
    it is disabled by default for security purposes. To enable, set
    ``file_recv`` to ``True`` in the master configuration file, and restart the
    master.

    CLI Example:

    .. code-block:: bash

        salt '*' cp.push /etc/fstab
    '''
    log.debug('Trying to copy {0!r} to master'.format(path))
    if '../' in path or not os.path.isabs(path):
        log.debug('Path must be absolute, returning False')
        return False
    path = os.path.realpath(path)
    if not os.path.isfile(path):
        log.debug('Path failed os.path.isfile check, returning False')
        return False
    auth = _auth()

    load = {'cmd': '_file_recv',
            'id': __opts__['id'],
            'path': path.lstrip(os.sep),
            'tok': auth.gen_token('salt')}
    sreq = salt.transport.Channel.factory(__opts__)
    with salt.utils.fopen(path, 'rb') as fp_:
        while True:
            load['loc'] = fp_.tell()
            load['data'] = fp_.read(__opts__['file_buffer_size'])
            if not load['data']:
                return True
            ret = sreq.send(load)
            if not ret:
                log.error('cp.push Failed transfer failed. Ensure master has '
                '\'file_recv\' set to \'True\' and that the file is not '
                'larger than the \'file_recv_size_max\' setting on the master.')
                return ret


def push_dir(path, glob=None):
    '''
    Push a directory from the minion up to the master, the files will be saved
    to the salt master in the master's minion files cachedir (defaults to
    ``/var/cache/salt/master/minions/minion-id/files``).  It also has a glob
    for matching specific files using globbing.

    .. versionadded:: 2014.7.0

    Since this feature allows a minion to push files up to the master server it
    is disabled by default for security purposes. To enable, set ``file_recv``
    to ``True`` in the master configuration file, and restart the master.

    CLI Example:

    .. code-block:: bash

        salt '*' cp.push /usr/lib/mysql
        salt '*' cp.push_dir /etc/modprobe.d/ glob='*.conf'
    '''
    if '../' in path or not os.path.isabs(path):
        return False
    path = os.path.realpath(path)
    if os.path.isfile(path):
        return push(path)
    else:
        filelist = []
        for root, dirs, files in os.walk(path):
            filelist += [os.path.join(root, tmpfile) for tmpfile in files]
        if glob is not None:
            filelist = filter(lambda fi: fnmatch.fnmatch(fi, glob), filelist)
        for tmpfile in filelist:
            ret = push(tmpfile)
            if not ret:
                return ret
    return True
