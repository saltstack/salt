'''
The backend for the git based file server system. This system allows for salt
to directly reference a remote git repository as the source of truth for files.

When using the git file server backend, 
'''

# Import python libs
import os

# Import third party libs
has_git = False
try:
    import git
    has_git = True
except ImportError:
    pass

# Import salt libs


def __virtual__():
    '''
    Only load if gitpython is available
    '''
    if not isinstance(__opts__['file_roots'], list):
        return False
    return 'git' if has_git else False


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
            repo.create_remote(__opts__['file_roots'][ind])
        repos.append(git.Repo.init(rp_))
    return repos


def update():
    '''
    Execute a git pull on all of the repos
    '''
    repos = init()
    for repo in repos:
        origin = repo.remotes[0]
        origin.pull()


def envs():
    '''
    Return a list of refs that can be used as environments
    '''
    pass


def _find_file(path, ref='base'):
    '''
    Search the environment for the relative path
    '''
    if os.path.isabs(path):
        return


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
