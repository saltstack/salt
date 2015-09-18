# -*- coding: utf-8 -*-
'''
Interaction with Git repositories
=================================

Important: Before using git over ssh, make sure your remote host fingerprint
exists in "~/.ssh/known_hosts" file. To avoid requiring password
authentication, it is also possible to pass private keys to use explicitly.

.. code-block:: yaml

    https://github.com/saltstack/salt.git:
      git.latest:
        - rev: develop
        - target: /tmp/salt
'''
from __future__ import absolute_import

# Import python libs
import logging
import os
import os.path
import shutil

# Import salt libs
import salt.utils
import salt.utils.url
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if git is available
    '''
    return __salt__['cmd.has_exec']('git')


def latest(name,
           rev=None,
           target=None,
           user=None,
           force=None,
           force_checkout=False,
           force_reset=False,
           submodules=False,
           mirror=False,
           bare=False,
           remote_name='origin',
           always_fetch=False,
           depth=None,
           identity=None,
           https_user=None,
           https_pass=None,
           onlyif=False,
           unless=False):
    '''
    Make sure the repository is cloned to the given directory and is up to date

    name
        Address of the remote repository as passed to "git clone"

    rev
        The remote branch, tag, or revision ID to checkout after
        clone / before update

    target
        Name of the target directory where repository is about to be cloned

    user
        Name of the user performing repository management operations

        .. versionadded:: 0.17.0

    force
        Force git to clone into pre-existing directories (deletes contents)

    force_checkout
        Force a checkout even if there might be overwritten changes
        (Default: False)

    force_reset
        Force the checkout to ``--reset hard`` to the remote ref
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

    depth
        Defines depth in history when git a clone is needed in order to ensure
        latest. E.g. ``depth: 1`` is usefull when deploying from a repository
        with a long history. Use rev to specify branch. This is not compatible with tags or revision IDs.(Default: ``None``)

    identity
        A path on the minion server to a private key to use over SSH

    https_user
        HTTP Basic Auth username for HTTPS (only) clones

        .. versionadded:: 2015.5.0

    https_pass
        HTTP Basic Auth password for HTTPS (only) clones

        .. versionadded:: 2015.5.0

    onlyif
        A command to run as a check, run the named command only if the command
        passed to the ``onlyif`` option returns true

    unless
        A command to run as a check, only run the named command if the command
        passed to the ``unless`` option returns false

    .. note::

        Clashing ID declarations can be avoided when including different
        branches from the same git repository in the same sls file by using the
        ``name`` declaration.  The example below checks out the ``gh-pages``
        and ``gh-pages-prod`` branches from the same repository into separate
        directories.  The example also sets up the ``ssh_known_hosts`` ssh key
        required to perform the git checkout.

    .. code-block:: yaml

        gitlab.example.com:
          ssh_known_hosts:
            - present
            - user: root
            - enc: ecdsa
            - fingerprint: 4e:94:b0:54:c1:5b:29:a2:70:0e:e1:a3:51:ee:ee:e3

        git-website-staging:
          git.latest:
            - name: git@gitlab.example.com:user/website.git
            - rev: gh-pages
            - target: /usr/share/nginx/staging
            - identity: /root/.ssh/website_id_rsa
            - require:
                - pkg: git
                - ssh_known_hosts: gitlab.example.com

        git-website-prod:
          git.latest:
            - name: git@gitlab.example.com:user/website.git
            - rev: gh-pages-prod
            - target: /usr/share/nginx/prod
            - identity: /root/.ssh/website_id_rsa
            - require:
                - pkg: git
                - ssh_known_hosts: gitlab.example.com
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    # Check to make sure rev and mirror/bare are not both in use
    if rev and (mirror or bare):
        return _fail(ret, ('"rev" is not compatible with the "mirror" and '
                           '"bare" arguments'))

    if not target:
        return _fail(ret, '"target" option is required')

    target = os.path.expanduser(target)

    try:
        desired_fetch_url = salt.utils.url.add_http_basic_auth(
            name,
            https_user,
            https_pass,
            https_only=True
        )
    except ValueError as exc:
        return _fail(ret, exc.__str__())

    redacted_fetch_url = \
        salt.utils.url.redact_http_basic_auth(desired_fetch_url)

    run_check_cmd_kwargs = {'runas': user}
    if 'shell' in __grains__:
        run_check_cmd_kwargs['shell'] = __grains__['shell']

    # check if git.latest should be applied
    cret = mod_run_check(
        run_check_cmd_kwargs, onlyif, unless
    )
    if isinstance(cret, dict):
        ret.update(cret)
        return ret

    bare = bare or mirror
    check = 'refs' if bare else '.git'
    checkdir = os.path.join(target, check)
    if os.path.isdir(target) and os.path.isdir(checkdir):
        # git pull is probably required
        log.debug(('target {0} is found, "git pull" '
                   'is probably required'.format(target)))
        try:
            try:
                current_rev = __salt__['git.revision'](target, user=user)
            except CommandExecutionError:
                current_rev = None

            # handle the case where a branch was provided for rev
            remote_rev, new_rev = None, None
            try:
                branch = __salt__['git.current_branch'](target, user=user)
            except CommandExecutionError:
                branch = None

            # We're only interested in the remote branch if a branch
            # (instead of a hash, for example) was provided for rev.
            if (branch != 'HEAD' and branch == rev) or rev is None:
                remote_rev = __salt__['git.ls_remote'](target,
                                                       repository=name,
                                                       branch=branch,
                                                       user=user,
                                                       identity=identity,
                                                       https_user=https_user,
                                                       https_pass=https_pass)

            # only do something, if the specified rev differs from the
            # current_rev and remote_rev
            if current_rev in [rev, remote_rev] or (remote_rev is not None and remote_rev.startswith(current_rev)):
                new_rev = current_rev
            else:

                if __opts__['test']:
                    ret['changes'] = {'old': current_rev, 'new': new_rev}
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
                                                    user=user,
                                                    redact_auth=False)
                if remote is None or remote[0] != desired_fetch_url:
                    __salt__['git.remote_set'](target,
                                               name=remote_name,
                                               url=name,
                                               user=user,
                                               https_user=https_user,
                                               https_pass=https_pass)
                    ret['changes']['remote/{0}'.format(remote_name)] = (
                        "{0} => {1}".format(
                            salt.utils.url.redact_http_basic_auth(str(remote)),
                            redacted_fetch_url
                        )
                    )
                    # Set to fetch later since we just added the remote and
                    # need to get the refs
                    always_fetch = True

                # check if rev is already present in repo, git-fetch otherwise
                if bare:
                    __salt__['git.fetch'](target,
                                          opts=fetch_opts,
                                          user=user,
                                          identity=identity)
                elif rev:

                    cmd = 'git rev-parse {0}^{{commit}}'.format(rev)
                    retcode = __salt__['cmd.retcode'](cmd,
                                                      cwd=target,
                                                      runas=user)
                    # there is a issues #3938 addressing this
                    if 0 != retcode or always_fetch:
                        __salt__['git.fetch'](target,
                                              opts=fetch_opts,
                                              user=user,
                                              identity=identity)

                    if force_reset:
                        opts = "--hard {0}/{1}".format(remote_name, rev)
                        __salt__['git.reset'](target,
                                              opts=opts,
                                              user=user)

                    __salt__['git.checkout'](target,
                                             rev,
                                             force=force_checkout,
                                             user=user)

                    if branch != 'HEAD':
                        try:
                            current_remote = __salt__['git.config_get'](
                                target, 'branch.{0}.remote'.format(rev),
                                user=user)
                        except CommandExecutionError:
                            current_remote = None

                        if current_remote != remote_name:
                            if __opts__['test']:
                                ret['changes'] = {'old': current_remote,
                                                  'new': remote_name}
                                return _neutral_test(
                                    ret,
                                    ('Repository {0} update is probably '
                                     'required. Current remote is {1} should '
                                     'be {2}'.format(target, current_remote,
                                                     remote_name)))
                            log.debug(
                                'Setting branch {0} to '
                                'upstream {1}'.format(rev, remote_name))
                            __salt__['git.branch'](
                                target, rev,
                                opts='--set-upstream '
                                '{0}/{1}'.format(remote_name, rev),
                                user=user)
                            ret['changes']['remote/''{0}/{1}'.format(
                                remote_name, rev)] = (
                                    '{0} => {1}'.format(current_remote,
                                                        remote_name))

                # check if we are on a branch to merge changes
                cmd = "git symbolic-ref -q HEAD"
                retcode = __salt__['cmd.retcode'](cmd, cwd=target, runas=user)
                if 0 == retcode:
                    __salt__['git.fetch' if bare else 'git.pull'](
                        target, opts=fetch_opts, user=user, identity=identity)

                if submodules:
                    __salt__['git.submodule'](target,
                                              user=user,
                                              identity=identity,
                                              opts='--recursive')

                try:
                    new_rev = __salt__['git.revision'](cwd=target, user=user)
                except CommandExecutionError:
                    new_rev = None
        except Exception as exc:
            log.error('Unexpected exception in git state', exc_info=True)
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
                if __opts__['test']:
                    return _neutral_test(
                        ret,
                        'Repository {0} is about to be cloned to {1}.'
                        'Since force option is in use, deleting.'.format(
                            name, target))

                log.debug(('target {0} found, but not a git repository. Since '
                           'force option is in use, deleting.').format(target))
                if os.path.islink(target):
                    os.remove(target)
                else:
                    shutil.rmtree(target)
            # git clone is required, but target exists and is non-empty
            elif os.listdir(target):
                return _fail(ret, 'Directory \'{0}\' exists, is non-empty, '
                             'and force option not in use'.format(target))

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

            # if depth is given add --depth <depth> to opts
            if depth is not None:
                opts += ' --depth {0}'.format(depth)
                if rev is not None:
                    opts += ' --branch {0}'.format(rev)

            # do the clone
            __salt__['git.clone'](target,
                                  name,
                                  user=user,
                                  opts=opts,
                                  identity=identity,
                                  https_user=https_user,
                                  https_pass=https_pass)

            if rev and not bare:
                __salt__['git.checkout'](target, rev, user=user)

            if submodules:
                __salt__['git.submodule'](target,
                                          user=user,
                                          identity=identity,
                                          opts='--recursive')

            new_rev = None
            if not bare:
                try:
                    new_rev = __salt__['git.revision'](cwd=target, user=user)
                except CommandExecutionError:
                    pass

        except Exception as exc:
            log.error('Unexpected exception in git state', exc_info=True)
            return _fail(
                ret,
                str(exc))

        message = 'Repository {0} cloned to {1}'.format(name, target)
        log.info(message)
        ret['comment'] = message

        ret['changes']['new'] = name
        ret['changes']['revision'] = new_rev
    return ret


