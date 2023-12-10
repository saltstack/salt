"""
Module for Solaris 10's zonecfg

:maintainer:    Jorge Schrauwen <sjorge@blackdot.be>
:maturity:      new
:platform:      OmniOS,OpenIndiana,SmartOS,OpenSolaris,Solaris 10
:depend:        salt.modules.file

.. versionadded:: 2017.7.0

.. warning::
    Oracle Solaris 11's zonecfg is not supported by this module!
"""

import logging
import re

import salt.utils.args
import salt.utils.data
import salt.utils.decorators
import salt.utils.files
import salt.utils.path
from salt.utils.odict import OrderedDict

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "zonecfg"

# Function aliases
__func_alias__ = {"import_": "import"}

# Global data
_zonecfg_info_resources = [
    "rctl",
    "net",
    "fs",
    "device",
    "dedicated-cpu",
    "dataset",
    "attr",
]

_zonecfg_info_resources_calculated = [
    "capped-cpu",
    "capped-memory",
]

_zonecfg_resource_setters = {
    "fs": ["dir", "special", "raw", "type", "options"],
    "net": [
        "address",
        "allowed-address",
        "global-nic",
        "mac-addr",
        "physical",
        "property",
        "vlan-id defrouter",
    ],
    "device": ["match", "property"],
    "rctl": ["name", "value"],
    "attr": ["name", "type", "value"],
    "dataset": ["name"],
    "dedicated-cpu": ["ncpus", "importance"],
    "capped-cpu": ["ncpus"],
    "capped-memory": ["physical", "swap", "locked"],
    "admin": ["user", "auths"],
}

_zonecfg_resource_default_selectors = {
    "fs": "dir",
    "net": "mac-addr",
    "device": "match",
    "rctl": "name",
    "attr": "name",
    "dataset": "name",
    "admin": "user",
}


@salt.utils.decorators.memoize
def _is_globalzone():
    """
    Check if we are running in the globalzone
    """
    if not __grains__["kernel"] == "SunOS":
        return False

    zonename = __salt__["cmd.run_all"]("zonename")
    if zonename["retcode"]:
        return False
    if zonename["stdout"] == "global":
        return True

    return False


def __virtual__():
    """
    We are available if we are have zonecfg and are the global zone on
    Solaris 10, OmniOS, OpenIndiana, OpenSolaris, or Smartos.
    """
    if _is_globalzone() and salt.utils.path.which("zonecfg"):
        if __grains__["os"] in ["OpenSolaris", "SmartOS", "OmniOS", "OpenIndiana"]:
            return __virtualname__
        elif (
            __grains__["os"] == "Oracle Solaris"
            and int(__grains__["osmajorrelease"]) == 10
        ):
            return __virtualname__
    return (
        False,
        f"{__virtualname__} module can only be loaded in a solaris globalzone.",
    )


def _clean_message(message):
    """Internal helper to sanitize message output"""
    message = message.replace("zonecfg: ", "")
    message = message.splitlines()
    for line in message:
        if line.startswith("On line"):
            message.remove(line)
    return "\n".join(message)


def _parse_value(value):
    """Internal helper for parsing configuration values into python values"""
    if isinstance(value, bool):
        return "true" if value else "false"
    elif isinstance(value, str):
        # parse compacted notation to dict
        listparser = re.compile(r"""((?:[^,"']|"[^"]*"|'[^']*')+)""")

        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            return listparser.split(value[1:-1])[1::2]
        elif value.startswith("(") and value.endswith(")"):
            rval = {}
            for pair in listparser.split(value[1:-1])[1::2]:
                pair = pair.split("=")
                if '"' in pair[1]:
                    pair[1] = pair[1].replace('"', "")
                if pair[1].isdigit():
                    rval[pair[0]] = int(pair[1])
                elif pair[1] == "true":
                    rval[pair[0]] = True
                elif pair[1] == "false":
                    rval[pair[0]] = False
                else:
                    rval[pair[0]] = pair[1]
            return rval
        else:
            if '"' in value:
                value = value.replace('"', "")
            if value.isdigit():
                return int(value)
            elif value == "true":
                return True
            elif value == "false":
                return False
            else:
                return value
    else:
        return value


