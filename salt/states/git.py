'''
Interaction with Git repositories.
==================================

NOTE: This modules is under heavy development and the API is subject to change.
It may be replaced with a generic VCS module if this proves viable.

.. code-block:: yaml

    https://github.com/saltstack/salt.git:
      git.latest:
        - rev: develop
        - target: /tmp/salt
'''
import logging
import os
import shutil

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if git is available
    '''
    return 'git' if __salt__['cmd.has_exec']('git') else False


def latest(name,
           rev=None,
           target=None,
           runas=None,
           force=None,
           submodules=False,
        ):
    '''
    Make sure the repository is cloned to the given directory and is up to date

    name
        Address of the remote repository as passed to "git clone"
    rev
        The remote branch, tag, or revision ID to checkout after
        clone / before update
    target
        Name of the target directory where repository is about to be cloned
    runas
        Name of the user performing repository management operations
    force
        Force git to clone into pre-existing directories (deletes contents)
    submodules
        Update submodules on clone or branch change (Default: False)
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    if not target:
        return _fail(ret, '"target" option is required')

    if os.path.isdir(target) and os.path.isdir('{0}/.git'.format(target)):
        # git pull is probably required
        log.debug(
                'target {0} is found, "git pull" is probably required'.format(
                    target)
                )
        current_rev = __salt__['git.revision'](target, user=runas)
        if not current_rev:
            return _fail(
                    ret,
                    'Seems that {0} is not a valid git repo'.format(target))
        if __opts__['test']:
            return _neutral_test(
                    ret,
                    ('Repository {0} update is probably required (current '
                    'revision is {1})').format(target, current_rev))
        if rev:
            __salt__['git.checkout'](target, rev, user=runas)
        __salt__['git.pull'](target, user=runas)

        if submodules:
            __salt__['git.submodule'](target, user=runas)

        new_rev = __salt__['git.revision'](cwd=target, user=runas)
        if current_rev != new_rev:
            log.info('Repository {0} updated: {1} => {2}'.format(target,
                                                                 current_rev,
                                                                 new_rev))
            ret['comment'] = 'Repository {0} updated'.format(target)
            ret['changes']['revision'] = '{0} => {1}'.format(
                    current_rev, new_rev)
    else:
        if os.path.isdir(target):
            # git clone is required, but target exists -- however it is empty
            if not os.listdir(target):
                log.debug(
                    'target {0} found, but not a git repository. Since empty,'
                    ' automatically deleting.'.format(target))
                shutil.rmtree(target)
            # git clone is required, target exists but force is turned on
            elif force:
                log.debug(
                    'target {0} found, but not a git repository. Since force option'
                    ' is in use, deleting.'.format(target))
                shutil.rmtree(target)
            # git clone is required, but target exists and is non-empty
            else:
                return _fail(ret, 'Directory exists, is non-empty, and force '
                    'option not in use')
        else:
            # git clone is required
            log.debug(
                    'target {0} is not found, "git clone" is required'.format(
                        target))
        if __opts__['test']:
            return _neutral_test(
                    ret,
                    'Repository {0} is about to be cloned to {1}'.format(
                        name, target))
        # make the clone
        result = __salt__['git.clone'](target, name, user=runas)
        if not os.path.isdir(target):
            return _fail(ret, result)

        if rev:
            __salt__['git.checkout'](target, rev, user=runas)

        if submodules:
            __salt__['git.submodule'](target, user=runas)

        new_rev = __salt__['git.revision'](cwd=target, user=runas)

        message = 'Repository {0} cloned to {1}'.format(name, target)
        log.info(message)
        ret['comment'] = message

        ret['changes']['new'] = name
        ret['changes']['revision'] = new_rev
    return ret


def _fail(ret, comment):
    ret['result'] = False
    ret['comment'] = comment
    return ret


def _neutral_test(ret, comment):
    ret['result'] = None
    ret['comment'] = comment
    return ret
