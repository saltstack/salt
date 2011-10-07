'''
Minion side functions for salt-cp
'''
# Import python libs
import os
import hashlib

# Import salt libs
import salt.minion

# Import Third Party Libs
import zmq

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

def list_master(env='base'):
    '''
    Retrieve all of the files on the master and cache them locally
    '''
    client = salt.minion.FileClient(__opts__)
    return client.file_list(env)

def hash_file(path, env='base'):
    '''
    Return the hash of a file, to get the hash of a file on the
    salt master file server prepend the path with salt://<file on server>
    otherwise, prepend the file with / for a local file.

    CLI Example:
    '''
    client = salt.minion.FileClient(__opts__)
    return client.hash_file(path, env)