def _sanitize_value(value):
    """Internal helper for converting pythonic values to configuration file values"""
    # dump dict into compated
    if isinstance(value, dict):
        new_value = []
        new_value.append("(")
        for k, v in value.items():
            new_value.append(k)
            new_value.append("=")
            new_value.append(v)
            new_value.append(",")
        new_value.append(")")
        return "".join(str(v) for v in new_value).replace(",)", ")")
    elif isinstance(value, list):
        new_value = []
        new_value.append("(")
        for item in value:
            if isinstance(item, OrderedDict):
                item = dict(item)
                for k, v in item.items():
                    new_value.append(k)
                    new_value.append("=")
                    new_value.append(v)
            else:
                new_value.append(item)
            new_value.append(",")
        new_value.append(")")
        return "".join(str(v) for v in new_value).replace(",)", ")")
    else:
        # note: we can't use shelx or pipes quote here because it makes zonecfg barf
        return f'"{value}"' if " " in value else value


def _dump_cfg(cfg_file):
    """Internal helper for debugging cfg files"""
    if __salt__["file.file_exists"](cfg_file):
        with salt.utils.files.fopen(cfg_file, "r") as fp_:
            log.debug(
                "zonecfg - configuration file:\n%s",
                "".join(salt.utils.data.decode(fp_.readlines())),
            )


def create(zone, brand, zonepath, force=False):
    """
    Create an in-memory configuration for the specified zone.

    zone : string
        name of zone
    brand : string
        brand name
    zonepath : string
        path of zone
    force : boolean
        overwrite configuration

    CLI Example:

    .. code-block:: bash

        salt '*' zonecfg.create deathscythe ipkg /zones/deathscythe
    """
    ret = {"status": True}

    # write config
    cfg_file = salt.utils.files.mkstemp()
    with salt.utils.files.fpopen(cfg_file, "w+", mode=0o600) as fp_:
        fp_.write("create -b -F\n" if force else "create -b\n")
        fp_.write(f"set brand={_sanitize_value(brand)}\n")
        fp_.write(f"set zonepath={_sanitize_value(zonepath)}\n")

    # create
    if not __salt__["file.directory_exists"](zonepath):
        __salt__["file.makedirs_perms"](
            zonepath if zonepath[-1] == "/" else f"{zonepath}/", mode="0700"
        )

    _dump_cfg(cfg_file)
    res = __salt__["cmd.run_all"](
        "zonecfg -z {zone} -f {cfg}".format(
            zone=zone,
            cfg=cfg_file,
        )
    )
    ret["status"] = res["retcode"] == 0
    ret["message"] = res["stdout"] if ret["status"] else res["stderr"]
    if ret["message"] == "":
        del ret["message"]
    else:
        ret["message"] = _clean_message(ret["message"])

    # cleanup config file
    if __salt__["file.file_exists"](cfg_file):
        __salt__["file.remove"](cfg_file)

    return ret


def create_from_template(zone, template):
    """
    Create an in-memory configuration from a template for the specified zone.

    zone : string
        name of zone
    template : string
        name of template

    .. warning::
        existing config will be overwritten!

    CLI Example:

    .. code-block:: bash

        salt '*' zonecfg.create_from_template leo tallgeese
    """
    ret = {"status": True}

    # create from template
    _dump_cfg(template)
    res = __salt__["cmd.run_all"](
        "zonecfg -z {zone} create -t {tmpl} -F".format(
            zone=zone,
            tmpl=template,
        )
    )
    ret["status"] = res["retcode"] == 0
    ret["message"] = res["stdout"] if ret["status"] else res["stderr"]
    if ret["message"] == "":
        del ret["message"]
    else:
        ret["message"] = _clean_message(ret["message"])

    return ret


