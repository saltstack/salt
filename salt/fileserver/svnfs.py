# -*- coding: utf-8 -*-
'''
The backed for the subversion based file server system.

After enabling this backend, branches, and tags in a remote subversion
repository are exposed to salt as different environments. This feature is
managed by the fileserver_backend option in the salt master config.

This backend assumes a standard svn layout with directories for ``branches``,
``tags``, and ``trunk``, at the repository root.

:depends:   - subversion
'''

# Import python libs
import os
import hashlib
import logging
import shutil

# Import third party libs
HAS_SVN = False
try:
    import pysvn
    HAS_SVN = True
    CLIENT = pysvn.Client()
except ImportError:
    pass

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'svn'


def __virtual__():
    '''
    Only load if subversion is available
    '''
    if not isinstance(__opts__['svnfs_remotes'], list):
        return False
    if not isinstance(__opts__['svnfs_root'], str):
        return False
    if not 'svn' in __opts__['fileserver_backend']:
        return False
    if not HAS_SVN:
        log.error('subversion fileserver backend is enabled in configuration '
                  'but could not be loaded, is pysvn installed?')
        return False
    return __virtualname__


def init():
    '''
    Return the list of svn repos
    '''
    bp_ = os.path.join(__opts__['cachedir'], 'svnfs')
    repos = []
    for _, opt in enumerate(__opts__['svnfs_remotes']):
        repo_hash = hashlib.md5(opt).hexdigest()
        rp_ = os.path.join(bp_, repo_hash)
        if not os.path.isdir(rp_):
            os.makedirs(rp_)
        try:
            CLIENT.checkout(opt, rp_)
            repos.append(rp_)
        except pysvn.ClientError:
            log.error('Failed to initialize svnfs {0}'.format(opt))
    return repos


def purge_cache():
    bp_ = os.path.join(__opts__['cachedir'], 'svnfs')
    try:
        remove_dirs = os.listdir(bp_)
    except OSError:
        remove_dirs = []
    for _, opt in enumerate(__opts__['svnfs_remotes']):
        repo_hash = hashlib.md5(opt).hexdigest()
        try:
            remove_dirs.remove(repo_hash)
        except ValueError:
            pass
    remove_dirs = [os.path.join(bp_, r) for r in remove_dirs if r not in ('hash', 'refs')]
    if remove_dirs:
        for r in remove_dirs:
            shutil.rmtree(r)
        return True
    return False


def update():
    '''
    Execute a svn update on all repos
    '''
    pid = os.getpid()
    purge_cache()
    repos = init()
    for repo in repos:
        lk_fn = os.path.join(repo, 'update.lk')
        with salt.utils.fopen(lk_fn, 'w+') as fp_:
            fp_.write(str(pid))
        CLIENT.update(repo)
        try:
            os.remove(lk_fn)
        except (OSError, IOError):
            pass


def envs():
    '''
    Return a list of refs that can be used as environments

    This assumes the "standard" svn structure of branches, tags, and trunk.
    '''
    ret = set()
    repos = init()
    for repo in repos:
        branch_root = os.path.join(repo, 'branches')
        if os.path.isdir(branch_root):
            branches = os.listdir(branch_root)
            ret.update(branches)

        tag_root = os.path.join(repo, 'tags')
        if os.path.isdir(tag_root):
            tags = os.listdir(tag_root)
            ret.update(tags)

        trunk_root = os.path.join(repo, 'trunk')
        if os.path.isdir(trunk_root):
            # Add base as the env for trunk
            ret.add('base')

    return list(ret)


def _env_root(repo, saltenv):
    '''
    Check if the requested env is a valid env for this repo.
    '''
    trunk_root = os.path.join(repo, 'trunk')
    if os.path.isdir(trunk_root) and saltenv == 'trunk':
        return trunk_root

    branch_root = os.path.join(repo, 'branches')
    if os.path.isdir(branch_root):
        branches = os.listdir(branch_root)
        if saltenv in branches:
            return os.path.join(branch_root, saltenv)

    tag_root = os.path.join(repo, 'tags')
    if os.path.isdir(tag_root):
        tags = os.listdir(tag_root)
        if saltenv in tags:
            return os.path.join(tag_root, saltenv)

    return False


