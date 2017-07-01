# -*- coding: utf-8 -*-
'''
Fileserver backend which serves files pushed to the Master

The :mod:`cp.push <salt.modules.cp.push>` function allows Minions to push files
up to the Master. Using this backend, these pushed files are exposed to other
Minions via the Salt fileserver.

To enable minionfs, :conf_master:`file_recv` needs to be set to ``True`` in
the master config file (otherwise :mod:`cp.push <salt.modules.cp.push>` will
not be allowed to push files to the Master), and ``minion`` must be added to
the :conf_master:`fileserver_backends` list.

.. code-block:: yaml

    fileserver_backend:
      - minion

Other minionfs settings include: :conf_master:`minionfs_whitelist`,
:conf_master:`minionfs_blacklist`, :conf_master:`minionfs_mountpoint`, and
:conf_master:`minionfs_env`.

.. seealso:: :ref:`tutorial-minionfs`

'''
from __future__ import absolute_import

# Import python libs
import os
import logging

# Import salt libs
import salt.fileserver
import salt.utils
import salt.utils.url

# Import third party libs
import salt.ext.six as six

log = logging.getLogger(__name__)


# Define the module's virtual name
__virtualname__ = 'minion'


def __virtual__():
    '''
    Only load if file_recv is enabled
    '''
    if __virtualname__ not in __opts__['fileserver_backend']:
        return False
    return __virtualname__ if __opts__['file_recv'] else False


def _is_exposed(minion):
    '''
    Check if the minion is exposed, based on the whitelist and blacklist
    '''
    return salt.utils.check_whitelist_blacklist(
        minion,
        whitelist=__opts__['minionfs_whitelist'],
        blacklist=__opts__['minionfs_blacklist']
    )


def find_file(path, tgt_env='base', **kwargs):  # pylint: disable=W0613
    '''
    Search the environment for the relative path
    '''
    fnd = {'path': '', 'rel': ''}
    if os.path.isabs(path):
        return fnd
    if tgt_env not in envs():
        return fnd
    if os.path.basename(path) == 'top.sls':
        log.debug('minionfs will NOT serve top.sls '
                  'for security reasons (path requested: {0})'.format(path))
        return fnd

    mountpoint = salt.utils.url.strip_proto(__opts__['minionfs_mountpoint'])
    # Remove the mountpoint to get the "true" path
    path = path[len(mountpoint):].lstrip(os.path.sep)
    try:
        minion, pushed_file = path.split(os.sep, 1)
    except ValueError:
        return fnd
    if not _is_exposed(minion):
        return fnd
    full = os.path.join(
        __opts__['cachedir'], 'minions', minion, 'files', pushed_file
    )
    if os.path.isfile(full) \
            and not salt.fileserver.is_file_ignored(__opts__, full):
        fnd['path'] = full
        fnd['rel'] = path
        fnd['stat'] = list(os.stat(full))
        return fnd
    return fnd


def envs():
    '''
    Returns the one environment specified for minionfs in the master
    configuration.
    '''
    return [__opts__['minionfs_env']]


def serve_file(load, fnd):
    '''
    Return a chunk from a file based on the data received

    CLI Example:

    .. code-block:: bash

        # Push the file to the master
        $ salt 'source-minion' cp.push /path/to/the/file
        $ salt 'destination-minion' cp.get_file salt://source-minion/path/to/the/file /destination/file
    '''
    ret = {'data': '', 'dest': ''}
    if not fnd['path']:
        return ret
    ret['dest'] = fnd['rel']
    gzip = load.get('gzip', None)
    fpath = os.path.normpath(fnd['path'])

    # AP
    # May I sleep here to slow down serving of big files?
    # How many threads are serving files?
    with salt.utils.fopen(fpath, 'rb') as fp_:
        fp_.seek(load['loc'])
        data = fp_.read(__opts__['file_buffer_size'])
        if data and six.PY3 and not salt.utils.is_bin_file(fpath):
            data = data.decode(__salt_system_encoding__)
        if gzip and data:
            data = salt.utils.gzip_util.compress(data, gzip)
            ret['gzip'] = gzip
        ret['data'] = data
    return ret


def update():
    '''
    When we are asked to update (regular interval) lets reap the cache
    '''
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

    if 'env' in load:
        salt.utils.warn_until(
            'Oxygen',
            'Parameter \'env\' has been detected in the argument list.  This '
            'parameter is no longer used and has been replaced by \'saltenv\' '
            'as of Salt 2016.11.0.  This warning will be removed in Salt Oxygen.'
            )
        load.pop('env')

    if load['saltenv'] not in envs():
        return {}

    # if the file doesn't exist, we can't get a hash
    if not path or not os.path.isfile(path):
        return ret

    # set the hash_type as it is determined by config-- so mechanism won't change that
    ret['hash_type'] = __opts__['hash_type']

    # check if the hash is cached
    # cache file's contents should be "hash:mtime"
    cache_path = os.path.join(
        __opts__['cachedir'],
        'minionfs/hash',
        load['saltenv'],
        '{0}.hash.{1}'.format(fnd['rel'], __opts__['hash_type'])
    )
    # if we have a cache, serve that if the mtime hasn't changed
    if os.path.exists(cache_path):
        try:
            with salt.utils.fopen(cache_path, 'rb') as fp_:
                try:
                    hsum, mtime = fp_.read().split(':')
                except ValueError:
                    log.debug(
                        'Fileserver attempted to read incomplete cache file. '
                        'Retrying.'
                    )
                    file_hash(load, fnd)
                    return ret
                if os.path.getmtime(path) == mtime:
                    # check if mtime changed
                    ret['hsum'] = hsum
                    return ret
        # Can't use Python select() because we need Windows support
        except os.error:
            log.debug(
                'Fileserver encountered lock when reading cache file. '
                'Retrying.'
            )
            file_hash(load, fnd)
            return ret

    # if we don't have a cache entry-- lets make one
    ret['hsum'] = salt.utils.get_hash(path, __opts__['hash_type'])
    cache_dir = os.path.dirname(cache_path)
    # make cache directory if it doesn't exist
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    # save the cache object "hash:mtime"
    cache_object = '{0}:{1}'.format(ret['hsum'], os.path.getmtime(path))
    with salt.utils.flopen(cache_path, 'w') as fp_:
        fp_.write(cache_object)
    return ret