def delete(zone):
    """
    Delete the specified configuration from memory and stable storage.

    zone : string
        name of zone

    CLI Example:

    .. code-block:: bash

        salt '*' zonecfg.delete epyon
    """
    ret = {"status": True}

    # delete zone
    res = __salt__["cmd.run_all"](
        "zonecfg -z {zone} delete -F".format(
            zone=zone,
        )
    )
    ret["status"] = res["retcode"] == 0
    ret["message"] = res["stdout"] if ret["status"] else res["stderr"]
    if ret["message"] == "":
        del ret["message"]
    else:
        ret["message"] = _clean_message(ret["message"])

    return ret


def export(zone, path=None):
    """
    Export the configuration from memory to stable storage.

    zone : string
        name of zone
    path : string
        path of file to export to

    CLI Example:

    .. code-block:: bash

        salt '*' zonecfg.export epyon
        salt '*' zonecfg.export epyon /zones/epyon.cfg
    """
    ret = {"status": True}

    # export zone
    res = __salt__["cmd.run_all"](
        "zonecfg -z {zone} export{path}".format(
            zone=zone,
            path=f" -f {path}" if path else "",
        )
    )
    ret["status"] = res["retcode"] == 0
    ret["message"] = res["stdout"] if ret["status"] else res["stderr"]
    if ret["message"] == "":
        del ret["message"]
    else:
        ret["message"] = _clean_message(ret["message"])

    return ret


def import_(zone, path):
    """
    Import the configuration to memory from stable storage.

    zone : string
        name of zone
    path : string
        path of file to export to

    CLI Example:

    .. code-block:: bash

        salt '*' zonecfg.import epyon /zones/epyon.cfg
    """
    ret = {"status": True}

    # create from file
    _dump_cfg(path)
    res = __salt__["cmd.run_all"](
        "zonecfg -z {zone} -f {path}".format(
            zone=zone,
            path=path,
        )
    )
    ret["status"] = res["retcode"] == 0
    ret["message"] = res["stdout"] if ret["status"] else res["stderr"]
    if ret["message"] == "":
        del ret["message"]
    else:
        ret["message"] = _clean_message(ret["message"])

    return ret


def _property(methode, zone, key, value):
    """
    internal handler for set and clear_property

    methode : string
        either set, add, or clear
    zone : string
        name of zone
    key : string
        name of property
    value : string
        value of property

    """
    ret = {"status": True}

    # generate update script
    cfg_file = None
    if methode not in ["set", "clear"]:
        ret["status"] = False
        ret["message"] = f"unkown methode {methode}!"
    else:
        cfg_file = salt.utils.files.mkstemp()
        with salt.utils.files.fpopen(cfg_file, "w+", mode=0o600) as fp_:
            if methode == "set":
                if isinstance(value, dict) or isinstance(value, list):
                    value = _sanitize_value(value)
                value = str(value).lower() if isinstance(value, bool) else str(value)
                fp_.write(f"{methode} {key}={_sanitize_value(value)}\n")
            elif methode == "clear":
                fp_.write(f"{methode} {key}\n")

    # update property
    if cfg_file:
        _dump_cfg(cfg_file)
        res = __salt__["cmd.run_all"](
            "zonecfg -z {zone} -f {path}".format(
                zone=zone,
                path=cfg_file,
            )
        )
        ret["status"] = res["retcode"] == 0
        ret["message"] = res["stdout"] if ret["status"] else res["stderr"]
        if ret["message"] == "":
            del ret["message"]
        else:
            ret["message"] = _clean_message(ret["message"])

        # cleanup config file
        if __salt__["file.file_exists"](cfg_file):
            __salt__["file.remove"](cfg_file)

    return ret


def set_property(zone, key, value):
    """
    Set a property

    zone : string
        name of zone
    key : string
        name of property
    value : string
        value of property

    CLI Example:

    .. code-block:: bash

        salt '*' zonecfg.set_property deathscythe cpu-shares 100
    """
    return _property(
        "set",
        zone,
        key,
        value,
    )


def clear_property(zone, key):
    """
    Clear a property

    zone : string
        name of zone
    key : string
        name of property

    CLI Example:

    .. code-block:: bash

        salt '*' zonecfg.clear_property deathscythe cpu-shares
    """
    return _property(
        "clear",
        zone,
        key,
        None,
    )


