'''
Interaction with Git repositories.
==================================

NOTE: This module is under heavy development and the API is subject to change.
It may be replaced with a generic VCS module if this proves viable.

Important: Before using git over ssh, make sure your remote host fingerprint
exists in "~/.ssh/known_hosts" file. To avoid requiring password
authentication, it is also possible to pass private keys to use explicitly.

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
           force_checkout=False,
           submodules=False,
           mirror=False,
           bare=False,
           remote_name='origin',
           always_fetch=False,
           identity=None):
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
    force_checkout
        Force a checkout even if there might be overwritten changes
        (Default: False)
    submodules
        Update submodules on clone or branch change (Default: False)
    mirror
        True if the repository is to be a mirror of the remote repository.
        This implies bare, and thus is incompatible with rev.
    bare
        True if the repository is to be a bare clone of the remote repository.
        This is incompatible with rev, as nothing will be checked out.
    remote_name
        defines a different remote name.
        For the first clone the given name is set to the default remote,
        else it is just a additional remote. (Default: 'origin')
    always_fetch
        If a tag or branch name is used as the rev a fetch will not occur
        until the tag or branch name changes. Setting this to true will force
        a fetch to occur. Only applies when rev is set. (Default: False)
    identity
        A path to a private key to use over SSH
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    if not target:
        return _fail(ret, '"target" option is required')

    bare = bare or mirror
    check = 'refs' if bare else '.git'

    if os.path.isdir(target) and os.path.isdir('{0}/{1}'.format(target,
                                                                check)):
        # git pull is probably required
        log.debug(('target {0} is found, "git pull" '
                   'is probably required'.format(target)))
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

                # if remote_name is defined set fetch_opts to remote_name
                if remote_name != 'origin':
                    fetch_opts = remote_name
                else:
                    fetch_opts = ''

                # check remote if fetch_url not == name set it
                remote = __salt__['git.remote_get'](target,
                                                    remote=remote_name,
                                                    user=runas)
                if remote is None or remote[0] != name:
                    __salt__['git.remote_set'](target,
                                               name=remote_name,
                                               url=name,
                                               user=runas)
                    ret['changes']['remote/{0}'.format(remote_name)] = "{0} => {1}".format(str(remote), name)

                # check if rev is already present in repo, git-fetch otherwise
                if bare:
                    __salt__['git.fetch'](target,
                                          opts=fetch_opts,
                                          user=runas,
                                          identity=identity)
                elif rev:

                    cmd = "git rev-parse " + rev
                    retcode = __salt__['cmd.retcode'](cmd,
                                                      cwd=target,
                                                      runas=runas)
                    # there is a issues #3938 addressing this
                    if 0 != retcode or always_fetch:
                        __salt__['git.fetch'](target,
                                              opts=fetch_opts,
                                              user=runas,
                                              identity=identity)

                    __salt__['git.checkout'](target,
                                             rev,
                                             force=force_checkout,
                                             user=runas)

                # check if we are on a branch to merge changes
                cmd = "git symbolic-ref -q HEAD > /dev/null"
                retcode = __salt__['cmd.retcode'](cmd, cwd=target, runas=runas)
                if 0 == retcode:
                    __salt__['git.fetch' if bare else 'git.pull'](target,
                                                                  opts=fetch_opts,
                                                                  user=runas,
                                                                  identity=identity)

                if submodules:
                    __salt__['git.submodule'](target,
                                              user=runas,
                                              identity=identity,
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
                log.debug(('target {0} found, but not a git repository. Since '
                           'force option is in use, deleting.').format(target))
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
            opts = '--mirror' if mirror else '--bare' if bare else ''
            # if remote_name is not origin add --origin <name> to opts
            if remote_name != 'origin':
                opts += ' --origin {0}'.format(remote_name)
            # do the clone
            __salt__['git.clone'](target,
                                  name,
                                  user=runas,
                                  opts=opts,
                                  identity=identity)

            if rev and not bare:
                __salt__['git.checkout'](target, rev, user=runas)

            if submodules:
                __salt__['git.submodule'](target,
                                          user=runas,
                                          identity=identity,
                                          opts='--recursive')

            new_rev = None if bare else (
                   __salt__['git.revision'](cwd=target, user=runas))

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
        Force-create a new repository into an pre-existing non-git directory
        (deletes contents)
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
        return _neutral_test(ret, ('New git repo set for'
                                   ' creation at {0}').format(name))

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