def file_list(load):
    '''
    Return a list of all files on the file server in a specified environment
    '''
    if 'env' in load:
        salt.utils.warn_until(
            'Oxygen',
            'Parameter \'env\' has been detected in the argument list.  This '
            'parameter is no longer used and has been replaced by \'saltenv\' '
            'as of Salt 2016.11.0.  This warning will be removed in Salt Oxygen.'
            )
        load.pop('env')

    if load['saltenv'] not in envs():
        return []
    mountpoint = salt.utils.url.strip_proto(__opts__['minionfs_mountpoint'])
    prefix = load.get('prefix', '').strip('/')
    if mountpoint and prefix.startswith(mountpoint + os.path.sep):
        prefix = prefix[len(mountpoint + os.path.sep):]

    minions_cache_dir = os.path.join(__opts__['cachedir'], 'minions')
    minion_dirs = os.listdir(minions_cache_dir)

    # If the prefix is not an empty string, then get the minion id from it. The
    # minion ID will be the part before the first slash, so if there is no
    # slash, this is an invalid path.
    if prefix:
        tgt_minion, _, prefix = prefix.partition('/')
        if not prefix:
            # No minion ID in path
            return []
        # Reassign minion_dirs so we don't unnecessarily walk every minion's
        # pushed files
        if tgt_minion not in minion_dirs:
            log.warning(
                'No files found in minionfs cache for minion ID \'{0}\''
                .format(tgt_minion)
            )
            return []
        minion_dirs = [tgt_minion]

    ret = []
    for minion in minion_dirs:
        if not _is_exposed(minion):
            continue
        minion_files_dir = os.path.join(minions_cache_dir, minion, 'files')
        if not os.path.isdir(minion_files_dir):
            log.debug(
                'minionfs: could not find files directory under {0}!'
                .format(os.path.join(minions_cache_dir, minion))
            )
            continue
        walk_dir = os.path.join(minion_files_dir, prefix)
        # Do not follow links for security reasons
        for root, _, files in os.walk(walk_dir, followlinks=False):
            for fname in files:
                # Ignore links for security reasons
                if os.path.islink(os.path.join(root, fname)):
                    continue
                relpath = os.path.relpath(
                    os.path.join(root, fname), minion_files_dir
                )
                if relpath.startswith('../'):
                    continue
                rel_fn = os.path.join(mountpoint, minion, relpath)
                if not salt.fileserver.is_file_ignored(__opts__, rel_fn):
                    ret.append(rel_fn)
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
            - source-minion/absolute
            - source-minion/absolute/path
    '''
    if 'env' in load:
        salt.utils.warn_until(
            'Oxygen',
            'Parameter \'env\' has been detected in the argument list.  This '
            'parameter is no longer used and has been replaced by \'saltenv\' '
            'as of Salt 2016.11.0.  This warning will be removed in Salt Oxygen.'
            )
        load.pop('env')

    if load['saltenv'] not in envs():
        return []
    mountpoint = salt.utils.url.strip_proto(__opts__['minionfs_mountpoint'])
    prefix = load.get('prefix', '').strip('/')
    if mountpoint and prefix.startswith(mountpoint + os.path.sep):
        prefix = prefix[len(mountpoint + os.path.sep):]

    minions_cache_dir = os.path.join(__opts__['cachedir'], 'minions')
    minion_dirs = os.listdir(minions_cache_dir)

    # If the prefix is not an empty string, then get the minion id from it. The
    # minion ID will be the part before the first slash, so if there is no
    # slash, this is an invalid path.
    if prefix:
        tgt_minion, _, prefix = prefix.partition('/')
        if not prefix:
            # No minion ID in path
            return []
        # Reassign minion_dirs so we don't unnecessarily walk every minion's
        # pushed files
        if tgt_minion not in minion_dirs:
            log.warning(
                'No files found in minionfs cache for minion ID \'{0}\''
                .format(tgt_minion)
            )
            return []
        minion_dirs = [tgt_minion]

    ret = []
    for minion in os.listdir(minions_cache_dir):
        if not _is_exposed(minion):
            continue
        minion_files_dir = os.path.join(minions_cache_dir, minion, 'files')
        if not os.path.isdir(minion_files_dir):
            log.warning(
                'minionfs: could not find files directory under {0}!'
                .format(os.path.join(minions_cache_dir, minion))
            )
            continue
        walk_dir = os.path.join(minion_files_dir, prefix)
        # Do not follow links for security reasons
        for root, _, _ in os.walk(walk_dir, followlinks=False):
            relpath = os.path.relpath(root, minion_files_dir)
            # Ensure that the current directory and directories outside of
            # the minion dir do not end up in return list
            if relpath in ('.', '..') or relpath.startswith('../'):
                continue
            ret.append(os.path.join(mountpoint, minion, relpath))
    return ret
