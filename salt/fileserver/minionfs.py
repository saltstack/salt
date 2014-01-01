# -*- coding: utf-8 -*-
'''
The backend for serving files pushed to master by cp.push (file_recv).

:conf_master:`file_recv` needs to be enabled in the master config file.
'''

# Import python libs
import os
import logging

try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    # fcntl is not available on windows
    HAS_FCNTL = False

# Import salt libs
import salt.fileserver
import salt.utils

log = logging.getLogger()


# Define the module's virtual name
__virtualname__ = 'minion'


def __virtual__():
    '''
    Only load if file_recv is enabled
    '''
    if not __virtualname__ in __opts__['fileserver_backend']:
        return False
    if not __opts__['file_recv']:
        return False
    return __virtualname__


def find_file(path, env='base', **kwargs):
    '''
    Search the environment for the relative path
    '''
    # AP logger.debug('minionfs is asked for {0}'.format(path))
    fnd = {'path': '', 'rel': ''}
    if os.path.isabs(path):
        return fnd
    if env not in envs():
        return fnd
    if path[-7:] == 'top.sls':
        log.debug('minionfs will NOT serve top.sls '
                     'for security reasons: {0}'.format(path))
        return fnd
    minion, pushed_file = path.split(os.sep, 1)
    full = os.path.join(__opts__['cachedir'], 'minions',
                                     minion, 'files', pushed_file)
    if os.path.isfile(full) and not salt.fileserver.is_file_ignored(__opts__, full):
        fnd['path'] = full
        fnd['rel'] = path
        return fnd
    # AP logger.debug('minionfs: full path for {0} is {1}'.format(path, full))
    return fnd


def envs():
    '''
    Return "base" as the file server environment, because there is only one set
    of minions.
    '''
    return ['base']


def serve_file(load, fnd):
    '''
    Return a chunk from a file based on the data received

    CLI Example:

    .. code-block:: bash

        $ salt 'source-minion' cp.push /path/to/the/file  # Push the file to the master
        $ salt 'destination-minion'  cp.get_file salt://source-minion/path/to/the/file /destination/file
    '''
    ret = {'data': '', 'dest': ''}
    if not fnd['path']:
        return ret
    ret['dest'] = fnd['rel']
    gzip = load.get('gzip', None)

    # AP
    # May I sleep here to slow down serving of big files?
    # How many threads are serving files?
    with salt.utils.fopen(fnd['path'], 'rb') as fp_:
        fp_.seek(load['loc'])
        data = fp_.read(__opts__['file_buffer_size'])
        if gzip and data:
            data = salt.utils.gzip_util.compress(data, gzip)
            ret['gzip'] = gzip
        ret['data'] = data
    return ret


def update():
    '''
    When we are asked to update (regular interval) lets reap the cache
    '''
    # AP logger.debug("minionfs: updating {0}".format(
    # AP                     os.path.join(__opts__['cachedir'], 'minionfs/hash')))
    try:
        salt.fileserver.reap_fileserver_cache_dir(
            os.path.join(__opts__['cachedir'], 'minionfs/hash'),
            find_file)
    except os.error:
        # Hash file won't exist if no files have yet been served up
        pass