def _resource(methode, zone, resource_type, resource_selector, **kwargs):
    """
    internal resource hanlder

    methode : string
        add or update
    zone : string
        name of zone
    resource_type : string
        type of resource
    resource_selector : string
        unique resource identifier
    **kwargs : string|int|...
        resource properties

    """
    ret = {"status": True}

    # parse kwargs
    kwargs = salt.utils.args.clean_kwargs(**kwargs)
    for k in kwargs:
        if isinstance(kwargs[k], dict) or isinstance(kwargs[k], list):
            kwargs[k] = _sanitize_value(kwargs[k])
    if methode not in ["add", "update"]:
        ret["status"] = False
        ret["message"] = f"unknown methode {methode}"
        return ret
    if methode in ["update"] and resource_selector and resource_selector not in kwargs:
        ret["status"] = False
        ret["message"] = "resource selector {} not found in parameters".format(
            resource_selector
        )
        return ret

    # generate update script
    cfg_file = salt.utils.files.mkstemp()
    with salt.utils.files.fpopen(cfg_file, "w+", mode=0o600) as fp_:
        if methode in ["add"]:
            fp_.write(f"add {resource_type}\n")
        elif methode in ["update"]:
            if resource_selector:
                value = kwargs[resource_selector]
                if isinstance(value, dict) or isinstance(value, list):
                    value = _sanitize_value(value)
                value = str(value).lower() if isinstance(value, bool) else str(value)
                fp_.write(
                    "select {} {}={}\n".format(
                        resource_type, resource_selector, _sanitize_value(value)
                    )
                )
            else:
                fp_.write(f"select {resource_type}\n")
        for k, v in kwargs.items():
            if methode in ["update"] and k == resource_selector:
                continue
            if isinstance(v, dict) or isinstance(v, list):
                value = _sanitize_value(value)
            value = str(v).lower() if isinstance(v, bool) else str(v)
            if k in _zonecfg_resource_setters[resource_type]:
                fp_.write(f"set {k}={_sanitize_value(value)}\n")
            else:
                fp_.write(f"add {k} {_sanitize_value(value)}\n")
        fp_.write("end\n")

    # update property
    if cfg_file:
        _dump_cfg(cfg_file)
        res = __salt__["cmd.run_all"](
            "zonecfg -z {zone} -f {path}".format(
                zone=zone,
                path=cfg_file,
            )
        )
        ret["status"] = res["retcode"] == 0
        ret["message"] = res["stdout"] if ret["status"] else res["stderr"]
        if ret["message"] == "":
            del ret["message"]
        else:
            ret["message"] = _clean_message(ret["message"])

        # cleanup config file
        if __salt__["file.file_exists"](cfg_file):
            __salt__["file.remove"](cfg_file)

    return ret


def add_resource(zone, resource_type, **kwargs):
    """
    Add a resource

    zone : string
        name of zone
    resource_type : string
        type of resource
    kwargs : string|int|...
        resource properties

    CLI Example:

    .. code-block:: bash

        salt '*' zonecfg.add_resource tallgeese rctl name=zone.max-locked-memory value='(priv=privileged,limit=33554432,action=deny)'
    """
    return _resource("add", zone, resource_type, None, **kwargs)


def update_resource(zone, resource_type, resource_selector, **kwargs):
    """
    Add a resource

    zone : string
        name of zone
    resource_type : string
        type of resource
    resource_selector : string
        unique resource identifier
    kwargs : string|int|...
        resource properties

    .. note::
        Set resource_selector to None for resource that do not require one.

    CLI Example:

    .. code-block:: bash

        salt '*' zonecfg.update_resource tallgeese rctl name name=zone.max-locked-memory value='(priv=privileged,limit=33554432,action=deny)'
    """
    return _resource("update", zone, resource_type, resource_selector, **kwargs)


