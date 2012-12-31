'''
Interaction with Git repositories.
==================================

NOTE: This modules is under heavy development and the API is subject to change.
It may be replaced with a generic VCS module if this proves viable.

Important, before using git over ssh, make sure your remote host fingerprint
exists in "~/.ssh/known_hosts" file.

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
        try:
            current_rev = __salt__['git.revision'](target, user=runas)

            #only do something, if the specified rev differs from the
            #current_rev
            if rev == current_rev:
                new_rev = current_rev
            else:

                if __opts__['test']:
                    return _neutral_test(
                        ret,
                        ('Repository {0} update is probably required (current '
                         'revision is {1})').format(target, current_rev))

                # check if rev is already present in repo and git-fetch otherwise
                if rev:

                    cmd = "git rev-parse "+rev
                    retcode = __salt__['cmd.retcode'](cmd, cwd=target, runas=runas)
                    if 0 != retcode:
                        __salt__['git.fetch'](target, user=runas)

                    __salt__['git.checkout'](target, rev, user=runas)

                # check if we are on a branch to merge changes
                cmd = "git symbolic-ref -q HEAD > /dev/null"
                retcode = __salt__['cmd.retcode'](cmd, cwd=target, runas=runas)
                if 0 == retcode:
                    __salt__['git.pull'](target, user=runas)

                if submodules:
                    __salt__['git.submodule'](target, user=runas,
                                              opts='--recursive')

                new_rev = __salt__['git.revision'](cwd=target, user=runas)

        except Exception as exc:
            return _fail(
                    ret,
                    str(exc))

        if current_rev != new_rev:
            log.info('Repository {0} updated: {1} => {2}'.format(target,
                                                                 current_rev,
                                                                 new_rev))
            ret['comment'] = 'Repository {0} updated'.format(target)
            ret['changes']['revision'] = '{0} => {1}'.format(
                    current_rev, new_rev)
    else:
        if os.path.isdir(target):
            # git clone is required, target exists but force is turned on
            if force:
                log.debug(
                    'target {0} found, but not a git repository. Since force option'
                    ' is in use, deleting.'.format(target))
                shutil.rmtree(target)
            # git clone is required, but target exists and is non-empty
            elif os.listdir(target):
                return _fail(ret, 'Directory exists, is non-empty, and force '
                    'option not in use')

        # git clone is required
        log.debug(
                'target {0} is not found, "git clone" is required'.format(
                    target))
        if 'test' in __opts__:
            if __opts__['test']:
                return _neutral_test(
                        ret,
                        'Repository {0} is about to be cloned to {1}'.format(
                            name, target))
        try:
            # make the clone
            __salt__['git.clone'](target, name, user=runas)

            if rev:
                __salt__['git.checkout'](target, rev, user=runas)

            if submodules:
                __salt__['git.submodule'](target, user=runas, opts='--recursive')

            new_rev = __salt__['git.revision'](cwd=target, user=runas)

        except Exception as exc:
            return _fail(
                    ret,
                    str(exc))

        message = 'Repository {0} cloned to {1}'.format(name, target)
        log.info(message)
        ret['comment'] = message

        ret['changes']['new'] = name
        ret['changes']['revision'] = new_rev
    return ret


def present(name, bare=True, runas=None, force=False):
    '''
    Make sure the repository is present in the given directory

    name
        Name of the directory where the repository is about to be created
    bare
        Create a bare repository (Default: True)
    runas
        Name of the user performing repository management operations
    force
        Force create a new repository into an pre-existing non-git directory (deletes contents)
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    # If the named directory is a git repo return True
    if os.path.isdir(name):
        if bare and os.path.isfile('{0}/HEAD'.format(name)):
            return ret
        elif not bare and os.path.isdir('{0}/.git'.format(name)):
            return ret
        # Directory exists and is not a git repo, if force is set destroy the
        # directory and recreate, otherwise throw an error
        elif not force and os.listdir(name):
            return _fail(ret,
                         'Directory which does not contain a git repo '
                         'is already present at {0}. To delete this '
                         'directory and create a fresh git repo set '
                         'force: True'.format(name))

    # Run test is set
    if __opts__['test']:
        ret['changes']['new repository'] = name
        return _neutral_test(ret, 'New git repo set for creation at {0}'.format(name))

    if force and os.path.isdir(name):
        shutil.rmtree(name)

    opts = '--bare' if bare else ''
    __salt__['git.init'](cwd=name, user=runas, opts=opts)

    message = 'Initialized repository {0}'.format(name)
    log.info(message)
    ret['changes']['new repository'] = name
    ret['comment'] = message

    return ret


def _fail(ret, comment):
    ret['result'] = False
    ret['comment'] = comment
    return ret


def _neutral_test(ret, comment):
    ret['result'] = None
    ret['comment'] = comment
    return ret
