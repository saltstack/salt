'''
The backend for the git based file server system.

After enabling this backend, branches and tags in a remote git repository
are exposed to salt as different environments. This feature is managed by
the fileserver_backend option in the salt master config.

:depends: git-python Python module
'''

# Import python libs
import glob
import os
import time
import hashlib
import logging

# Import third party libs
HAS_GIT = False
try:
    import git
    HAS_GIT = True
except ImportError:
    pass

# Import salt libs
import salt.utils
import salt.fileserver

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if git-python is available
    '''
    if not isinstance(__opts__['gitfs_remotes'], list):
        return False
    if not 'git' in __opts__['fileserver_backend']:
        return False
    if not HAS_GIT:
        log.error('Git fileserver backend is enabled in configuration but '
                  'could not be loaded, is git-python installed?')
        return False
    if not git.__version__ > '0.3.0':
        return False
    return 'git'


def _get_ref(repo, short):
    '''
    Return bool if the short ref is in the repo
    '''
    for ref in repo.refs:
        if isinstance(ref, git.RemoteReference):
            parted = ref.name.partition('/')
            refname = parted[2] if parted[2] else parted[0]
            if short == refname:
                return ref
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
    for ind in range(len(__opts__['gitfs_remotes'])):
        rp_ = os.path.join(bp_, str(ind))
        if not os.path.isdir(rp_):
            os.makedirs(rp_)
        repo = git.Repo.init(rp_)
        if not repo.remotes:
            try:
                repo.create_remote('origin', __opts__['gitfs_remotes'][ind])
            except Exception:
                # This exception occurs when two processes are trying to write
                # to the git config at once, go ahead and pass over it since
                # this is the only write
                # This should place a lock down
                pass
        if repo.remotes:
            repos.append(repo)
    return repos


def update():
    '''
    Execute a git pull on all of the repos
    '''
    pid = os.getpid()
    repos = init()
    for repo in repos:
        origin = repo.remotes[0]
        lk_fn = os.path.join(repo.working_dir, 'update.lk')
        with open(lk_fn, 'w+') as fp_:
            fp_.write(str(pid))
        origin.fetch()
        try:
            os.remove(lk_fn)
        except (OSError, IOError):
            pass


def envs():
    '''
    Return a list of refs that can be used as environments
    '''
    ret = set()
    repos = init()
    for repo in repos:
        remote = repo.remote()
        for ref in repo.refs:
            parted = ref.name.partition('/')
            short = parted[2] if parted[2] else parted[0]
            if isinstance(ref, git.Head):
                if short == 'master':
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
    if os.path.isabs(path):
        return fnd
    if short == 'base':
        short = 'master'
    dest = os.path.join(__opts__['cachedir'], 'gitfs/refs', short, path)
    hashes_glob = os.path.join(__opts__['cachedir'],
                                        'gitfs/hash',
                                        short,
                                        '{0}.hash.*'.format(path))
    blobshadest = os.path.join(
            __opts__['cachedir'],
            'gitfs/hash',
            short,
            '{0}.hash.blob_sha1'.format(path))
    lk_fn = os.path.join(
            __opts__['cachedir'],
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
        ref = _get_ref(repo, short)
        if not ref:
            # Branch or tag not found in repo, try the next
            continue
        tree = ref.commit.tree
        try:
            blob = tree / path
        except KeyError:
            continue
        _wait_lock(lk_fn, dest)
        if os.path.isfile(blobshadest) and os.path.isfile(dest):
            with open(blobshadest, 'r') as fp_:
                sha = fp_.read()
                if sha == blob.hexsha:
                    fnd['rel'] = path
                    fnd['path'] = dest
                    return fnd
        with open(lk_fn, 'w+') as fp_:
            fp_.write('')
        for filename in glob.glob(hashes_glob):
            try:
                os.remove(filename)
            except Exception:
                pass
        with open(dest, 'w+') as fp_:
            blob.stream_data(fp_)
        with open(blobshadest, 'w+') as fp_:
            fp_.write(blob.hexsha)
        try:
            os.remove(lk_fn)
        except (OSError, IOError):
            pass
        fnd['rel'] = path
        fnd['path'] = dest
        return fnd
    return fnd


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


def file_hash(load, fnd):
    '''
    Return a file hash, the hash type is set in the master config file
    '''
    if 'path' not in load or 'env' not in load:
        return ''
    ret = {'hash_type': __opts__['hash_type']}
    short = load['env']
    if short == 'base':
        short = 'master'
    relpath = fnd['rel']
    path = fnd['path']
    hashdest = os.path.join(
            __opts__['cachedir'],
            'gitfs/hash',
            short,
            '{0}.hash.{1}'.format(relpath, __opts__['hash_type']))
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


def file_list(load):
    '''
    Return a list of all files on the file server in a specified
    environment
    '''
    ret = []
    if 'env' not in load:
        return ret
    if load['env'] == 'base':
        load['env'] = 'master'
    repos = init()
    for repo in repos:
        ref = _get_ref(repo, load['env'])
        if not ref:
            continue
        tree = ref.commit.tree
        for blob in tree.traverse():
            if not isinstance(blob, git.Blob):
                continue
            ret.append(blob.path)
    return ret


def file_list_emptydirs(load):
    '''
    Return a list of all empty directories on the master
    '''
    ret = []
    if 'env' not in load:
        return ret
    if load['env'] == 'base':
        load['env'] = 'master'
    repos = init()
    for repo in repos:
        ref = _get_ref(repo, load['env'])
        if not ref:
            continue
        tree = ref.commit.tree
        for blob in tree.traverse():
            if not isinstance(blob, git.Tree):
                continue
            if not blob.blobs:
                ret.append(blob.path)
    return ret


def dir_list(load):
    '''
    Return a list of all directories on the master
    '''
    ret = []
    if 'env' not in load:
        return ret
    if load['env'] == 'base':
        load['env'] = 'master'
    repos = init()
    for repo in repos:
        ref = _get_ref(repo, load['env'])
        if not ref:
            continue
        tree = ref.commit.tree
        for blob in tree.traverse():
            if not isinstance(blob, git.Tree):
                continue
            ret.append(blob.path)
    return ret
