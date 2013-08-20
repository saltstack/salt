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
            with open(os.path.join(rp_, '.hg', 'config'), 'w') as hgconfig:
                hgconfig.write('[paths]')
                hgconfig.write('default = {0}'.format(
                    __opts__['hgfs_remotes'][ind]))
            repos.append(repo)

    return repos


def update():
    '''
    Execute a hg pull on all of the repos
    '''


def envs():
    '''
    Return a list of refs that can be used as environments
    '''


def find_file(path, short='base', **kwargs):
    '''
    Find the first file to match the path and ref, read the file out of hg
    and send the path to the newly cached file
    '''


def serve_file(load, fnd):
    '''
    Return a chunk from a file based on the data received
    '''


def file_hash(load, fnd):
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