def remove_resource(zone, resource_type, resource_key, resource_value):
    """
    Remove a resource

    zone : string
        name of zone
    resource_type : string
        type of resource
    resource_key : string
        key for resource selection
    resource_value : string
        value for resource selection

    .. note::
        Set resource_selector to None for resource that do not require one.

    CLI Example:

    .. code-block:: bash

        salt '*' zonecfg.remove_resource tallgeese rctl name zone.max-locked-memory
    """
    ret = {"status": True}

    # generate update script
    cfg_file = salt.utils.files.mkstemp()
    with salt.utils.files.fpopen(cfg_file, "w+", mode=0o600) as fp_:
        if resource_key:
            fp_.write(
                "remove {} {}={}\n".format(
                    resource_type, resource_key, _sanitize_value(resource_value)
                )
            )
        else:
            fp_.write(f"remove {resource_type}\n")

    # update property
    if cfg_file:
        _dump_cfg(cfg_file)
        res = __salt__["cmd.run_all"](
            "zonecfg -z {zone} -f {path}".format(
                zone=zone,
                path=cfg_file,
            )
        )
        ret["status"] = res["retcode"] == 0
        ret["message"] = res["stdout"] if ret["status"] else res["stderr"]
        if ret["message"] == "":
            del ret["message"]
        else:
            ret["message"] = _clean_message(ret["message"])

        # cleanup config file
        if __salt__["file.file_exists"](cfg_file):
            __salt__["file.remove"](cfg_file)

    return ret


def info(zone, show_all=False):
    """
    Display the configuration from memory

    zone : string
        name of zone
    show_all : boolean
        also include calculated values like capped-cpu, cpu-shares, ...

    CLI Example:

    .. code-block:: bash

        salt '*' zonecfg.info tallgeese
    """
    ret = {}

    # dump zone
    res = __salt__["cmd.run_all"](
        "zonecfg -z {zone} info".format(
            zone=zone,
        )
    )
    if res["retcode"] == 0:
        # parse output
        resname = None
        resdata = {}
        for line in res["stdout"].split("\n"):
            # skip some bad data
            if ":" not in line:
                continue

            # skip calculated values (if requested)
            if line.startswith("["):
                if not show_all:
                    continue
                line = line.rstrip()[1:-1]

            # extract key
            key = line.strip().split(":")[0]
            if "[" in key:
                key = key[1:]

            # parse calculated resource (if requested)
            if key in _zonecfg_info_resources_calculated:
                if resname:
                    ret[resname].append(resdata)
                if show_all:
                    resname = key
                    resdata = {}
                    if key not in ret:
                        ret[key] = []
                else:
                    resname = None
                    resdata = {}
            # parse resources
            elif key in _zonecfg_info_resources:
                if resname:
                    ret[resname].append(resdata)
                resname = key
                resdata = {}
                if key not in ret:
                    ret[key] = []
            # store resource property
            elif line.startswith("\t"):
                # ship calculated values (if requested)
                if line.strip().startswith("["):
                    if not show_all:
                        continue
                    line = line.strip()[1:-1]
                if key == "property":  # handle special 'property' keys
                    if "property" not in resdata:
                        resdata[key] = {}
                    kv = _parse_value(line.strip()[line.strip().index(":") + 1 :])
                    if "name" in kv and "value" in kv:
                        resdata[key][kv["name"]] = kv["value"]
                    else:
                        log.warning("zonecfg.info - not sure how to deal with: %s", kv)
                else:
                    resdata[key] = _parse_value(
                        line.strip()[line.strip().index(":") + 1 :]
                    )
            # store property
            else:
                if resname:
                    ret[resname].append(resdata)
                resname = None
                resdata = {}
                if key == "property":  # handle special 'property' keys
                    if "property" not in ret:
                        ret[key] = {}
                    kv = _parse_value(line.strip()[line.strip().index(":") + 1 :])
                    if "name" in kv and "value" in kv:
                        res[key][kv["name"]] = kv["value"]
                    else:
                        log.warning("zonecfg.info - not sure how to deal with: %s", kv)
                else:
                    ret[key] = _parse_value(line.strip()[line.strip().index(":") + 1 :])
        # store hanging resource
        if resname:
            ret[resname].append(resdata)

    return ret
