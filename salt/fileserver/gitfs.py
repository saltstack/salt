# -*- coding: utf-8 -*-
'''
Git Fileserver Backend

With this backend, branches and tags in a remote git repository are exposed to
salt as different environments.

To enable, add ``git`` to the :conf_master:`fileserver_backend` option in the
Master config file.

.. code-block:: yaml

    fileserver_backend:
      - git

As of Salt 2014.7.0, the Git fileserver backend supports GitPython_, pygit2_,
and dulwich_ to provide the Python interface to git. If more than one of these
are present, the order of preference for which one will be chosen is the same
as the order in which they were listed: pygit2, GitPython, dulwich (keep in
mind, this order is subject to change).

An optional master config parameter (:conf_master:`gitfs_provider`) can be used
to specify which provider should be used.

More detailed information on how to use gitfs can be found in the :ref:`Gitfs
Walkthrough <tutorial-gitfs>`.

.. note:: Minimum requirements

    To use GitPython_ for gitfs requires a minimum GitPython version of 0.3.0,
    as well as the git CLI utility. Instructions for installing GitPython can
    be found :ref:`here <gitfs-dependencies>`.

    To use pygit2_ for gitfs requires a minimum pygit2_ version of 0.20.3.
    pygit2_ 0.20.3 requires libgit2_ 0.20.0. pygit2_ and libgit2_ are developed
    alongside one another, so it is recommended to keep them both at the same
    major release to avoid unexpected behavior. For example, pygit2_ 0.21.x
    requires libgit2_ 0.21.x, pygit2_ 0.22.x will require libgit2_ 0.22.x, etc.

    To find stale refs, pygit2 additionally requires the git CLI utility to be
    installed.

.. _GitPython: https://github.com/gitpython-developers/GitPython
.. _pygit2: https://github.com/libgit2/pygit2
.. _libgit2: https://libgit2.github.com/
.. _dulwich: https://www.samba.org/~jelmer/dulwich/
'''

# Import python libs
from __future__ import absolute_import
import logging

PER_REMOTE_OVERRIDES = ('base', 'mountpoint', 'root', 'ssl_verify')
SYMLINK_RECURSE_DEPTH = 100

# Auth support (auth params can be global or per-remote, too)
AUTH_PROVIDERS = ('pygit2',)
AUTH_PARAMS = ('user', 'password', 'pubkey', 'privkey', 'passphrase',
               'insecure_auth')

# Import salt libs
import salt.utils.gitfs
from salt.exceptions import FileserverConfigError

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'git'


def __virtual__():
    '''
    Only load if the desired provider module is present and gitfs is enabled
    properly in the master config file.
    '''
    if __virtualname__ not in __opts__['fileserver_backend']:
        return False
    try:
        salt.utils.gitfs.GitFS(__opts__)
        # Initialization of the GitFS object did not fail, so we know we have
        # valid configuration syntax and that a valid provider was detected.
        return __virtualname__
    except FileserverConfigError:
        pass
    return False


def clear_cache():
    '''
    Completely clear gitfs cache
    '''
    gitfs = salt.utils.gitfs.GitFS(__opts__)
    return gitfs.clear_cache()


def clear_lock(remote=None, lock_type='update'):
    '''
    Clear update.lk
    '''
    gitfs = salt.utils.gitfs.GitFS(__opts__)
    gitfs.init_remotes(__opts__['gitfs_remotes'], PER_REMOTE_OVERRIDES)
    return gitfs.clear_lock(remote=remote, lock_type=lock_type)


def lock(remote=None):
    '''
    Place an update.lk

    ``remote`` can either be a dictionary containing repo configuration
    information, or a pattern. If the latter, then remotes for which the URL
    matches the pattern will be locked.
    '''
    gitfs = salt.utils.gitfs.GitFS(__opts__)
    gitfs.init_remotes(__opts__['gitfs_remotes'], PER_REMOTE_OVERRIDES)
    return gitfs.lock(remote=remote)


def update():
    '''
    Execute a git fetch on all of the repos
    '''
    gitfs = salt.utils.gitfs.GitFS(__opts__)
    gitfs.init_remotes(__opts__['gitfs_remotes'], PER_REMOTE_OVERRIDES)
    gitfs.update()


def envs(ignore_cache=False):
    '''
    Return a list of refs that can be used as environments
    '''
    gitfs = salt.utils.gitfs.GitFS(__opts__)
    gitfs.init_remotes(__opts__['gitfs_remotes'], PER_REMOTE_OVERRIDES)
    return gitfs.envs(ignore_cache=ignore_cache)


def find_file(path, tgt_env='base', **kwargs):  # pylint: disable=W0613
    '''
    Find the first file to match the path and ref, read the file out of git
    and send the path to the newly cached file
    '''
    gitfs = salt.utils.gitfs.GitFS(__opts__)
    gitfs.init_remotes(__opts__['gitfs_remotes'], PER_REMOTE_OVERRIDES)
    return gitfs.find_file(path, tgt_env=tgt_env, **kwargs)


def init():
    '''
    Initialize remotes. This is only used by the master's pre-flight checks,
    and is not invoked by GitFS.
    '''
    gitfs = salt.utils.gitfs.GitFS(__opts__)
    gitfs.init_remotes(__opts__['gitfs_remotes'], PER_REMOTE_OVERRIDES)


def serve_file(load, fnd):
    '''
    Return a chunk from a file based on the data received
    '''
    gitfs = salt.utils.gitfs.GitFS(__opts__)
    gitfs.init_remotes(__opts__['gitfs_remotes'], PER_REMOTE_OVERRIDES)
    return gitfs.serve_file(load, fnd)


def file_hash(load, fnd):
    '''
    Return a file hash, the hash type is set in the master config file
    '''
    gitfs = salt.utils.gitfs.GitFS(__opts__)
    gitfs.init_remotes(__opts__['gitfs_remotes'], PER_REMOTE_OVERRIDES)
    return gitfs.file_hash(load, fnd)


def file_list(load):
    '''
    Return a list of all files on the file server in a specified
    environment (specified as a key within the load dict).
    '''
    gitfs = salt.utils.gitfs.GitFS(__opts__)
    gitfs.init_remotes(__opts__['gitfs_remotes'], PER_REMOTE_OVERRIDES)
    return gitfs.file_list(load)


def file_list_emptydirs(load):  # pylint: disable=W0613
    '''
    Return a list of all empty directories on the master
    '''
    # Cannot have empty dirs in git
    return []


def dir_list(load):
    '''
    Return a list of all directories on the master
    '''
    gitfs = salt.utils.gitfs.GitFS(__opts__)
    gitfs.init_remotes(__opts__['gitfs_remotes'], PER_REMOTE_OVERRIDES)
    return gitfs.dir_list(load)


def symlink_list(load):
    '''
    Return a dict of all symlinks based on a given path in the repo
    '''
    gitfs = salt.utils.gitfs.GitFS(__opts__)
    gitfs.init_remotes(__opts__['gitfs_remotes'], PER_REMOTE_OVERRIDES)
    return gitfs.symlink_list(load)
