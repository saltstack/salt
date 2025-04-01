"""
Module for managing NFS version 3.
"""

import logging

import salt.utils.files
import salt.utils.path
import salt.utils.stringutils

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only work on POSIX-like systems
    """
    if not salt.utils.path.which("showmount"):
        return (
            False,
            "The nfs3 execution module failed to load: the showmount binary is not in"
            " the path.",
        )
    return True


def list_exports(exports="/etc/exports"):
    """
    List configured exports

    CLI Example:

    .. code-block:: bash

        salt '*' nfs.list_exports
    """
    ret = {}
    with salt.utils.files.fopen(exports, "r") as efl:
        for line in salt.utils.stringutils.to_unicode(efl.read()).splitlines():
            if not line:
                continue
            if line.startswith("#"):
                continue
            comps = line.split()

            # Handle the case where the same path is given twice
            if not comps[0] in ret:
                ret[comps[0]] = []

            newshares = []
            for perm in comps[1:]:
                if perm.startswith("/"):
                    newshares.append(perm)
                    continue
                permcomps = perm.split("(")
                permcomps[1] = permcomps[1].replace(")", "")
                hosts = permcomps[0]
                if not isinstance(hosts, str):
                    # Lists, etc would silently mangle /etc/exports
                    raise TypeError("hosts argument must be a string")
                options = permcomps[1].split(",")
                ret[comps[0]].append({"hosts": hosts, "options": options})
            for share in newshares:
                ret[share] = ret[comps[0]]
    return ret


def del_export(exports="/etc/exports", path=None):
    """
    Remove an export

    CLI Example:

    .. code-block:: bash

        salt '*' nfs.del_export /media/storage
    """
    edict = list_exports(exports)
    del edict[path]
    _write_exports(exports, edict)
    return edict


def add_export(exports="/etc/exports", path=None, hosts=None, options=None):
    """
    Add an export

    CLI Example:

    .. code-block:: bash

        salt '*' nfs3.add_export path='/srv/test' hosts='127.0.0.1' options=['rw']
    """
    if options is None:
        options = []
    if not isinstance(hosts, str):
        # Lists, etc would silently mangle /etc/exports
        raise TypeError("hosts argument must be a string")
    edict = list_exports(exports)
    if path not in edict:
        edict[path] = []
    new = {"hosts": hosts, "options": options}
    edict[path].append(new)
    _write_exports(exports, edict)

    return new


def _write_exports(exports, edict):
    """
    Write an exports file to disk

    If multiple shares were initially configured per line, like:

        /media/storage /media/data *(ro,sync,no_subtree_check)

    ...then they will be saved to disk with only one share per line:

        /media/storage *(ro,sync,no_subtree_check)
        /media/data *(ro,sync,no_subtree_check)
    """
    with salt.utils.files.fopen(exports, "w") as efh:
        for export in edict:
            line = salt.utils.stringutils.to_str(export)
            for perms in edict[export]:
                hosts = perms["hosts"]
                options = ",".join(perms["options"])
                line += f" {hosts}({options})"
            efh.write(f"{line}\n")


def reload_exports():
    """
    Trigger a reload of the exports file to apply changes

    CLI Example:

    .. code-block:: bash

        salt '*' nfs3.reload_exports
    """
    ret = {}

    command = "exportfs -r"

    output = __salt__["cmd.run_all"](command)
    ret["stdout"] = output["stdout"]
    ret["stderr"] = output["stderr"]
    # exportfs always returns 0, so retcode is useless
    # We will consider it an error if stderr is nonempty
    ret["result"] = output["stderr"] == ""

    return ret
