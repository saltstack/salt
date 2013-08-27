'''
The default file server backend

Based on the environments in the :conf_master:`file_roots` configuration
option.
'''

# Import python libs
import os

# Import salt libs
import salt.fileserver
import salt.utils


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
    salt.fileserver.reap_fileserver_cache_dir(os.path.join(__opts__['cachedir'], 'roots/hash'), find_file)

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
        with salt.utils.fopen(cache_path, 'rb') as fp_:
            hsum, mtime = fp_.read().split(':')
            if os.path.getmtime(path) == mtime:
                # check if mtime changed
                ret['hsum'] = hsum
                return ret

    # if we don't have a cache entry-- lets make one
    ret['hsum'] = salt.utils.get_hash(path, __opts__['hash_type'])
    cache_dir = os.path.dirname(cache_path)
    # make cache directory if it doesn't exist
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    # save the cache object "hash:mtime"
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
        prefix = load['prefix'].strip('/')
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
        prefix = load['prefix'].strip('/')
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
        prefix = load['prefix'].strip('/')
        for root, dirs, files in os.walk(os.path.join(path, prefix), followlinks=True):
            ret.append(os.path.relpath(root, path))
    return ret
