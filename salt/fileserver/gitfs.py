'''
The backend for the git based file server system. This system allows for salt
to directly reference a remote git repository as the source of truth for files.

When using the git file server backend,
'''

# Import python libs
import os
import hashlib
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


def __virtual__():
    '''
    Only load if gitpython is available
    '''
    if not isinstance(__opts__['file_roots'], list):
        return False
    return 'git' if HAS_GIT else False


def _check_ref(short, repo):
    '''
    Return bool if the short ref is in the repo
    '''
    for ref in repo.refs:
        if isinstance(ref, git.TagReference):
            if short == os.path.basename(ref.name):
                return True
        elif isinstance(ref, git.Head):
            if short == os.path.basename(ref.name):
                return True
    return False


def init():
    '''
    Return the git repo object for this session
    '''
    bp_ = os.path.join(__opts__['cachedir'], 'gitfs')
    repos = []
    for ind in range(len(__opts__['file_roots'])):
        rp_ = os.path.join(bp_, str(ind))
        if not os.path.isdir(rp_):
            os.makedirs(rp_)
        repo = git.Repo.init(rp_)
        if not repo.remotes:
            repo.create_remote('origin', __opts__['file_roots'][ind])
        repos.append(repo.remotes.origin)
    return repos


def update():
    '''
    Execute a git pull on all of the repos
    '''
    repos = init()
    for repo in repos:
        for ref in repo.refs:
            if isinstance(ref, git.refs.remote.RemoteReference):
                found = False
                short = os.path.basename(ref.name)
                for branch in repo.branches:
                    if os.path.basename(branch.name) == short:
                        # Found it, make sure it has the correct ref
                        if not branch.tracking_branch() is ref:
                            branch.set_tracking_branch
                if not found:
                    branch = repo.create_head('refs/heads/{0}'.format(short))
                    branch.set_tracking_branch(ref)

        origin = repo.remotes[0]
        origin.fetch()


def envs():
    '''
    Return a list of refs that can be used as environments
    '''
    ret = set()
    repos = init()
    for repo in repos:
        for ref in repo.refs:
            if isinstance(ref, git.refs.head.Head):
                short = os.path.basename(ref.name)
                ret.add(short)
    return list(ret)


def _find_file(path, short='base'):
    '''
    Find the first file to match the path and ref, read the file out of git
    and send the path to the newly cached file
    '''
    if os.path.isabs(path):
        return fnd
    fnd = {'path': '',
           'rel': ''}
    if short == 'base':
        short = 'master'
    dest = os.path.join(__opts__['cachedir'], 'gitfs/refs', short, path)
    shadest = os.path.join(
            __opts__['cachedir'],
            'gitfs/hash',
            short,
            '{0}.sha1'.format(path))
    md5dest = os.path.join(
            __opts__['cachedir'],
            'gitfs/hash',
            short,
            '{0}.md5'.format(path))
    destdir = os.path.dirname(dest)
    shadir = os.path.dirname(shadest)
    if not os.path.isdir(destdir):
        os.makedirs(destdir)
    if not os.path.isdir(shadir):
        os.makedirs(shadir)
    repos = init()
    for repo in repos:
        ref = _get_ref(repo, short)
        if not ref:
            # Branch or tag not found in repo, try the next
            continue
        tree = ref.commit.tree
        try:
            blob = tree/path
        except KeyError:
            continue
        if os.path.isfile(shadest) and os.path.isfile(dest):
            with open(shadest, 'r') as fp_:
                sha = fp_.read()
                if sha == blob.hexsha:
                    fnd['rel'] = path
                    fnd['path'] = dest
                    return fnd
        with open(dest, 'w+') as fp_:
            git.util.stream_copy(blob.data_stream, fp_)
        with open(shadest, 'w+') as fp_:
            fp_.write(blob.hexsha)
        if os.path.isfile(md5dest):
            try:
                os.remove(md5dest)
            except Exception:
                pass
        fnd['rel'] = path
        fnd['path'] = dest
        return fnd
    return fnd


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
    ret = {'hash_type': __opts__['hash_type']}
    short = load['env']
    if short == 'base':
        short = 'master'
    path = _find_file(load['path'], short)['path']
    hashdest = os.path.join(
            __opts__['cachedir'],
            'gitfs/hash',
            short,
            '{0}.hash'.format(path))
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
    repos = init()
    for repo in repos:
        ref = _get_ref(repo, load[env])
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
    repos = init()
    for repo in repos:
        ref = _get_ref(repo, load[env])
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
    repos = init()
    for repo in repos:
        ref = _get_ref(repo, load[env])
        if not ref:
            continue
        tree = ref.commit.tree
        for blob in tree.traverse():
            if not isinstance(blob, git.Tree):
                continue
            ret.append(blob.path)
    return ret
