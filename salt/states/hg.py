'''
Interaction with Mercurial repositories.
========================================

NOTE: This module is currently experimental. Most of this code is copied from
git.py with changes to handle hg.

Before using hg over ssh, make sure the remote host fingerprint already exists
in ~/.ssh/known_hosts, and the remote host has this host's public key.

.. code-block:: yaml

    https://bitbucket.org/example_user/example_repo:
        hg.latest:
          - rev: tip
          - target: /tmp/example_repo
'''
import logging
import os
import shutil

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if hg is available
    '''
    return 'hg' if __salt__['cmd.has_exec']('hg') else False


def latest(name,
           rev=None,
           target=None,
           runas=None,
           force=None,
        ):
    '''
    Make sure the repository is cloned to to given directory and is up to date

    name
        Address of the remote repository as passed to "hg clone"
    rev
        The remote branch, tag, or revision hash to clone/pull
    target
        Name of the target directory where repository is about to be cloned
    runas
        Name of the user performing repository management operations
    force
        Force hg to clone into pre-existing directories (deletes contents)
    '''
