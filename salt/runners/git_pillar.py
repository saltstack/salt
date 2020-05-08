# -*- coding: utf-8 -*-
"""
Runner module to directly manage the git external pillar
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import logging

# Import salt libs
import salt.pillar.git_pillar
import salt.utils.gitfs
from salt.exceptions import SaltRunnerError

log = logging.getLogger(__name__)


def update(branch=None, repo=None):
    """
    .. versionadded:: 2014.1.0

    .. versionchanged:: 2015.8.4
        This runner function now supports the :ref:`git_pillar
        configuration schema <git-pillar-configuration>` introduced in
        2015.8.0. Additionally, the branch and repo can now be omitted to
        update all git_pillar remotes. The return data has also changed to
        a dictionary. The values will be ``True`` only if new commits were
        fetched, and ``False`` if there were errors or no new commits were
        fetched.

    .. versionchanged:: 2018.3.0
        The return for a given git_pillar remote will now be ``None`` when no
        changes were fetched. ``False`` now is reserved only for instances in
        which there were errors.

    Fetch one or all configured git_pillar remotes.

    .. note::
        This will *not* fast-forward the git_pillar cachedir on the master. All
        it does is perform a ``git fetch``. If this runner is executed with
        ``-l debug``, you may see a log message that says that the repo is
        up-to-date. Keep in mind that Salt automatically fetches git_pillar
        repos roughly every 60 seconds (or whatever
        :conf_master:`loop_interval` is set to). So, it is possible that the
        repo was fetched automatically in the time between when changes were
        pushed to the repo, and when this runner was executed. When in doubt,
        simply refresh pillar data using :py:func:`saltutil.refresh_pillar
        <salt.modules.saltutil.refresh_pillar>` and then use
        :py:func:`pillar.item <salt.modules.pillar.item>` to check if the
        pillar data has changed as expected.

    CLI Example:

    .. code-block:: bash

        # Update specific branch and repo
        salt-run git_pillar.update branch='branch' repo='https://foo.com/bar.git'
        # Update all repos
        salt-run git_pillar.update
        # Run with debug logging
        salt-run git_pillar.update -l debug
    """
    ret = {}
    for ext_pillar in __opts__.get("ext_pillar", []):
        pillar_type = next(iter(ext_pillar))
        if pillar_type != "git":
            continue
        pillar_conf = ext_pillar[pillar_type]
        pillar = salt.utils.gitfs.GitPillar(
            __opts__,
            pillar_conf,
            per_remote_overrides=salt.pillar.git_pillar.PER_REMOTE_OVERRIDES,
            per_remote_only=salt.pillar.git_pillar.PER_REMOTE_ONLY,
            global_only=salt.pillar.git_pillar.GLOBAL_ONLY,
        )
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
            except Exception as exc:  # pylint: disable=broad-except
                log.error(
                    "Exception '%s' caught while fetching git_pillar " "remote '%s'",
                    exc,
                    remote.id,
                    exc_info_on_loglevel=logging.DEBUG,
                )
                result = False
            finally:
                remote.clear_lock()
            ret[remote.id] = result

    if not ret:
        if branch is not None or repo is not None:
            raise SaltRunnerError(
                "Specified git branch/repo not found in ext_pillar config"
            )
        else:
            raise SaltRunnerError("No git_pillar remotes are configured")

    return ret
