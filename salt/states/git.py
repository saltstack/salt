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
import copy
import logging
import os
import re
import shutil

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError
from salt.ext import six

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if git is available
    '''
    return __salt__['cmd.has_exec']('git')


def _parse_fetch(output):
    '''
    Go through the output from a git fetch and return a dict
    '''
    update_re = re.compile(
        '.*(?:([0-9a-f]+)\.\.([0-9a-f]+)|'
        '\[(?:new (tag|branch)|tag update)\])\s+(.+)->'
    )
    ret = {}
    for line in output.splitlines():
        match = update_re.match(line)
        if match:
            old_sha, new_sha, new_ref_type, ref_name = \
                match.groups()
            ref_name = refname.rstrip()
            if new_ref_type is not None:
                # ref is a new tag/branch
                ref_key = 'new tags' \
                    if new_ref_type == 'tag' \
                    else 'new branches'
                ret.setdefault(ref_key, []).append(ref_name)
            elif old_sha is not None:
                # ref is a branch update
                ret.setdefault('updated_branches', {})[ref_name] = \
                    {'old': old_sha, 'new': new_sha}
            else:
                # ref is an updated tag
                ret.setdefault('updated tags', []).append(ref_name)
    return ret


def _get_local_rev(target, user):
    '''
    Return the local revision for before/after comparisons
    '''
    log.debug('Checking local revision for {0}'.format(target))
    try:
        return __salt__['git.revision'](target, user=user, ignore_retcode=True)
    except CommandExecutionError:
        log.debug('No local revision for {0}'.format(target))
        return None


def _strip_exc(exc):
    '''
    Strip the actual command that was run
    '''
    return re.sub('^Command [\'"].+[\'"] failed: ', '', exc.strerror)


def _fail(ret, comment):
    ret['result'] = False
    ret['comment'] = comment
    return ret


def _neutral_test(ret, comment):
    ret['result'] = None
    ret['comment'] = comment
    return ret


def latest(name,
           rev=None,
           target=None,
           user=None,
           force=False,
           force_checkout=False,
           force_reset=False,
           submodules=False,
           bare=False,
           mirror=False,
           remote='origin',
           always_fetch=False,
           fetch_tags=True,
           depth=None,
           identity=None,
           https_user=None,
           https_pass=None,
           remote_name=None,
           onlyif=False,
           unless=False):
    '''
    Make sure the repository is cloned to the given directory and is up to
    date.  The remote tracking branch will be set to ``<remote>/<rev>``.

    name
        Address of the remote repository as passed to "git clone"

    rev
        The remote branch, tag, or revision ID to checkout after
        clone / before update

    target
        Name of the target directory where repository is about to be cloned

    user
        User under which to run git commands. By default, commands are run by
        the user under which the minion is running.

        .. versionadded:: 0.17.0

    force
        Force git to clone into pre-existing directories (deletes contents)

    force_checkout : False
        Force a checkout even if there might be overwritten changes

    force_reset : False
        Force the checkout to ``--reset hard`` to the remote ref

    submodules : False
        Update submodules on clone or branch change

    bare : False
        Set to ``True`` if the repository is to be a bare clone of the remote
        repository.

        .. note:

            Setting this option to ``True`` is incompatible with the ``rev``
            argument.

    mirror
        Set to ``True`` if the repository is to be a mirror of the remote
        repository. This implies that ``bare`` set to ``True``, and thus is
        incompatible with ``rev``.

    remote : origin
        Git remote to use. If this state needs to clone the repo, it will clone
        it using this value as the initial remote name. If the repository
        already exists, and a remote by this name is not present, one will be
        added.

    remote_name
        .. deprecated:: 2015.5.4
            Use ``remote`` instead. For earlier Salt versions, ``remote_name``
            must be used.

    always_fetch : False
        If a tag or branch name is used as the rev a fetch will not occur until
        the tag or branch name changes. Setting this to ``True`` will force a
        fetch to occur. Only applies when ``rev`` is set.

    fetch_tags : True
        If ``True``, then when a fetch is performed all tags will be fetched,
        even those which are not reachable by any branch on the remote.

    depth
        Defines depth in history when git a clone is needed in order to ensure
        latest. E.g. ``depth: 1`` is usefull when deploying from a repository
        with a long history. Use rev to specify branch. This is not compatible
        with tags or revision IDs.

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

    if remote_name is not None:
        salt.utils.warn_until(
            'Nitrogen',
            'The \'remote_name\' argument to the git.latest state has been '
            'deprecated, please use \'remote\' instead.'
        )
        remote = remote_name

    if not remote:
        return _fail(ret, '\'remote\' option is required')

    if not target:
        return _fail(ret, '\'target\' option is required')

    locals_ = locals()
    # Force these arguments to be strings
    for param in ('rev', 'target', 'user', 'remote', 'identity',
                  'https_user', 'https_pass'):
        if not isinstance(locals_[param], six.string_types):
            locals_[param] = str(locals_[param])
    # Force these arguments to be absolute paths
    for param in ('target', 'identity'):
        if not os.path.isabs(locals_[param]):
            return _fail(
                ret,
                '{0} \'{1}\' is not an absolute path'.format(
                    param,
                    locals_[param]
                )
            )

    if os.path.isfile(target):
        return _fail(
            ret,
            'Target \'{0}\' exists and is a regular file, cannot proceed'
            .format(target)
        )

    if mirror:
        bare = True

    # Check to make sure rev and mirror/bare are not both in use
    if rev and bare:
        return _fail(ret, ('\'rev\' is not compatible with the \'mirror\' and '
                           '\'bare\' arguments'))

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

    fetch_opts = [
        'refs/heads/*:refs/remotes/{0}/*'.format(remote),
        '+refs/tags/*:refs/tags/*'
    ] if fetch_tags else []

    check = 'refs' if bare else '.git'
    gitdir = os.path.join(target, check)
    if os.path.isdir(gitdir) or __salt__['git.is_worktree'](target):
        # Target directory is a git repository or git worktree
        try:
            local_rev = _get_local_rev(target, user)

            log.debug('Checking local branch for {0}'.format(target))
            try:
                local_branch = __salt__['git.current_branch'](
                    target, user=user, ignore_retcode=True)
            except CommandExecutionError:
                log.debug('No local branch for {0}'.format(target))
                local_branch = None

            if (local_branch != 'HEAD' and local_branch == rev) \
                    or rev is None \
                    or local_rev is None:
                # We're only interested in the remote branch if a branch
                # (instead of a hash, for example) was provided as the 'rev'
                # param, or if the local checkout is empty.
                remote_rev = __salt__['git.ls_remote'](
                    target,
                    remote=name,
                    ref='HEAD' if rev is None else rev,
                    user=user,
                    identity=identity,
                    https_user=https_user,
                    https_pass=https_pass) or None
            else:
                remote_rev = None

            if local_rev is None and rev and remote_rev is None:
                # Local checkout is empty, and a specific rev is desired, but
                # that rev doesn't exist on the remote repo.
                return _fail(
                    ret,
                    'Local checkout of repository is empty and no revision '
                    'matching \'{0}\' exists in the remote repository'
                    .format(rev)
                )

            if local_rev in [x for x in (rev, remote_rev) if x is not None] \
                    or (remote_rev is not None
                        and remote_rev.startswith(local_rev)):
                # One of the following is true:
                #
                # 1) The desired revision is a SHA1 hash which matches the SHA1
                #    of the local checkout's HEAD.
                # 2) No revision was specified, and SHA1 hash of the remote
                #    repository's HEAD matches that of the the local checkout's
                #    HEAD.
                #
                # In either case, no changes need to be made, so set new_rev to
                # the same value as local_rev and don't make any changes.
                new_rev = local_rev
            else:
                # If always_fetch is set to True, then we definitely need to
                # fetch. Otherwise, we'll rely on the logic below to turn on
                # fetch_needed if a fetch is required.
                fetch_needed = always_fetch
                try:
                    fetch_url = __salt__['git.remote_get'](target,
                                                           remote=remote,
                                                           user=user)['fetch']
                except CommandExecutionError:
                    log.debug(
                        'Remote \'{0}\' not found in git checkout at {1}'
                        .format(remote, target)
                    )
                    fetch_url = None

                if name != fetch_url:
                    if __opts__['test']:
                        return _neutral_test(
                            ret,
                            'Remote \'{0}\' would be set to {1} in git '
                            'checkout at {2}, and remote would be fetched. '
                            'If, after the fetch, the SHA1 hash of the '
                            'desired revision has changed, then {2} would be '
                            'updated.'.format(remote, fetch_url, target)
                        )
                    # The fetch_url for the desired remote does not match the
                    # specified URL (or the remote does not exist), so set the
                    # remote URL.
                    __salt__['git.remote_set'](target,
                                               url=name,
                                               remote=remote,
                                               user=user,
                                               https_user=https_user,
                                               https_pass=https_pass)
                    ret['changes']['remotes/{0}'.format(remote)] = {
                        'old': fetch_url,
                        'new': name
                    }
                    # We need to fetch since the remote was just set and we
                    # need to grab all its refs.
                    fetch_needed = True

                if rev:
                    # Check to see if the rev exists and resolves to a commit
                    try:
                        __salt__['git.rev_parse'](target,
                                                  rev + '^{commit}',
                                                  ignore_retcode=True)
                    except CommandExecutionError:
                        # The rev doesn't exist, we need to fetch to see if the
                        # remote repo now has the rev.
                        fetch_needed = True

                    local_branches = __salt__['git.list_branches'](
                        target, user=user)
                    if rev not in local_branches:
                        checkout_rev = '/'.join((remote, rev))
                        checkout_opts = ['-b', rev]
                    else:
                        checkout_rev = rev
                        checkout_opts = []

                    if __opts__['test']:
                        actions = []
                        if fetch_needed:
                            actions.append(
                                'Remote \'{0}\' would be fetched'
                                .format(remote)
                            )
                        actions.append(
                            '\'{0}\' would be checked out as {1}branch '
                            '\'{2}\''.format(
                                '/'.join((remote, rev)),
                                'new ' if '-b' in checkout_opts else '',
                                rev
                            )
                        )
                        if force_reset:
                            actions.append(
                                'Repository would be hard-reset to {0}/{1}'
                                .format(remote, rev)
                            )
                        return _fail(ret, '. '.join(actions) + '.')

                    if fetch_needed:
                        output = __salt__['git.fetch'](
                            target,
                            remote=remote,
                            opts=fetch_opts,
                            user=user,
                            identity=identity)
                        fetch_changes = _parse_fetch(output)
                        if fetch_changes:
                            ret['changes']['fetch'] = fetch_changes

                    log.debug('checkout_opts = {0}'.format(checkout_opts))
                    __salt__['git.checkout'](target,
                                             checkout_rev,
                                             force=force_checkout,
                                             opts=checkout_opts,
                                             user=user)

                    if force_reset:
                        opts = ['--hard', '/'.join((remote, rev))]
                        __salt__['git.reset'](target, opts=opts, user=user)

                    try:
                        upstream = __salt__['git.rev_parse'](
                            target,
                            rev + '@{upstream}',
                            opts=['--abbrev-ref'],
                            user=user)
                    except CommandExecutionError:
                        upstream = None

                    desired_upstream = '/'.join((remote, rev))
                    if upstream != desired_upstream:
                        log.debug(
                            'Setting remote tracking branch for branch '
                            '\'{0}\' in local checkout {1} to {2}'.format(
                                rev,
                                target,
                                desired_upstream
                            )
                        )
                        __salt__['git.branch'](
                            target,
                            rev,
                            opts=['--set-upstream-to', desired_upstream],
                            user=user)
                        ret['changes']['upstream'] = {'old': upstream,
                                                      'new': desired_upstream}

                # Check first to see if we are on a branch before trying to
                # merge changes. (The call to git.symbolic_ref will only return
                # output if HEAD points to a branch.)
                if __salt__['git.symbolic_ref'](
                        target,
                        'HEAD',
                        opts=['--quiet'],
                        ignore_retcode=True):
                    if bare:
                        # The earlier fetch is only performed if rev is
                        # specified, so we need to fetch here for bare/mirror
                        output = __salt__['git.fetch'](
                            target,
                            remote=remote,
                            opts=fetch_opts,
                            user=user,
                            identity=identity)
                        fetch_changes = _parse_fetch(output)
                        if fetch_changes:
                            ret['changes']['fetch'] = fetch_changes
                    else:
                        __salt__['git.merge'](target, user=user)

                if submodules:
                    __salt__['git.submodule'](target,
                                              'update',
                                              opts=['--recursive'],
                                              user=user,
                                              identity=identity)

                try:
                    new_rev = __salt__['git.revision'](
                        cwd=target,
                        user=user,
                        ignore_retcode=True)
                except CommandExecutionError:
                    new_rev = None

        except Exception as exc:
            log.error(
                'Unexpected exception in git.latest state',
                exc_info=True
            )
            if isinstance(exc, CommandExecutionError):
                comment = _strip_exc(exc)
            else:
                comment = str(exc)
            return _fail(ret, comment)

        if local_rev != new_rev:
            log.info(
                'Repository {0} updated: {1} => {2}'.format(
                    target, local_rev, new_rev)
            )
            ret['comment'] = 'Repository {0} updated'.format(target)
            ret['changes']['revision'] = {'old': local_rev, 'new': new_rev}
        else:
            ret['comment'] = 'Repository {0} is up-to-date'.format(target)
    else:
        if os.path.isdir(target):
            if force:
                # Clone is required, and target directory exists, but the
                # ``force`` option is enabled, so we need to clear out its
                # contents to proceed.
                if __opts__['test']:
                    return _neutral_test(
                        ret,
                        'Target directory {0} exists. Since force=True, the '
                        'contents of {0} would be deleted, and {1} would be '
                        'cloned into this directory.'.format(target, name)
                    )
                log.debug(
                    'Removing contents of {0} to clone repository {1} in its '
                    'place (force=True set in git.latest state)'
                    .format(target, name)
                )
                try:
                    if os.path.islink(target):
                        os.unlink(target)
                    else:
                        salt.utils.rm_rf(target)
                except OSError as exc:
                    return _fail(
                        ret,
                        'Unable to remove {0}: {1}'.format(target, exc)
                    )
            # Clone is required, but target dir exists and is non-empty. We
            # can't proceed.
            elif os.listdir(target):
                return _fail(
                    ret,
                    'Target \'{0}\' exists, is non-empty and is not a git '
                    'repository. Set the \'force\' option to True to remove '
                    'this directory\'s contents and proceed with cloning the '
                    'remote repository'.format(target)
                )

        log.debug(
            'Target {0} is not found, \'git clone\' is required'.format(target)
        )
        if 'test' in __opts__:
            if __opts__['test']:
                return _neutral_test(
                    ret,
                    'Repository {0} would be cloned to {1}'.format(
                        name, target
                    )
                )
        try:
            local_rev = _get_local_rev(target, user)

            clone_opts = ['--mirror'] if mirror else ['--bare'] if bare else []
            if remote != 'origin':
                clone_opts.extend(['--origin', remote])
            if depth is not None:
                clone_opts.extend(['--depth', str(depth)])

            __salt__['git.clone'](target,
                                  name,
                                  user=user,
                                  opts=clone_opts,
                                  identity=identity,
                                  https_user=https_user,
                                  https_pass=https_pass)
            ret['changes']['new'] = name + ' => ' + target

            # Check for HEAD in remote repo
            remote_rev = __salt__['git.ls_remote'](target,
                                                   remote=name,
                                                   ref='HEAD',
                                                   user=user,
                                                   identity=identity,
                                                   https_user=https_user,
                                                   https_pass=https_pass)

            if rev and not bare:
                if not remote_rev:
                    # No HEAD means the remote repo is empty, which means our
                    # new clone will also be empty. This state has failed, since
                    # a rev was specified but no matching rev exists on the
                    # remote host.
                    return _fail(
                        ret,
                        '{0} was cloned but is empty, so {1}/{2} cannot be '
                        'checked out'.format(name, remote, rev)
                    )
                else:
                    __salt__['git.checkout'](target, rev, user=user)

            if submodules and remote_rev:
                __salt__['git.submodule'](target,
                                          'update',
                                          opts=['--recursive'],
                                          user=user,
                                          identity=identity)

            try:
                new_rev = __salt__['git.revision'](
                    cwd=target,
                    user=user,
                    ignore_retcode=True)
            except CommandExecutionError:
                new_rev = None

        except Exception as exc:
            log.error(
                'Unexpected exception in git.latest state',
                exc_info=True
            )
            if isinstance(exc, CommandExecutionError):
                comment = _strip_exc(exc)
            else:
                comment = str(exc)
            return _fail(ret, comment)

        message = 'Repository {0} cloned to {1}'.format(name, target)
        log.info(message)
        ret['comment'] = message
        ret['changes']['revision'] = {'old': local_rev, 'new': new_rev}
    return ret


