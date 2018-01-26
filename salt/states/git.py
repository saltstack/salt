# -*- coding: utf-8 -*-
'''
States to manage git repositories and git configuration

.. important::
    Before using git over ssh, make sure your remote host fingerprint exists in
    your ``~/.ssh/known_hosts`` file.

.. versionchanged:: 2015.8.8
    This state module now requires git 1.6.5 (released 10 October 2009) or
    newer.
'''
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import copy
import errno
import logging
import os
import re
import string

# Import salt libs
import salt.utils.args
import salt.utils.files
import salt.utils.url
import salt.utils.versions
from salt.exceptions import CommandExecutionError
from salt.utils.versions import LooseVersion as _LooseVersion

# Import 3rd-party libs
from salt.ext import six

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if git is available
    '''
    if 'git.version' not in __salt__:
        return False
    git_ver = _LooseVersion(__salt__['git.version'](versioninfo=False))
    return git_ver >= _LooseVersion('1.6.5')


def _revs_equal(rev1, rev2, rev_type):
    '''
    Shorthand helper function for comparing SHA1s. If rev_type == 'sha1' then
    the comparison will be done using str.startwith() to allow short SHA1s to
    compare successfully.

    NOTE: This means that rev2 must be the short rev.
    '''
    if (rev1 is None and rev2 is not None) \
            or (rev2 is None and rev1 is not None):
        return False
    elif rev1 is rev2 is None:
        return True
    elif rev_type == 'sha1':
        return rev1.startswith(rev2)
    else:
        return rev1 == rev2


def _short_sha(sha1):
    return sha1[:7] if sha1 is not None else None


def _format_comments(comments):
    '''
    Return a joined list
    '''
    ret = '. '.join(comments)
    if len(comments) > 1:
        ret += '.'
    return ret


def _need_branch_change(branch, local_branch):
    '''
    Short hand for telling when a new branch is needed
    '''
    return branch is not None and branch != local_branch


def _get_branch_opts(branch, local_branch, all_local_branches,
                     desired_upstream, git_ver=None):
    '''
    DRY helper to build list of opts for git.branch, for the purposes of
    setting upstream tracking branch
    '''
    if branch is not None and branch not in all_local_branches:
        # We won't be setting upstream because the act of checking out a new
        # branch will set upstream for us
        return None

    if git_ver is None:
        git_ver = _LooseVersion(__salt__['git.version'](versioninfo=False))

    ret = []
    if git_ver >= _LooseVersion('1.8.0'):
        ret.extend(['--set-upstream-to', desired_upstream])
    else:
        ret.append('--set-upstream')
        # --set-upstream does not assume the current branch, so we have to
        # tell it which branch we'll be using
        ret.append(local_branch if branch is None else branch)
        ret.append(desired_upstream)
    return ret


def _get_local_rev_and_branch(target, user, password):
    '''
    Return the local revision for before/after comparisons
    '''
    log.info('Checking local revision for %s', target)
    try:
        local_rev = __salt__['git.revision'](target,
                                             user=user,
                                             password=password,
                                             ignore_retcode=True)
    except CommandExecutionError:
        log.info('No local revision for %s', target)
        local_rev = None

    log.info('Checking local branch for %s', target)
    try:
        local_branch = __salt__['git.current_branch'](target,
                                                      user=user,
                                                      password=password,
                                                      ignore_retcode=True)
    except CommandExecutionError:
        log.info('No local branch for %s', target)
        local_branch = None

    return local_rev, local_branch


def _strip_exc(exc):
    '''
    Strip the actual command that was run from exc.strerror to leave just the
    error message
    '''
    return re.sub(r'^Command [\'"].+[\'"] failed: ', '', exc.strerror)


def _uptodate(ret, target, comments=None, local_changes=False):
    ret['comment'] = 'Repository {0} is up-to-date'.format(target)
    if local_changes:
        ret['comment'] += ', but with local changes. Set \'force_reset\' to ' \
                          'True to purge local changes.'
    if comments:
        # Shouldn't be making any changes if the repo was up to date, but
        # report on them so we are alerted to potential problems with our
        # logic.
        ret['comment'] += '\n\nChanges made: ' + comments
    return ret


def _neutral_test(ret, comment):
    ret['result'] = None
    ret['comment'] = comment
    return ret


def _fail(ret, msg, comments=None):
    ret['result'] = False
    if comments:
        msg += '\n\nChanges already made: '
        msg += _format_comments(comments)
    ret['comment'] = msg
    return ret


def _failed_fetch(ret, exc, comments=None):
    msg = (
        'Fetch failed. Set \'force_fetch\' to True to force the fetch if the '
        'failure was due to not being able to fast-forward. Output of the fetch '
        'command follows:\n\n{0}'.format(_strip_exc(exc))
    )
    return _fail(ret, msg, comments)


def _failed_submodule_update(ret, exc, comments=None):
    msg = 'Failed to update submodules: ' + _strip_exc(exc)
    return _fail(ret, msg, comments)


def _not_fast_forward(ret, rev, pre, post, branch, local_branch,
                      default_branch, local_changes, comments):
    branch_msg = ''
    if branch is None:
        if rev != 'HEAD':
            if local_branch != rev:
                branch_msg = (
                    ' The desired rev ({0}) differs from the name of the '
                    'local branch ({1}), if the desired rev is a branch name '
                    'then a forced update could possibly be avoided by '
                    'setting the \'branch\' argument to \'{0}\' instead.'
                    .format(rev, local_branch)
                )
        else:
            if default_branch is not None and local_branch != default_branch:
                branch_msg = (
                    ' The default remote branch ({0}) differs from the '
                    'local branch ({1}). This could be caused by changing the '
                    'default remote branch, or if the local branch was '
                    'manually changed. Rather than forcing an update, it '
                    'may be advisable to set the \'branch\' argument to '
                    '\'{0}\' instead. To ensure that this state follows the '
                    '\'{0}\' branch instead of the remote HEAD, set the '
                    '\'rev\' argument to \'{0}\'.'
                    .format(default_branch, local_branch)
                )

    pre = _short_sha(pre)
    post = _short_sha(post)
    return _fail(
        ret,
        'Repository would be updated {0}{1}, but {2}. Set \'force_reset\' to '
        'True to force this update{3}.{4}'.format(
            'from {0} to {1}'.format(pre, post)
                if local_changes and pre != post
                else 'to {0}'.format(post),
            ' (after checking out local branch \'{0}\')'.format(branch)
                if _need_branch_change(branch, local_branch)
                else '',
            'this is not a fast-forward merge'
                if not local_changes
                else 'there are uncommitted changes',
            ' and discard these changes' if local_changes else '',
            branch_msg,
        ),
        comments
    )


def latest(name,
           rev='HEAD',
           target=None,
           branch=None,
           user=None,
           password=None,
           update_head=True,
           force_checkout=False,
           force_clone=False,
           force_fetch=False,
           force_reset=False,
           submodules=False,
           bare=False,
           mirror=False,
           remote='origin',
           fetch_tags=True,
           depth=None,
           identity=None,
           https_user=None,
           https_pass=None,
           onlyif=False,
           unless=False,
           refspec_branch='*',
           refspec_tag='*',
           **kwargs):
    '''
    Make sure the repository is cloned to the given directory and is
    up-to-date.

    name
        Address of the remote repository, as passed to ``git clone``

        .. note::
             From the `Git documentation`_, there are two URL formats
             supported for SSH authentication. The below two examples are
             equivalent:

             .. code-block:: text

                 # ssh:// URL
                 ssh://user@server/project.git

                 # SCP-like syntax
                 user@server:project.git

             A common mistake is to use an ``ssh://`` URL, but with a colon
             after the domain instead of a slash. This is invalid syntax in
             Git, and will therefore not work in Salt. When in doubt, confirm
             that a ``git clone`` works for the URL before using it in Salt.

             It has been reported by some users that SCP-like syntax is
             incompatible with git repos hosted on `Atlassian Stash/BitBucket
             Server`_. In these cases, it may be necessary to use ``ssh://``
             URLs for SSH authentication.

        .. _`Git documentation`: https://git-scm.com/book/en/v2/Git-on-the-Server-The-Protocols#The-SSH-Protocol
        .. _`Atlassian Stash/BitBucket Server`: https://www.atlassian.com/software/bitbucket/server

    rev : HEAD
        The remote branch, tag, or revision ID to checkout after clone / before
        update. If specified, then Salt will also ensure that the tracking
        branch is set to ``<remote>/<rev>``, unless ``rev`` refers to a tag or
        SHA1, in which case Salt will ensure that the tracking branch is unset.

        If ``rev`` is not specified, it will be assumed to be ``HEAD``, and
        Salt will not manage the tracking branch at all.

        .. versionchanged:: 2015.8.0
            If not specified, ``rev`` now defaults to the remote repository's
            HEAD.

    target
        Name of the target directory where repository is about to be cloned

    branch
        Name of the local branch into which to checkout the specified rev. If
        not specified, then Salt will not care what branch is being used
        locally and will just use whatever branch is currently there.

        .. versionadded:: 2015.8.0

        .. note::
            If this argument is not specified, this means that Salt will not
            change the local branch if the repository is reset to another
            branch/tag/SHA1. For example, assume that the following state was
            run initially:

            .. code-block:: yaml

                foo_app:
                  git.latest:
                    - name: https://mydomain.tld/apps/foo.git
                    - target: /var/www/foo
                    - user: www

            This would have cloned the HEAD of that repo (since a ``rev``
            wasn't specified), and because ``branch`` is not specified, the
            branch in the local clone at ``/var/www/foo`` would be whatever the
            default branch is on the remote repository (usually ``master``, but
            not always). Now, assume that it becomes necessary to switch this
            checkout to the ``dev`` branch. This would require ``rev`` to be
            set, and probably would also require ``force_reset`` to be enabled:

            .. code-block:: yaml

                foo_app:
                  git.latest:
                    - name: https://mydomain.tld/apps/foo.git
                    - target: /var/www/foo
                    - user: www
                    - rev: dev
                    - force_reset: True

            The result of this state would be to perform a hard-reset to
            ``origin/dev``. Since ``branch`` was not specified though, while
            ``/var/www/foo`` would reflect the contents of the remote repo's
            ``dev`` branch, the local branch would still remain whatever it was
            when it was cloned. To make the local branch match the remote one,
            set ``branch`` as well, like so:

            .. code-block:: yaml

                foo_app:
                  git.latest:
                    - name: https://mydomain.tld/apps/foo.git
                    - target: /var/www/foo
                    - user: www
                    - rev: dev
                    - branch: dev
                    - force_reset: True

            This may seem redundant, but Salt tries to support a wide variety
            of use cases, and doing it this way allows for the use case where
            the local branch doesn't need to be strictly managed.

    user
        Local system user under which to run git commands. By default, commands
        are run by the user under which the minion is running.

        .. note::
            This is not to be confused with the username for http(s)/SSH
            authentication.

        .. versionadded:: 0.17.0

    password
        Windows only. Required when specifying ``user``. This parameter will be
        ignored on non-Windows platforms.

        .. versionadded:: 2016.3.4

    update_head : True
        If set to ``False``, then the remote repository will be fetched (if
        necessary) to ensure that the commit to which ``rev`` points exists in
        the local checkout, but no changes will be made to the local HEAD.

        .. versionadded:: 2015.8.3

    force_checkout : False
        When checking out the local branch, the state will fail if there are
        unwritten changes. Set this argument to ``True`` to discard unwritten
        changes when checking out.

    force_clone : False
        If the ``target`` directory exists and is not a git repository, then
        this state will fail. Set this argument to ``True`` to remove the
        contents of the target directory and clone the repo into it.

    force_fetch : False
        If a fetch needs to be performed, non-fast-forward fetches will cause
        this state to fail. Set this argument to ``True`` to force the fetch
        even if it is a non-fast-forward update.

        .. versionadded:: 2015.8.0

    force_reset : False
        If the update is not a fast-forward, this state will fail. Set this
        argument to ``True`` to force a hard-reset to the remote revision in
        these cases.

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

    fetch_tags : True
        If ``True``, then when a fetch is performed all tags will be fetched,
        even those which are not reachable by any branch on the remote.

    depth
        Defines depth in history when git a clone is needed in order to ensure
        latest. E.g. ``depth: 1`` is useful when deploying from a repository
        with a long history. Use rev to specify branch. This is not compatible
        with tags or revision IDs.

    identity
        Path to a private key to use for ssh URLs. This can be either a single
        string, or a list of strings. For example:

        .. code-block:: yaml

            # Single key
            git@github.com:user/repo.git:
              git.latest:
                - user: deployer
                - identity: /home/deployer/.ssh/id_rsa

            # Two keys
            git@github.com:user/repo.git:
              git.latest:
                - user: deployer
                - identity:
                  - /home/deployer/.ssh/id_rsa
                  - /home/deployer/.ssh/id_rsa_alternate

        If multiple keys are specified, they will be tried one-by-one in order
        for each git command which needs to authenticate.

        .. warning::

            Unless Salt is invoked from the minion using ``salt-call``, the
            key(s) must be passphraseless. For greater security with
            passphraseless private keys, see the `sshd(8)`_ manpage for
            information on securing the keypair from the remote side in the
            ``authorized_keys`` file.

            .. _`sshd(8)`: http://www.man7.org/linux/man-pages/man8/sshd.8.html#AUTHORIZED_KEYS_FILE%20FORMAT

        .. versionchanged:: 2015.8.7
            Salt will no longer attempt to use passphrase-protected keys unless
            invoked from the minion using ``salt-call``, to prevent blocking
            waiting for user input.

        .. versionchanged:: 2016.3.0
            Key can now be specified as a SaltStack fileserver URL (e.g.
            ``salt://path/to/identity_file``).

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

    refspec_branch : *
        A glob expression defining which branches to retrieve when fetching.
        See `git-fetch(1)`_ for more information on how refspecs work.

        .. versionadded:: 2017.7.0

    refspec_tag : *
        A glob expression defining which tags to retrieve when fetching. See
        `git-fetch(1)`_ for more information on how refspecs work.

        .. versionadded:: 2017.7.0

    .. _`git-fetch(1)`: http://git-scm.com/docs/git-fetch

    .. note::
        Clashing ID declarations can be avoided when including different
        branches from the same git repository in the same SLS file by using the
        ``name`` argument. The example below checks out the ``gh-pages`` and
        ``gh-pages-prod`` branches from the same repository into separate
        directories. The example also sets up the ``ssh_known_hosts`` ssh key
        required to perform the git checkout.

        Also, it has been reported that the SCP-like syntax for

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

            git-website-staging:
              git.latest:
                - name: git@gitlab.example.com:user/website.git
                - rev: gh-pages
                - target: /usr/share/nginx/staging
                - identity: salt://website/id_rsa
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

    kwargs = salt.utils.args.clean_kwargs(**kwargs)
    if kwargs:
        return _fail(
            ret,
            salt.utils.args.invalid_kwargs(kwargs, raise_exc=False)
        )

    if not remote:
        return _fail(ret, '\'remote\' argument is required')

    if not target:
        return _fail(ret, '\'target\' argument is required')

    if not rev:
        return _fail(
            ret,
            '\'{0}\' is not a valid value for the \'rev\' argument'.format(rev)
        )

    # Ensure that certain arguments are strings to ensure that comparisons work
    if not isinstance(rev, six.string_types):
        rev = six.text_type(rev)
    if target is not None:
        if not isinstance(target, six.string_types):
            target = six.text_type(target)
        if not os.path.isabs(target):
            return _fail(
                ret,
                'target \'{0}\' is not an absolute path'.format(target)
            )
    if branch is not None and not isinstance(branch, six.string_types):
        branch = six.text_type(branch)
    if user is not None and not isinstance(user, six.string_types):
        user = six.text_type(user)
    if password is not None and not isinstance(password, six.string_types):
        password = six.text_type(password)
    if remote is not None and not isinstance(remote, six.string_types):
        remote = six.text_type(remote)
    if identity is not None:
        if isinstance(identity, six.string_types):
            identity = [identity]
        elif not isinstance(identity, list):
            return _fail(ret, 'identity must be either a list or a string')
        for ident_path in identity:
            if 'salt://' in ident_path:
                try:
                    ident_path = __salt__['cp.cache_file'](ident_path, __env__)
                except IOError as exc:
                    log.exception('Failed to cache %s', ident_path)
                    return _fail(
                        ret,
                        'identity \'{0}\' does not exist.'.format(
                            ident_path
                        )
                    )
            if not os.path.isabs(ident_path):
                return _fail(
                    ret,
                    'identity \'{0}\' is not an absolute path'.format(
                        ident_path
                    )
                )
    if https_user is not None and not isinstance(https_user, six.string_types):
        https_user = six.text_type(https_user)
    if https_pass is not None and not isinstance(https_pass, six.string_types):
        https_pass = six.text_type(https_pass)

    if os.path.isfile(target):
        return _fail(
            ret,
            'Target \'{0}\' exists and is a regular file, cannot proceed'
            .format(target)
        )

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

    if mirror:
        bare = True

    # Check to make sure rev and mirror/bare are not both in use
    if rev != 'HEAD' and bare:
        return _fail(ret, ('\'rev\' is not compatible with the \'mirror\' and '
                           '\'bare\' arguments'))

    run_check_cmd_kwargs = {'runas': user, 'password': password}
    if 'shell' in __grains__:
        run_check_cmd_kwargs['shell'] = __grains__['shell']

    # check if git.latest should be applied
    cret = mod_run_check(
        run_check_cmd_kwargs, onlyif, unless
    )
    if isinstance(cret, dict):
        ret.update(cret)
        return ret

    refspecs = [
        'refs/heads/{0}:refs/remotes/{1}/{0}'.format(refspec_branch, remote),
        '+refs/tags/{0}:refs/tags/{0}'.format(refspec_tag)
    ] if fetch_tags else []

    log.info('Checking remote revision for %s', name)
    try:
        all_remote_refs = __salt__['git.remote_refs'](
            name,
            heads=False,
            tags=False,
            user=user,
            password=password,
            identity=identity,
            https_user=https_user,
            https_pass=https_pass,
            ignore_retcode=False,
            saltenv=__env__)
    except CommandExecutionError as exc:
        return _fail(
            ret,
            'Failed to check remote refs: {0}'.format(_strip_exc(exc))
        )

    if 'HEAD' in all_remote_refs:
        head_rev = all_remote_refs['HEAD']
        for refname, refsha in six.iteritems(all_remote_refs):
            if refname.startswith('refs/heads/'):
                if refsha == head_rev:
                    default_branch = refname.partition('refs/heads/')[-1]
                    break
        else:
            default_branch = None
    else:
        head_rev = None
        default_branch = None

    desired_upstream = False
    if bare:
        remote_rev = None
        remote_rev_type = None
    else:
        if rev == 'HEAD':
            if head_rev is not None:
                remote_rev = head_rev
                # Just go with whatever the upstream currently is
                desired_upstream = None
                remote_rev_type = 'sha1'
            else:
                # Empty remote repo
                remote_rev = None
                remote_rev_type = None
        elif 'refs/heads/' + rev in all_remote_refs:
            remote_rev = all_remote_refs['refs/heads/' + rev]
            desired_upstream = '/'.join((remote, rev))
            remote_rev_type = 'branch'
        elif 'refs/tags/' + rev + '^{}' in all_remote_refs:
            # Annotated tag
            remote_rev = all_remote_refs['refs/tags/' + rev + '^{}']
            remote_rev_type = 'tag'
        elif 'refs/tags/' + rev in all_remote_refs:
            # Non-annotated tag
            remote_rev = all_remote_refs['refs/tags/' + rev]
            remote_rev_type = 'tag'
        else:
            if len(rev) <= 40 \
                    and all(x in string.hexdigits for x in rev):
                # git ls-remote did not find the rev, and because it's a
                # hex string <= 40 chars we're going to assume that the
                # desired rev is a SHA1
                rev = rev.lower()
                remote_rev = rev
                remote_rev_type = 'sha1'
            else:
                remote_rev = None
                remote_rev_type = None

        # For the comment field of the state return dict, the remote location
        # (and short-sha1, if rev is not a sha1) is referenced several times,
        # determine it once here and reuse the value below.
        if remote_rev_type == 'sha1':
            if rev == 'HEAD':
                remote_loc = 'remote HEAD (' + remote_rev[:7] + ')'
            else:
                remote_loc = remote_rev[:7]
        elif remote_rev is not None:
            remote_loc = '{0} ({1})'.format(
                desired_upstream if remote_rev_type == 'branch' else rev,
                remote_rev[:7]
            )
        else:
            # Shouldn't happen but log a warning here for future
            # troubleshooting purposes in the event we find a corner case.
            log.warning(
                'Unable to determine remote_loc. rev is %s, remote_rev is '
                '%s, remove_rev_type is %s, desired_upstream is %s, and bare '
                'is%s set',
                rev,
                remote_rev,
                remote_rev_type,
                desired_upstream,
                ' not' if not bare else ''
            )
            remote_loc = None

    if depth is not None and remote_rev_type != 'branch':
        return _fail(
            ret,
            'When \'depth\' is used, \'rev\' must be set to the name of a '
            'branch on the remote repository'
        )

    if remote_rev is None and not bare:
        if rev != 'HEAD':
            # A specific rev is desired, but that rev doesn't exist on the
            # remote repo.
            return _fail(
                ret,
                'No revision matching \'{0}\' exists in the remote '
                'repository'.format(rev)
            )

    git_ver = _LooseVersion(__salt__['git.version'](versioninfo=False))

    check = 'refs' if bare else '.git'
    gitdir = os.path.join(target, check)
    comments = []
    if os.path.isdir(gitdir) or __salt__['git.is_worktree'](target,
                                                            user=user,
                                                            password=password):
        # Target directory is a git repository or git worktree
        try:
            all_local_branches = __salt__['git.list_branches'](
                target, user=user, password=password)
            all_local_tags = __salt__['git.list_tags'](target,
                                                       user=user,
                                                       password=password)
            local_rev, local_branch = \
                _get_local_rev_and_branch(target, user, password)

            if not bare and remote_rev is None and local_rev is not None:
                return _fail(
                    ret,
                    'Remote repository is empty, cannot update from a '
                    'non-empty to an empty repository'
                )

            # Base rev and branch are the ones from which any reset or merge
            # will take place. If the branch is not being specified, the base
            # will be the "local" rev and branch, i.e. those we began with
            # before this state was run. If a branch is being specified and it
            # both exists and is not the one with which we started, then we'll
            # be checking that branch out first, and it instead becomes our
            # base. The base branch and rev will be used below in comparisons
            # to determine what changes to make.
            base_rev = local_rev
            base_branch = local_branch
            if _need_branch_change(branch, local_branch):
                if branch not in all_local_branches:
                    # We're checking out a new branch, so the base_rev and
                    # remote_rev will be identical.
                    base_rev = remote_rev
                else:
                    base_branch = branch
                    # Desired branch exists locally and is not the current
                    # branch. We'll be performing a checkout to that branch
                    # eventually, but before we do that we need to find the
                    # current SHA1.
                    try:
                        base_rev = __salt__['git.rev_parse'](
                            target,
                            branch + '^{commit}',
                            user=user,
                            password=password,
                            ignore_retcode=True)
                    except CommandExecutionError as exc:
                        return _fail(
                            ret,
                            'Unable to get position of local branch \'{0}\': '
                            '{1}'.format(branch, _strip_exc(exc)),
                            comments
                        )

            remotes = __salt__['git.remotes'](target,
                                              user=user,
                                              password=password,
                                              redact_auth=False)

            revs_match = _revs_equal(local_rev, remote_rev, remote_rev_type)
            try:
                # If not a bare repo, check `git diff HEAD` to determine if
                # there are local changes.
                local_changes = bool(
                    not bare
                    and
                    __salt__['git.diff'](target,
                                         'HEAD',
                                         user=user,
                                         password=password)
                )
            except CommandExecutionError:
                # No need to capture the error and log it, the _git_run()
                # helper in the git execution module will have already logged
                # the output from the command.
                log.warning(
                    'git.latest: Unable to determine if %s has local changes',
                    target
                )
                local_changes = False

            if local_changes and revs_match:
                if force_reset:
                    msg = (
                        '{0} is up-to-date, but with local changes. Since '
                        '\'force_reset\' is enabled, these local changes '
                        'would be reset.'.format(target)
                    )
                    if __opts__['test']:
                        ret['changes']['forced update'] = True
                        if comments:
                            msg += _format_comments(comments)
                        return _neutral_test(ret, msg)
                    log.debug(msg.replace('would', 'will'))
                else:
                    log.debug(
                        '%s up-to-date, but with local changes. Since '
                        '\'force_reset\' is disabled, no changes will be '
                        'made.', target
                    )
                    return _uptodate(ret,
                                     target,
                                     _format_comments(comments),
                                     local_changes)

            if remote_rev_type == 'sha1' \
                    and base_rev is not None \
                    and base_rev.startswith(remote_rev):
                # Either we're already checked out to the branch we need and it
                # is up-to-date, or the branch to which we need to switch is
                # on the same SHA1 as the desired remote revision. Either way,
                # we know we have the remote rev present already and no fetch
                # will be needed.
                has_remote_rev = True
            else:
                has_remote_rev = False
                if remote_rev is not None:
                    try:
                        __salt__['git.rev_parse'](
                            target,
                            remote_rev + '^{commit}',
                            user=user,
                            password=password,
                            ignore_retcode=True)
                    except CommandExecutionError:
                        # Local checkout doesn't have the remote_rev
                        pass
                    else:
                        # The object might exist enough to get a rev-parse to
                        # work, while the local ref could have been
                        # deleted/changed/force updated. Do some further sanity
                        # checks to determine if we really do have the
                        # remote_rev.
                        if remote_rev_type == 'branch':
                            if remote in remotes:
                                try:
                                    # Do a rev-parse on <remote>/<rev> to get
                                    # the local SHA1 for it, so we can compare
                                    # it to the remote_rev SHA1.
                                    local_copy = __salt__['git.rev_parse'](
                                        target,
                                        desired_upstream,
                                        user=user,
                                        password=password,
                                        ignore_retcode=True)
                                except CommandExecutionError:
                                    pass
                                else:
                                    # If the SHA1s don't match, then the remote
                                    # branch was force-updated, and we need to
                                    # fetch to update our local copy the ref
                                    # for the remote branch. If they do match,
                                    # then we have the remote_rev and don't
                                    # need to fetch.
                                    if local_copy == remote_rev:
                                        has_remote_rev = True
                        elif remote_rev_type == 'tag':
                            if rev in all_local_tags:
                                try:
                                    local_tag_sha1 = __salt__['git.rev_parse'](
                                        target,
                                        rev + '^{commit}',
                                        user=user,
                                        password=password,
                                        ignore_retcode=True)
                                except CommandExecutionError:
                                    # Shouldn't happen if the tag exists
                                    # locally but account for this just in
                                    # case.
                                    local_tag_sha1 = None
                                if local_tag_sha1 == remote_rev:
                                    has_remote_rev = True
                                else:
                                    if not force_reset:
                                        # SHA1 of tag on remote repo is
                                        # different than local tag. Unless
                                        # we're doing a hard reset then we
                                        # don't need to proceed as we know that
                                        # the fetch will update the tag and the
                                        # only way to make the state succeed is
                                        # to reset the branch to point at the
                                        # tag's new location.
                                        return _fail(
                                            ret,
                                            '\'{0}\' is a tag, but the remote '
                                            'SHA1 for this tag ({1}) doesn\'t '
                                            'match the local SHA1 ({2}). Set '
                                            '\'force_reset\' to True to force '
                                            'this update.'.format(
                                                rev,
                                                _short_sha(remote_rev),
                                                _short_sha(local_tag_sha1)
                                            )
                                        )
                        elif remote_rev_type == 'sha1':
                            has_remote_rev = True

            # If fast_forward is not boolean, then we don't know if this will
            # be a fast forward or not, because a fetch is required.
            fast_forward = None if not local_changes else False

            if has_remote_rev:
                if (not revs_match and not update_head) \
                        and (branch is None or branch == local_branch):
                    ret['comment'] = remote_loc.capitalize() \
                        if rev == 'HEAD' \
                        else remote_loc
                    ret['comment'] += (
                        ' is already present and local HEAD ({0}) does not '
                        'match, but update_head=False. HEAD has not been '
                        'updated locally.'.format(local_rev[:7])
                    )
                    return ret

                # No need to check if this is a fast_forward if we already know
                # that it won't be (due to local changes).
                if fast_forward is not False:
                    if base_rev is None:
                        # If we're here, the remote_rev exists in the local
                        # checkout but there is still no HEAD locally. A
                        # possible reason for this is that an empty repository
                        # existed there and a remote was added and fetched, but
                        # the repository was not fast-forwarded. Regardless,
                        # going from no HEAD to a locally-present rev is
                        # considered a fast-forward update, unless there are
                        # local changes.
                        fast_forward = not bool(local_changes)
                    else:
                        fast_forward = __salt__['git.merge_base'](
                            target,
                            refs=[base_rev, remote_rev],
                            is_ancestor=True,
                            user=user,
                            password=password,
                            ignore_retcode=True)

            if fast_forward is False:
                if not force_reset:
                    return _not_fast_forward(
                        ret,
                        rev,
                        base_rev,
                        remote_rev,
                        branch,
                        local_branch,
                        default_branch,
                        local_changes,
                        comments)
                merge_action = 'hard-reset'
            elif fast_forward is True:
                merge_action = 'fast-forwarded'
            else:
                merge_action = 'updated'

            if base_branch is None:
                # No local branch, no upstream tracking branch
                upstream = None
            else:
                try:
                    upstream = __salt__['git.rev_parse'](
                        target,
                        base_branch + '@{upstream}',
                        opts=['--abbrev-ref'],
                        user=user,
                        password=password,
                        ignore_retcode=True)
                except CommandExecutionError:
                    # There is a local branch but the rev-parse command
                    # failed, so that means there is no upstream tracking
                    # branch. This could be because it is just not set, or
                    # because the branch was checked out to a SHA1 or tag
                    # instead of a branch. Set upstream to False to make a
                    # distinction between the case above where there is no
                    # local_branch (when the local checkout is an empty
                    # repository).
                    upstream = False

            if remote in remotes:
                fetch_url = remotes[remote]['fetch']
            else:
                log.debug(
                    'Remote \'%s\' not found in git checkout at %s',
                    remote, target
                )
                fetch_url = None

            if remote_rev is not None and desired_fetch_url != fetch_url:
                if __opts__['test']:
                    actions = [
                        'Remote \'{0}\' would be changed from {1} to {2}'
                        .format(
                            remote,
                            salt.utils.url.redact_http_basic_auth(fetch_url),
                            redacted_fetch_url
                        )
                    ]
                    if not has_remote_rev:
                        actions.append('Remote would be fetched')
                    if not revs_match:
                        if update_head:
                            ret['changes']['revision'] = {
                                'old': local_rev, 'new': remote_rev
                            }
                            if fast_forward is False:
                                ret['changes']['forced update'] = True
                            actions.append(
                                'Repository would be {0} to {1}'.format(
                                    merge_action,
                                    _short_sha(remote_rev)
                                )
                            )
                    if ret['changes']:
                        return _neutral_test(ret, _format_comments(actions))
                    else:
                        if not revs_match and not update_head:
                            # Repo content would not be modified but the remote
                            # URL would be modified, so we can't just say that
                            # the repo is up-to-date, we need to inform the
                            # user of the actions taken.
                            ret['comment'] = _format_comments(actions)
                            return ret
                        return _uptodate(ret,
                                         target,
                                         _format_comments(actions))

                # The fetch_url for the desired remote does not match the
                # specified URL (or the remote does not exist), so set the
                # remote URL.
                __salt__['git.remote_set'](target,
                                           url=name,
                                           remote=remote,
                                           user=user,
                                           password=password,
                                           https_user=https_user,
                                           https_pass=https_pass)
                if fetch_url is None:
                    comments.append(
                        'Remote \'{0}\' set to {1}'.format(
                            remote,
                            redacted_fetch_url
                        )
                    )
                    ret['changes']['new'] = name + ' => ' + remote
                else:
                    comments.append(
                        'Remote \'{0}\' changed from {1} to {2}'.format(
                            remote,
                            salt.utils.url.redact_http_basic_auth(fetch_url),
                            redacted_fetch_url
                        )
                    )

            if remote_rev is not None:
                if __opts__['test']:
                    actions = []
                    if not has_remote_rev:
                        actions.append(
                            'Remote \'{0}\' would be fetched'.format(remote)
                        )
                    if (not revs_match) \
                            and (update_head or (branch is not None
                                                 and branch != local_branch)):
                        ret['changes']['revision'] = {
                            'old': local_rev, 'new': remote_rev
                        }
                    if _need_branch_change(branch, local_branch):
                        if branch not in all_local_branches:
                            actions.append(
                                'New branch \'{0}\' would be checked '
                                'out, with {1} as a starting '
                                'point'.format(branch, remote_loc)
                            )
                            if desired_upstream:
                                actions.append(
                                    'Tracking branch would be set to {0}'
                                    .format(desired_upstream)
                                )
                        else:
                            actions.append(
                                'Branch \'{0}\' would be checked out '
                                'and {1} to {2}'.format(
                                    branch,
                                    merge_action,
                                    _short_sha(remote_rev)
                                )
                            )
                    else:
                        if not revs_match:
                            if update_head:
                                if fast_forward is True:
                                    actions.append(
                                        'Repository would be fast-forwarded from '
                                        '{0} to {1}'.format(
                                            _short_sha(local_rev),
                                            _short_sha(remote_rev)
                                        )
                                    )
                                else:
                                    actions.append(
                                        'Repository would be {0} from {1} to {2}'
                                        .format(
                                            'hard-reset'
                                                if force_reset and has_remote_rev
                                                else 'updated',
                                            _short_sha(local_rev),
                                            _short_sha(remote_rev)
                                        )
                                    )
                            else:
                                actions.append(
                                    'Local HEAD ({0}) does not match {1} but '
                                    'update_head=False, HEAD would not be '
                                    'updated locally'.format(
                                        local_rev[:7],
                                        remote_loc
                                    )
                                )

                    # Check if upstream needs changing
                    if not upstream and desired_upstream:
                        actions.append(
                            'Tracking branch would be set to {0}'.format(
                                desired_upstream
                            )
                        )
                    elif upstream and desired_upstream is False:
                        actions.append(
                            'Tracking branch would be unset'
                        )
                    elif desired_upstream and upstream != desired_upstream:
                        actions.append(
                            'Tracking branch would be '
                            'updated to {0}'.format(desired_upstream)
                        )
                    if ret['changes']:
                        return _neutral_test(ret, _format_comments(actions))
                    else:
                        formatted_actions = _format_comments(actions)
                        if not revs_match \
                                and not update_head \
                                and formatted_actions:
                            ret['comment'] = formatted_actions
                            return ret
                        return _uptodate(ret,
                                         target,
                                         _format_comments(actions))

                if not upstream and desired_upstream:
                    upstream_action = (
                        'Tracking branch was set to {0}'.format(
                            desired_upstream
                        )
                    )
                    branch_opts = _get_branch_opts(
                        branch,
                        local_branch,
                        all_local_branches,
                        desired_upstream,
                        git_ver)
                elif upstream and desired_upstream is False:
                    # If the remote_rev is a tag or SHA1, and there is an
                    # upstream tracking branch, we will unset it. However, we
                    # can only do this if the git version is 1.8.0 or newer, as
                    # the --unset-upstream option was not added until that
                    # version.
                    if git_ver >= _LooseVersion('1.8.0'):
                        upstream_action = 'Tracking branch was unset'
                        branch_opts = ['--unset-upstream']
                    else:
                        branch_opts = None
                elif desired_upstream and upstream != desired_upstream:
                    upstream_action = (
                        'Tracking branch was updated to {0}'.format(
                            desired_upstream
                        )
                    )
                    branch_opts = _get_branch_opts(
                        branch,
                        local_branch,
                        all_local_branches,
                        desired_upstream,
                        git_ver)
                else:
                    branch_opts = None

                if branch_opts is not None and local_branch is None:
                    return _fail(
                        ret,
                        'Cannot set/unset upstream tracking branch, local '
                        'HEAD refers to nonexistent branch. This may have '
                        'been caused by cloning a remote repository for which '
                        'the default branch was renamed or deleted. If you '
                        'are unable to fix the remote repository, you can '
                        'work around this by setting the \'branch\' argument '
                        '(which will ensure that the named branch is created '
                        'if it does not already exist).',
                        comments
                    )
                remote_tags = set([
                    x.replace('refs/tags/', '') for x in __salt__['git.ls_remote'](
                        cwd=target,
                        remote=remote,
                        opts="--tags",
                        user=user,
                        password=password,
                        identity=identity,
                        saltenv=__env__,
                        ignore_retcode=True,
                    ).keys() if '^{}' not in x
                ])
                if set(all_local_tags) != remote_tags:
                    has_remote_rev = False
                    ret['changes']['new_tags'] = list(remote_tags.symmetric_difference(
                        all_local_tags
                    ))

                if not has_remote_rev:
                    try:
                        fetch_changes = __salt__['git.fetch'](
                            target,
                            remote=remote,
                            force=force_fetch,
                            refspecs=refspecs,
                            user=user,
                            password=password,
                            identity=identity,
                            saltenv=__env__)
                    except CommandExecutionError as exc:
                        return _failed_fetch(ret, exc, comments)
                    else:
                        if fetch_changes:
                            comments.append(
                                '{0} was fetched, resulting in updated '
                                'refs'.format(name)
                            )

                    try:
                        __salt__['git.rev_parse'](
                            target,
                            remote_rev + '^{commit}',
                            user=user,
                            password=password,
                            ignore_retcode=True)
                    except CommandExecutionError as exc:
                        return _fail(
                            ret,
                            'Fetch did not successfully retrieve rev \'{0}\' '
                            'from {1}: {2}'.format(rev, name, exc)
                        )

                    if (not revs_match and not update_head) \
                            and (branch is None or branch == local_branch):
                        # Rev now exists locally (was fetched), and since we're
                        # not updating HEAD we'll just exit here.
                        ret['comment'] = remote_loc.capitalize() \
                            if rev == 'HEAD' \
                            else remote_loc
                        ret['comment'] += (
                            ' is already present and local HEAD ({0}) does not '
                            'match, but update_head=False. HEAD has not been '
                            'updated locally.'.format(local_rev[:7])
                        )
                        return ret

                    # Now that we've fetched, check again whether or not
                    # the update is a fast-forward.
                    if base_rev is None:
                        fast_forward = True
                    else:
                        fast_forward = __salt__['git.merge_base'](
                            target,
                            refs=[base_rev, remote_rev],
                            is_ancestor=True,
                            user=user,
                            password=password)

                    if fast_forward is False and not force_reset:
                        return _not_fast_forward(
                            ret,
                            rev,
                            base_rev,
                            remote_rev,
                            branch,
                            local_branch,
                            default_branch,
                            local_changes,
                            comments)

                if _need_branch_change(branch, local_branch):
                    if local_changes and not force_checkout:
                        return _fail(
                            ret,
                            'Local branch \'{0}\' has uncommitted '
                            'changes. Set \'force_checkout\' to True to '
                            'discard them and proceed.'.format(local_branch)
                        )

                    # TODO: Maybe re-retrieve all_local_branches to handle
                    # the corner case where the destination branch was
                    # added to the local checkout during a fetch that takes
                    # a long time to complete.
                    if branch not in all_local_branches:
                        if rev == 'HEAD':
                            checkout_rev = remote_rev
                        else:
                            checkout_rev = desired_upstream \
                                if desired_upstream \
                                else rev
                        checkout_opts = ['-b', branch]
                    else:
                        checkout_rev = branch
                        checkout_opts = []
                    __salt__['git.checkout'](target,
                                             checkout_rev,
                                             force=force_checkout,
                                             opts=checkout_opts,
                                             user=user,
                                             password=password)
                    if '-b' in checkout_opts:
                        comments.append(
                            'New branch \'{0}\' was checked out, with {1} '
                            'as a starting point'.format(
                                branch,
                                remote_loc
                            )
                        )
                    else:
                        comments.append(
                            '\'{0}\' was checked out'.format(checkout_rev)
                        )

                if local_changes:
                    comments.append('Local changes were discarded')

                if fast_forward is False:
                    __salt__['git.reset'](
                        target,
                        opts=['--hard', remote_rev],
                        user=user,
                        password=password,
                    )
                    ret['changes']['forced update'] = True
                    comments.append(
                        'Repository was hard-reset to {0}'.format(remote_loc)
                    )

                if branch_opts is not None:
                    __salt__['git.branch'](
                        target,
                        opts=branch_opts,
                        user=user,
                        password=password)
                    comments.append(upstream_action)

                # Fast-forward to the desired revision
                if fast_forward is True \
                        and not _revs_equal(base_rev,
                                            remote_rev,
                                            remote_rev_type):
                    if desired_upstream or rev == 'HEAD':
                        # Check first to see if we are on a branch before
                        # trying to merge changes. (The call to
                        # git.symbolic_ref will only return output if HEAD
                        # points to a branch.)
                        if __salt__['git.symbolic_ref'](target,
                                                        'HEAD',
                                                        opts=['--quiet'],
                                                        user=user,
                                                        password=password,
                                                        ignore_retcode=True):

                            if git_ver >= _LooseVersion('1.8.1.6'):
                                # --ff-only added in version 1.8.1.6. It's not
                                # 100% necessary, but if we can use it, we'll
                                # ensure that the merge doesn't go through if
                                # not a fast-forward. Granted, the logic that
                                # gets us to this point shouldn't allow us to
                                # attempt this merge if it's not a
                                # fast-forward, but it's an extra layer of
                                # protection.
                                merge_opts = ['--ff-only']
                            else:
                                merge_opts = []

                            __salt__['git.merge'](
                                target,
                                rev=remote_rev,
                                opts=merge_opts,
                                user=user,
                                password=password)
                            comments.append(
                                'Repository was fast-forwarded to {0}'
                                .format(remote_loc)
                            )
                        else:
                            return _fail(
                                ret,
                                'Unable to fast-forward, HEAD is detached',
                                comments
                            )
                    else:
                        # Update is a fast forward, but we cannot merge to that
                        # commit so we'll reset to it.
                        __salt__['git.reset'](
                            target,
                            opts=['--hard',
                                  remote_rev if rev == 'HEAD' else rev],
                            user=user,
                            password=password)
                        comments.append(
                            'Repository was reset to {0} (fast-forward)'
                            .format(rev)
                        )

                # TODO: Figure out how to add submodule update info to
                # test=True return data, and changes dict.
                if submodules:
                    try:
                        __salt__['git.submodule'](
                            target,
                            'update',
                            opts=['--init', '--recursive'],
                            user=user,
                            password=password,
                            identity=identity,
                            saltenv=__env__)
                    except CommandExecutionError as exc:
                        return _failed_submodule_update(ret, exc, comments)
            elif bare:
                if __opts__['test']:
                    msg = (
                        'Bare repository at {0} would be fetched'
                        .format(target)
                    )
                    if ret['changes']:
                        return _neutral_test(ret, msg)
                    else:
                        return _uptodate(ret, target, msg)
                try:
                    fetch_changes = __salt__['git.fetch'](
                        target,
                        remote=remote,
                        force=force_fetch,
                        refspecs=refspecs,
                        user=user,
                        password=password,
                        identity=identity,
                        saltenv=__env__)
                except CommandExecutionError as exc:
                    return _failed_fetch(ret, exc, comments)
                else:
                    comments.append(
                        'Bare repository at {0} was fetched{1}'.format(
                            target,
                            ', resulting in updated refs'
                                if fetch_changes
                                else ''
                        )
                    )
            try:
                new_rev = __salt__['git.revision'](
                    cwd=target,
                    user=user,
                    password=password,
                    ignore_retcode=True)
            except CommandExecutionError:
                new_rev = None

        except Exception as exc:
            log.error(
                'Unexpected exception in git.latest state',
                exc_info=True
            )
            if isinstance(exc, CommandExecutionError):
                msg = _strip_exc(exc)
            else:
                msg = six.text_type(exc)
            return _fail(ret, msg, comments)

        if not bare and not _revs_equal(new_rev,
                                        remote_rev,
                                        remote_rev_type):
            return _fail(ret, 'Failed to update repository', comments)

        if local_rev != new_rev:
            log.info(
                'Repository %s updated: %s => %s',
                target, local_rev, new_rev
            )
            ret['comment'] = _format_comments(comments)
            ret['changes']['revision'] = {'old': local_rev, 'new': new_rev}
        else:
            return _uptodate(ret, target, _format_comments(comments))
    else:
        if os.path.isdir(target):
            target_contents = os.listdir(target)
            if force_clone:
                # Clone is required, and target directory exists, but the
                # ``force`` option is enabled, so we need to clear out its
                # contents to proceed.
                if __opts__['test']:
                    ret['changes']['forced clone'] = True
                    ret['changes']['new'] = name + ' => ' + target
                    return _neutral_test(
                        ret,
                        'Target directory {0} exists. Since force_clone=True, '
                        'the contents of {0} would be deleted, and {1} would '
                        'be cloned into this directory.'.format(target, name)
                    )
                log.debug(
                    'Removing contents of %s to clone repository %s in its '
                    'place (force_clone=True set in git.latest state)',
                    target, name
                )
                removal_errors = {}
                for target_object in target_contents:
                    target_path = os.path.join(target, target_object)
                    try:
                        salt.utils.files.rm_rf(target_path)
                    except OSError as exc:
                        if exc.errno != errno.ENOENT:
                            removal_errors[target_path] = exc
                if removal_errors:
                    err_strings = [
                        '  {0}\n    {1}'.format(k, v)
                        for k, v in six.iteritems(removal_errors)
                    ]
                    return _fail(
                        ret,
                        'Unable to remove\n{0}'.format('\n'.join(err_strings)),
                        comments
                    )
                ret['changes']['forced clone'] = True
            # Clone is required, but target dir exists and is non-empty. We
            # can't proceed.
            elif target_contents:
                return _fail(
                    ret,
                    'Target \'{0}\' exists, is non-empty and is not a git '
                    'repository. Set the \'force_clone\' option to True to '
                    'remove this directory\'s contents and proceed with '
                    'cloning the remote repository'.format(target)
                )

        log.debug('Target %s is not found, \'git clone\' is required', target)
        if __opts__['test']:
            ret['changes']['new'] = name + ' => ' + target
            return _neutral_test(
                ret,
                'Repository {0} would be cloned to {1}'.format(
                    name, target
                )
            )
        try:
            clone_opts = ['--mirror'] if mirror else ['--bare'] if bare else []
            if remote != 'origin':
                clone_opts.extend(['--origin', remote])
            if depth is not None:
                clone_opts.extend(['--depth', six.text_type(depth), '--branch', rev])

            # We're cloning a fresh repo, there is no local branch or revision
            local_branch = local_rev = None

            try:
                __salt__['git.clone'](target,
                                      name,
                                      user=user,
                                      password=password,
                                      opts=clone_opts,
                                      identity=identity,
                                      https_user=https_user,
                                      https_pass=https_pass,
                                      saltenv=__env__)
            except CommandExecutionError as exc:
                msg = 'Clone failed: {0}'.format(_strip_exc(exc))
                return _fail(ret, msg, comments)

            ret['changes']['new'] = name + ' => ' + target
            comments.append(
                '{0} cloned to {1}{2}'.format(
                    name,
                    target,
                    ' as mirror' if mirror
                        else ' as bare repository' if bare
                        else ''
                )
            )

            if not bare:
                if not remote_rev:
                    if rev != 'HEAD':
                        # No HEAD means the remote repo is empty, which means
                        # our new clone will also be empty. This state has
                        # failed, since a rev was specified but no matching rev
                        # exists on the remote host.
                        msg = (
                            '%s was cloned but is empty, so {0}/{1} '
                            'cannot be checked out'.format(remote, rev)
                        )
                        log.error(msg, name)
                        # Disable check for string substitution
                        return _fail(ret, msg % 'Repository', comments)  # pylint: disable=E1321
                else:
                    if remote_rev_type == 'tag' \
                            and rev not in __salt__['git.list_tags'](
                                target, user=user, password=password):
                        return _fail(
                            ret,
                            'Revision \'{0}\' does not exist in clone'
                            .format(rev),
                            comments
                        )

                    if branch is not None:
                        if branch not in \
                                __salt__['git.list_branches'](
                                    target,
                                    user=user,
                                    password=password):
                            if rev == 'HEAD':
                                checkout_rev = remote_rev
                            else:
                                checkout_rev = desired_upstream \
                                    if desired_upstream \
                                    else rev
                            __salt__['git.checkout'](target,
                                                     checkout_rev,
                                                     opts=['-b', branch],
                                                     user=user,
                                                     password=password)
                            comments.append(
                                'Branch \'{0}\' checked out, with {1} '
                                'as a starting point'.format(
                                    branch,
                                    remote_loc
                                )
                            )

                    local_rev, local_branch = \
                        _get_local_rev_and_branch(target, user, password)

                    if local_branch is None \
                            and remote_rev is not None \
                            and 'HEAD' not in all_remote_refs:
                        return _fail(
                            ret,
                            'Remote HEAD refers to a ref that does not exist. '
                            'This can happen when the default branch on the '
                            'remote repository is renamed or deleted. If you '
                            'are unable to fix the remote repository, you can '
                            'work around this by setting the \'branch\' argument '
                            '(which will ensure that the named branch is created '
                            'if it does not already exist).',
                            comments
                        )

                    if not _revs_equal(local_rev, remote_rev, remote_rev_type):
                        __salt__['git.reset'](
                            target,
                            opts=['--hard', remote_rev],
                            user=user,
                            password=password)
                        comments.append(
                            'Repository was reset to {0}'.format(remote_loc)
                        )

                    try:
                        upstream = __salt__['git.rev_parse'](
                            target,
                            local_branch + '@{upstream}',
                            opts=['--abbrev-ref'],
                            user=user,
                            password=password,
                            ignore_retcode=True)
                    except CommandExecutionError:
                        upstream = False

                    if not upstream and desired_upstream:
                        upstream_action = (
                            'Tracking branch was set to {0}'.format(
                                desired_upstream
                            )
                        )
                        branch_opts = _get_branch_opts(
                            branch,
                            local_branch,
                            __salt__['git.list_branches'](target,
                                                          user=user,
                                                          password=password),
                            desired_upstream,
                            git_ver)
                    elif upstream and desired_upstream is False:
                        # If the remote_rev is a tag or SHA1, and there is an
                        # upstream tracking branch, we will unset it. However,
                        # we can only do this if the git version is 1.8.0 or
                        # newer, as the --unset-upstream option was not added
                        # until that version.
                        if git_ver >= _LooseVersion('1.8.0'):
                            upstream_action = 'Tracking branch was unset'
                            branch_opts = ['--unset-upstream']
                        else:
                            branch_opts = None
                    elif desired_upstream and upstream != desired_upstream:
                        upstream_action = (
                            'Tracking branch was updated to {0}'.format(
                                desired_upstream
                            )
                        )
                        branch_opts = _get_branch_opts(
                            branch,
                            local_branch,
                            __salt__['git.list_branches'](target,
                                                          user=user,
                                                          password=password),
                            desired_upstream,
                            git_ver)
                    else:
                        branch_opts = None

                    if branch_opts is not None:
                        __salt__['git.branch'](
                            target,
                            opts=branch_opts,
                            user=user,
                            password=password)
                        comments.append(upstream_action)

            if submodules and remote_rev:
                try:
                    __salt__['git.submodule'](target,
                                              'update',
                                              opts=['--init', '--recursive'],
                                              user=user,
                                              password=password,
                                              identity=identity)
                except CommandExecutionError as exc:
                    return _failed_submodule_update(ret, exc, comments)

            try:
                new_rev = __salt__['git.revision'](
                    cwd=target,
                    user=user,
                    password=password,
                    ignore_retcode=True)
            except CommandExecutionError:
                new_rev = None

        except Exception as exc:
            log.error(
                'Unexpected exception in git.latest state',
                exc_info=True
            )
            if isinstance(exc, CommandExecutionError):
                msg = _strip_exc(exc)
            else:
                msg = six.text_type(exc)
            return _fail(ret, msg, comments)

        msg = _format_comments(comments)
        log.info(msg)
        ret['comment'] = msg
        if new_rev is not None:
            ret['changes']['revision'] = {'old': None, 'new': new_rev}
    return ret


def present(name,
            force=False,
            bare=True,
            template=None,
            separate_git_dir=None,
            shared=None,
            user=None,
            password=None):
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

    password
        Windows only. Required when specifying ``user``. This parameter will be
        ignored on non-Windows platforms.

      .. versionadded:: 2016.3.4

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
                 __salt__['git.is_worktree'](name, user=user, password=password)):
            return ret
        # Directory exists and is not a git repo, if force is set destroy the
        # directory and recreate, otherwise throw an error
        elif force:
            # Directory exists, and the ``force`` option is enabled, so we need
            # to clear out its contents to proceed.
            if __opts__['test']:
                ret['changes']['new'] = name
                ret['changes']['forced init'] = True
                return _neutral_test(
                    ret,
                    'Target directory {0} exists. Since force=True, the '
                    'contents of {0} would be deleted, and a {1}repository '
                    'would be initialized in its place.'
                    .format(name, 'bare ' if bare else '')
                )
            log.debug(
                'Removing contents of %s to initialize %srepository in its '
                'place (force=True set in git.present state)',
                name, 'bare ' if bare else ''
            )
            try:
                if os.path.islink(name):
                    os.unlink(name)
                else:
                    salt.utils.files.rm_rf(name)
            except OSError as exc:
                return _fail(
                    ret,
                    'Unable to remove {0}: {1}'.format(name, exc)
                )
            else:
                ret['changes']['forced init'] = True
        elif os.listdir(name):
            return _fail(
                ret,
                'Target \'{0}\' exists, is non-empty, and is not a git '
                'repository. Set the \'force\' option to True to remove '
                'this directory\'s contents and proceed with initializing a '
                'repository'.format(name)
            )

    # Run test is set
    if __opts__['test']:
        ret['changes']['new'] = name
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
                         user=user,
                         password=password)

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


