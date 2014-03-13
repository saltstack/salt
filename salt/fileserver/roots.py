# -*- coding: utf-8 -*-
'''
The default file server backend

Based on the environments in the :conf_master:`file_roots` configuration
option.
'''

# Import python libs
import os
import logging

try:
    import fcntl
    HAS_FCNTL = os.uname()[0] != "SunOS"
except ImportError:
    # fcntl is not available on windows
    HAS_FCNTL = False

# Import salt libs
import salt.fileserver
import salt.utils
from salt.utils.event import tagify

log = logging.getLogger(__name__)


def find_file(path, env='base', **kwargs):
    '''
    Search the environment for the relative path
    '''
    fnd = {'path': '',
           'rel': ''}
    if os.path.isabs(path):
        return fnd
    if env not in __opts__['file_roots']:
        return fnd
    if 'index' in kwargs:
        try:
            root = __opts__['file_roots'][env][int(kwargs['index'])]
        except IndexError:
            # An invalid index was passed
            return fnd
        except ValueError:
            # An invalid index option was passed
            return fnd
        full = os.path.join(root, path)
        if os.path.isfile(full) and not salt.fileserver.is_file_ignored(__opts__, full):
            fnd['path'] = full
            fnd['rel'] = path
        return fnd
    for root in __opts__['file_roots'][env]:
        full = os.path.join(root, path)
        if os.path.isfile(full) and not salt.fileserver.is_file_ignored(__opts__, full):
            fnd['path'] = full
            fnd['rel'] = path
            return fnd
    return fnd


def envs():
    '''
    Return the file server environments
    '''
    return __opts__['file_roots'].keys()


def serve_file(load, fnd):
    '''
    Return a chunk from a file based on the data received
    '''
    ret = {'data': '',
           'dest': ''}
    if 'path' not in load or 'loc' not in load or 'env' not in load:
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
    try:
        salt.fileserver.reap_fileserver_cache_dir(
            os.path.join(__opts__['cachedir'], 'roots/hash'),
            find_file
        )
    except (IOError, OSError):
        # Hash file won't exist if no files have yet been served up
        pass

    mtime_map_path = os.path.join(__opts__['cachedir'], 'roots/mtime_map')
    # data to send on event
    data = {'changed': False,
            'backend': 'roots'}

    old_mtime_map = {}
    # if you have an old map, load that
    if os.path.exists(mtime_map_path):
        with salt.utils.fopen(mtime_map_path, 'rb') as fp_:
            for line in fp_:
                file_path, mtime = line.split(':', 1)
                old_mtime_map[file_path] = mtime

    # generate the new map
    new_mtime_map = salt.fileserver.generate_mtime_map(__opts__['file_roots'])

    # compare the maps, set changed to the return value
    data['changed'] = salt.fileserver.diff_mtime_map(old_mtime_map, new_mtime_map)

    # write out the new map
    mtime_map_path_dir = os.path.dirname(mtime_map_path)
    if not os.path.exists(mtime_map_path_dir):
        os.makedirs(mtime_map_path_dir)
    with salt.utils.fopen(mtime_map_path, 'w') as fp_:
        for file_path, mtime in new_mtime_map.iteritems():
            fp_.write('{file_path}:{mtime}\n'.format(file_path=file_path,
                                                     mtime=mtime))

    # if there is a change, fire an event
    event = salt.utils.event.MasterEvent(__opts__['sock_dir'])
    event.fire_event(data, tagify(['roots', 'update'], prefix='fileserver'))


def file_hash(load, fnd):
    '''
    Return a file hash, the hash type is set in the master config file
    '''
    if 'path' not in load or 'env' not in load:
        return ''
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
                              'roots/hash',
                              load['env'],
                              '{0}.hash.{1}'.format(fnd['rel'],
                              __opts__['hash_type']))
    # if we have a cache, serve that if the mtime hasn't changed
    if os.path.exists(cache_path):
        try:
            with salt.utils.fopen(cache_path, 'rb') as fp_:
                try:
                    hsum, mtime = fp_.read().split(':')
                except ValueError:
                    log.debug('Fileserver attempted to read incomplete cache file. Retrying.')
                    # Delete the file since its incomplete (either corrupted or incomplete)
                    try :
                        os.unlink(cache_path)
                    except os.error:
                        pass
                    return file_hash(load, fnd)
                if os.path.getmtime(path) == mtime:
                    # check if mtime changed
                    ret['hsum'] = hsum
                    return ret
        except (os.error, IOError):  # Can't use Python select() because we need Windows support
            log.debug("Fileserver encountered lock when reading cache file. Retrying.")
            # Delete the file since its incomplete (either corrupted or incomplete)
            try :
                os.unlink(cache_path)
            except os.error:
                pass
            return file_hash(load, fnd)

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
    Return a list of all files on the file server in a specified
    environment
    '''
    ret = []
    if load['env'] not in __opts__['file_roots']:
        return ret

    for path in __opts__['file_roots'][load['env']]:
        try:
            prefix = load['prefix'].strip('/')
        except KeyError:
            prefix = ''
        for root, dirs, files in os.walk(os.path.join(path, prefix), followlinks=True):
            for fname in files:
                rel_fn = os.path.relpath(
                            os.path.join(root, fname),
                            path
                        )
                if not salt.fileserver.is_file_ignored(__opts__, rel_fn):
                    ret.append(rel_fn)
    return ret


def file_list_emptydirs(load):
    '''
    Return a list of all empty directories on the master
    '''
    ret = []
    if load['env'] not in __opts__['file_roots']:
        return ret
    for path in __opts__['file_roots'][load['env']]:
        try:
            prefix = load['prefix'].strip('/')
        except KeyError:
            prefix = ''
        for root, dirs, files in os.walk(os.path.join(path, prefix), followlinks=True):
            if len(dirs) == 0 and len(files) == 0:
                rel_fn = os.path.relpath(root, path)
                if not salt.fileserver.is_file_ignored(__opts__, rel_fn):
                    ret.append(rel_fn)
    return ret


def dir_list(load):
    '''
    Return a list of all directories on the master
    '''
    ret = []
    if load['env'] not in __opts__['file_roots']:
        return ret
    for path in __opts__['file_roots'][load['env']]:
        try:
            prefix = load['prefix'].strip('/')
        except KeyError:
            prefix = ''
        for root, dirs, files in os.walk(os.path.join(path, prefix), followlinks=True):
            ret.append(os.path.relpath(root, path))
    return ret
