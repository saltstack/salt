'''
The backed for the mercurial based file server system.

After enabling this backend, branches, bookmarks, and tags in a remote
mercurial repository are exposed to salt as different environments. This
feature is managed by the fileserver_backend option in the salt master config.

:depends:   - mercurial
'''

# Import python libs
import os
import logging

# Import third party libs
HAS_HG = False
try:
    import hgapi
    HAS_HG = True
except ImportError:
    pass

# Import salt libs
import salt.utils
import salt.fileserver


log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if mercurial is available
    '''
    if not isinstance(__opts__['hgfs_remotes'], list):
        return False
    if not isinstance(__opts__['hgfs_root'], str):
        return False
    if not 'hg' in __opts__['fileserver_backend']:
        return False
    if not HAS_HG:
        log.error('Mercurial fileserver backend is enabled in configuration '
                  'but could not be loaded, is hgapi installed?')
        return False


def _get_ref(repo, short):
    '''
    Return bool if short ref is in the repo
    '''
    for ref in repo.get_branch_names():
        if short == ref:
            return ref
    for ref in repo.get_tags().keys():
        if short == ref:
            return ref
    return False


def init():
    '''
    Return the hg repo object for this session
    '''
    bp_ = os.path.join(__opts__['cachedir'], 'hgfs')
    repos = []
    for ind in range(len(__opts__['hgfs_remotes'])):
        rp_ = os.path.join(bp_, str(ind))
        if not os.path.isdir(rp_):
            os.makedirs(rp_)
        repo = hgapi.Repo(rp_)
        repo.hg_init()
        if not repo.config('paths', 'default'):
            hgconfpath = os.path.join(rp_, '.hg', 'config')
            with salt.utils.fopen(hgconfpath, 'w+') as hgconfig:
                hgconfig.write('[paths]')
                hgconfig.write('default = {0}'.format(
                    __opts__['hgfs_remotes'][ind]))
            repos.append(repo)

    return repos


def update():
    '''
    Execute a hg pull on all of the repos
    '''
    pid = os.getpid()
    repos = init()
    for repo in repos:
        default = repo.config('paths', 'default')
        lk_fn = os.path.join(repo.path, 'update.lk')
        with salt.utils.fopen(lk_fn, 'w+') as fp_:
            fp_.write(str(pid))
        repo.hg_command('pull', default)
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
        branches = repo.get_branch_names()
        for branch in branches:
            if branch == 'default':
                branch = 'base'
            ret.add(branch)
        tags = repo.get_tags()
        for tag in tags.keys():
            ret.add(tag)
    return list(ret)


def find_file(path, short='base', **kwargs):
    '''
    Find the first file to match the path and ref, read the file out of hg
    and send the path to the newly cached file
    '''


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
        short = 'default'
    relpath = fnd['rel']
    path = fnd['path']
    hashdest = os.path.join(__opts__['cachedir'],
                            'hgfs/hash',
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


def file_list(load):
    '''
    Return a list of all files on the file server in a specified
    environment
    '''


def file_list_emptydirs(load):
    '''
    Return a list of all empty directories on the master
    '''


def dir_list(load):
    '''
    Return a list of all directories on the master
    '''
