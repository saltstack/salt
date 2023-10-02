"""
Module for running fmadm and fmdump on Solaris

:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:platform:      solaris,illumos

.. versionadded:: 2016.3.0
"""

import logging

import salt.utils.decorators as decorators
import salt.utils.path
import salt.utils.platform
from salt.utils.odict import OrderedDict

log = logging.getLogger(__name__)

# Function aliases
__func_alias__ = {
    "list_records": "list",
}

# Define the module's virtual name
__virtualname__ = "fmadm"


@decorators.memoize
def _check_fmadm():
    """
    Looks to see if fmadm is present on the system
    """
    return salt.utils.path.which("fmadm")


def _check_fmdump():
    """
    Looks to see if fmdump is present on the system
    """
    return salt.utils.path.which("fmdump")


def __virtual__():
    """
    Provides fmadm only on Solaris
    """
    if salt.utils.platform.is_sunos() and _check_fmadm() and _check_fmdump():
        return __virtualname__
    return (
        False,
        "{} module can only be loaded on Solaris with the fault management installed".format(
            __virtualname__
        ),
    )


def _parse_fmdump(output):
    """
    Parses fmdump output
    """
    result = []
    output = output.split("\n")

    # extract header
    header = [field for field in output[0].lower().split(" ") if field]
    del output[0]

    # parse entries
    for entry in output:
        entry = [item for item in entry.split(" ") if item]
        entry = [f"{entry[0]} {entry[1]} {entry[2]}"] + entry[3:]

        # prepare faults
        fault = OrderedDict()
        for field in header:
            fault[field] = entry[header.index(field)]

        result.append(fault)

    return result


def _parse_fmdump_verbose(output):
    """
    Parses fmdump verbose output
    """
    result = []
    output = output.split("\n")

    fault = []
    verbose_fault = {}
    for line in output:
        if line.startswith("TIME"):
            fault.append(line)
            if verbose_fault:
                result.append(verbose_fault)
                verbose_fault = {}
        elif len(fault) == 1:
            fault.append(line)
            verbose_fault = _parse_fmdump("\n".join(fault))[0]
            fault = []
        elif verbose_fault:
            if "details" not in verbose_fault:
                verbose_fault["details"] = ""
            if line.strip() == "":
                continue
            verbose_fault["details"] = "{}{}\n".format(verbose_fault["details"], line)
    if len(verbose_fault) > 0:
        result.append(verbose_fault)

    return result


def _parse_fmadm_config(output):
    """
    Parsbb fmdump/fmadm output
    """
    result = []
    output = output.split("\n")

    # extract header
    header = [field for field in output[0].lower().split(" ") if field]
    del output[0]

    # parse entries
    for entry in output:
        entry = [item for item in entry.split(" ") if item]
        entry = entry[0:3] + [" ".join(entry[3:])]

        # prepare component
        component = OrderedDict()
        for field in header:
            component[field] = entry[header.index(field)]

        result.append(component)

    # keying
    keyed_result = OrderedDict()
    for component in result:
        keyed_result[component["module"]] = component
        del keyed_result[component["module"]]["module"]

    result = keyed_result

    return result


def _fmadm_action_fmri(action, fmri):
    """
    Internal function for fmadm.repqired, fmadm.replaced, fmadm.flush
    """
    ret = {}
    fmadm = _check_fmadm()
    cmd = f"{fmadm} {action} {fmri}"
    res = __salt__["cmd.run_all"](cmd)
    retcode = res["retcode"]
    result = {}
    if retcode != 0:
        result["Error"] = res["stderr"]
    else:
        result = True

    return result


def _parse_fmadm_faulty(output):
    """
    Parse fmadm faulty output
    """

    def _merge_data(summary, fault):
        result = {}
        uuid = summary["event-id"]
        del summary["event-id"]

        result[uuid] = OrderedDict()
        result[uuid]["summary"] = summary
        result[uuid]["fault"] = fault
        return result

    result = {}
    summary = []
    summary_data = {}
    fault_data = {}
    data_key = None

    for line in output.split("\n"):
        # we hit a divider
        if line.startswith("-"):
            if summary and summary_data and fault_data:
                # we have data, store it and reset
                result.update(_merge_data(summary_data, fault_data))

                summary = []
                summary_data = {}
                fault_data = {}
                continue
            else:
                # we don't have all data, colelct more
                continue

        # if we do not have the header, store it
        if not summary:
            summary.append(line)
            continue

        # if we have the header but no data, store the data and parse it
        if summary and not summary_data:
            summary.append(line)
            summary_data = _parse_fmdump("\n".join(summary))[0]
            continue

        # if we have a header and data, assume the other lines are details
        if summary and summary_data:
            # if line starts with a whitespace and we already have a key, append
            if line.startswith(" ") and data_key:
                fault_data[data_key] = "{}\n{}".format(
                    fault_data[data_key], line.strip()
                )
            # we have a key : value line, parse it
            elif ":" in line:
                line = line.split(":")
                data_key = line[0].strip()
                fault_data[data_key] = ":".join(line[1:]).strip()
                # note: for some reason Chassis_id is lobbed ofter Platform, fix that here
                if data_key == "Platform":
                    fault_data["Chassis_id"] = (
                        fault_data[data_key][fault_data[data_key].index("Chassis_id") :]
                        .split(":")[-1]
                        .strip()
                    )
                    fault_data[data_key] = fault_data[data_key][
                        0 : fault_data[data_key].index("Chassis_id")
                    ].strip()

    # we have data, store it and reset
    result.update(_merge_data(summary_data, fault_data))

    return result


