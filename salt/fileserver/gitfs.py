# -*- coding: utf-8 -*-
'''
The backend for the git based file server system.

After enabling this backend, branches and tags in a remote git repository
are exposed to salt as different environments. This feature is managed by
the fileserver_backend option in the salt master config.

:depends:   - gitpython Python module
'''

# Import python libs
import glob
import os
import shutil
import time
import hashlib
import logging
import distutils.version  # pylint: disable=E0611

# Import third party libs
HAS_GIT = False
try:
    import git
    import gitdb
    HAS_GIT = True
except ImportError:
    pass

# Import salt libs
import salt.utils
import salt.fileserver
from salt.utils.event import tagify

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'git'


def __virtual__():
    '''
    Only load if gitpython is available
    '''
    if not __virtualname__ in __opts__['fileserver_backend']:
        return False
    if not HAS_GIT:
        log.error('Git fileserver backend is enabled in configuration but '
                  'could not be loaded, is GitPython installed?')
        return False
    gitver = distutils.version.LooseVersion(git.__version__)
    minver = distutils.version.LooseVersion('0.3.0')
    if gitver < minver:
        log.error('Git fileserver backend is enabled in configuration but '
                  'GitPython version is not greater than 0.3.0, '
                  'version {0} detected'.format(git.__version__))
        return False
    return __virtualname__


def _get_tree(repo, short):
    '''
    Return a git.Tree object if the branch/tag/SHA is found, otherwise False
    '''
    for ref in repo.refs:
        if isinstance(ref, git.RemoteReference):
            parted = ref.name.partition('/')
            refname = parted[2] if parted[2] else parted[0]
            if short == refname:
                return ref.commit.tree
    # branch or tag not matched, check if 'short' is a commit
    try:
        commit = repo.rev_parse(short)
    except gitdb.exc.BadObject:
        pass
    else:
        return commit.tree
    return False


def _wait_lock(lk_fn, dest):
    '''
    If the write lock is there, check to see if the file is actually being
    written. If there is no change in the file size after a short sleep,
    remove the lock and move forward.
    '''
    if not os.path.isfile(lk_fn):
        return False
    if not os.path.isfile(dest):
        # The dest is not here, sleep for a bit, if the dest is not here yet
        # kill the lockfile and start the write
        time.sleep(1)
        if not os.path.isfile(dest):
            try:
                os.remove(lk_fn)
            except (OSError, IOError):
                pass
            return False
    # There is a lock file, the dest is there, stat the dest, sleep and check
    # that the dest is being written, if it is not being written kill the lock
    # file and continue. Also check if the lock file is gone.
    s_count = 0
    s_size = os.stat(dest).st_size
    while True:
        time.sleep(1)
        if not os.path.isfile(lk_fn):
            return False
        size = os.stat(dest).st_size
        if size == s_size:
            s_count += 1
            if s_count >= 3:
                # The file is not being written to, kill the lock and proceed
                try:
                    os.remove(lk_fn)
                except (OSError, IOError):
                    pass
                return False
        else:
            s_size = size
    return False


def init():
    '''
    Return the git repo object for this session
    '''
    bp_ = os.path.join(__opts__['cachedir'], 'gitfs')
    repos = []
    for _, opt in enumerate(__opts__['gitfs_remotes']):
        repo_hash = hashlib.md5(opt).hexdigest()
        rp_ = os.path.join(bp_, repo_hash)
        if not os.path.isdir(rp_):
            os.makedirs(rp_)

        if not os.listdir(rp_):
            repo = git.Repo.init(rp_)
        else:
            try:
                repo = git.Repo(rp_)
            except git.exc.InvalidGitRepositoryError:
                log.error(
                    'Cache path {0} (corresponding remote: {1}) exists but '
                    'is not a valid git repository. You will need to manually '
                    'delete this directory on the master to continue to use '
                    'this gitfs remote.'.format(rp_, opt)
                )
                continue
            except Exception as exc:
                log.error(
                    'GitPython exception caught while initializing repo {0}'
                    'for gitfs: {1}. Perhaps git is not available.'
                    .format(opt, exc)
                )
                continue

        if not repo.remotes:
            try:
                repo.create_remote('origin', opt)
                # ignore git ssl verification if requested
                if __opts__.get('gitfs_ssl_verify', True):
                    repo.git.config('http.sslVerify', 'true')
                else:
                    repo.git.config('http.sslVerify', 'false')
            except os.error:
                # This exception occurs when two processes are trying to write
                # to the git config at once, go ahead and pass over it since
                # this is the only write
                # This should place a lock down
                pass
        if repo.remotes:
            repos.append(repo)
    return repos


def purge_cache():
    bp_ = os.path.join(__opts__['cachedir'], 'gitfs')
    try:
        remove_dirs = os.listdir(bp_)
    except OSError:
        remove_dirs = []
    for _, opt in enumerate(__opts__['gitfs_remotes']):
        repo_hash = hashlib.md5(opt).hexdigest()
        try:
            remove_dirs.remove(repo_hash)
        except ValueError:
            pass
    remove_dirs = [os.path.join(bp_, r) for r in remove_dirs
                   if r not in ('hash', 'refs', 'envs.p')]
    if remove_dirs:
        for r in remove_dirs:
            shutil.rmtree(r)
        return True
    return False


