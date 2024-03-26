"""
Manage vms running on the OpenBSD VMM hypervisor using vmctl(8).

.. versionadded:: 2019.2.0

:codeauthor: ``Jasper Lievisse Adriaanse <jasper@openbsd.org>``

.. note::

    This module requires the `vmd` service to be running on the OpenBSD
    target machine.
"""

import logging
import re

import salt.utils.path
from salt.exceptions import CommandExecutionError, SaltInvocationError

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only works on OpenBSD with vmctl(8) present.
    """
    if __grains__["os"] == "OpenBSD" and salt.utils.path.which("vmctl"):
        return True

    return (
        False,
        "The vmm execution module cannot be loaded: either the system is not OpenBSD or"
        " the vmctl binary was not found",
    )


def _id_to_name(id):
    """
    Lookup the name associated with a VM id.
    """
    vm = status(id=id)
    if vm == {}:
        return None
    else:
        return vm["name"]


def create_disk(name, size):
    """
    Create a VMM disk with the specified `name` and `size`.

    size:
        Size in megabytes, or use a specifier such as M, G, T.

    CLI Example:

    .. code-block:: bash

        salt '*' vmctl.create_disk /path/to/disk.img size=10G
    """
    ret = False
    cmd = f"vmctl create {name} -s {size}"

    result = __salt__["cmd.run_all"](cmd, output_loglevel="trace", python_shell=False)

    if result["retcode"] == 0:
        ret = True
    else:
        raise CommandExecutionError(
            "Problem encountered creating disk image",
            info={"errors": [result["stderr"]], "changes": ret},
        )

    return ret


def load(path):
    """
    Load additional configuration from the specified file.

    path
        Path to the configuration file.

    CLI Example:

    .. code-block:: bash

        salt '*' vmctl.load path=/etc/vm.switches.conf
    """
    ret = False
    cmd = f"vmctl load {path}"
    result = __salt__["cmd.run_all"](cmd, output_loglevel="trace", python_shell=False)
    if result["retcode"] == 0:
        ret = True
    else:
        raise CommandExecutionError(
            "Problem encountered running vmctl",
            info={"errors": [result["stderr"]], "changes": ret},
        )

    return ret


def reload():
    """
    Remove all stopped VMs and reload configuration from the default configuration file.

    CLI Example:

    .. code-block:: bash

        salt '*' vmctl.reload
    """
    ret = False
    cmd = "vmctl reload"
    result = __salt__["cmd.run_all"](cmd, output_loglevel="trace", python_shell=False)
    if result["retcode"] == 0:
        ret = True
    else:
        raise CommandExecutionError(
            "Problem encountered running vmctl",
            info={"errors": [result["stderr"]], "changes": ret},
        )

    return ret


def reset(all=False, vms=False, switches=False):
    """
    Reset the running state of VMM or a subsystem.

    all:
        Reset the running state.

    switches:
        Reset the configured switches.

    vms:
        Reset and terminate all VMs.

    CLI Example:

    .. code-block:: bash

        salt '*' vmctl.reset all=True
    """
    ret = False
    cmd = ["vmctl", "reset"]

    if all:
        cmd.append("all")
    elif vms:
        cmd.append("vms")
    elif switches:
        cmd.append("switches")

    result = __salt__["cmd.run_all"](cmd, output_loglevel="trace", python_shell=False)
    if result["retcode"] == 0:
        ret = True
    else:
        raise CommandExecutionError(
            "Problem encountered running vmctl",
            info={"errors": [result["stderr"]], "changes": ret},
        )

    return ret


def start(
    name=None,
    id=None,
    bootpath=None,
    disk=None,
    disks=None,
    local_iface=False,
    memory=None,
    nics=0,
    switch=None,
):
    """
    Starts a VM defined by the specified parameters.
    When both a name and id are provided, the id is ignored.

    name:
        Name of the defined VM.

    id:
        VM id.

    bootpath:
        Path to a kernel or BIOS image to load.

    disk:
        Path to a single disk to use.

    disks:
        List of multiple disks to use.

    local_iface:
        Whether to add a local network interface. See "LOCAL INTERFACES"
        in the vmctl(8) manual page for more information.

    memory:
        Memory size of the VM specified in megabytes.

    switch:
        Add a network interface that is attached to the specified
        virtual switch on the host.

    CLI Example:

    .. code-block:: bash

        salt '*' vmctl.start 2   # start VM with id 2
        salt '*' vmctl.start name=web1 bootpath='/bsd.rd' nics=2 memory=512M disk='/disk.img'
    """
    ret = {"changes": False, "console": None}
    cmd = ["vmctl", "start"]

    if not (name or id):
        raise SaltInvocationError('Must provide either "name" or "id"')
    elif name:
        cmd.append(name)
    else:
        cmd.append(id)
        name = _id_to_name(id)

    if nics > 0:
        cmd.append(f"-i {nics}")

    # Paths cannot be appended as otherwise the inserted whitespace is treated by
    # vmctl as being part of the path.
    if bootpath:
        cmd.extend(["-b", bootpath])

    if memory:
        cmd.append(f"-m {memory}")

    if switch:
        cmd.append(f"-n {switch}")

    if local_iface:
        cmd.append("-L")

    if disk and disks:
        raise SaltInvocationError('Must provide either "disks" or "disk"')

    if disk:
        cmd.extend(["-d", disk])

    if disks:
        cmd.extend(["-d", x] for x in disks)

    # Before attempting to define a new VM, make sure it doesn't already exist.
    # Otherwise return to indicate nothing was changed.
    if len(cmd) > 3:
        vmstate = status(name)
        if vmstate:
            ret["comment"] = "VM already exists and cannot be redefined"
            return ret

    result = __salt__["cmd.run_all"](cmd, output_loglevel="trace", python_shell=False)

    if result["retcode"] == 0:
        ret["changes"] = True
        m = re.match(r".*successfully, tty (\/dev.*)", result["stderr"])
        if m:
            ret["console"] = m.groups()[0]
        else:
            m = re.match(r".*Operation already in progress$", result["stderr"])
            if m:
                ret["changes"] = False
    else:
        raise CommandExecutionError(
            "Problem encountered running vmctl",
            info={"errors": [result["stderr"]], "changes": ret},
        )

    return ret


def status(name=None, id=None):
    """
    List VMs running on the host, or only the VM specified by ``id``.  When
    both a name and id are provided, the id is ignored.

    name:
        Name of the defined VM.

    id:
        VM id.

    CLI Example:

    .. code-block:: bash

        salt '*' vmctl.status           # to list all VMs
        salt '*' vmctl.status name=web1 # to get a single VM
    """
    ret = {}
    cmd = ["vmctl", "status"]

    result = __salt__["cmd.run_all"](cmd, output_loglevel="trace", python_shell=False)

    if result["retcode"] != 0:
        raise CommandExecutionError(
            "Problem encountered running vmctl",
            info={"error": [result["stderr"]], "changes": ret},
        )

    # Grab the header and save it with the lowercase names.
    header = result["stdout"].splitlines()[0].split()
    header = [x.lower() for x in header]

    # A VM can be in one of the following states (from vmm.c:vcpu_state_decode())
    # - stopped
    # - running
    # - requesting termination
    # - terminated
    # - unknown

    for line in result["stdout"].splitlines()[1:]:
        data = line.split()
        vm = dict(list(zip(header, data)))
        vmname = vm.pop("name")
        if vm["pid"] == "-":
            # If the VM has no PID it's not running.
            vm["state"] = "stopped"
        elif vmname and data[-2] == "-":
            # When a VM does have a PID and the second to last field is a '-', it's
            # transitioning to another state. A VM name itself cannot contain a
            # '-' so it's safe to split on '-'.
            vm["state"] = data[-1]
        else:
            vm["state"] = "running"

        # When the status is requested of a single VM (by name) which is stopping,
        # vmctl doesn't print the status line. So we'll parse the full list and
        # return when we've found the requested VM.
        if id and int(vm["id"]) == id:
            return {vmname: vm}
        elif name and vmname == name:
            return {vmname: vm}
        else:
            ret[vmname] = vm

    # Assert we've not come this far when an id or name have been provided. That
    # means the requested VM does not exist.
    if id or name:
        return {}

    return ret


def stop(name=None, id=None):
    """
    Stop (terminate) the VM identified by the given id or name.
    When both a name and id are provided, the id is ignored.

    name:
        Name of the defined VM.

    id:
        VM id.

    CLI Example:

    .. code-block:: bash

        salt '*' vmctl.stop name=alpine
    """
    ret = {}
    cmd = ["vmctl", "stop"]

    if not (name or id):
        raise SaltInvocationError('Must provide either "name" or "id"')
    elif name:
        cmd.append(name)
    else:
        cmd.append(id)

    result = __salt__["cmd.run_all"](cmd, output_loglevel="trace", python_shell=False)

    if result["retcode"] == 0:
        if re.match("^vmctl: sent request to terminate vm.*", result["stderr"]):
            ret["changes"] = True
        else:
            ret["changes"] = False
    else:
        raise CommandExecutionError(
            "Problem encountered running vmctl",
            info={"errors": [result["stderr"]], "changes": ret},
        )

    return ret