def list_records(after=None, before=None):
    """
    Display fault management logs

    after : string
        filter events after time, see man fmdump for format

    before : string
        filter events before time, see man fmdump for format

    CLI Example:

    .. code-block:: bash

        salt '*' fmadm.list
    """
    ret = {}
    fmdump = _check_fmdump()
    cmd = "{cmd}{after}{before}".format(
        cmd=fmdump,
        after=f" -t {after}" if after else "",
        before=f" -T {before}" if before else "",
    )
    res = __salt__["cmd.run_all"](cmd)
    retcode = res["retcode"]
    result = {}
    if retcode != 0:
        result["Error"] = "error executing fmdump"
    else:
        result = _parse_fmdump(res["stdout"])

    return result


def show(uuid):
    """
    Display log details

    uuid: string
        uuid of fault

    CLI Example:

    .. code-block:: bash

        salt '*' fmadm.show 11b4070f-4358-62fa-9e1e-998f485977e1
    """
    ret = {}
    fmdump = _check_fmdump()
    cmd = f"{fmdump} -u {uuid} -V"
    res = __salt__["cmd.run_all"](cmd)
    retcode = res["retcode"]
    result = {}
    if retcode != 0:
        result["Error"] = "error executing fmdump"
    else:
        result = _parse_fmdump_verbose(res["stdout"])

    return result


def config():
    """
    Display fault manager configuration

    CLI Example:

    .. code-block:: bash

        salt '*' fmadm.config
    """
    ret = {}
    fmadm = _check_fmadm()
    cmd = f"{fmadm} config"
    res = __salt__["cmd.run_all"](cmd)
    retcode = res["retcode"]
    result = {}
    if retcode != 0:
        result["Error"] = "error executing fmadm config"
    else:
        result = _parse_fmadm_config(res["stdout"])

    return result


def load(path):
    """
    Load specified fault manager module

    path: string
        path of fault manager module

    CLI Example:

    .. code-block:: bash

        salt '*' fmadm.load /module/path
    """
    ret = {}
    fmadm = _check_fmadm()
    cmd = f"{fmadm} load {path}"
    res = __salt__["cmd.run_all"](cmd)
    retcode = res["retcode"]
    result = {}
    if retcode != 0:
        result["Error"] = res["stderr"]
    else:
        result = True

    return result


def unload(module):
    """
    Unload specified fault manager module

    module: string
        module to unload

    CLI Example:

    .. code-block:: bash

        salt '*' fmadm.unload software-response
    """
    ret = {}
    fmadm = _check_fmadm()
    cmd = f"{fmadm} unload {module}"
    res = __salt__["cmd.run_all"](cmd)
    retcode = res["retcode"]
    result = {}
    if retcode != 0:
        result["Error"] = res["stderr"]
    else:
        result = True

    return result


def reset(module, serd=None):
    """
    Reset module or sub-component

    module: string
        module to unload
    serd : string
        serd sub module

    CLI Example:

    .. code-block:: bash

        salt '*' fmadm.reset software-response
    """
    ret = {}
    fmadm = _check_fmadm()
    cmd = "{cmd} reset {serd}{module}".format(
        cmd=fmadm, serd=f"-s {serd} " if serd else "", module=module
    )
    res = __salt__["cmd.run_all"](cmd)
    retcode = res["retcode"]
    result = {}
    if retcode != 0:
        result["Error"] = res["stderr"]
    else:
        result = True

    return result


def flush(fmri):
    """
    Flush cached state for resource

    fmri: string
        fmri

    CLI Example:

    .. code-block:: bash

        salt '*' fmadm.flush fmri
    """
    return _fmadm_action_fmri("flush", fmri)


def repaired(fmri):
    """
    Notify fault manager that resource has been repaired

    fmri: string
        fmri

    CLI Example:

    .. code-block:: bash

        salt '*' fmadm.repaired fmri
    """
    return _fmadm_action_fmri("repaired", fmri)


def replaced(fmri):
    """
    Notify fault manager that resource has been replaced

    fmri: string
        fmri

    CLI Example:

    .. code-block:: bash

        salt '*' fmadm.repaired fmri
    """
    return _fmadm_action_fmri("replaced", fmri)


def acquit(fmri):
    """
    Acquit resource or acquit case

    fmri: string
        fmri or uuid

    CLI Example:

    .. code-block:: bash

        salt '*' fmadm.acquit fmri | uuid
    """
    return _fmadm_action_fmri("acquit", fmri)


def faulty():
    """
    Display list of faulty resources

    CLI Example:

    .. code-block:: bash

        salt '*' fmadm.faulty
    """
    fmadm = _check_fmadm()
    cmd = "{cmd} faulty".format(
        cmd=fmadm,
    )
    res = __salt__["cmd.run_all"](cmd)
    result = {}
    if res["stdout"] == "":
        result = False
    else:
        result = _parse_fmadm_faulty(res["stdout"])

    return result


def healthy():
    """
    Return whether fmadm is reporting faults

    CLI Example:

    .. code-block:: bash

        salt '*' fmadm.healthy
    """
    return False if faulty() else True