def update():
    '''
    Execute a git pull on all of the repos
    '''
    # data for the fileserver event
    data = {'changed': False,
            'backend': 'gitfs'}
    pid = os.getpid()
    data['changed'] = purge_cache()
    repos = init()
    for repo in repos:
        origin = repo.remotes[0]
        lk_fn = os.path.join(repo.working_dir, 'update.lk')
        with salt.utils.fopen(lk_fn, 'w+') as fp_:
            fp_.write(str(pid))
        try:
            for fetch in origin.fetch():
                if fetch.old_commit is not None:
                    data['changed'] = True
        except Exception as exc:
            log.warning('GitPython exception caught while fetching: '
                        '{0}'.format(exc))
        try:
            os.remove(lk_fn)
        except (IOError, OSError):
            pass

    env_cache = os.path.join(__opts__['cachedir'], 'gitfs/envs.p')
    if data.get('changed', False) is True or not os.path.isfile(env_cache):
        new_envs = envs(ignore_cache=True)
        serial = salt.payload.Serial(__opts__)
        with salt.utils.fopen(env_cache, 'w+b') as fp_:
            fp_.write(serial.dumps(new_envs))
            log.trace('Wrote env cache data to {0}'.format(env_cache))

    # if there is a change, fire an event
    if __opts__.get('fileserver_events', False):
        event = salt.utils.event.MasterEvent(__opts__['sock_dir'])
        event.fire_event(data, tagify(['gitfs', 'update'], prefix='fileserver'))
    try:
        salt.fileserver.reap_fileserver_cache_dir(
            os.path.join(__opts__['cachedir'], 'gitfs/hash'),
            find_file
        )
    except (IOError, OSError):
        # Hash file won't exist if no files have yet been served up
        pass


def envs(ignore_cache=False):
    '''
    Return a list of refs that can be used as environments
    '''
    if not ignore_cache:
        env_cache = os.path.join(__opts__['cachedir'], 'gitfs/envs.p')
        cache_match = salt.fileserver.check_env_cache(__opts__, env_cache)
        if cache_match is not None:
            return cache_match
    base_branch = __opts__['gitfs_base']
    ret = set()
    repos = init()
    for repo in repos:
        remote = repo.remote()
        for ref in repo.refs:
            parted = ref.name.partition('/')
            short = parted[2] if parted[2] else parted[0]
            if isinstance(ref, git.Head):
                if short == base_branch:
                    short = 'base'
                if ref not in remote.stale_refs:
                    ret.add(short)
            elif isinstance(ref, git.Tag):
                ret.add(short)
    return list(ret)


def find_file(path, short='base', **kwargs):
    '''
    Find the first file to match the path and ref, read the file out of git
    and send the path to the newly cached file
    '''
    fnd = {'path': '',
           'rel': ''}
    base_branch = __opts__['gitfs_base']
    if os.path.isabs(path):
        return fnd

    local_path = path
    if __opts__['gitfs_root']:
        path = os.path.join(__opts__['gitfs_root'], local_path)

    if short == 'base':
        short = base_branch
    dest = os.path.join(__opts__['cachedir'], 'gitfs/refs', short, path)
    hashes_glob = os.path.join(__opts__['cachedir'],
                               'gitfs/hash',
                               short,
                               '{0}.hash.*'.format(path))
    blobshadest = os.path.join(__opts__['cachedir'],
                               'gitfs/hash',
                               short,
                               '{0}.hash.blob_sha1'.format(path))
    lk_fn = os.path.join(__opts__['cachedir'],
                         'gitfs/hash',
                         short,
                         '{0}.lk'.format(path))
    destdir = os.path.dirname(dest)
    hashdir = os.path.dirname(blobshadest)
    if not os.path.isdir(destdir):
        os.makedirs(destdir)
    if not os.path.isdir(hashdir):
        os.makedirs(hashdir)
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
        tree = _get_tree(repo, short)
        if not tree:
            # Branch or tag not found in repo, try the next
            continue
        try:
            blob = tree / path
        except KeyError:
            continue
        _wait_lock(lk_fn, dest)
        if os.path.isfile(blobshadest) and os.path.isfile(dest):
            with salt.utils.fopen(blobshadest, 'r') as fp_:
                sha = fp_.read()
                if sha == blob.hexsha:
                    fnd['rel'] = local_path
                    fnd['path'] = dest
                    return fnd
        with salt.utils.fopen(lk_fn, 'w+') as fp_:
            fp_.write('')
        for filename in glob.glob(hashes_glob):
            try:
                os.remove(filename)
            except Exception:
                pass
        with salt.utils.fopen(dest, 'w+') as fp_:
            blob.stream_data(fp_)
        with salt.utils.fopen(blobshadest, 'w+') as fp_:
            fp_.write(blob.hexsha)
        try:
            os.remove(lk_fn)
        except (OSError, IOError):
            pass
        fnd['rel'] = local_path
        fnd['path'] = dest
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
    ret = {'hash_type': __opts__['hash_type']}
    short = load['saltenv']
    base_branch = __opts__['gitfs_base']
    if short == 'base':
        short = base_branch
    relpath = fnd['rel']
    path = fnd['path']
    if __opts__['gitfs_root']:
        relpath = os.path.join(__opts__['gitfs_root'], relpath)
        path = os.path.join(__opts__['gitfs_root'], path)

    hashdest = os.path.join(__opts__['cachedir'],
                            'gitfs/hash',
                            short,
                            '{0}.hash.{1}'.format(relpath,
                                                  __opts__['hash_type']))
    if not os.path.isfile(hashdest):
        with salt.utils.fopen(path, 'rb') as fp_:
            ret['hsum'] = getattr(hashlib, __opts__['hash_type'])(
                fp_.read()).hexdigest()
        with salt.utils.fopen(hashdest, 'w+') as fp_:
            fp_.write(ret['hsum'])
        return ret
    else:
        with salt.utils.fopen(hashdest, 'rb') as fp_:
            ret['hsum'] = fp_.read()
        return ret