def present(name, bare=True, user=None, force=False, shared=None):
    '''
    Make sure the repository is present in the given directory

    name
        Name of the directory where the repository is about to be created

    bare
        Create a bare repository (Default: True)

    user
        Name of the user performing repository management operations

        .. versionadded:: 0.17.0

    force
        Force-create a new repository into an pre-existing non-git directory
        (deletes contents)

    shared
        Specify the permission for sharing, see git-init for details (Default: None)

       .. versionadded:: 2015.5.0
    '''
    name = os.path.expanduser(name)
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    # If the named directory is a git repo return True
    if os.path.isdir(name):
        if bare and os.path.isfile(os.path.join(name, 'HEAD')):
            return ret
        elif not bare and os.path.isdir(os.path.join(name, '.git')):
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
        if os.path.islink(name):
            os.remove(name)
        else:
            shutil.rmtree(name)

    opts = '--bare' if bare else ''
    opts += ' --shared={0}'.format(shared) if shared else ''
    __salt__['git.init'](cwd=name, user=user, opts=opts)

    message = 'Initialized repository {0}'.format(name)
    log.info(message)
    ret['changes']['new repository'] = name
    ret['comment'] = message

    return ret


def config(name,
           value,
           repo=None,
           user=None,
           is_global=False):
    '''
    .. versionadded:: 2014.7.0

    Manage a git config setting for a user or repository

    name
        Name of the git config value to set

    value
        Value to set

    repo : None
        An optional location of a git repository for local operations

    user : None
        Optional name of a user as whom `git config` will be run

    is_global : False
        Whether or not to pass the `--global` option to `git config`

    Local config example:

    .. code-block:: yaml

        mylocalrepo:
          git.config:
            - name: user.email
            - value: fester@bestertester.net
            - repo: file://my/path/to/repo

    Global config example:

    .. code-block:: yaml

        mylocalrepo:
          git.config:
            - name: user.name
            - value: Esther Bestertester
            - user: ebestertester
            - is_global: True
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    # get old value
    try:
        oval = __salt__['git.config_get'](setting_name=name,
                                          cwd=repo,
                                          user=user)
    except CommandExecutionError:
        oval = None

    if value == oval:
        ret['comment'] = 'No changes made'
    else:
        if __opts__['test']:
            nval = value
        else:
            # set new value
            __salt__['git.config_set'](setting_name=name,
                                       setting_value=value,
                                       cwd=repo,
                                       user=user,
                                       is_global=is_global)

            # get new value
            nval = __salt__['git.config_get'](setting_name=name,
                                              cwd=repo,
                                              user=user)

        if oval is None:
            oval = 'None'

        ret['changes'][name] = '{0} => {1}'.format(oval, nval)

    return ret


def _fail(ret, comment):
    ret['result'] = False
    ret['comment'] = comment
    return ret


def _neutral_test(ret, comment):
    ret['result'] = None
    ret['comment'] = comment
    return ret


def mod_run_check(cmd_kwargs, onlyif, unless):
    '''
    Execute the onlyif and unless logic.
    Return a result dict if:
    * onlyif failed (onlyif != 0)
    * unless succeeded (unless == 0)
    else return True
    '''
    if onlyif:
        if __salt__['cmd.retcode'](onlyif, **cmd_kwargs) != 0:
            return {'comment': 'onlyif execution failed',
                    'skip_watch': True,
                    'result': True}

    if unless:
        if __salt__['cmd.retcode'](unless, **cmd_kwargs) == 0:
            return {'comment': 'unless execution succeeded',
                    'skip_watch': True,
                    'result': True}

    # No reason to stop, return True
    return True
