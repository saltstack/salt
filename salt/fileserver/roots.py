'''
The default file server backend based on the environments in the file_roots
configuraiton option
'''

# Import python libs
import os
import hashlib

# Import salt libs
import salt.fileserver
import salt.utils


def _find_file(path, env='base'):
    '''
    Search the environment for the relative path
    '''
    fnd = {'path': '',
           'rel': ''}
    if os.path.isabs(path):
        return fnd
    if env not in __opts__['file_roots']:
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


def serve_file(load):
    '''
    Return a chunk from a file based on the data received
    '''
    ret = {'data': '',
           'dest': ''}
    if 'path' not in load or 'loc' not in load or 'env' not in load:
        return ret
    fnd = _find_file(load['path'], load['env'])
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


def file_hash(load):
    '''
    Return a file hash, the hash type is set in the master config file
    '''
    if 'path' not in load or 'env' not in load:
        return ''
    path = _find_file(load['path'], load['env'])['path']
    if not path:
        return {}
    ret = {}
    with salt.utils.fopen(path, 'rb') as fp_:
        ret['hsum'] = getattr(hashlib, __opts__['hash_type'])(
                fp_.read()).hexdigest()
    ret['hash_type'] = __opts__['hash_type']
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
        for root, dirs, files in os.walk(path, followlinks=True):
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
        for root, dirs, files in os.walk(path, followlinks=True):
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
        for root, dirs, files in os.walk(path, followlinks=True):
            ret.append(os.path.relpath(root, path))
    return ret