def _file_lists(load, form):
    '''
    Return a dict containing the file lists for files, dirs, emtydirs and symlinks
    '''
    if 'env' in load:
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' '
            'not \'env\'. This functionality will be removed in Salt Boron.'
        )
        load['saltenv'] = load.pop('env')

    list_cachedir = os.path.join(__opts__['cachedir'], 'file_lists/gitfs')
    if not os.path.isdir(list_cachedir):
        try:
            os.makedirs(list_cachedir)
        except os.error:
            log.critical('Unable to make cachedir {0}'.format(list_cachedir))
            return []
    list_cache = os.path.join(list_cachedir, '{0}.p'.format(load['saltenv']))
    w_lock = os.path.join(list_cachedir, '.{0}.w'.format(load['saltenv']))
    cache_match, refresh_cache, save_cache = \
        salt.fileserver.check_file_list_cache(
            __opts__, form, list_cache, w_lock
        )
    if cache_match is not None:
        return cache_match
    if refresh_cache:
        ret = {'links': []}
        ret['files'] = _get_file_list(load)
        ret['dirs'] = _get_dir_list(load)
        ret['empty_dirs'] = _get_file_list_emptydirs(load)
        if save_cache:
            salt.fileserver.write_file_list_cache(
                __opts__, ret, list_cache, w_lock
            )
        return ret.get(form, [])
    # Shouldn't get here, but if we do, this prevents a TypeError
    return []


def file_list(load):
    '''
    Return a list of all files on the file server in a specified
    environment
    '''
    return _file_lists(load, 'files')


def _get_file_list(load):
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
    base_branch = __opts__['gitfs_base']
    if 'saltenv' not in load:
        return ret
    if load['saltenv'] == 'base':
        load['saltenv'] = base_branch
    repos = init()
    for repo in repos:
        tree = _get_tree(repo, load['saltenv'])
        if not tree:
            continue
        if __opts__['gitfs_root']:
            try:
                tree = tree / __opts__['gitfs_root']
            except KeyError:
                continue
        for blob in tree.traverse():
            if not isinstance(blob, git.Blob):
                continue
            if __opts__['gitfs_root']:
                ret.append(os.path.relpath(blob.path, __opts__['gitfs_root']))
                continue
            ret.append(blob.path)
    return ret


def file_list_emptydirs(load):
    '''
    Return a list of all empty directories on the master
    '''
    return _file_lists(load, 'empty_dirs')


def _get_file_list_emptydirs(load):
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
    base_branch = __opts__['gitfs_base']
    if 'saltenv' not in load:
        return ret
    if load['saltenv'] == 'base':
        load['saltenv'] = base_branch
    repos = init()
    for repo in repos:
        tree = _get_tree(repo, load['saltenv'])
        if not tree:
            continue
        if __opts__['gitfs_root']:
            try:
                tree = tree / __opts__['gitfs_root']
            except KeyError:
                continue
        for blob in tree.traverse():
            if not isinstance(blob, git.Tree):
                continue
            if not blob.blobs:
                if __opts__['gitfs_root']:
                    ret.append(
                        os.path.relpath(blob.path, __opts__['gitfs_root'])
                    )
                    continue
                ret.append(blob.path)
    return ret


def dir_list(load):
    '''
    Return a list of all directories on the master
    '''
    return _file_lists(load, 'dirs')


def _get_dir_list(load):
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
    base_branch = __opts__['gitfs_base']
    if 'saltenv' not in load:
        return ret
    if load['saltenv'] == 'base':
        load['saltenv'] = base_branch
    repos = init()
    for repo in repos:
        tree = _get_tree(repo, load['saltenv'])
        if not tree:
            continue
        if __opts__['gitfs_root']:
            try:
                tree = tree / __opts__['gitfs_root']
            except KeyError:
                continue
        for blob in tree.traverse():
            if not isinstance(blob, git.Tree):
                continue
            if __opts__['gitfs_root']:
                ret.append(os.path.relpath(blob.path, __opts__['gitfs_root']))
                continue
            ret.append(blob.path)
    return ret