def present(name,
            force=False,
            bare=True,
            template=None,
            separate_git_dir=None,
            shared=None,
            user=None):
    '''
    Ensure that a repository exists in the given directory

    .. warning::
        If the minion has Git 2.5 or later installed, ``name`` points to a
        worktree_, and ``force`` is set to ``True``, then the worktree will be
        deleted. This has been corrected in Salt 2015.8.0.

    name
        Path to the directory

        .. versionchanged:: 2015.8.0
            This path must now be absolute

    force : False
        If ``True``, and if ``name`` points to an existing directory which does
        not contain a git repository, then the contents of that directory will
        be recursively removed and a new repository will be initialized in its
        place.

    bare : True
        If ``True``, and a repository must be initialized, then the repository
        will be a bare repository.

        .. note::
            This differs from the default behavior of :py:func:`git.init
            <salt.modules.git.init>`, make sure to set this value to ``False``
            if a bare repo is not desired.

    template
        If a new repository is initialized, this argument will specify an
        alternate `template directory`_

        .. versionadded:: 2015.8.0

    separate_git_dir
        If a new repository is initialized, this argument will specify an
        alternate ``$GIT_DIR``

        .. versionadded:: 2015.8.0

    shared
        Set sharing permissions on git repo. See `git-init(1)`_ for more
        details.

        .. versionadded:: 2015.5.0

    user
        User under which to run git commands. By default, commands are run by
        the user under which the minion is running.

        .. versionadded:: 0.17.0

    .. _`git-init(1)`: http://git-scm.com/docs/git-init
    .. _`worktree`: http://git-scm.com/docs/git-worktree
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    # If the named directory is a git repo return True
    if os.path.isdir(name):
        if bare and os.path.isfile(os.path.join(name, 'HEAD')):
            return ret
        elif not bare and \
                (os.path.isdir(os.path.join(name, '.git')) or
                 __salt__['git.is_worktree'](name)):
            return ret
        # Directory exists and is not a git repo, if force is set destroy the
        # directory and recreate, otherwise throw an error
        elif force:
            # Directory exists, and the ``force`` option is enabled, so we need
            # to clear out its contents to proceed.
            if __opts__['test']:
                return _neutral_test(
                    ret,
                    'Target directory {0} exists. Since force=True, the '
                    'contents of {0} would be deleted, and a {1}repository '
                    'would be initialized in its place.'
                    .format(name, 'bare ' if bare else '')
                )
            log.debug(
                'Removing contents of {0} to initialize {1}repository in its '
                'place (force=True set in git.present state)'
                .format(name, 'bare ' if bare else '')
            )
            try:
                if os.path.islink(name):
                    os.unlink(name)
                else:
                    salt.utils.rm_rf(name)
            except OSError as exc:
                return _fail(
                    ret,
                    'Unable to remove {0}: {1}'.format(name, exc)
                )
        elif os.listdir(name):
            return _fail(
                ret,
                'Target \'{0}\' exists, is non-empty, and is not a git '
                'repository. Set the \'force\' option to True to remove this '
                'directory\'s contents and proceed with initializing a '
                'repository'.format(target)
            )

    # Run test is set
    if __opts__['test']:
        return _neutral_test(
            ret,
            'New {0}repository would be created'.format(
                'bare ' if bare else ''
            )
        )

    __salt__['git.init'](cwd=name,
                         bare=bare,
                         template=template,
                         separate_git_dir=separate_git_dir,
                         shared=shared,
                         user=user)

    actions = [
        'Initialized {0}repository in {1}'.format(
            'bare ' if bare else '',
            name
        )
    ]
    if template:
        actions.append('Template directory set to {0}'.format(template))
    if separate_git_dir:
        actions.append('Gitdir set to {0}'.format(separate_git_dir))
    message = '. '.join(actions)
    if len(actions) > 1:
        message += '.'
    log.info(message)
    ret['changes']['new'] = name
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


def mod_run_check(cmd_kwargs, onlyif, unless):
    '''
    Execute the onlyif and unless logic. Return a result dict if:

    * onlyif failed (onlyif != 0)
    * unless succeeded (unless == 0)

    Otherwise, returns ``True``
    '''
    cmd_kwargs = copy.deepcopy(cmd_kwargs)
    cmd_kwargs['python_shell'] = True
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