def detached(name,
           rev,
           target=None,
           remote='origin',
           user=None,
           password=None,
           force_clone=False,
           force_checkout=False,
           fetch_remote=True,
           hard_reset=False,
           submodules=False,
           identity=None,
           https_user=None,
           https_pass=None,
           onlyif=False,
           unless=False,
           **kwargs):
    '''
    .. versionadded:: 2016.3.0

    Make sure a repository is cloned to the given target directory and is
    a detached HEAD checkout of the commit ID resolved from ``ref``.

    name
        Address of the remote repository.

    rev
        The branch, tag, or commit ID to checkout after clone.
        If a branch or tag is specified it will be resolved to a commit ID
        and checked out.

    ref
        .. deprecated:: 2017.7.0
            Use ``rev`` instead.

    target
        Name of the target directory where repository is about to be cloned.

    remote : origin
        Git remote to use. If this state needs to clone the repo, it will clone
        it using this value as the initial remote name. If the repository
        already exists, and a remote by this name is not present, one will be
        added.

    user
        User under which to run git commands. By default, commands are run by
        the user under which the minion is running.

    password
        Windows only. Required when specifying ``user``. This parameter will be
        ignored on non-Windows platforms.

      .. versionadded:: 2016.3.4

    force_clone : False
        If the ``target`` directory exists and is not a git repository, then
        this state will fail. Set this argument to ``True`` to remove the
        contents of the target directory and clone the repo into it.

    force_checkout : False
        When checking out the revision ID, the state will fail if there are
        unwritten changes. Set this argument to ``True`` to discard unwritten
        changes when checking out.

    fetch_remote : True
        If ``False`` a fetch will not be performed and only local refs
        will be reachable.

    hard_reset : False
        If ``True`` a hard reset will be performed before the checkout and any
        uncommitted modifications to the working directory will be discarded.
        Untracked files will remain in place.

        .. note::
            Changes resulting from a hard reset will not trigger requisites.

    submodules : False
        Update submodules

    identity
        A path on the minion (or a SaltStack fileserver URL, e.g.
        ``salt://path/to/identity_file``) to a private key to use for SSH
        authentication.

    https_user
        HTTP Basic Auth username for HTTPS (only) clones

    https_pass
        HTTP Basic Auth password for HTTPS (only) clones

    onlyif
        A command to run as a check, run the named command only if the command
        passed to the ``onlyif`` option returns true

    unless
        A command to run as a check, only run the named command if the command
        passed to the ``unless`` option returns false

    '''

    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    ref = kwargs.pop('ref', None)
    kwargs = salt.utils.args.clean_kwargs(**kwargs)
    if kwargs:
        return _fail(
            ret,
            salt.utils.args.invalid_kwargs(kwargs, raise_exc=False)
        )

    if ref is not None:
        rev = ref
        deprecation_msg = (
            'The \'ref\' argument has been renamed to \'rev\' for '
            'consistency. Please update your SLS to reflect this.'
        )
        ret.setdefault('warnings', []).append(deprecation_msg)
        salt.utils.versions.warn_until('Fluorine', deprecation_msg)

    if not rev:
        return _fail(
            ret,
            '\'{0}\' is not a valid value for the \'rev\' argument'.format(rev)
        )

    if not target:
        return _fail(
            ret,
            '\'{0}\' is not a valid value for the \'target\' argument'.format(rev)
        )

    # Ensure that certain arguments are strings to ensure that comparisons work
    if not isinstance(rev, six.string_types):
        rev = six.text_type(rev)
    if target is not None:
        if not isinstance(target, six.string_types):
            target = six.text_type(target)
        if not os.path.isabs(target):
            return _fail(
                ret,
                'Target \'{0}\' is not an absolute path'.format(target)
            )
    if user is not None and not isinstance(user, six.string_types):
        user = six.text_type(user)
    if remote is not None and not isinstance(remote, six.string_types):
        remote = six.text_type(remote)
    if identity is not None:
        if isinstance(identity, six.string_types):
            identity = [identity]
        elif not isinstance(identity, list):
            return _fail(ret, 'Identity must be either a list or a string')
        for ident_path in identity:
            if 'salt://' in ident_path:
                try:
                    ident_path = __salt__['cp.cache_file'](ident_path)
                except IOError as exc:
                    log.error('Failed to cache %s: %s', ident_path, exc)
                    return _fail(
                        ret,
                        'Identity \'{0}\' does not exist.'.format(
                            ident_path
                        )
                    )
            if not os.path.isabs(ident_path):
                return _fail(
                    ret,
                    'Identity \'{0}\' is not an absolute path'.format(
                        ident_path
                    )
                )
    if https_user is not None and not isinstance(https_user, six.string_types):
        https_user = six.text_type(https_user)
    if https_pass is not None and not isinstance(https_pass, six.string_types):
        https_pass = six.text_type(https_pass)

    if os.path.isfile(target):
        return _fail(
            ret,
            'Target \'{0}\' exists and is a regular file, cannot proceed'
            .format(target)
        )

    try:
        desired_fetch_url = salt.utils.url.add_http_basic_auth(
            name,
            https_user,
            https_pass,
            https_only=True
        )
    except ValueError as exc:
        return _fail(ret, exc.__str__())

    redacted_fetch_url = salt.utils.url.redact_http_basic_auth(desired_fetch_url)

    # Check if onlyif or unless conditions match
    run_check_cmd_kwargs = {'runas': user}
    if 'shell' in __grains__:
        run_check_cmd_kwargs['shell'] = __grains__['shell']
    cret = mod_run_check(
        run_check_cmd_kwargs, onlyif, unless
    )
    if isinstance(cret, dict):
        ret.update(cret)
        return ret

    # Determine if supplied ref is a hash
    remote_rev_type = 'ref'
    if len(rev) <= 40 \
            and all(x in string.hexdigits for x in rev):
        rev = rev.lower()
        remote_rev_type = 'hash'

    comments = []
    hash_exists_locally = False
    local_commit_id = None

    gitdir = os.path.join(target, '.git')
    if os.path.isdir(gitdir) \
            or __salt__['git.is_worktree'](target, user=user, password=password):
        # Target directory is a git repository or git worktree

        local_commit_id = _get_local_rev_and_branch(target, user, password)[0]

        if remote_rev_type is 'hash':
            try:
                __salt__['git.describe'](target,
                                         rev,
                                         user=user,
                                         password=password,
                                         ignore_retcode=True)
            except CommandExecutionError:
                hash_exists_locally = False
            else:
                # The rev is a hash and it exists locally so skip to checkout
                hash_exists_locally = True
        else:
            # Check that remote is present and set to correct url
            remotes = __salt__['git.remotes'](target,
                                              user=user,
                                              password=password,
                                              redact_auth=False)

            if remote in remotes and name in remotes[remote]['fetch']:
                pass
            else:
                # The fetch_url for the desired remote does not match the
                # specified URL (or the remote does not exist), so set the
                # remote URL.
                current_fetch_url = None
                if remote in remotes:
                    current_fetch_url = remotes[remote]['fetch']

                if __opts__['test']:
                    return _neutral_test(
                        ret,
                        'Remote {0} would be set to {1}'.format(
                            remote, name
                        )
                    )

                __salt__['git.remote_set'](target,
                                           url=name,
                                           remote=remote,
                                           user=user,
                                           password=password,
                                           https_user=https_user,
                                           https_pass=https_pass)
                comments.append(
                    'Remote {0} updated from \'{1}\' to \'{2}\''.format(
                        remote,
                        current_fetch_url,
                        name
                    )
                )

    else:
        # Clone repository
        if os.path.isdir(target):
            target_contents = os.listdir(target)
            if force_clone:
                # Clone is required, and target directory exists, but the
                # ``force`` option is enabled, so we need to clear out its
                # contents to proceed.
                if __opts__['test']:
                    return _neutral_test(
                        ret,
                        'Target directory {0} exists. Since force_clone=True, '
                        'the contents of {0} would be deleted, and {1} would '
                        'be cloned into this directory.'.format(target, name)
                    )
                log.debug(
                    'Removing contents of %s to clone repository %s in its '
                    'place (force_clone=True set in git.detached state)',
                    target, name
                )
                removal_errors = {}
                for target_object in target_contents:
                    target_path = os.path.join(target, target_object)
                    try:
                        salt.utils.files.rm_rf(target_path)
                    except OSError as exc:
                        if exc.errno != errno.ENOENT:
                            removal_errors[target_path] = exc
                if removal_errors:
                    err_strings = [
                        '  {0}\n    {1}'.format(k, v)
                        for k, v in six.iteritems(removal_errors)
                    ]
                    return _fail(
                        ret,
                        'Unable to remove\n{0}'.format('\n'.join(err_strings)),
                        comments
                    )
                ret['changes']['forced clone'] = True
            elif target_contents:
                # Clone is required, but target dir exists and is non-empty. We
                # can't proceed.
                return _fail(
                    ret,
                    'Target \'{0}\' exists, is non-empty and is not a git '
                    'repository. Set the \'force_clone\' option to True to '
                    'remove this directory\'s contents and proceed with '
                    'cloning the remote repository'.format(target)
                )

        log.debug('Target %s is not found, \'git clone\' is required', target)
        if __opts__['test']:
            return _neutral_test(
                ret,
                'Repository {0} would be cloned to {1}'.format(
                    name, target
                )
            )
        try:
            clone_opts = ['--no-checkout']
            if remote != 'origin':
                clone_opts.extend(['--origin', remote])

            __salt__['git.clone'](target,
                                  name,
                                  user=user,
                                  password=password,
                                  opts=clone_opts,
                                  identity=identity,
                                  https_user=https_user,
                                  https_pass=https_pass,
                                  saltenv=__env__)
            comments.append('{0} cloned to {1}'.format(name, target))

        except Exception as exc:
            log.error(
                'Unexpected exception in git.detached state',
                exc_info=True
            )
            if isinstance(exc, CommandExecutionError):
                msg = _strip_exc(exc)
            else:
                msg = six.text_type(exc)
            return _fail(ret, msg, comments)

    # Repository exists and is ready for fetch/checkout
    refspecs = [
        'refs/heads/*:refs/remotes/{0}/*'.format(remote),
        '+refs/tags/*:refs/tags/*'
    ]
    if hash_exists_locally or fetch_remote is False:
        pass
    else:
        # Fetch refs from remote
        if __opts__['test']:
            return _neutral_test(
                ret,
                'Repository remote {0} would be fetched'.format(remote)
            )
        try:
            fetch_changes = __salt__['git.fetch'](
                target,
                remote=remote,
                force=True,
                refspecs=refspecs,
                user=user,
                password=password,
                identity=identity,
                saltenv=__env__)
        except CommandExecutionError as exc:
            msg = 'Fetch failed'
            msg += ':\n\n' + six.text_type(exc)
            return _fail(ret, msg, comments)
        else:
            if fetch_changes:
                comments.append(
                    'Remote {0} was fetched, resulting in updated '
                    'refs'.format(remote)
                )

    #get refs and checkout
    checkout_commit_id = ''
    if remote_rev_type is 'hash':
        if __salt__['git.describe'](target, rev, user=user, password=password):
            checkout_commit_id = rev
        else:
            return _fail(
                ret,
                'Revision \'{0}\' does not exist'.format(rev)
            )
    else:
        try:
            all_remote_refs = __salt__['git.remote_refs'](
                target,
                user=user,
                password=password,
                identity=identity,
                https_user=https_user,
                https_pass=https_pass,
                ignore_retcode=False)

            if 'refs/remotes/'+remote+'/'+rev in all_remote_refs:
                checkout_commit_id = all_remote_refs['refs/remotes/' + remote + '/' + rev]
            elif 'refs/tags/' + rev in all_remote_refs:
                checkout_commit_id = all_remote_refs['refs/tags/' + rev]
            else:
                return _fail(
                    ret,
                    'Revision \'{0}\' does not exist'.format(rev)
                )

        except CommandExecutionError as exc:
            return _fail(
                ret,
                'Failed to list refs for {0}: {1}'.format(remote, _strip_exc(exc))
            )

    if hard_reset:
        if __opts__['test']:
            return _neutral_test(
                ret,
                'Hard reset to HEAD would be performed on {0}'.format(target)
            )
        __salt__['git.reset'](
            target,
            opts=['--hard', 'HEAD'],
            user=user,
            password=password)
        comments.append(
            'Repository was reset to HEAD before checking out revision'
        )

    # TODO: implement clean function for git module and add clean flag

    if checkout_commit_id == local_commit_id:
        new_rev = None
    else:
        if __opts__['test']:
            ret['changes']['HEAD'] = {'old': local_commit_id, 'new': checkout_commit_id}
            return _neutral_test(
                ret,
                'Commit ID {0} would be checked out at {1}'.format(
                    checkout_commit_id,
                    target
                )
            )
        __salt__['git.checkout'](target,
                                 checkout_commit_id,
                                 force=force_checkout,
                                 user=user,
                                 password=password)
        comments.append(
            'Commit ID {0} was checked out at {1}'.format(
                checkout_commit_id,
                target
            )
        )

        try:
            new_rev = __salt__['git.revision'](
                cwd=target,
                user=user,
                password=password,
                ignore_retcode=True)
        except CommandExecutionError:
            new_rev = None

    if submodules:
        __salt__['git.submodule'](target,
                                  'update',
                                  opts=['--init', '--recursive'],
                                  user=user,
                                  password=password,
                                  identity=identity)
        comments.append(
            'Submodules were updated'
        )

    if new_rev is not None:
        ret['changes']['HEAD'] = {'old': local_commit_id, 'new': new_rev}
    else:
        comments.append("Already checked out at correct revision")

    msg = _format_comments(comments)
    log.info(msg)
    ret['comment'] = msg

    return ret


