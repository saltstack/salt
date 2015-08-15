# -*- coding: utf-8 -*-
'''
Interaction with Git repositories
=================================

Important: Before using git over ssh, make sure your remote host fingerprint
exists in your ``~/.ssh/known_hosts`` file. To avoid requiring password
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
import string

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


def _format_comments(comments):
    '''
    Return a joined list
    '''
    ret = '. '.join(comments)
    if len(comments) > 1:
        ret += '.'
    return ret


def _parse_fetch(output):
    '''
    Go through the output from a git fetch and return a dict
    '''
    update_re = re.compile(
        r'.*(?:([0-9a-f]+)\.\.([0-9a-f]+)|'
        r'\[(?:new (tag|branch)|tag update)\])\s+(.+)->'
    )
    ret = {}
    for line in output.splitlines():
        match = update_re.match(line)
        if match:
            old_sha, new_sha, new_ref_type, ref_name = \
                match.groups()
            ref_name = ref_name.rstrip()
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


def _get_local_rev_and_branch(target, user):
    '''
    Return the local revision for before/after comparisons
    '''
    log.info('Checking local revision for {0}'.format(target))
    try:
        local_rev = __salt__['git.revision'](target,
                                             user=user,
                                             ignore_retcode=True)
    except CommandExecutionError:
        log.info('No local revision for {0}'.format(target))
        local_rev = None

    log.info('Checking local branch for {0}'.format(target))
    try:
        local_branch = __salt__['git.current_branch'](target,
                                                      user=user,
                                                      ignore_retcode=True)
    except CommandExecutionError:
        log.info('No local branch for {0}'.format(target))
        local_branch = None

    return local_rev, local_branch


def _strip_exc(exc):
    '''
    Strip the actual command that was run from exc.strerror to leave just the
    error message
    '''
    return re.sub('^Command [\'"].+[\'"] failed: ', '', exc.strerror)


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


def _not_fast_forward(ret, pre, post, branch, local_branch, comments):
    return _fail(
        ret,
        'Repository would be updated from {0} to {1}{2}, but this is not a '
        'fast-forward merge. Set \'force_reset\' to True to force this '
        'update.'.format(
            pre[:7],
            post[:7],
            ' (after checking out local branch \'{0}\')'.format(branch)
                if branch != local_branch
                else ''
        ),
        comments
    )


def latest(name,
           rev=None,
           target=None,
           branch=None,
           user=None,
           force_clone=False,
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
           force=None,
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

    branch
        Name of the branch into which to checkout the specified rev. If not
        specified, this will default to the value of ``rev``. This option is
        useful when checking out a tag, to avoid ambiguous refs in the local
        checkout.

        .. versionadded:: 2015.8.0

    user
        User under which to run git commands. By default, commands are run by
        the user under which the minion is running.

        .. versionadded:: 0.17.0

    force_clone : False
        Force git to clone into pre-existing directories (deletes contents)

    force : False
        .. deprecated:: 2015.8.0
            Use ``force_clone`` instead. For earlier Salt versions, ``force``
            must be used.

    force_checkout : False
        Force a checkout even if there might be overwritten changes

    force_reset : False
        Force a hard-reset to the remote ref, if necessary

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
        .. deprecated:: 2015.8.0
            Use ``remote`` instead. For earlier Salt versions, ``remote_name``
            must be used.

    always_fetch : False
        It ``False``, then if the local checkout has an upstream tracking
        branch, and the tracking branch will not be changed by this state, a
        fetch will not be performed. Set to ``True`` to force a fetch in this
        instance.

        .. versionchanged:: 2015.8.0
            In addition to the above condition, a fetch will also not be
            performed if the local checkout already has an up-to-date version
            of ``rev``.

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

    if force is not None:
        salt.utils.warn_until(
            'Nitrogen',
            'The \'force\' argument to the git.latest state has been '
            'deprecated, please use \'force_clone\' instead.'
        )
        force_clone = force

    if not remote:
        return _fail(ret, '\'remote\' option is required')

    if not target:
        return _fail(ret, '\'target\' option is required')

    if branch is None:
        branch = rev

    # Ensure that certain arguments are strings to ensure that comparisons work
    if rev is not None and not isinstance(rev, six.string_types):
        rev = str(rev)
    if target is not None and not isinstance(target, six.string_types):
        target = str(target)
    if branch is not None and not isinstance(branch, six.string_types):
        branch = str(branch)
    if user is not None and not isinstance(user, six.string_types):
        user = str(user)
    if remote is not None and not isinstance(remote, six.string_types):
        remote = str(remote)
    if identity is not None and not isinstance(identity, six.string_types):
        identity = str(identity)
    if https_user is not None and not isinstance(https_user, six.string_types):
        https_user = str(https_user)
    if https_pass is not None and not isinstance(https_pass, six.string_types):
        https_pass = str(https_pass)

    # Force these arguments to be absolute paths
    locals_ = locals()
    for param in ('target', 'identity'):
        if locals_[param] is not None and not os.path.isabs(locals_[param]):
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

    log.info('Checking remote revision for {0}'.format(name))
    remote_rev_matches = __salt__['git.ls_remote'](
        None,
        remote=name,
        ref='HEAD' if rev is None else rev,
        user=user,
        identity=identity,
        https_user=https_user,
        https_pass=https_pass)

    if bare:
        remote_rev = None
    else:
        if remote_rev_matches:
            ref_name = 'refs/heads/' + rev
            if 'refs/heads/' + rev in remote_rev_matches:
                remote_rev = remote_rev_matches['refs/heads/' + rev]
                desired_upstream = '/'.join((remote, rev))
                remote_rev_type = 'branch'
            elif 'refs/tags/' + rev in remote_rev_matches:
                remote_rev = remote_rev_matches['refs/tags/' + rev]
                desired_upstream = False
                remote_rev_type = 'tag'
        else:
            if len(rev) <= 40 \
                    and all(x in string.hexdigits for x in rev):
                # git ls-remote did not find the rev, and because it's a
                # hex string <= 40 chars we're going to assume that the
                # desired rev is a SHA1
                remote_rev = rev
                desired_upstream = False
                remote_rev_type = 'sha1'
            else:
                remote_rev = None

    if rev and remote_rev is None:
        # A specific rev is desired, but that rev doesn't exist on the
        # remote repo.
        return _fail(
            ret,
            'No revision matching \'{0}\' exists in the remote '
            'repository'.format(rev)
        )

    check = 'refs' if bare else '.git'
    gitdir = os.path.join(target, check)
    comments = []
    if os.path.isdir(gitdir) or __salt__['git.is_worktree'](target):
        # Target directory is a git repository or git worktree
        try:
            all_local_branches = __salt__['git.list_branches'](
                target, user=user)
            has_local_branch = local_branch in all_local_branches
            all_local_tags = __salt__['git.list_tags'](target, user=user)
            local_rev, local_branch = _get_local_rev_and_branch(target, user)

            if local_rev is not None and remote_rev is None:
                return _fail(
                    ret,
                    'Remote repository is empty, cannot update from {0} to an '
                    'empty repository'.format(local_rev[:7])
                )

            remotes = __salt__['git.remotes'](target, user=user)
            if remote not in remotes \
                    or local_rev not in [x for x in (rev, remote_rev)
                                         if x is not None]:
                # One of the following is true:
                #
                # 1) The remote is not present in the local checkout
                # 2) HEAD in the local checkout does not match the the desired
                #    remote revision
                #
                # We need to make changes.

                has_remote_rev = False
                if remote_rev is not None:
                    try:
                        resolved_remote_rev = __salt__['git.rev_parse'](
                            target,
                            remote_rev + '^{commit}',
                            ignore_retcode=True)
                        has_remote_rev = True
                    except CommandExecutionError:
                        # Local checkout doesn't have the remote_rev
                        pass
                    else:
                        if remote_rev_type == 'tag':
                            # The object might exist enough to get a rev-parse
                            # to work, while the local ref could have been
                            # deleted. Do some further sanity checks to
                            # determine if we really do have the remote_rev
                            if rev not in all_local_tags:
                                # Local tag doesn't exist, we'll need to fetch
                                has_remote_rev = False
                            else:
                                try:
                                    local_tag_sha1 = __salt__['git.rev_parse'](
                                        target,
                                        rev,
                                        ignore_retcode=True)
                                except CommandExecutionError:
                                    # Shouldn't happen if the tag exists
                                    # locally but account for this just in
                                    # case.
                                    local_tag_sha1 = None
                                if local_tag_sha1 != remote_rev \
                                        and fast_forward is False:
                                    # Remote tag is different than local tag,
                                    # unless we're doing a hard reset then we
                                    # don't need to proceed as we know that the
                                    # fetch will update the tag and the only
                                    # way to make the state succeed is to reset
                                    # the branch to point at the tag's new rev
                                    return _fail(
                                        ret,
                                        '\'{0}\' is a tag, but the remote '
                                        'SHA1 for this tag ({1}) doesn\'t '
                                        'match the local SHA1 ({2}). Set '
                                        '\'force_reset\' to True to force '
                                        'this update.'.format(
                                            rev,
                                            remote_rev[:7],
                                            local_tag_sha1[:7] if
                                                local_tag_sha1 is not None
                                                else None
                                        )
                                    )

                pre_rev = None
                if not has_remote_rev or not has_local_branch:
                    # Either the remote rev could not be found with git
                    # ls-remote (in which case we won't know more until
                    # fetching) or we're going to be checking out a new branch
                    # and don't have to worry about fast-forwarding.
                    fast_forward = None
                else:
                    if branch == local_branch:
                        pre_rev = local_rev
                    else:
                        try:
                            pre_rev = __salt__['git.rev_parse'](
                                target,
                                remote_rev + '^{commit}',
                                ignore_retcode=True)
                        except CommandExecutionError:
                            pre_rev = None

                    if pre_rev is None:
                        # If we're here, the remote_rev doesn't exist in the
                        # local checkout, so we don't know yet whether or not
                        # we can fast-forward and we need a fetch to know for
                        # sure.
                        fast_forward = None
                    else:
                        fast_forward = __salt__['git.merge_base'](
                            target,
                            refs=[pre_rev, remote_rev],
                            is_ancestor=True,
                            user=user)

                if fast_forward is False:
                    if not force_reset:
                        return _not_fast_forward(
                            ret,
                            pre_rev,
                            remote_rev,
                            branch,
                            local_branch,
                            comments)
                    merge_action = 'hard-reset'
                elif fast_forward is True:
                    merge_action = 'fast-forwarded'
                else:
                    merge_action = None

                # If always_fetch is set to True, then we definitely need to
                # fetch. Otherwise, we'll rely on the logic below to turn on
                # fetch_needed if a fetch is required.
                fetch_needed = always_fetch

                if local_branch is None:
                    # No local branch, no upstream tracking branch
                    upstream = None
                else:
                    try:
                        upstream = __salt__['git.rev_parse'](
                            target,
                            local_branch + '@{upstream}',
                            opts=['--abbrev-ref'],
                            user=user)
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
                        'Remote \'{0}\' not found in git checkout at {1}'
                        .format(remote, target)
                    )
                    fetch_url = None

                if name != fetch_url:
                    if __opts__['test']:
                        ret['changes']['remotes/{0}'.format(remote)] = {
                            'old': fetch_url,
                            'new': name
                        }
                        actions = [
                            'Remote \'{0}\' would be set to {1}'.format(
                                remote,
                                name
                            )
                        ]
                        actions.append('Remote would be fetched')
                        if has_remote_rev:
                            # Even though we are fetching since we are
                            # modifying the remote, since we know we have the
                            # remove rev already, we can report on what the
                            # changes would be.
                            if local_rev != remote_rev:
                                ret['changes']['revision'] = {
                                    'old': local_rev, 'new': remote_rev
                                }
                            if fast_forward is False:
                                ret['changes']['forced update'] = True
                            actions.append(
                                'Repository would be {0} to {1}'.format(
                                    merge_action,
                                    remote_rev[:7]
                                )
                            )
                        else:
                            actions.append(
                                'Repository may be updated depending on '
                                'outcome of fetch'
                            )
                        return _neutral_test(ret, _format_comments(actions))

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
                    comments.append(
                        'Remote \'{0}\' set to {1}'.format(remote, name)
                    )
                    # We need to fetch since the remote was just set and we
                    # need to grab all its refs.
                    fetch_needed = True

                if rev:
                    if not has_remote_rev:
                        fetch_needed = True

                    if __opts__['test']:
                        ret['changes']['revision'] = {
                            'old': local_rev, 'new': remote_rev
                        }
                        actions = []
                        if fetch_needed:
                            actions.append(
                                'Remote \'{0}\' would be fetched'
                                .format(remote)
                            )
                        if branch != local_branch:
                            ret['changes']['local branch'] = {
                                'old': local_branch, 'new': branch
                            }
                            if not has_local_branch:
                                actions.append(
                                    'New branch \'{0}\' would be checked out, '
                                    'with {1} ({2}) as a starting point'
                                    .format(
                                        branch,
                                        desired_upstream if desired_upstream
                                            else rev,
                                        remote_rev)
                                )
                                if desired_upstream:
                                    actions.append(
                                        'Upstream tracking branch would be '
                                        'set to {0}'.format(desired_upstream)
                                    )
                            else:
                                ret['changes']['hard reset'] = True
                                actions.append(
                                    'Branch \'{0}\' would be checked out and '
                                    '{1} to {2}'.format(
                                        branch,
                                        merge_action,
                                        remote_rev
                                    )
                                )
                        else:
                            msg = (
                                'Repository would be {0} from {1} to {2}'
                                .format(
                                    'hard-reset'
                                        if force_reset and has_remote_rev
                                        else 'updated',
                                    local_rev[:7],
                                    remote_rev[:7]
                                )
                            )
                            if force_reset:
                                # We don't want to put these two if statements
                                # onto a single line because it will result in
                                # inaccurate comments. Don't do this.
                                if not has_remote_rev:
                                    msg += (
                                        ', and would be hard-reset if the '
                                        'update is not a fast-forward'
                                    )
                            else:
                                msg += (
                                    ', but this update would not be made (and '
                                    'the state will fail) if it is not a '
                                    'fast-forward'
                                )
                            actions.append(msg)

                        # Check if upstream needs changing
                        upstream_changed = False
                        if not upstream and desired_upstream:
                            upstream_changed = True
                            actions.append(
                                'Upstream tracking branch would be set to {0}'
                                .format(desired_upstream)
                            )
                        elif upstream and not desired_upstream:
                            upstream_changed = True
                            actions.append(
                                'Upstream tracking branch would be unset'
                            )
                        elif upstream != desired_upstream:
                            upstream_changed = True
                            actions.append(
                                'Upstream tracking branch would be updated to '
                                '{0}'.format(desired_upstream)
                            )
                        if upstream_changed:
                            ret['changes']['upstream'] = {
                                'old': upstream,
                                'new': desired_upstream
                            }
                        return _neutral_test(ret, _format_comments(actions))

                    if not upstream and desired_upstream:
                        upstream_action = (
                            'Upstream tracking branch was set to {0}'
                            .format(desired_upstream)
                        )
                        branch_opts = ['--set-upstream-to', desired_upstream]
                    elif upstream and not desired_upstream:
                        upstream_action = 'Upstream tracking branch was unset'
                        branch_opts = ['--unset-upstream']
                    elif upstream != desired_upstream:
                        upstream_action = (
                            'Upstream tracking branch was updated to {0}'
                            .format(desired_upstream)
                        )
                        branch_opts = ['--set-upstream-to', desired_upstream]
                        fetch_needed = True
                    else:
                        branch_opts = None

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

                    try:
                        __salt__['git.rev_parse'](
                            target,
                            remote_rev + '^{commit}',
                            ignore_retcode=True)
                    except CommandExecutionError as exc:
                        return _fail(
                            ret,
                            'Fetch did not successfully retrieve remote rev '
                            '{0}: {1}'.format(remote_rev[:7], exc)
                        )

                    # Now that we've fetched, check again whether or not the
                    # update is a fast-forward.
                    if not has_local_branch:
                        # We're checking out a new branch, so we don't even
                        # care about fast-forwarding
                        fast_forward = None
                    else:
                        if branch == local_branch:
                            pre_rev = local_rev
                        else:
                            try:
                                pre_rev = __salt__['git.rev_parse'](
                                    target,
                                    branch + '^{commit}',
                                    ignore_retcode=True)
                            except CommandExecutionError as exc:
                                # Shouldn't ever get here but gracefully fail
                                # if we do.
                                msg = (
                                    'Failed to find commit ID of local branch '
                                    '\'{0}\': {1}'.format(
                                        branch,
                                        _strip_exc(exc)
                                    )
                                )
                                return _fail(ret, msg, comments)

                        fast_forward = __salt__['git.merge_base'](
                            target,
                            refs=[pre_rev, remote_rev],
                            is_ancestor=True,
                            user=user)

                    if fast_forward is False and not force_reset:
                        return _not_fast_forward(
                            ret,
                            pre_rev,
                            remote_rev,
                            branch,
                            local_branch,
                            comments)

                    if branch != local_branch:
                        # TODO: Maybe re-retrieve all_local_branches to handle
                        # the corner case where the destination branch was
                        # added to the local checkout during a fetch that takes
                        # a long time to complete.
                        if not has_local_branch:
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
                                                 user=user)
                        ret['changes']['local branch'] = {
                            'old': local_branch, 'new': branch
                        }

                    if fast_forward is False:
                        reset_ref = desired_upstream \
                            if desired_upstream \
                            else rev
                        __salt__['git.reset'](
                            target,
                            opts=['--hard', reset_ref],
                            user=user
                        )
                        ret['changes']['forced update'] = True
                        comments.append(
                            'Repository was hard-reset to {0}'
                            .format(reset_ref)
                        )

                    if branch_opts is not None:
                        __salt__['git.branch'](
                            target,
                            branch,
                            opts=branch_opts,
                            user=user)
                        ret['changes']['upstream'] = {
                            'old': upstream,
                            'new': desired_upstream if desired_upstream
                                else None
                        }
                        comments.append(upstream_action)

                    if fast_forward is True and desired_upstream:
                        # Check first to see if we are on a branch before
                        # trying to merge changes. (The call to
                        # git.symbolic_ref will only return output if HEAD
                        # points to a branch.)
                        if __salt__['git.symbolic_ref'](
                                target,
                                'HEAD',
                                opts=['--quiet'],
                                ignore_retcode=True):
                            __salt__['git.merge'](
                                target,
                                opts=['--ff-only'],
                                user=user
                            )
                            comments.append('Repository was fast-forwarded')
                        else:
                            # Shouldn't ever happen but fail with a meaningful
                            # error message if it does.
                            msg = (
                                'Unable to merge {0}, HEAD is detached'
                                .format(desired_upstream)
                            )

                    # TODO: Figure out how to add submodule update info to
                    # test=True return data, and changes dict.
                    if submodules:
                        __salt__['git.submodule'](target,
                                                  'update',
                                                  opts=['--recursive'],
                                                  user=user,
                                                  identity=identity)
                elif bare:
                    if __opts__['test']:
                        return _neutral_test(
                            ret,
                            'Bare repository at {0} would be fetched'
                            .format(target)
                        )
                    output = __salt__['git.fetch'](
                        target,
                        remote=remote,
                        opts=fetch_opts,
                        user=user,
                        identity=identity)
                    fetch_changes = _parse_fetch(output)
                    if fetch_changes:
                        ret['changes']['fetch'] = fetch_changes
                    comments.append(
                        'Bare repository at {0} was fetched'.format(target)
                    )
                try:
                    new_rev = __salt__['git.revision'](
                        cwd=target,
                        user=user,
                        ignore_retcode=True)
                except CommandExecutionError:
                    new_rev = None

            else:
                # One of the following is true:
                #
                # 1) The desired revision is a branch/tag/SHA1 and its SHA1 hash
                #    matches the SHA1 of the local checkout's HEAD.
                # 2) No revision was specified, and SHA1 hash of the remote
                #    repository's HEAD matches that of the the local checkout's
                #    HEAD.
                #
                # In either case, no changes need to be made, so set new_rev to
                # the same value as local_rev and don't make any changes.
                new_rev = local_rev

        except Exception as exc:
            log.error(
                'Unexpected exception in git.latest state',
                exc_info=True
            )
            if isinstance(exc, CommandExecutionError):
                msg = _strip_exc(exc)
            else:
                msg = str(exc)
            return _fail(ret, msg, comments)

        if local_rev != new_rev:
            log.info(
                'Repository {0} updated: {1} => {2}'.format(
                    target, local_rev, new_rev)
            )
            ret['comment'] = _format_comments(comments)
            ret['changes']['revision'] = {'old': local_rev, 'new': new_rev}
        else:
            ret['comment'] = 'Repository {0} is up-to-date'.format(target)
    else:
        if os.path.isdir(target):
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
                    'Removing contents of {0} to clone repository {1} in its '
                    'place (force_clone=True set in git.latest state)'
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
                        'Unable to remove {0}: {1}'.format(target, exc),
                        comments
                    )
                else:
                    ret['changes']['forced clone'] = True
            # Clone is required, but target dir exists and is non-empty. We
            # can't proceed.
            elif os.listdir(target):
                return _fail(
                    ret,
                    'Target \'{0}\' exists, is non-empty and is not a git '
                    'repository. Set the \'force_clone\' option to True to '
                    'remove this directory\'s contents and proceed with '
                    'cloning the remote repository'.format(target)
                )

        log.debug(
            'Target {0} is not found, \'git clone\' is required'.format(target)
        )
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
                clone_opts.extend(['--depth', str(depth)])

            __salt__['git.clone'](target,
                                  name,
                                  user=user,
                                  opts=clone_opts,
                                  identity=identity,
                                  https_user=https_user,
                                  https_pass=https_pass)
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
                    msg = (
                        '{{0}} was cloned but is empty, so {0}/{1} '
                        'cannot be checked out'.format(remote, rev)
                    )
                    log.error(msg.format(name))
                    return _fail(ret, msg.format('Repository'), comments)
                else:
                    local_rev, local_branch = \
                        _get_local_rev_and_branch(target, user)
                    all_local_branches = __salt__['git.list_branches'](
                        target, user=user)
                    has_local_branch = local_branch in all_local_branches
                    if remote_rev_type == 'tag' \
                            and rev not in __salt__['git.list_tags'](
                                target, user=user):
                        return _fail(
                            ret,
                            'Revision \'{0}\' does not exist in clone'
                            .format(rev),
                            comments
                        )
                    if not has_local_branch:
                        checkout_rev = desired_upstream if desired_upstream \
                            else rev
                        checkout_opts = ['-b', branch]
                    else:
                        checkout_rev = branch
                        checkout_opts = []
                    __salt__['git.checkout'](target,
                                             checkout_rev,
                                             opts=checkout_opts,
                                             user=user)
                    ret['changes']['local branch'] = {
                        'old': None, 'new': branch
                    }
                    if desired_upstream:
                        ret['changes']['upstream'] = {
                            'old': None, 'new': desired_upstream
                        }

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
                msg = _strip_exc(exc)
            else:
                msg = str(exc)
            return _fail(ret, msg, comments)

        msg = _format_comments(comments)
        log.info(msg)
        ret['comment'] = msg
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


def config_unset(name,
                 value_regex=None,
                 repo=None,
                 user=None,
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
            will be deleted (this is the only way to delete mutliple values
            from a multivar). If ``all`` is set to ``False``, then this state
            will fail if the regex matches more than one value in a multivar.

    all : False
        If ``True``, unset all matches

    repo : None
        An optional location of a git repository for local operations

    user : None
        Optional name of a user as whom `git config` will be run

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
    kwargs = salt.utils.clean_kwargs(**kwargs)
    global_ = kwargs.pop('global', False)
    all_ = kwargs.pop('all', False)
    if kwargs:
        return _fail(
            ret,
            salt.utils.invalid_kwargs(kwargs, raise_exc=False)
        )

    if not global_ and not repo:
        return _fail(
            ret,
            'Non-global config options require the \'repo\' argument to be '
            'set'
        )

    if not isinstance(name, six.string_types):
        name = str(name)
    if value_regex is not None:
        if not isinstance(value_regex, six.string_types):
            value_regex = str(value_regex)

    # Ensure that the key regex matches the full key name
    key = '^' + name.lstrip('^').rstrip('$') + '$'

    # Get matching keys/values
    pre_matches = __salt__['git.config_get_regexp'](
        cwd='global' if global_ else repo,
        key=key,
        value_regex=value_regex,
        user=user,
        ignore_retcode=True
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
            cwd='global' if global_ else repo,
            key=key,
            value_regex=None,
            user=user,
            ignore_retcode=True
        )

    failed = []
    # Unset the specified value(s). There is no unset for regexes so loop
    # through the pre_matches dict and unset each matching key individually.
    for key_name in pre_matches:
        try:
            __salt__['git.config_unset'](
                cwd='global' if global_ else repo,
                key=name,
                value_regex=value_regex,
                all=all_,
                user=user
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
        cwd='global' if global_ else repo,
        key=key,
        value_regex=None,
        user=user,
        ignore_retcode=True
    )

    for key_name, values in six.iteritems(pre):
        if key_name not in post:
            ret['changes'][key_name] = pre[key_name]
        unset = [x for x in pre[key_name] if x not in post[key_name]]
        if unset:
            ret['changes'][key_name] = unset

    if value_regex is None:
        post_matches = post
    else:
        post_matches = __salt__['git.config_get_regexp'](
            cwd='global' if global_ else repo,
            key=key,
            value_regex=value_regex,
            user=user,
            ignore_retcode=True
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
               cwd=None,
               value=None,
               multivar=None,
               repo=None,
               user=None,
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

    repo : None
        An optional location of a git repository for local operations

    user : None
        Optional name of a user as whom `git config` will be run

    global : False
        If ``True``, this will set a global git config option

        .. versionchanged:: 2015.8.0
            Option renamed from ``is_global`` to ``global``. For earlier
            versions, use ``is_global``.


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
    kwargs = salt.utils.clean_kwargs(**kwargs)
    global_ = kwargs.pop('global', False)
    is_global = kwargs.pop('is_global', False)
    if kwargs:
        return _fail(
            ret,
            salt.utils.invalid_kwargs(kwargs, raise_exc=False)
        )

    if is_global:
        salt.utils.warn_until(
            'Nitrogen',
            'The \'is_global\' argument to the git.config_set state has been '
            'deprecated, please use \'global\' instead.'
        )
        global_ = is_global

    if not global_ and not repo:
        return _fail(
            ret,
            'Non-global config options require the \'repo\' argument to be '
            'set'
        )

    if not isinstance(name, six.string_types):
        name = str(name)
    if value is not None:
        if not isinstance(value, six.string_types):
            value = str(value)
        value_comment = '\'' + value + '\''
        desired = [value]
    if multivar is not None:
        if not isinstance(multivar, list):
            try:
                multivar = multivar.split(',')
            except AttributeError:
                multivar = str(multivar).split(',')
        else:
            new_multivar = []
            for item in multivar:
                if isinstance(item, six.string_types):
                    new_multivar.append(item)
                else:
                    new_multivar.append(str(item))
            multivar = new_multivar
        value_comment = multivar
        desired = multivar

    # Get current value
    pre = __salt__['git.config_get'](
        cwd='global' if global_ else repo,
        key=name,
        all=True,
        user=user,
        ignore_retcode=True
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
        __salt__['git.config_set'](
            cwd='global' if global_ else repo,
            key=name,
            value=value,
            multivar=multivar,
            user=user
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

    # Check value to make sure that it now matches the value we set
    post = __salt__['git.config_get'](
        cwd='global' if global_ else repo,
        key=name,
        all=True,
        user=user,
        ignore_retcode=True
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


def config(name, value=None, multivar=None, repo=None, user=None, **kwargs):
    '''
    Pass through to git.config_set and display a deprecation warning
    '''
    salt.utils.warn_until(
        'Nitrogen',
        'The \'git.config\' state has been renamed to \'git.config_set\', '
        'please update your SLS files'
    )
    return config_set(name=name,
                      value=value,
                      multivar=multivar,
                      repo=repo,
                      user=user,
                      **kwargs)


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
