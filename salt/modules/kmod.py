"""
Module to manage Linux kernel modules
"""

import logging
import os
import re

import salt.utils.files
import salt.utils.path

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only runs on Linux systems
    """
    return __grains__["kernel"] == "Linux"


def _new_mods(pre_mods, post_mods):
    """
    Return a list of the new modules, pass an lsmod dict before running
    modprobe and one after modprobe has run
    """
    pre = set()
    post = set()
    for mod in pre_mods:
        pre.add(mod["module"])
    for mod in post_mods:
        post.add(mod["module"])
    return post - pre


def _rm_mods(pre_mods, post_mods):
    """
    Return a list of the new modules, pass an lsmod dict before running
    modprobe and one after modprobe has run
    """
    pre = set()
    post = set()
    for mod in pre_mods:
        pre.add(mod["module"])
    for mod in post_mods:
        post.add(mod["module"])
    return pre - post


def _get_modules_conf():
    """
    Return location of modules config file.
    Default: /etc/modules
    """
    if "systemd" in __grains__:
        return "/etc/modules-load.d/salt_managed.conf"
    return "/etc/modules"


def _strip_module_name(mod):
    """
    Return module name and strip configuration. It is possible insert modules
    in this format:
        bonding mode=4 miimon=1000
    This method return only 'bonding'
    """
    if mod.strip() == "":
        return False
    return mod.split()[0]


def _set_persistent_module(mod):
    """
    Add module to configuration file to make it persistent. If module is
    commented uncomment it.
    """
    conf = _get_modules_conf()
    if not os.path.exists(conf):
        __salt__["file.touch"](conf)
    mod_name = _strip_module_name(mod)
    if not mod_name or mod_name in mod_list(True) or mod_name not in available():
        return set()
    escape_mod = re.escape(mod)
    # If module is commented only uncomment it
    if __salt__["file.search"](
        conf, "^#[\t ]*{}[\t ]*$".format(escape_mod), multiline=True
    ):
        __salt__["file.uncomment"](conf, escape_mod)
    else:
        __salt__["file.append"](conf, mod)
    return {mod_name}


def _remove_persistent_module(mod, comment):
    """
    Remove module from configuration file. If comment is true only comment line
    where module is.
    """
    conf = _get_modules_conf()
    mod_name = _strip_module_name(mod)
    if not mod_name or mod_name not in mod_list(True):
        return set()
    escape_mod = re.escape(mod)
    if comment:
        __salt__["file.comment"](conf, "^[\t ]*{}[\t ]?".format(escape_mod))
    else:
        __salt__["file.sed"](conf, "^[\t ]*{}[\t ]?".format(escape_mod), "")
    return {mod_name}


def available():
    """
    Return a list of all available kernel modules

    CLI Example:

    .. code-block:: bash

        salt '*' kmod.available
    """
    ret = []

    mod_dir = os.path.join("/lib/modules/", os.uname()[2])

    built_in_file = os.path.join(mod_dir, "modules.builtin")
    if os.path.exists(built_in_file):
        with salt.utils.files.fopen(built_in_file, "r") as f:
            for line in f:
                # Strip .ko from the basename
                ret.append(os.path.basename(line)[:-4])

    for root, dirs, files in salt.utils.path.os_walk(mod_dir):
        for fn_ in files:
            if ".ko" in fn_:
                ret.append(fn_[: fn_.index(".ko")].replace("-", "_"))

    if "Arch" in __grains__["os_family"]:
        # Sadly this path is relative to kernel major version but ignores minor version
        mod_dir_arch = "/lib/modules/extramodules-" + os.uname()[2][0:3] + "-ARCH"
        for root, dirs, files in salt.utils.path.os_walk(mod_dir_arch):
            for fn_ in files:
                if ".ko" in fn_:
                    ret.append(fn_[: fn_.index(".ko")].replace("-", "_"))

    return sorted(list(ret))


def check_available(mod):
    """
    Check to see if the specified kernel module is available

    CLI Example:

    .. code-block:: bash

        salt '*' kmod.check_available kvm
    """
    return mod in available()


def lsmod():
    """
    Return a dict containing information about currently loaded modules

    CLI Example:

    .. code-block:: bash

        salt '*' kmod.lsmod
    """
    ret = []
    for line in __salt__["cmd.run"]("lsmod").splitlines():
        comps = line.split()
        if not len(comps) > 2:
            continue
        if comps[0] == "Module":
            continue
        mdat = {
            "size": comps[1],
            "module": comps[0],
            "depcount": comps[2],
        }
        if len(comps) > 3:
            mdat["deps"] = comps[3].split(",")
        else:
            mdat["deps"] = []
        ret.append(mdat)
    return ret


def mod_list(only_persist=False):
    """
    Return a list of the loaded module names

    only_persist
        Only return the list of loaded persistent modules

    CLI Example:

    .. code-block:: bash

        salt '*' kmod.mod_list
    """
    mods = set()
    if only_persist:
        conf = _get_modules_conf()
        if os.path.exists(conf):
            try:
                with salt.utils.files.fopen(conf, "r") as modules_file:
                    for line in modules_file:
                        line = line.strip()
                        mod_name = _strip_module_name(line)
                        if not line.startswith("#") and mod_name:
                            mods.add(mod_name)
            except OSError:
                log.error("kmod module could not open modules file at %s", conf)
    else:
        for mod in lsmod():
            mods.add(mod["module"])
    return sorted(list(mods))


def load(mod, persist=False):
    """
    Load the specified kernel module

    mod
        Name of module to add

    persist
        Write module to /etc/modules to make it load on system reboot

    CLI Example:

    .. code-block:: bash

        salt '*' kmod.load kvm
    """
    pre_mods = lsmod()
    res = __salt__["cmd.run_all"]("modprobe {}".format(mod), python_shell=False)
    if res["retcode"] == 0:
        post_mods = lsmod()
        mods = _new_mods(pre_mods, post_mods)
        persist_mods = set()
        if persist:
            persist_mods = _set_persistent_module(mod)
        return sorted(list(mods | persist_mods))
    else:
        return "Error loading module {}: {}".format(mod, res["stderr"])


def is_loaded(mod):
    """
    Check to see if the specified kernel module is loaded

    CLI Example:

    .. code-block:: bash

        salt '*' kmod.is_loaded kvm
    """
    return mod in mod_list()


def remove(mod, persist=False, comment=True):
    """
    Remove the specified kernel module

    mod
        Name of module to remove

    persist
        Also remove module from /etc/modules

    comment
        If persist is set don't remove line from /etc/modules but only
        comment it

    CLI Example:

    .. code-block:: bash

        salt '*' kmod.remove kvm
    """
    pre_mods = lsmod()
    res = __salt__["cmd.run_all"]("rmmod {}".format(mod), python_shell=False)
    if res["retcode"] == 0:
        post_mods = lsmod()
        mods = _rm_mods(pre_mods, post_mods)
        persist_mods = set()
        if persist:
            persist_mods = _remove_persistent_module(mod, comment)
        return sorted(list(mods | persist_mods))
    else:
        return "Error removing module {}: {}".format(mod, res["stderr"])
