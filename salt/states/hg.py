"""
Interaction with Mercurial repositories
=======================================

Before using hg over ssh, make sure the remote host fingerprint already exists
in ~/.ssh/known_hosts, and the remote host has this host's public key.

.. code-block:: yaml

    https://bitbucket.org/example_user/example_repo:
        hg.latest:
          - rev: tip
          - target: /tmp/example_repo
"""

import logging
import os
import shutil

import salt.utils.platform
from salt.exceptions import CommandExecutionError
from salt.states.git import _fail, _neutral_test

log = logging.getLogger(__name__)

HG_BINARY = "hg.exe" if salt.utils.platform.is_windows() else "hg"


def __virtual__():
    """
    Only load if hg is available
    """
    if __salt__["cmd.has_exec"](HG_BINARY):
        return True
    return (False, f"Command {HG_BINARY} not found")


def latest(
    name,
    rev=None,
    target=None,
    clean=False,
    user=None,
    identity=None,
    force=False,
    opts=False,
    update_head=True,
):
    """
    Make sure the repository is cloned to the given directory and is up to date

    name
        Address of the remote repository as passed to "hg clone"

    rev
        The remote branch, tag, or revision hash to clone/pull

    target
        Target destination directory path on minion to clone into

    clean
        Force a clean update with -C (Default: False)

    user
        Name of the user performing repository management operations

        .. versionadded:: 0.17.0

    identity
        Private SSH key on the minion server for authentication (ssh://)

        .. versionadded:: 2015.5.0

    force
        Force hg to clone into pre-existing directories (deletes contents)

    opts
        Include additional arguments and options to the hg command line

    update_head
        Should we update the head if new changes are found? Defaults to True

        .. versionadded:: 2017.7.0

    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    if not target:
        return _fail(ret, '"target option is required')

    is_repository = os.path.isdir(target) and os.path.isdir(f"{target}/.hg")

    if is_repository:
        ret = _update_repo(
            ret, name, target, clean, user, identity, rev, opts, update_head
        )
    else:
        if os.path.isdir(target):
            fail = _handle_existing(ret, target, force)
            if fail is not None:
                return fail
        else:
            log.debug('target %s is not found, "hg clone" is required', target)
        if __opts__["test"]:
            return _neutral_test(
                ret, f"Repository {name} is about to be cloned to {target}"
            )
        _clone_repo(ret, target, name, user, identity, rev, opts)
    return ret


def _update_repo(ret, name, target, clean, user, identity, rev, opts, update_head):
    """
    Update the repo to a given revision. Using clean passes -C to the hg up
    """
    log.debug('target %s is found, "hg pull && hg up is probably required"', target)

    current_rev = __salt__["hg.revision"](target, user=user, rev=".")
    if not current_rev:
        return _fail(ret, f"Seems that {target} is not a valid hg repo")

    if __opts__["test"]:
        return _neutral_test(
            ret,
            "Repository {} update is probably required (current revision is {})".format(
                target, current_rev
            ),
        )

    try:
        pull_out = __salt__["hg.pull"](
            target, user=user, identity=identity, opts=opts, repository=name
        )
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = err
        return ret

    if update_head is False:
        changes = "no changes found" not in pull_out
        if changes:
            ret["comment"] = (
                "Update is probably required but update_head=False so we will skip"
                " updating."
            )
        else:
            ret["comment"] = (
                "No changes found and update_head=False so will skip updating."
            )
        return ret

    if rev:
        try:
            __salt__["hg.update"](target, rev, force=clean, user=user)
        except CommandExecutionError as err:
            ret["result"] = False
            ret["comment"] = err
            return ret
    else:
        try:
            __salt__["hg.update"](target, "tip", force=clean, user=user)
        except CommandExecutionError as err:
            ret["result"] = False
            ret["comment"] = err
            return ret

    new_rev = __salt__["hg.revision"](cwd=target, user=user, rev=".")

    if current_rev != new_rev:
        revision_text = f"{current_rev} => {new_rev}"
        log.info("Repository %s updated: %s", target, revision_text)
        ret["comment"] = f"Repository {target} updated."
        ret["changes"]["revision"] = revision_text
    elif "error:" in pull_out:
        return _fail(ret, f"An error was thrown by hg:\n{pull_out}")
    return ret


def _handle_existing(ret, target, force):
    not_empty = os.listdir(target)
    if not not_empty:
        log.debug(
            "target %s found, but directory is empty, automatically deleting", target
        )
        shutil.rmtree(target)
    elif force:
        log.debug(
            "target %s found and is not empty. "
            "Since force option is in use, deleting anyway.",
            target,
        )
        shutil.rmtree(target)
    else:
        return _fail(ret, "Directory exists, and is not empty")


def _clone_repo(ret, target, name, user, identity, rev, opts):
    try:
        result = __salt__["hg.clone"](
            target, name, user=user, identity=identity, opts=opts
        )
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = err
        return ret

    if not os.path.isdir(target):
        return _fail(ret, result)

    if rev:
        try:
            __salt__["hg.update"](target, rev, user=user)
        except CommandExecutionError as err:
            ret["result"] = False
            ret["comment"] = err
            return ret

    new_rev = __salt__["hg.revision"](cwd=target, user=user)
    message = f"Repository {name} cloned to {target}"
    log.info(message)
    ret["comment"] = message

    ret["changes"]["new"] = name
    ret["changes"]["revision"] = new_rev

    return ret
