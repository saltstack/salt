# -*- coding: utf-8 -*-
'''
Runner module to directly manage the git external pillar
'''
from __future__ import absolute_import

# Import python libs
import logging

# Import salt libs
import salt.pillar.git_pillar
import salt.utils.gitfs
from salt.exceptions import SaltRunnerError
from salt.ext import six

log = logging.getLogger(__name__)


def update(branch=None, repo=None):
    '''
    .. versionadded:: 2014.1.0

    .. versionchanged:: 2015.8.4
        This runner function now supports the :ref:`new git_pillar
        configuration schema <git-pillar-2015-8-0-and-later>` introduced in
        2015.8.0. Additionally, the branch and repo can now be omitted to
        update all git_pillar remotes. The return data has also changed. For
        releases 2015.8.3 and earlier, there is no value returned. Starting
        with 2015.8.4, the return data is a dictionary. If using the :ref:`old
        git_pillar configuration schema <git-pillar-pre-2015-8-0>`, then the
        dictionary values will be ``True`` if the update completed without
        error, and ``False`` if an error occurred. If using the :ref:`new
        git_pillar configuration schema <git-pillar-2015-8-0-and-later>`, the
        values will be ``True`` only if new commits were fetched, and ``False``
        if there were errors or no new commits were fetched.

    Update one or all configured git_pillar remotes.

    CLI Example:

    .. code-block:: bash

        # Update specific branch and repo
        salt-run git_pillar.update branch='branch' repo='https://foo.com/bar.git'
        # Update all repos (2015.8.4 and later)
        salt-run git_pillar.update
        # Run with debug logging
        salt-run git_pillar.update -l debug
    '''
    ret = {}
    for ext_pillar in __opts__.get('ext_pillar', []):
        pillar_type = next(iter(ext_pillar))
        if pillar_type != 'git':
            continue
        pillar_conf = ext_pillar[pillar_type]
        if isinstance(pillar_conf, six.string_types):
            parts = pillar_conf.split()
            if len(parts) >= 2:
                desired_branch, desired_repo = parts[:2]
                # Skip this remote if it doesn't match the search criteria
                if branch is not None:
                    if branch != desired_branch:
                        continue
                if repo is not None:
                    if repo != desired_repo:
                        continue
                ret[pillar_conf] = salt.pillar.git_pillar._LegacyGitPillar(
                    parts[0],
                    parts[1],
                    __opts__).update()

        else:
            pillar = salt.utils.gitfs.GitPillar(__opts__)
            pillar.init_remotes(pillar_conf,
                                salt.pillar.git_pillar.PER_REMOTE_OVERRIDES)
            for remote in pillar.remotes:
                # Skip this remote if it doesn't match the search criteria
                if branch is not None:
                    if branch != remote.branch:
                        continue
                if repo is not None:
                    if repo != remote.url:
                        continue
                try:
                    result = remote.fetch()
                except Exception as exc:
                    log.error(
                        'Exception \'{0}\' caught while fetching git_pillar '
                        'remote \'{1}\''.format(exc, remote.id),
                        exc_info_on_loglevel=logging.DEBUG
                    )
                    result = False
                finally:
                    remote.clear_lock()
                ret[remote.id] = result

    if not ret:
        if branch is not None or repo is not None:
            raise SaltRunnerError(
                'Specified git branch/repo not found in ext_pillar config'
            )
        else:
            raise SaltRunnerError('No git_pillar remotes are configured')

    return ret