def file_hash(load, fnd):
    '''
    Return a file hash, the hash type is set in the master config file
    '''
    path = fnd['path']
    ret = {}

    # if the file doesn't exist, we can't get a hash
    if not path or not os.path.isfile(path):
        return ret

    # set the hash_type as it is determined by config-- so mechanism won't change that
    ret['hash_type'] = __opts__['hash_type']

    # check if the hash is cached
    # cache file's contents should be "hash:mtime"
    cache_path = os.path.join(__opts__['cachedir'],
                              'minionfs/hash',
                              load['saltenv'],
                              '{0}.hash.{1}'.format(
                                    fnd['rel'], __opts__['hash_type'])
                            )
    # if we have a cache, serve that if the mtime hasn't changed
    if os.path.exists(cache_path):
        try:
            with salt.utils.fopen(cache_path, 'rb') as fp_:
                try:
                    hsum, mtime = fp_.read().split(':')
                except ValueError:
                    log.debug('Fileserver attempted to read incomplete cache file. Retrying.')
                    file_hash(load, fnd)
                    return(ret)
                if os.path.getmtime(path) == mtime:
                    # check if mtime changed
                    ret['hsum'] = hsum
                    return ret
        except os.error:  # Can't use Python select() because we need Windows support
            log.debug("Fileserver encountered lock when reading cache file. Retrying.")
            file_hash(load, fnd)
            return(ret)

    # if we don't have a cache entry-- lets make one
    ret['hsum'] = salt.utils.get_hash(path, __opts__['hash_type'])
    cache_dir = os.path.dirname(cache_path)
    # make cache directory if it doesn't exist
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    # save the cache object "hash:mtime"
    if HAS_FCNTL:
        with salt.utils.flopen(cache_path, 'w') as fp_:
            fp_.write('{0}:{1}'.format(ret['hsum'], os.path.getmtime(path)))
            fcntl.flock(fp_.fileno(), fcntl.LOCK_UN)
        return ret
    else:
        with salt.utils.fopen(cache_path, 'w') as fp_:
            fp_.write('{0}:{1}'.format(ret['hsum'], os.path.getmtime(path)))
        return ret


def file_list(load):
    '''
    Return a list of all files on the file server in a specified environment
    '''
    # AP logger.debug('minionfs is asked for file_list of {0}'.format(os.path.join(__opts__['cachedir'], 'minions')))
    ret = []
    prefix = load.get('prefix', '').strip('/')
    minions_cache_dir = os.path.join(__opts__['cachedir'], 'minions')
    for minion_dir in os.listdir(minions_cache_dir):
        minion_files_dir = os.path.join(minions_cache_dir, minion_dir, 'files')
        if not os.path.isdir(minion_files_dir):
            log.debug('minionfs: could not find files directory under {0}!'
                             .format(os.path.join(minions_cache_dir, minion_dir))
                        )
            continue
        # Always ignore links for security reasons
        for root, dirs, files in os.walk(
                                     os.path.join(minion_files_dir,
                                                  prefix
                                     ), followlinks=False):
            for fname in files:
                if os.path.islink(os.path.join(root, fname)):
                    continue
                rel_fn = os.path.join(minion_dir,
                                      os.path.relpath(os.path.join(root, fname),
                                                      minion_files_dir
                                                     )
                                      )
                if not salt.fileserver.is_file_ignored(__opts__, rel_fn):
                    ret.append(rel_fn)
    # AP logger.debug('minionfs: file_list is returning {0}'.format(ret))
    return ret


# There should be no emptydirs
#def file_list_emptydirs(load):


def dir_list(load):
    '''
    Return a list of all directories on the master

    CLI Example:

    .. code-block:: bash

        $ salt 'source-minion' cp.push /absolute/path/file  # Push the file to the master
        $ salt 'destination-minion' cp.list_master_dirs
        destination-minion:
            - .
            - source-minion/absolute
            - source-minion/absolute/path
    '''
    ret = []
    prefix = load.get('prefix', '').strip('/')
    minions_cache_dir = os.path.join(__opts__['cachedir'], 'minions')
    for minion_dir in os.listdir(minions_cache_dir):
        minion_files_dir = os.path.join(minions_cache_dir, minion_dir, 'files')
        if not os.path.isdir(minion_files_dir):
            log.debug('minionfs: could not find files directory under {0}!'
                             .format(os.path.join(minions_cache_dir, minion_dir))
                        )
            continue
        # Always ignore links for security reasons
        for root, dirs, files in os.walk(
                os.path.join(
                    minion_files_dir,
                    prefix
                    ),
                followlinks=False):
            rel_fn = os.path.join(
                    minion_dir,
                    os.path.relpath(root, minion_files_dir)
                    )
            ret.append(rel_fn)
    # AP logger.debug('minionfs: dir_list is returning {0}'.format(ret))
    return ret
