"""
Manage UEFI boot entries using efibootmgr
"""

import re
import salt.utils.path


def __virtual__():
    if __grains__.get("kernel") != "Linux":
        return (False, "efi module only supports Linux")
    elif salt.utils.path.which("efibootmgr"):
        return "efi"
    return (False, "efibootmgr not found")


def list_entries():
    """
    List EFI boot entries

    CLI Example:

    .. code-block:: bash

        salt '*' efi.list_entries
    """
    ret = {}
    out = __salt__["cmd.run_stdout"](["efibootmgr", "-v"])

    # Regex to capture BootXXXX* <label> <path>
    entry_re = re.compile(r"Boot([0-9A-F]{4})\*\s+(.*)\s+(.*)")

    for line in out.splitlines():
        match = entry_re.match(line)
        if match:
            bootnum, label, path = match.groups()
            ret[bootnum] = {"label": label, "path": path}

    return ret


def get_bootorder():
    """
    Get the current boot order

    CLI Example:

    .. code-block:: bash

        salt '*' efi.get_bootorder
    """
    out = __salt__["cmd.run_stdout"](["efibootmgr", "-v"])

    match = re.search(r"BootOrder:\s*(.*)", out)
    if match:
        return match.group(1).split(",")
    return []


def add_entry(label, loader, disk="/dev/sda", part=1):
    """
    Add a new EFI entry

    CLI Example:

    .. code-block:: bash

        salt '*' efi.add_entry label=Debian loader='\\EFI\\debian\\grub.efi'
    """
    return (
        __salt__["cmd.retcode"](
            ["efibootmgr", "-c", "-d", disk, "-p", part, "-L", label, "-l", loader]
        )
        == 0
    )


def remove_entry(bootnum):
    """
    Remove an EFI entry

    CLI Example:

    .. code-block:: bash

        salt '*' efi.remove_entry 0001
    """
    return __salt__["cmd.retcode"](["efibootmgr", "-b", bootnum, "-B"]) == 0


def set_bootorder(bootorder):
    """
    Set boot order

    CLI Example:

    .. code-block:: bash

        salt '*' efi.set_bootorder '["0001", "0002"]'
    """

    return __salt__["cmd.retcode"](["efibootmgr", "-o" ",".join(bootorder)]) == 0
