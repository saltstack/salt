# -*- coding: utf-8 -*-
'''
The backend for serving files from the Azure blob storage service.

To enable, add ``azurefs`` to the :conf_master:`fileserver_backend` option in
the Master config file.

.. code-block:: yaml

    fileserver_backend:
      - azurefs

Each environment is configured as a storage container. The name of the container
must match the name of the environment. The ``storage_account`` is the name of
the storage account inside Azure where the container lives, and the
``storage_key`` is the access key used for that storage account:

.. code-block:: yaml

    azurefs_envs:
      base:
        storage_account: my_storage
        storage_key: frehgfw34fWGegG07fwsfw343tGFDSDGDFGD==

With this configuration, multiple storage accounts can be used with a single
salt instrastructure.
'''

# Import python libs
from __future__ import absolute_import
import os
import os.path
import logging
import time

try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    # fcntl is not available on windows
    HAS_FCNTL = False

# Import salt libs
import salt.fileserver
import salt.utils
import salt.syspaths

try:
    import salt.utils.msazure as azure
    HAS_AZURE = True
except ImportError:
    HAS_AZURE = False

__virtualname__ = 'azurefs'

log = logging.getLogger()


def __virtual__():
    '''
    Only load if file_recv is enabled
    '''
    if __virtualname__ not in __opts__['fileserver_backend']:
        return False

    if not HAS_AZURE:
        return False

    return True


def find_file(path, saltenv='base', **kwargs):
    '''
    Search the environment for the relative path
    '''
    if 'env' in kwargs:
        salt.utils.warn_until(
            'Oxygen',
            'Parameter \'env\' has been detected in the argument list.  This '
            'parameter is no longer used and has been replaced by \'saltenv\' '
            'as of Salt Carbon.  This warning will be removed in Salt Oxygen.'
            )
        kwargs.pop('env')

    fnd = {'path': '',
           'rel': ''}
    try:
        root = os.path.join(salt.syspaths.CACHE_DIR, 'azure')
    except IndexError:
        # An invalid index was passed
        return fnd
    except ValueError:
        # An invalid index option was passed
        return fnd
    full = os.path.join(root, path)
    if os.path.isfile(full) and not salt.fileserver.is_file_ignored(
                                                            __opts__, full):
        fnd['path'] = full
        fnd['rel'] = path
        fnd['stat'] = list(os.stat(full))
    return fnd


def envs():
    '''
    Treat each container as an environment
    '''
    containers = __opts__.get('azurefs_containers', [])
    return containers.keys()


def serve_file(load, fnd):
    '''
    Return a chunk from a file based on the data received
    '''
    if 'env' in load:
        salt.utils.warn_until(
            'Oxygen',
            'Parameter \'env\' has been detected in the argument list.  This '
            'parameter is no longer used and has been replaced by \'saltenv\' '
            'as of Salt Carbon.  This warning will be removed in Salt Oxygen.'
            )
        load.pop('env')

    ret = {'data': '',
           'dest': ''}
    if 'path' not in load or 'loc' not in load or 'saltenv' not in load:
        return ret
    if not fnd['path']:
        return ret
    ret['dest'] = fnd['rel']
    gzip = load.get('gzip', None)

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
    base_dir = os.path.join(salt.syspaths.CACHE_DIR, 'azure')
    if not os.path.isdir(base_dir):
        os.makedirs(base_dir)

    try:
        salt.fileserver.reap_fileserver_cache_dir(
            os.path.join(base_dir, 'hash'),
            find_file
        )
    except (IOError, OSError):
        # Hash file won't exist if no files have yet been served up
        pass

    data_dict = {}
    if os.listdir(base_dir):
        # Find out what the latest file is, so that we only update files more
        # recent than that, and not the entire filesystem

        all_files = []
        for root, subFolders, files in os.walk(base_dir):
            for fn_ in files:
                full_path = os.path.join(root, fn_)
                all_files.append([
                    os.path.getmtime(full_path),
                    full_path,
                ])
        if all_files:
            all_files.sort()
            all_files.reverse()
            latest_stamp = os.path.getmtime(all_files[0][1])
            format_stamp = time.strftime(
                '%Y-%m-%d %H:%M:%S', time.localtime(latest_stamp)
            )

        #data_dict={'sysparm_query': 'sys_updated_on > {0}'.format(format_stamp)}

    # Pull in any files that have changed
    envs = __opts__.get('azurefs_envs', [])
    for env in envs:
        storage_conn = azure.get_storage_conn(opts=envs[env])
        result = azure.list_blobs(
            storage_conn=storage_conn,
            container=env,
        )

        # Write out any new files to disk
        for blob in result:
            file_name = os.path.join(base_dir, blob)

            # Make sure the directory exists first
            comps = file_name.split('/')
            file_path = '/'.join(comps[:-1])
            if not os.path.exists(file_path):
                os.makedirs(file_path)

            # Write out the file
            azure.get_blob(
                storage_conn=storage_conn,
                container=env,
                name=blob,
                local_path=file_name,
            )

            time_stamp = time.mktime(
                time.strptime(
                    result[blob]['properties']['last_modified'][0],
                    '%a, %d %b %Y %H:%M:%S %Z'
                ),
            )
            os.utime(file_name, (time_stamp, time_stamp))


def file_hash(load, fnd):
    '''
    Return a file hash, the hash type is set in the master config file
    '''
    path = fnd['path']
    ret = {}

    # if the file doesn't exist, we can't get a hash
    if not path or not os.path.isfile(path):
        return ret

    # set the hash_type as it is determined by config
    # -- so mechanism won't change that
    ret['hash_type'] = __opts__['hash_type']

    # check if the hash is cached
    # cache file's contents should be 'hash:mtime'
    cache_path = os.path.join(salt.syspaths.CACHE_DIR,
                              'azure/hash',
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
                    log.debug(
                        'Fileserver attempted to read'
                        'incomplete cache file. Retrying.'
                    )
                    file_hash(load, fnd)
                    return ret
                if os.path.getmtime(path) == mtime:
                    # check if mtime changed
                    ret['hsum'] = hsum
                    return ret
        except os.error:
            # Can't use Python select() because we need Windows support
            log.debug(
                'Fileserver encountered lock'
                'when reading cache file. Retrying.'
            )
            file_hash(load, fnd)
            return ret

    # if we don't have a cache entry-- lets make one
    ret['hsum'] = salt.utils.get_hash(path, __opts__['hash_type'])
    cache_dir = os.path.dirname(cache_path)
    # make cache directory if it doesn't exist
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    # save the cache object 'hash:mtime'
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
    ret = []
    envs = __opts__.get('azurefs_envs', [])
    storage_conn = azure.get_storage_conn(opts=envs[load['saltenv']])
    result = azure.list_blobs(
        storage_conn=storage_conn,
        container=load['saltenv'],
    )
    for blob in result:
        ret.append(blob)
    return ret


def dir_list(load):
    '''
    Return a list of all directories on the master
    '''
    ret = []
    envs = __opts__.get('azurefs_envs', [])
    storage_conn = azure.get_storage_conn(opts=envs[load['saltenv']])
    result = azure.list_blobs(
        storage_conn=storage_conn,
        container=load['saltenv'],
    )
    for blob in result:
        if '/' not in blob:
            continue
        comps = blob.split('/')
        path = '/'.join(comps[:-1])
        if path not in ret:
            ret.append(path)
    return ret
