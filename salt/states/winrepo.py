"""
Manage Windows Package Repository
"""

import itertools

# Python Libs
import os
import stat

import salt.config

# Salt Modules
import salt.runner
import salt.syspaths
import salt.utils.path


def __virtual__():
    return "winrepo"


def genrepo(name, force=False, allow_empty=False):
    """
    Refresh the winrepo.p file of the repository (salt-run winrepo.genrepo)

    If ``force`` is ``True`` no checks will be made and the repository will be
    generated if ``allow_empty`` is ``True`` then the state will not return an
    error if there are 0 packages,

    .. note::

        This state only loads on minions that have the ``roles: salt-master``
        grain set.

    Example:

    .. code-block:: yaml

        winrepo:
          winrepo.genrepo
    """

    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    master_config = salt.config.master_config(
        os.path.join(salt.syspaths.CONFIG_DIR, "master")
    )

    winrepo_dir = master_config["winrepo_dir"]
    winrepo_cachefile = master_config["winrepo_cachefile"]

    # We're actually looking for the full path to the cachefile here, so
    # prepend the winrepo_dir
    winrepo_cachefile = os.path.join(winrepo_dir, winrepo_cachefile)

    # Check if the winrepo directory exists
    # if not search for a file with a newer mtime than the winrepo_cachefile file
    execute = False
    if not force:
        if not os.path.exists(winrepo_dir):
            ret["result"] = False
            ret["comment"] = "{} is missing".format(winrepo_dir)
            return ret
        elif not os.path.exists(winrepo_cachefile):
            execute = True
            ret["comment"] = "{} is missing".format(winrepo_cachefile)
        else:
            winrepo_cachefile_mtime = os.stat(winrepo_cachefile)[stat.ST_MTIME]
            for root, dirs, files in salt.utils.path.os_walk(winrepo_dir):
                for name in itertools.chain(files, dirs):
                    full_path = os.path.join(root, name)
                    if os.stat(full_path)[stat.ST_MTIME] > winrepo_cachefile_mtime:
                        ret["comment"] = "mtime({}) < mtime({})".format(
                            winrepo_cachefile, full_path
                        )
                        execute = True
                        break

    if __opts__["test"]:
        ret["result"] = None
        return ret

    if not execute and not force:
        return ret

    runner = salt.runner.RunnerClient(master_config)
    runner_ret = runner.cmd("winrepo.genrepo", [])
    ret["changes"] = {"winrepo": runner_ret}
    if isinstance(runner_ret, dict) and runner_ret == {} and not allow_empty:
        os.remove(winrepo_cachefile)
        ret["result"] = False
        ret["comment"] = "winrepo.genrepo returned empty"
    return ret
