# -*- coding: utf-8 -*-
"""
Runner to manage Windows software repo
"""

# WARNING: Any modules imported here must also be added to
# salt/modules/win_repo.py

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import os

import salt.loader
import salt.minion
import salt.template
import salt.utils.files
import salt.utils.gitfs
import salt.utils.msgpack
import salt.utils.path

# Import salt libs
from salt.exceptions import CommandExecutionError, SaltRenderError

# Import third party libs
from salt.ext import six

log = logging.getLogger(__name__)

# Global parameters which can be overridden on a per-remote basis
PER_REMOTE_OVERRIDES = ("ssl_verify", "refspecs")

# Fall back to default per-remote-only. This isn't technically needed since
# salt.utils.gitfs.GitBase.__init__ will default to
# salt.utils.gitfs.PER_REMOTE_ONLY for this value, so this is mainly for
# runners and other modules that import salt.runners.winrepo.
PER_REMOTE_ONLY = salt.utils.gitfs.PER_REMOTE_ONLY
GLOBAL_ONLY = ("branch",)


def genrepo(opts=None, fire_event=True):
    """
    Generate winrepo_cachefile based on sls files in the winrepo_dir

    opts
        Specify an alternate opts dict. Should not be used unless this function
        is imported into an execution module.

    fire_event : True
        Fire an event on failure. Only supported on the master.

    CLI Example:

    .. code-block:: bash

        salt-run winrepo.genrepo
    """
    if opts is None:
        opts = __opts__

    winrepo_dir = opts["winrepo_dir"]
    winrepo_cachefile = opts["winrepo_cachefile"]

    ret = {}
    if not os.path.exists(winrepo_dir):
        os.makedirs(winrepo_dir)
    renderers = salt.loader.render(opts, __salt__)
    for root, _, files in salt.utils.path.os_walk(winrepo_dir):
        for name in files:
            if name.endswith(".sls"):
                try:
                    config = salt.template.compile_template(
                        os.path.join(root, name),
                        renderers,
                        opts["renderer"],
                        opts["renderer_blacklist"],
                        opts["renderer_whitelist"],
                    )
                except SaltRenderError as exc:
                    log.debug("Failed to render %s.", os.path.join(root, name))
                    log.debug("Error: %s.", exc)
                    continue
                if config:
                    revmap = {}
                    for pkgname, versions in six.iteritems(config):
                        log.debug("Compiling winrepo data for package '%s'", pkgname)
                        for version, repodata in six.iteritems(versions):
                            log.debug(
                                "Compiling winrepo data for %s version %s",
                                pkgname,
                                version,
                            )
                            if not isinstance(version, six.string_types):
                                config[pkgname][six.text_type(version)] = config[
                                    pkgname
                                ].pop(version)
                            if not isinstance(repodata, dict):
                                msg = "Failed to compile {0}.".format(
                                    os.path.join(root, name)
                                )
                                log.debug(msg)
                                if fire_event:
                                    try:
                                        __jid_event__.fire_event(
                                            {"error": msg}, "progress"
                                        )
                                    except NameError:
                                        log.error(
                                            "Attempted to fire the an event "
                                            "with the following error, but "
                                            "event firing is not supported: %s",
                                            msg,
                                        )
                                continue
                            revmap[repodata["full_name"]] = pkgname
                    ret.setdefault("repo", {}).update(config)
                    ret.setdefault("name_map", {}).update(revmap)
    with salt.utils.files.fopen(
        os.path.join(winrepo_dir, winrepo_cachefile), "w+b"
    ) as repo:
        repo.write(salt.utils.msgpack.dumps(ret))
    return ret


def update_git_repos(opts=None, clean=False, masterless=False):
    """
    Checkout git repos containing Windows Software Package Definitions

    opts
        Specify an alternate opts dict. Should not be used unless this function
        is imported into an execution module.

    clean : False
        Clean repo cachedirs which are not configured under
        :conf_master:`winrepo_remotes`.

        .. warning::
            This argument should not be set to ``True`` if a mix of git and
            non-git repo definitions are being used, as it will result in the
            non-git repo definitions being removed.

        .. versionadded:: 2015.8.0

    CLI Examples:

    .. code-block:: bash

        salt-run winrepo.update_git_repos
        salt-run winrepo.update_git_repos clean=True
    """
    if opts is None:
        opts = __opts__

    winrepo_dir = opts["winrepo_dir"]
    winrepo_remotes = opts["winrepo_remotes"]

    winrepo_cfg = [
        (winrepo_remotes, winrepo_dir),
        (opts["winrepo_remotes_ng"], opts["winrepo_dir_ng"]),
    ]

    ret = {}
    for remotes, base_dir in winrepo_cfg:
        if not any(
            (salt.utils.gitfs.GITPYTHON_VERSION, salt.utils.gitfs.PYGIT2_VERSION)
        ):
            # Use legacy code
            winrepo_result = {}
            for remote_info in remotes:
                if "/" in remote_info:
                    targetname = remote_info.split("/")[-1]
                else:
                    targetname = remote_info
                rev = "HEAD"
                # If a revision is specified, use it.
                try:
                    rev, remote_url = remote_info.strip().split()
                except ValueError:
                    remote_url = remote_info
                gittarget = os.path.join(base_dir, targetname).replace(".", "_")
                if masterless:
                    result = __salt__["state.single"](
                        "git.latest",
                        name=remote_url,
                        rev=rev,
                        branch="winrepo",
                        target=gittarget,
                        force_checkout=True,
                        force_reset=True,
                    )
                    if isinstance(result, list):
                        # Errors were detected
                        raise CommandExecutionError(
                            "Failed up update winrepo remotes: {0}".format(
                                "\n".join(result)
                            )
                        )
                    if "name" not in result:
                        # Highstate output dict, the results are actually nested
                        # one level down.
                        key = next(iter(result))
                        result = result[key]
                else:
                    mminion = salt.minion.MasterMinion(opts)
                    result = mminion.states["git.latest"](
                        remote_url,
                        rev=rev,
                        branch="winrepo",
                        target=gittarget,
                        force_checkout=True,
                        force_reset=True,
                    )
                winrepo_result[result["name"]] = result["result"]
            ret.update(winrepo_result)
        else:
            # New winrepo code utilizing salt.utils.gitfs
            try:
                winrepo = salt.utils.gitfs.WinRepo(
                    opts,
                    remotes,
                    per_remote_overrides=PER_REMOTE_OVERRIDES,
                    per_remote_only=PER_REMOTE_ONLY,
                    global_only=GLOBAL_ONLY,
                    cache_root=base_dir,
                )
                winrepo.fetch_remotes()
                # Since we're not running update(), we need to manually call
                # clear_old_remotes() to remove directories from remotes that
                # have been removed from configuration.
                if clean:
                    winrepo.clear_old_remotes()
                winrepo.checkout()
            except Exception as exc:  # pylint: disable=broad-except
                msg = "Failed to update winrepo_remotes: {0}".format(exc)
                log.error(msg, exc_info_on_loglevel=logging.DEBUG)
                return msg
            ret.update(winrepo.winrepo_dirs)
    return ret