def config_unset(name,
                 value_regex=None,
                 repo=None,
                 user=None,
                 password=None,
                 **kwargs):
    r'''
    .. versionadded:: 2015.8.0

    Ensure that the named config key is not present

    name
        The name of the configuration key to unset. This value can be a regex,
        but the regex must match the entire key name. For example, ``foo\.``
        would not match all keys in the ``foo`` section, it would be necessary
        to use ``foo\..+`` to do so.

    value_regex
        Regex indicating the values to unset for the matching key(s)

        .. note::
            This option behaves differently depending on whether or not ``all``
            is set to ``True``. If it is, then all values matching the regex
            will be deleted (this is the only way to delete multiple values
            from a multivar). If ``all`` is set to ``False``, then this state
            will fail if the regex matches more than one value in a multivar.

    all : False
        If ``True``, unset all matches

    repo
        Location of the git repository for which the config value should be
        set. Required unless ``global`` is set to ``True``.

    user
        User under which to run git commands. By default, commands are run by
        the user under which the minion is running.

    password
        Windows only. Required when specifying ``user``. This parameter will be
        ignored on non-Windows platforms.

      .. versionadded:: 2016.3.4

    global : False
        If ``True``, this will set a global git config option


    **Examples:**

    .. code-block:: yaml

        # Value matching 'baz'
        mylocalrepo:
          git.config_unset:
            - name: foo.bar
            - value_regex: 'baz'
            - repo: /path/to/repo

        # Ensure entire multivar is unset
        mylocalrepo:
          git.config_unset:
            - name: foo.bar
            - all: True

        # Ensure all variables in 'foo' section are unset, including multivars
        mylocalrepo:
          git.config_unset:
            - name: 'foo\..+'
            - all: True

        # Ensure that global config value is unset
        mylocalrepo:
          git.config_unset:
            - name: foo.bar
            - global: True
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'No matching keys are set'}

    # Sanitize kwargs and make sure that no invalid ones were passed. This
    # allows us to accept 'global' as an argument to this function without
    # shadowing global(), while also not allowing unwanted arguments to be
    # passed.
    kwargs = salt.utils.args.clean_kwargs(**kwargs)
    global_ = kwargs.pop('global', False)
    all_ = kwargs.pop('all', False)
    if kwargs:
        return _fail(
            ret,
            salt.utils.args.invalid_kwargs(kwargs, raise_exc=False)
        )

    if not global_ and not repo:
        return _fail(
            ret,
            'Non-global config options require the \'repo\' argument to be '
            'set'
        )

    if not isinstance(name, six.string_types):
        name = six.text_type(name)
    if value_regex is not None:
        if not isinstance(value_regex, six.string_types):
            value_regex = six.text_type(value_regex)

    # Ensure that the key regex matches the full key name
    key = '^' + name.lstrip('^').rstrip('$') + '$'

    # Get matching keys/values
    pre_matches = __salt__['git.config_get_regexp'](
        cwd=repo,
        key=key,
        value_regex=value_regex,
        user=user,
        password=password,
        ignore_retcode=True,
        **{'global': global_}
    )

    if not pre_matches:
        # No changes need to be made
        return ret

    # Perform sanity check on the matches. We can't proceed if the value_regex
    # matches more than one value in a given key, and 'all' is not set to True
    if not all_:
        greedy_matches = ['{0} ({1})'.format(x, ', '.join(y))
                          for x, y in six.iteritems(pre_matches)
                          if len(y) > 1]
        if greedy_matches:
            if value_regex is not None:
                return _fail(
                    ret,
                    'Multiple values are matched by value_regex for the '
                    'following keys (set \'all\' to True to force removal): '
                    '{0}'.format('; '.join(greedy_matches))
                )
            else:
                return _fail(
                    ret,
                    'Multivar(s) matched by the key expression (set \'all\' '
                    'to True to force removal): {0}'.format(
                        '; '.join(greedy_matches)
                    )
                )

    if __opts__['test']:
        ret['changes'] = pre_matches
        return _neutral_test(
            ret,
            '{0} key(s) would have value(s) unset'.format(len(pre_matches))
        )

    if value_regex is None:
        pre = pre_matches
    else:
        # Get all keys matching the key expression, so we can accurately report
        # on changes made.
        pre = __salt__['git.config_get_regexp'](
            cwd=repo,
            key=key,
            value_regex=None,
            user=user,
            password=password,
            ignore_retcode=True,
            **{'global': global_}
        )

    failed = []
    # Unset the specified value(s). There is no unset for regexes so loop
    # through the pre_matches dict and unset each matching key individually.
    for key_name in pre_matches:
        try:
            __salt__['git.config_unset'](
                cwd=repo,
                key=name,
                value_regex=value_regex,
                all=all_,
                user=user,
                password=password,
                **{'global': global_}
            )
        except CommandExecutionError as exc:
            msg = 'Failed to unset \'{0}\''.format(key_name)
            if value_regex is not None:
                msg += ' using value_regex \'{1}\''
            msg += ': ' + _strip_exc(exc)
            log.error(msg)
            failed.append(key_name)

    if failed:
        return _fail(
            ret,
            'Error(s) occurred unsetting values for the following keys (see '
            'the minion log for details): {0}'.format(', '.join(failed))
        )

    post = __salt__['git.config_get_regexp'](
        cwd=repo,
        key=key,
        value_regex=None,
        user=user,
        password=password,
        ignore_retcode=True,
        **{'global': global_}
    )

    for key_name in pre:
        if key_name not in post:
            ret['changes'][key_name] = pre[key_name]
        unset = [x for x in pre[key_name] if x not in post[key_name]]
        if unset:
            ret['changes'][key_name] = unset

    if value_regex is None:
        post_matches = post
    else:
        post_matches = __salt__['git.config_get_regexp'](
            cwd=repo,
            key=key,
            value_regex=value_regex,
            user=user,
            password=password,
            ignore_retcode=True,
            **{'global': global_}
        )

    if post_matches:
        failed = ['{0} ({1})'.format(x, ', '.join(y))
                  for x, y in six.iteritems(post_matches)]
        return _fail(
            ret,
            'Failed to unset value(s): {0}'.format('; '.join(failed))
        )

    ret['comment'] = 'Value(s) successfully unset'
    return ret


def config_set(name,
               value=None,
               multivar=None,
               repo=None,
               user=None,
               password=None,
               **kwargs):
    '''
    .. versionadded:: 2014.7.0
    .. versionchanged:: 2015.8.0
        Renamed from ``git.config`` to ``git.config_set``. For earlier
        versions, use ``git.config``.

    Ensure that a config value is set to the desired value(s)

    name
        Name of the git config value to set

    value
        Set a single value for the config item

    multivar
        Set multiple values for the config item

        .. note::
            The order matters here, if the same parameters are set but in a
            different order, they will be removed and replaced in the order
            specified.

        .. versionadded:: 2015.8.0

    repo
        Location of the git repository for which the config value should be
        set. Required unless ``global`` is set to ``True``.

    user
        User under which to run git commands. By default, the commands are run
        by the user under which the minion is running.

    password
        Windows only. Required when specifying ``user``. This parameter will be
        ignored on non-Windows platforms.

      .. versionadded:: 2016.3.4

    global : False
        If ``True``, this will set a global git config option

    **Local Config Example:**

    .. code-block:: yaml

        # Single value
        mylocalrepo:
          git.config_set:
            - name: user.email
            - value: foo@bar.net
            - repo: /path/to/repo

        # Multiple values
        mylocalrepo:
          git.config_set:
            - name: mysection.myattribute
            - multivar:
              - foo
              - bar
              - baz
            - repo: /path/to/repo

    **Global Config Example (User ``foo``):**

    .. code-block:: yaml

        mylocalrepo:
          git.config_set:
            - name: user.name
            - value: Foo Bar
            - user: foo
            - global: True
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    if value is not None and multivar is not None:
        return _fail(
            ret,
            'Only one of \'value\' and \'multivar\' is permitted'
        )

    # Sanitize kwargs and make sure that no invalid ones were passed. This
    # allows us to accept 'global' as an argument to this function without
    # shadowing global(), while also not allowing unwanted arguments to be
    # passed.
    kwargs = salt.utils.args.clean_kwargs(**kwargs)
    global_ = kwargs.pop('global', False)
    if kwargs:
        return _fail(
            ret,
            salt.utils.args.invalid_kwargs(kwargs, raise_exc=False)
        )

    if not global_ and not repo:
        return _fail(
            ret,
            'Non-global config options require the \'repo\' argument to be '
            'set'
        )

    if not isinstance(name, six.string_types):
        name = six.text_type(name)
    if value is not None:
        if not isinstance(value, six.string_types):
            value = six.text_type(value)
        value_comment = '\'' + value + '\''
        desired = [value]
    if multivar is not None:
        if not isinstance(multivar, list):
            try:
                multivar = multivar.split(',')
            except AttributeError:
                multivar = six.text_type(multivar).split(',')
        else:
            new_multivar = []
            for item in multivar:
                if isinstance(item, six.string_types):
                    new_multivar.append(item)
                else:
                    new_multivar.append(six.text_type(item))
            multivar = new_multivar
        value_comment = multivar
        desired = multivar

    # Get current value
    pre = __salt__['git.config_get'](
        cwd=repo,
        key=name,
        user=user,
        password=password,
        ignore_retcode=True,
        **{'all': True, 'global': global_}
    )

    if desired == pre:
        ret['comment'] = '{0}\'{1}\' is already set to {2}'.format(
            'Global key ' if global_ else '',
            name,
            value_comment
        )
        return ret

    if __opts__['test']:
        ret['changes'] = {'old': pre, 'new': desired}
        msg = '{0}\'{1}\' would be {2} {3}'.format(
            'Global key ' if global_ else '',
            name,
            'added as' if pre is None else 'set to',
            value_comment
        )
        return _neutral_test(ret, msg)

    try:
        # Set/update config value
        post = __salt__['git.config_set'](
            cwd=repo,
            key=name,
            value=value,
            multivar=multivar,
            user=user,
            password=password,
            **{'global': global_}
        )
    except CommandExecutionError as exc:
        return _fail(
            ret,
            'Failed to set {0}\'{1}\' to {2}: {3}'.format(
                'global key ' if global_ else '',
                name,
                value_comment,
                _strip_exc(exc)
            )
        )

    if pre != post:
        ret['changes'][name] = {'old': pre, 'new': post}

    if post != desired:
        return _fail(
            ret,
            'Failed to set {0}\'{1}\' to {2}'.format(
                'global key ' if global_ else '',
                name,
                value_comment
            )
        )

    ret['comment'] = '{0}\'{1}\' was {2} {3}'.format(
        'Global key ' if global_ else '',
        name,
        'added as' if pre is None else 'set to',
        value_comment
    )
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
            return {'comment': 'onlyif condition is false',
                    'skip_watch': True,
                    'result': True}

    if unless:
        if __salt__['cmd.retcode'](unless, **cmd_kwargs) == 0:
            return {'comment': 'unless condition is true',
                    'skip_watch': True,
                    'result': True}

    # No reason to stop, return True
    return True
