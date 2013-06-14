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

# Import python libs
import logging
import os
import shutil

# Import salt libs
from salt.states.git import _fail, _neutral_test
from salt import utils

log = logging.getLogger(__name__)

if utils.is_windows():
    hg_binary = "hg.exe"
else:
    hg_binary = "hg"

def __virtual__():
    '''
    Only load if hg is available
    '''
    return 'hg' if __salt__['cmd.has_exec'](hg_binary) else False


def latest(name,
           rev=None,
           target=None,
           runas=None,
           force=False,
        ):
    '''
    Make sure the repository is cloned to the given directory and is up to date

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
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    if not target:
        return _fail(ret, '"target option is required')

    is_repository = (
            os.path.isdir(target) and
            os.path.isdir('{0}/.hg'.format(target)))

    if is_repository:
        ret = _update_repo(ret, target, runas, rev)
    else:
        if os.path.isdir(target):
            fail = _handle_existing(ret, target, force)
            if fail is not None:
                return fail
        else:
            log.debug(
                    'target {0} is not found, "hg clone" is required'.format(
                        target))
        if __opts__['test']:
            return _neutral_test(
                    ret,
                    'Repository {0} is about to be cloned to {1}'.format(
                        name, target))
        _clone_repo(ret, target, name, runas, rev)
    return ret


def _update_repo(ret, target, runas, rev):
    log.debug(
            'target {0} is found, '
            '"hg pull && hg up is probably required"'.format(target)
    )

    current_rev = __salt__['hg.revision'](target, user=runas)
    if not current_rev:
        return _fail(
                ret,
                'Seems that {0} is not a valid hg repo'.format(target))

    if __opts__['test']:
        test_result = (
                'Repository {0} update is probably required (current '
                'revision is {1})').format(target, current_rev)
        return _neutral_test(
                ret,
                test_result)

    pull_out = __salt__['hg.pull'](target, user=runas)

    if rev:
        __salt__['hg.update'](target, rev, user=runas)
    else:
        __salt__['hg.update'](target, 'tip', user=runas)

    new_rev = __salt__['hg.revision'](cwd=target, user=runas)

    if current_rev != new_rev:
        revision_text = '{0} => {1}'.format(current_rev, new_rev)
        log.info(
                'Repository {0} updated: {1}'.format(
                    target, revision_text)
        )
        ret['comment'] = 'Repository {0} updated.'.format(target)
        ret['changes']['revision'] = revision_text
    elif 'error:' in pull_out:
        return _fail(
            ret,
            'An error was thrown by hg:\n{0}'.format(pull_out)
        )
    return ret


def _handle_existing(ret, target, force):
    is_empty = os.listdir(target)
    if is_empty:
        log.debug(
            'target {0} found, but directory is empty, automatically '
            'deleting'.format(target))
        shutil.rmtree(target)
    elif force:
        log.debug(
            'target {0} found and is not empty. Since force option is'
            ' in use, deleting anyway.'.format(target))
        shutil.rmtree(target)
    else:
        return _fail(ret, 'Directory exists, and is not empty')


def _clone_repo(ret, target, name, runas, rev):
    result = __salt__['hg.clone'](target, name, user=runas)

    if not os.path.isdir(target):
        return _fail(ret, result)

    if rev:
        __salt__['hg.update'](target, rev, user=runas)

    new_rev = __salt__['hg.revision'](cwd=target, user=runas)
    message = 'Repository {0} cloned to {1}'.format(name, target)
    log.info(message)
    ret['comment'] = message

    ret['changes']['new'] = name
    ret['changes']['revision'] = new_rev

    return ret