def find_file(path, saltenv='base', env=None, **kwargs):
    '''
    Find the first file to match the path and ref. This operates similarly to
    the roots file sever but with assumptions of the directory structure
    based of svn standard practices.
    '''
    if env is not None:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        # Backwards compatibility
        saltenv = env

    fnd = {'path': '',
           'rel': ''}
    if os.path.isabs(path):
        return fnd

    local_path = path
    path = os.path.join(__opts__['svnfs_root'], local_path)

    if saltenv == 'base':
        saltenv = 'trunk'

    repos = init()
    if 'index' in kwargs:
        try:
            repos = [repos[int(kwargs['index'])]]
        except IndexError:
            # Invalid index param
            return fnd
        except ValueError:
            # Invalid index option
            return fnd
    for repo in repos:
        env_root = _env_root(repo, saltenv)
        if not env_root:
            # Branch or tag not found in repo, try the next
            continue
        full = os.path.join(env_root, path)
        if os.path.isfile(full):
            fnd['rel'] = local_path
            fnd['path'] = full
            return fnd
    return fnd


def serve_file(load, fnd):
    '''
    Return a chunk from a file based on the data received
    '''
    if 'env' in load:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        load['saltenv'] = load.pop('env')

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


def file_hash(load, fnd):
    '''
    Return a file hash, the hash type is set in the master config file
    '''
    if 'env' in load:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        load['saltenv'] = load.pop('env')

    if 'path' not in load or 'saltenv' not in load:
        return ''
    saltenv = load['saltenv']
    if saltenv == 'base':
        saltenv = 'trunk'
    relpath = fnd['rel']
    path = fnd['path']
    ret = {}

    if __opts__['svnfs_root']:
        relpath = os.path.join(__opts__['svnfs_root'], relpath)
        path = os.path.join(__opts__['svnfs_root'], path)

    # if the file doesn't exist, we can't get a hash
    if not path or not os.path.isfile(path):
        return ret

    # set the hash_type as it is determined by config-- so mechanism won't change that
    ret['hash_type'] = __opts__['hash_type']

    # check if the hash is cached
    # cache file's contents should be "hash:mtime"
    cache_path = os.path.join(__opts__['cachedir'],
                              'svnfs/hash',
                              saltenv,
                              '{0}.hash.{1}'.format(relpath,
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
    if 'env' in load:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        load['saltenv'] = load.pop('env')

    ret = []
    if 'saltenv' not in load:
        return ret
    if load['saltenv'] == 'base':
        load['saltenv'] = 'trunk'
    repos = init()
    for repo in repos:
        env_root = _env_root(repo, load['saltenv'])
        if env_root:
            for root, dirs, files in os.walk(env_root):
                for fname in files:
                    rel_fn = os.path.relpath(os.path.join(root, fname),
                                             env_root)
                    ret.append(rel_fn)
    return ret


def file_list_emptydirs(load):
    '''
    Return a list of all empty directories on the master
    '''
    if 'env' in load:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        load['saltenv'] = load.pop('env')

    ret = []
    if 'saltenv' not in load:
        return ret
    if load['saltenv'] == 'base':
        load['saltenv'] = 'trunk'
    repos = init()
    for repo in repos:
        env_root = _env_root(repo, load['saltenv'])
        if env_root:
            for root, dirs, files in os.walk(env_root):
                if len(dirs) == 0 and len(files) == 0:
                    rel_fn = os.path.relpath(root, env_root)
                    ret.append(rel_fn)
    return ret


def dir_list(load):
    '''
    Return a list of all directories on the master
    '''
    if 'env' in load:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        load['saltenv'] = load.pop('env')

    ret = []
    if 'saltenv' not in load:
        return ret
    if load['saltenv'] == 'base':
        load['saltenv'] = 'trunk'
    repos = init()
    for repo in repos:
        env_root = _env_root(repo, load['saltenv'])
        if env_root:
            for root, dirs, files in os.walk(env_root):
                ret.append(os.path.relpath(root, env_root))
    return ret
