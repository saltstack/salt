# -*- coding: utf-8 -*-
'''
Git Fileserver Backend

With this backend, branches and tags in a remote git repository are exposed to
salt as different environments.

To enable, add ``gitfs`` to the :conf_master:`fileserver_backend` option in the
Master config file.

.. code-block:: yaml

    fileserver_backend:
      - gitfs

.. note::
    ``git`` also works here. Prior to the 2018.3.0 release, *only* ``git``
    would work.

The Git fileserver backend supports both pygit2_ and GitPython_, to provide the
Python interface to git. If both are present, the order of preference for which
one will be chosen is the same as the order in which they were listed: pygit2,
then GitPython.

An optional master config parameter (:conf_master:`gitfs_provider`) can be used
to specify which provider should be used, in the event that compatible versions
of both pygit2_ and GitPython_ are installed.

More detailed information on how to use GitFS can be found in the :ref:`GitFS
Walkthrough <tutorial-gitfs>`.

.. note:: Minimum requirements

    To use pygit2_ for GitFS requires a minimum pygit2_ version of 0.20.3.
    pygit2_ 0.20.3 requires libgit2_ 0.20.0. pygit2_ and libgit2_ are developed
    alongside one another, so it is recommended to keep them both at the same
    major release to avoid unexpected behavior. For example, pygit2_ 0.21.x
    requires libgit2_ 0.21.x, pygit2_ 0.22.x will require libgit2_ 0.22.x, etc.

    To use GitPython_ for GitFS requires a minimum GitPython version of 0.3.0,
    as well as the git CLI utility. Instructions for installing GitPython can
    be found :ref:`here <gitfs-dependencies>`.

    To clear stale refs the git CLI utility must also be installed.

.. _pygit2: https://github.com/libgit2/pygit2
.. _libgit2: https://libgit2.github.com/
.. _GitPython: https://github.com/gitpython-developers/GitPython
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

PER_REMOTE_OVERRIDES = (
    'base', 'mountpoint', 'root', 'ssl_verify',
    'saltenv_whitelist', 'saltenv_blacklist',
    'env_whitelist', 'env_blacklist', 'refspecs',
    'disable_saltenv_mapping', 'ref_types', 'update_interval',
)
PER_REMOTE_ONLY = ('all_saltenvs', 'name', 'saltenv')

# Auth support (auth params can be global or per-remote, too)
AUTH_PROVIDERS = ('pygit2',)
AUTH_PARAMS = ('user', 'password', 'pubkey', 'privkey', 'passphrase',
               'insecure_auth')

# Import salt libs
import salt.utils.gitfs
from salt.exceptions import FileserverConfigError

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'gitfs'


def _gitfs(init_remotes=True):
    return salt.utils.gitfs.GitFS(
        __opts__,
        __opts__['gitfs_remotes'],
        per_remote_overrides=PER_REMOTE_OVERRIDES,
        per_remote_only=PER_REMOTE_ONLY,
        init_remotes=init_remotes)


def __virtual__():
    '''
    Only load if the desired provider module is present and gitfs is enabled
    properly in the master config file.
    '''
    if __virtualname__ not in __opts__['fileserver_backend']:
        return False
    try:
        _gitfs(init_remotes=False)
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
    return _gitfs(init_remotes=False).clear_cache()


def clear_lock(remote=None, lock_type='update'):
    '''
    Clear update.lk
    '''
    return _gitfs().clear_lock(remote=remote, lock_type=lock_type)


def lock(remote=None):
    '''
    Place an update.lk

    ``remote`` can either be a dictionary containing repo configuration
    information, or a pattern. If the latter, then remotes for which the URL
    matches the pattern will be locked.
    '''
    return _gitfs().lock(remote=remote)


def update(remotes=None):
    '''
    Execute a git fetch on all of the repos
    '''
    _gitfs().update(remotes)


def update_intervals():
    '''
    Returns the update intervals for each configured remote
    '''
    return _gitfs().update_intervals()


def envs(ignore_cache=False):
    '''
    Return a list of refs that can be used as environments
    '''
    return _gitfs().envs(ignore_cache=ignore_cache)


def find_file(path, tgt_env='base', **kwargs):  # pylint: disable=W0613
    '''
    Find the first file to match the path and ref, read the file out of git
    and send the path to the newly cached file
    '''
    return _gitfs().find_file(path, tgt_env=tgt_env, **kwargs)


def init():
    '''
    Initialize remotes. This is only used by the master's pre-flight checks,
    and is not invoked by GitFS.
    '''
    _gitfs()


def serve_file(load, fnd):
    '''
    Return a chunk from a file based on the data received
    '''
    return _gitfs().serve_file(load, fnd)


def file_hash(load, fnd):
    '''
    Return a file hash, the hash type is set in the master config file
    '''
    return _gitfs().file_hash(load, fnd)


def file_list(load):
    '''
    Return a list of all files on the file server in a specified
    environment (specified as a key within the load dict).
    '''
    return _gitfs().file_list(load)


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
    return _gitfs().dir_list(load)


def symlink_list(load):
    '''
    Return a dict of all symlinks based on a given path in the repo
    '''
    return _gitfs().symlink_list(load)
