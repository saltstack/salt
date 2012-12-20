'''
Minion side functions for salt-cp
'''

# Import python libs
import os
import logging

# Import salt libs
import salt.minion
import salt.fileclient
import salt.utils
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)


def recv(files, dest):
    '''
    Used with salt-cp, pass the files dict, and the destination.

    This function receives small fast copy files from the master via salt-cp
    '''
    ret = {}
    for path, data in files.items():
        if os.path.basename(path) == os.path.basename(dest)\
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
    if not 'cp.fileclient' in __context__:
        __context__['cp.fileclient'] = salt.fileclient.get_file_client(__opts__)


def _render_filenames(path, dest, env, template):
    if not template:
        return (path, dest)

    # render the path as a template using path_template_engine as the engine
    if template not in salt.utils.templates.template_registry:
        raise CommandExecutionError(
            'Attempted to render file paths with unavailable engine '
            '{0}'.format(template)
        )

    kwargs = {}
    kwargs['salt'] = __salt__
    kwargs['pillar'] = __pillar__
    kwargs['grains'] = __grains__
    kwargs['opts'] = __opts__
    kwargs['env'] = env

    def _render(contents):
        # write out path to temp file
        tmp_path_fn = salt.utils.mkstemp()
        with salt.utils.fopen(tmp_path_fn, 'w+') as fp_:
            fp_.write(contents)
        data = salt.utils.templates.template_registry[template](
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


def get_file(path, dest, env='base', makedirs=False, template=None, gzip=None):
    '''
    Used to get a single file from the salt master

    CLI Example::

        salt '*' cp.get_file salt://path/to/file /minion/dest

    Template rendering can be enabled on both the source and destination file names
    like so::

        salt '*' cp.get_file "salt://{{grains.os}}/vimrc" /etc/vimrc template=jinja

    This example would instruct all Salt minions to download the vimrc from a
    directory with the same name as their os grain and copy it to /etc/vimrc

    For larger files, the cp.get_file module also supports gzip compression.
    Because gzip is CPU-intensive, this should only be used in
    scenarios where the compression ratio is very high (e.g. pretty-printed JSON
    or YAML files).

    Use the *gzip* named argument to enable it.  Valid values are 1..9,
    where 1 is the lightest compression and 9 the heaviest.  1 uses the least CPU
    on the master (and minion), 9 uses the most.
    '''
    (path, dest) = _render_filenames(path, dest, env, template)

    if not hash_file(path, env):
        return ''
    else:
        _mk_client()
        return __context__['cp.fileclient'].get_file(
                path,
                dest,
                makedirs,
                env,
                gzip)


def get_template(path, dest, template='jinja', env='base', **kwargs):
    '''
    Render a file as a template before setting it down

    CLI Example::

        salt '*' cp.get_template salt://path/to/template /minion/dest
    '''
    _mk_client()
    if not 'salt' in kwargs:
        kwargs['salt'] = __salt__
    if not 'pillar' in kwargs:
        kwargs['pillar'] = __pillar__
    if not 'grains' in kwargs:
        kwargs['grains'] = __grains__
    if not 'opts' in kwargs:
        kwargs['opts'] = __opts__
    return __context__['cp.fileclient'].get_template(
            path,
            dest,
            template,
            False,
            env,
            **kwargs)


def get_dir(path, dest, env='base', template=None, gzip=None):
    '''
    Used to recursively copy a directory from the salt master

    CLI Example::

        salt '*' cp.get_dir salt://path/to/dir/ /minion/dest

    get_dir supports the same template and gzip arguments as get_file.
    '''
    (path, dest) = _render_filenames(path, dest, env, template)

    _mk_client()
    return __context__['cp.fileclient'].get_dir(path, dest, env, gzip)


def get_url(path, dest, env='base'):
    '''
    Used to get a single file from a URL.

    CLI Example::

        salt '*' cp.get_url salt://my/file /tmp/mine
        salt '*' cp.get_url http://www.slashdot.org /tmp/index.html
    '''
    _mk_client()
    return __context__['cp.fileclient'].get_url(path, dest, False, env)


def get_file_str(path, env='base'):
    '''
    Return the contents of a file from a url

    CLI Example::

        salt '*' cp.get_file_str salt://my/file
    '''
    fn_ = cache_file(path, env)
    with salt.utils.fopen(fn_, 'r') as fp_:
        data = fp_.read()
    return data


def cache_file(path, env='base'):
    '''
    Used to cache a single file in the local salt-master file cache.

    CLI Example::

        salt '*' cp.cache_file salt://path/to/file
    '''
    _mk_client()
    result = __context__['cp.fileclient'].cache_file(path, env)
    if not result:
        log.error('Unable to cache file "{0}" from env '
                  '"{1}".'.format(path,env))
    return result


def cache_files(paths, env='base'):
    '''
    Used to gather many files from the master, the gathered files will be
    saved in the minion cachedir reflective to the paths retrieved from the
    master.

    CLI Example::

        salt '*' cp.cache_files salt://pathto/file1,salt://pathto/file1
    '''
    _mk_client()
    return __context__['cp.fileclient'].cache_files(paths, env)


def cache_dir(path, env='base', include_empty=False):
    '''
    Download and cache everything under a directory from the master

    CLI Example::

        salt '*' cp.cache_dir salt://path/to/dir
    '''
    _mk_client()
    return __context__['cp.fileclient'].cache_dir(path, env, include_empty)


def cache_master(env='base'):
    '''
    Retrieve all of the files on the master and cache them locally

    CLI Example::

        salt '*' cp.cache_master
    '''
    _mk_client()
    return __context__['cp.fileclient'].cache_master(env)


def cache_local_file(path):
    '''
    Cache a local file on the minion in the localfiles cache

    CLI Example::

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


def list_states(env='base'):
    '''
    List all of the available state modules in an environment

    CLI Example::

        salt '*' cp.list_states
    '''
    _mk_client()
    return __context__['cp.fileclient'].list_states(env)


def list_master(env='base'):
    '''
    List all of the files stored on the master

    CLI Example::

        salt '*' cp.list_master
    '''
    _mk_client()
    return __context__['cp.fileclient'].file_list(env)


def list_master_dirs(env='base'):
    '''
    List all of the directories stored on the master

    CLI Exmaple::

        salt '*' cp.list_master_dirs
    '''
    _mk_client()
    return __context__['cp.fileclient'].dir_list(env)


def list_minion(env='base'):
    '''
    List all of the files cached on the minion

    CLI Example::

        salt '*' cp.list_minion
    '''
    _mk_client()
    return __context__['cp.fileclient'].file_local_list(env)


def is_cached(path, env='base'):
    '''
    Return a boolean if the given path on the master has been cached on the
    minion

    CLI Example::

        salt '*' cp.is_cached salt://path/to/file
    '''
    _mk_client()
    return __context__['cp.fileclient'].is_cached(path, env)


def hash_file(path, env='base'):
    '''
    Return the hash of a file, to get the hash of a file on the
    salt master file server prepend the path with salt://<file on server>
    otherwise, prepend the file with / for a local file.

    CLI Example::

        salt '*' cp.hash_file salt://path/to/file
    '''
    _mk_client()
    return __context__['cp.fileclient'].hash_file(path, env)
