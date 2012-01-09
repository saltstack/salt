'''
Minion side functions for salt-cp
'''

import os

import salt.minion


def recv(files, dest):
    '''
    Used with salt-cp, pass the files dict, and the destination.

    This function receives small fast copy files from the master via salt-cp
    '''
    ret = {}
    for path, data in files.items():
        final = ''
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
            open(final, 'w+').write(data)
            ret[final] = True
        except IOError:
            ret[final] = False

    return ret


def get_file(path, dest, env='base'):
    '''
    Used to get a single file from the salt master
    '''
    client = salt.minion.FileClient(__opts__)
    return client.get_file(path, dest, False, env)


def get_url(path, dest, env='base'):
    '''
    Used to get a single file from a URL.
    For example,
        cp.get_url salt://my/file /tmp/mine
        cp.get_url http://www.slashdot.org /tmp/index.html
    '''
    client = salt.minion.FileClient(__opts__)
    return client.get_url(path, dest, False, env)


def cache_file(path, env='base'):
    '''
    Used to cache a single file in the local salt-master file cache.
    '''
    client = salt.minion.FileClient(__opts__)
    return client.cache_file(path, env)


def cache_files(paths, env='base'):
    '''
    Used to gather many files from the master, the gathered files will be
    saved in the minion cachedir reflective to the paths retrieved from the
    master.
    '''
    client = salt.minion.FileClient(__opts__)
    return client.cache_files(paths, env)


def cache_dir(path, env='base'):
    '''
    Download and cache everything under a directory from the master
    '''
    client = salt.minion.FileClient(__opts__)
    return client.cache_dir(path, env)


def cache_master(env='base'):
    '''
    Retrieve all of the files on the master and cache them locally
    '''
    client = salt.minion.FileClient(__opts__)
    return client.cache_master(env)


def cache_local_file(path):
    '''
    Cache a local file on the minion in the localfiles cache
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
    client = salt.minion.FileClient(__opts__)
    return client.cache_local_file(path)


def list_master(env='base'):
    '''
    List all of the files stored on the master
    '''
    client = salt.minion.FileClient(__opts__)
    return client.file_list(env)


def list_minion(env='base'):
    '''
    List all of the files cached on the minion
    '''
    client = salt.minion.FileClient(__opts__)
    return client.file_local_list(env)


def is_cached(path, env='base'):
    '''
    Return a boolean if the given path on the master has been cached on the
    minion
    '''
    client = salt.minion.FileClient(__opts__)
    return client.is_cached(path, env)


def hash_file(path, env='base'):
    '''
    Return the hash of a file, to get the hash of a file on the
    salt master file server prepend the path with salt://<file on server>
    otherwise, prepend the file with / for a local file.
    '''
    client = salt.minion.FileClient(__opts__)
    return client.hash_file(path, env)
