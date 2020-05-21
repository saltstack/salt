# -*- coding: utf-8 -*-
"""
Execute calls on selinux

.. note::
    This module requires the ``semanage``, ``setsebool``, and ``semodule``
    commands to be available on the minion. On RHEL-based distributions,
    ensure that the ``policycoreutils`` and ``policycoreutils-python``
    packages are installed. If not on a Fedora or RHEL-based distribution,
    consult the selinux documentation for your distribution to ensure that the
    proper packages are installed.
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import os
import re

import salt.utils.decorators as decorators

# Import salt libs
import salt.utils.files
import salt.utils.path
import salt.utils.stringutils
import salt.utils.versions
from salt.exceptions import CommandExecutionError, SaltInvocationError

# Import 3rd-party libs
from salt.ext import six

_SELINUX_FILETYPES = {
    "a": "all files",
    "f": "regular file",
    "d": "directory",
    "c": "character device",
    "b": "block device",
    "s": "socket",
    "l": "symbolic link",
    "p": "named pipe",
}


def __virtual__():
    """
    Check if the os is Linux, and then if selinux is running in permissive or
    enforcing mode.
    """
    required_cmds = ("semanage", "setsebool", "semodule")

    # Iterate over all of the commands this module uses and make sure
    # each of them are available in the standard PATH to prevent breakage
    for cmd in required_cmds:
        if not salt.utils.path.which(cmd):
            return (False, cmd + " is not in the path")
    # SELinux only makes sense on Linux *obviously*
    if __grains__["kernel"] == "Linux":
        return "selinux"
    return (False, "Module only works on Linux with selinux installed")


# Cache the SELinux directory to not look it up over and over
@decorators.memoize
def selinux_fs_path():
    """
    Return the location of the SELinux VFS directory

    CLI Example:

    .. code-block:: bash

        salt '*' selinux.selinux_fs_path
    """
    # systems running systemd (e.g. Fedora 15 and newer)
    # have the selinux filesystem in a different location
    try:
        for directory in ("/sys/fs/selinux", "/selinux"):
            if os.path.isdir(directory):
                if os.path.isfile(os.path.join(directory, "enforce")):
                    return directory
        return None
    # If selinux is Disabled, the path does not exist.
    except AttributeError:
        return None


def getenforce():
    """
    Return the mode selinux is running in

    CLI Example:

    .. code-block:: bash

        salt '*' selinux.getenforce
    """
    _selinux_fs_path = selinux_fs_path()
    if _selinux_fs_path is None:
        return "Disabled"
    try:
        enforce = os.path.join(_selinux_fs_path, "enforce")
        with salt.utils.files.fopen(enforce, "r") as _fp:
            if salt.utils.stringutils.to_unicode(_fp.readline()).strip() == "0":
                return "Permissive"
            else:
                return "Enforcing"
    except (IOError, OSError, AttributeError):
        return "Disabled"


def getconfig():
    """
    Return the selinux mode from the config file

    CLI Example:

    .. code-block:: bash

        salt '*' selinux.getconfig
    """
    try:
        config = "/etc/selinux/config"
        with salt.utils.files.fopen(config, "r") as _fp:
            for line in _fp:
                line = salt.utils.stringutils.to_unicode(line)
                if line.strip().startswith("SELINUX="):
                    return line.split("=")[1].capitalize().strip()
    except (IOError, OSError, AttributeError):
        return None
    return None


def setenforce(mode):
    """
    Set the SELinux enforcing mode

    CLI Example:

    .. code-block:: bash

        salt '*' selinux.setenforce enforcing
    """
    if isinstance(mode, six.string_types):
        if mode.lower() == "enforcing":
            mode = "1"
            modestring = "Enforcing"
        elif mode.lower() == "permissive":
            mode = "0"
            modestring = "Permissive"
        elif mode.lower() == "disabled":
            mode = "0"
            modestring = "Disabled"
        else:
            return "Invalid mode {0}".format(mode)
    elif isinstance(mode, int):
        if mode:
            mode = "1"
        else:
            mode = "0"
    else:
        return "Invalid mode {0}".format(mode)

    # enforce file does not exist if currently disabled.  Only for toggling enforcing/permissive
    if getenforce() != "Disabled":
        enforce = os.path.join(selinux_fs_path(), "enforce")
        try:
            with salt.utils.files.fopen(enforce, "w") as _fp:
                _fp.write(salt.utils.stringutils.to_str(mode))
        except (IOError, OSError) as exc:
            msg = "Could not write SELinux enforce file: {0}"
            raise CommandExecutionError(msg.format(exc))

    config = "/etc/selinux/config"
    try:
        with salt.utils.files.fopen(config, "r") as _cf:
            conf = _cf.read()
        try:
            with salt.utils.files.fopen(config, "w") as _cf:
                conf = re.sub(r"\nSELINUX=.*\n", "\nSELINUX=" + modestring + "\n", conf)
                _cf.write(salt.utils.stringutils.to_str(conf))
        except (IOError, OSError) as exc:
            msg = "Could not write SELinux config file: {0}"
            raise CommandExecutionError(msg.format(exc))
    except (IOError, OSError) as exc:
        msg = "Could not read SELinux config file: {0}"
        raise CommandExecutionError(msg.format(exc))

    return getenforce()


def getsebool(boolean):
    """
    Return the information on a specific selinux boolean

    CLI Example:

    .. code-block:: bash

        salt '*' selinux.getsebool virt_use_usb
    """
    return list_sebool().get(boolean, {})


def setsebool(boolean, value, persist=False):
    """
    Set the value for a boolean

    CLI Example:

    .. code-block:: bash

        salt '*' selinux.setsebool virt_use_usb off
    """
    if persist:
        cmd = "setsebool -P {0} {1}".format(boolean, value)
    else:
        cmd = "setsebool {0} {1}".format(boolean, value)
    return not __salt__["cmd.retcode"](cmd, python_shell=False)


def setsebools(pairs, persist=False):
    """
    Set the value of multiple booleans

    CLI Example:

    .. code-block:: bash

        salt '*' selinux.setsebools '{virt_use_usb: on, squid_use_tproxy: off}'
    """
    if not isinstance(pairs, dict):
        return {}
    if persist:
        cmd = "setsebool -P "
    else:
        cmd = "setsebool "
    for boolean, value in six.iteritems(pairs):
        cmd = "{0} {1}={2}".format(cmd, boolean, value)
    return not __salt__["cmd.retcode"](cmd, python_shell=False)


def list_sebool():
    """
    Return a structure listing all of the selinux booleans on the system and
    what state they are in

    CLI Example:

    .. code-block:: bash

        salt '*' selinux.list_sebool
    """
    bdata = __salt__["cmd.run"]("semanage boolean -l").splitlines()
    ret = {}
    for line in bdata[1:]:
        if not line.strip():
            continue
        comps = line.split()
        ret[comps[0]] = {
            "State": comps[1][1:],
            "Default": comps[3][:-1],
            "Description": " ".join(comps[4:]),
        }
    return ret


def getsemod(module):
    """
    Return the information on a specific selinux module

    CLI Example:

    .. code-block:: bash

        salt '*' selinux.getsemod mysql

    .. versionadded:: 2016.3.0
    """
    return list_semod().get(module, {})


def setsemod(module, state):
    """
    Enable or disable an SELinux module.

    CLI Example:

    .. code-block:: bash

        salt '*' selinux.setsemod nagios Enabled

    .. versionadded:: 2016.3.0
    """
    if state.lower() == "enabled":
        cmd = "semodule -e {0}".format(module)
    elif state.lower() == "disabled":
        cmd = "semodule -d {0}".format(module)
    return not __salt__["cmd.retcode"](cmd)


def install_semod(module_path):
    """
    Install custom SELinux module from file

    CLI Example:

    .. code-block:: bash

        salt '*' selinux.install_semod [salt://]path/to/module.pp

    .. versionadded:: 2016.11.6
    """
    if module_path.find("salt://") == 0:
        module_path = __salt__["cp.cache_file"](module_path)
    cmd = "semodule -i {0}".format(module_path)
    return not __salt__["cmd.retcode"](cmd)


def remove_semod(module):
    """
    Remove SELinux module

    CLI Example:

    .. code-block:: bash

        salt '*' selinux.remove_semod module_name

    .. versionadded:: 2016.11.6
    """
    cmd = "semodule -r {0}".format(module)
    return not __salt__["cmd.retcode"](cmd)


def list_semod():
    """
    Return a structure listing all of the selinux modules on the system and
    what state they are in

    CLI Example:

    .. code-block:: bash

        salt '*' selinux.list_semod

    .. versionadded:: 2016.3.0
    """
    helptext = __salt__["cmd.run"]("semodule -h").splitlines()
    semodule_version = ""
    for line in helptext:
        if line.strip().startswith("full"):
            semodule_version = "new"

    if semodule_version == "new":
        mdata = __salt__["cmd.run"]("semodule -lfull").splitlines()
        ret = {}
        for line in mdata:
            if not line.strip():
                continue
            comps = line.split()
            if len(comps) == 4:
                ret[comps[1]] = {"Enabled": False, "Version": None}
            else:
                ret[comps[1]] = {"Enabled": True, "Version": None}
    else:
        mdata = __salt__["cmd.run"]("semodule -l").splitlines()
        ret = {}
        for line in mdata:
            if not line.strip():
                continue
            comps = line.split()
            if len(comps) == 3:
                ret[comps[0]] = {"Enabled": False, "Version": comps[1]}
            else:
                ret[comps[0]] = {"Enabled": True, "Version": comps[1]}
    return ret


def _validate_filetype(filetype):
    """
    .. versionadded:: 2017.7.0

    Checks if the given filetype is a valid SELinux filetype
    specification. Throws an SaltInvocationError if it isn't.
    """
    if filetype not in _SELINUX_FILETYPES.keys():
        raise SaltInvocationError("Invalid filetype given: {0}".format(filetype))
    return True


def _parse_protocol_port(name, protocol, port):
    """
    .. versionadded:: 2019.2.0

    Validates and parses the protocol and port/port range from the name
    if both protocol and port are not provided.

    If the name is in a valid format, the protocol and port are ignored if provided

    Examples: tcp/8080 or udp/20-21
    """
    protocol_port_pattern = r"^(tcp|udp)\/(([\d]+)\-?[\d]+)$"
    name_parts = re.match(protocol_port_pattern, name)
    if not name_parts:
        name_parts = re.match(protocol_port_pattern, "{0}/{1}".format(protocol, port))
    if not name_parts:
        raise SaltInvocationError(
            'Invalid name "{0}" format and protocol and port not provided or invalid: "{1}" "{2}".'.format(
                name, protocol, port
            )
        )
    return name_parts.group(1), name_parts.group(2)


def _context_dict_to_string(context):
    """
    .. versionadded:: 2017.7.0

    Converts an SELinux file context from a dict to a string.
    """
    return "{sel_user}:{sel_role}:{sel_type}:{sel_level}".format(**context)


def _context_string_to_dict(context):
    """
    .. versionadded:: 2017.7.0

    Converts an SELinux file context from string to dict.
    """
    if not re.match("[^:]+:[^:]+:[^:]+:[^:]+$", context):
        raise SaltInvocationError(
            "Invalid SELinux context string: {0}. "
            + 'Expected "sel_user:sel_role:sel_type:sel_level"'
        )
    context_list = context.split(":", 3)
    ret = {}
    for index, value in enumerate(["sel_user", "sel_role", "sel_type", "sel_level"]):
        ret[value] = context_list[index]
    return ret


def filetype_id_to_string(filetype="a"):
    """
    .. versionadded:: 2017.7.0

    Translates SELinux filetype single-letter representation to a more
    human-readable version (which is also used in `semanage fcontext
    -l`).
    """
    _validate_filetype(filetype)
    return _SELINUX_FILETYPES.get(filetype, "error")


def fcontext_get_policy(
    name, filetype=None, sel_type=None, sel_user=None, sel_level=None
):
    """
    .. versionadded:: 2017.7.0

    Returns the current entry in the SELinux policy list as a
    dictionary. Returns None if no exact match was found.

    Returned keys are:

    * filespec (the name supplied and matched)
    * filetype (the descriptive name of the filetype supplied)
    * sel_user, sel_role, sel_type, sel_level (the selinux context)

    For a more in-depth explanation of the selinux context, go to
    https://access.redhat.com/documentation/en-US/Red_Hat_Enterprise_Linux/6/html/Security-Enhanced_Linux/chap-Security-Enhanced_Linux-SELinux_Contexts.html

    name
        filespec of the file or directory. Regex syntax is allowed.

    filetype
        The SELinux filetype specification. Use one of [a, f, d, c, b,
        s, l, p]. See also `man semanage-fcontext`. Defaults to 'a'
        (all files).

    CLI Example:

    .. code-block:: bash

        salt '*' selinux.fcontext_get_policy my-policy
    """
    if filetype:
        _validate_filetype(filetype)
    re_spacer = "[ ]+"
    cmd_kwargs = {
        "spacer": re_spacer,
        "filespec": re.escape(name),
        "sel_user": sel_user or "[^:]+",
        "sel_role": "[^:]+",  # se_role for file context is always object_r
        "sel_type": sel_type or "[^:]+",
        "sel_level": sel_level or "[^:]+",
    }
    cmd_kwargs["filetype"] = (
        "[[:alpha:] ]+" if filetype is None else filetype_id_to_string(filetype)
    )
    cmd = (
        "semanage fcontext -l | egrep "
        + "'^{filespec}{spacer}{filetype}{spacer}{sel_user}:{sel_role}:{sel_type}:{sel_level}$'".format(
            **cmd_kwargs
        )
    )
    current_entry_text = __salt__["cmd.shell"](cmd, ignore_retcode=True)
    if current_entry_text == "":
        return None

    parts = re.match(
        r"^({filespec}) +([a-z ]+) (.*)$".format(**{"filespec": re.escape(name)}),
        current_entry_text,
    )
    ret = {
        "filespec": parts.group(1).strip(),
        "filetype": parts.group(2).strip(),
    }
    ret.update(_context_string_to_dict(parts.group(3).strip()))

    return ret


def fcontext_add_policy(
    name, filetype=None, sel_type=None, sel_user=None, sel_level=None
):
    """
    .. versionadded:: 2019.2.0

    Adds the SELinux policy for a given filespec and other optional parameters.

    Returns the result of the call to semanage.

    Note that you don't have to remove an entry before setting a new
    one for a given filespec and filetype, as adding one with semanage
    automatically overwrites a previously configured SELinux context.

    name
        filespec of the file or directory. Regex syntax is allowed.

    file_type
        The SELinux filetype specification. Use one of [a, f, d, c, b,
        s, l, p]. See also ``man semanage-fcontext``. Defaults to 'a'
        (all files).

    sel_type
        SELinux context type. There are many.

    sel_user
        SELinux user. Use ``semanage login -l`` to determine which ones
        are available to you.

    sel_level
        The MLS range of the SELinux context.

    CLI Example:

    .. code-block:: bash

        salt '*' selinux.fcontext_add_policy my-policy
    """
    return _fcontext_add_or_delete_policy(
        "add", name, filetype, sel_type, sel_user, sel_level
    )


def fcontext_delete_policy(
    name, filetype=None, sel_type=None, sel_user=None, sel_level=None
):
    """
    .. versionadded:: 2019.2.0

    Deletes the SELinux policy for a given filespec and other optional parameters.

    Returns the result of the call to semanage.

    Note that you don't have to remove an entry before setting a new
    one for a given filespec and filetype, as adding one with semanage
    automatically overwrites a previously configured SELinux context.

    name
        filespec of the file or directory. Regex syntax is allowed.

    file_type
        The SELinux filetype specification. Use one of [a, f, d, c, b,
        s, l, p]. See also ``man semanage-fcontext``. Defaults to 'a'
        (all files).

    sel_type
        SELinux context type. There are many.

    sel_user
        SELinux user. Use ``semanage login -l`` to determine which ones
        are available to you.

    sel_level
        The MLS range of the SELinux context.

    CLI Example:

    .. code-block:: bash

        salt '*' selinux.fcontext_delete_policy my-policy
    """
    return _fcontext_add_or_delete_policy(
        "delete", name, filetype, sel_type, sel_user, sel_level
    )


def fcontext_add_or_delete_policy(
    action, name, filetype=None, sel_type=None, sel_user=None, sel_level=None
):
    """
    .. versionadded:: 2017.7.0

    Adds or deletes the SELinux policy for a given filespec and other optional parameters.

    Returns the result of the call to semanage.

    Note that you don't have to remove an entry before setting a new
    one for a given filespec and filetype, as adding one with semanage
    automatically overwrites a previously configured SELinux context.

    .. warning::

        Use :mod:`selinux.fcontext_add_policy()<salt.modules.selinux.fcontext_add_policy>`,
        or :mod:`selinux.fcontext_delete_policy()<salt.modules.selinux.fcontext_delete_policy>`.

    .. deprecated:: 2019.2.0

    action
        The action to perform. Either ``add`` or ``delete``.

    name
        filespec of the file or directory. Regex syntax is allowed.

    file_type
        The SELinux filetype specification. Use one of [a, f, d, c, b,
        s, l, p]. See also ``man semanage-fcontext``. Defaults to 'a'
        (all files).

    sel_type
        SELinux context type. There are many.

    sel_user
        SELinux user. Use ``semanage login -l`` to determine which ones
        are available to you.

    sel_level
        The MLS range of the SELinux context.

    CLI Example:

    .. code-block:: bash

        salt '*' selinux.fcontext_add_or_delete_policy add my-policy
    """
    salt.utils.versions.warn_until(
        "Sodium",
        "The 'selinux.fcontext_add_or_delete_policy' module has been deprecated. Please use the "
        "'selinux.fcontext_add_policy' and 'selinux.fcontext_delete_policy' modules instead. "
        "Support for the 'selinux.fcontext_add_or_delete_policy' module will be removed in Salt "
        "{version}.",
    )
    return _fcontext_add_or_delete_policy(
        action, name, filetype, sel_type, sel_user, sel_level
    )


def _fcontext_add_or_delete_policy(
    action, name, filetype=None, sel_type=None, sel_user=None, sel_level=None
):
    """
    .. versionadded:: 2019.2.0

    Performs the action as called from ``fcontext_add_policy`` or ``fcontext_delete_policy``.

    Returns the result of the call to semanage.
    """
    if action not in ["add", "delete"]:
        raise SaltInvocationError(
            'Actions supported are "add" and "delete", not "{0}".'.format(action)
        )
    cmd = "semanage fcontext --{0}".format(action)
    # "semanage --ftype a" isn't valid on Centos 6,
    # don't pass --ftype since "a" is the default filetype.
    if filetype is not None and filetype != "a":
        _validate_filetype(filetype)
        cmd += " --ftype {0}".format(filetype)
    if sel_type is not None:
        cmd += " --type {0}".format(sel_type)
    if sel_user is not None:
        cmd += " --seuser {0}".format(sel_user)
    if sel_level is not None:
        cmd += " --range {0}".format(sel_level)
    cmd += " " + re.escape(name)
    return __salt__["cmd.run_all"](cmd)


def fcontext_policy_is_applied(name, recursive=False):
    """
    .. versionadded:: 2017.7.0

    Returns an empty string if the SELinux policy for a given filespec
    is applied, returns string with differences in policy and actual
    situation otherwise.

    name
        filespec of the file or directory. Regex syntax is allowed.

    CLI Example:

    .. code-block:: bash

        salt '*' selinux.fcontext_policy_is_applied my-policy
    """
    cmd = "restorecon -n -v "
    if recursive:
        cmd += "-R "
    cmd += re.escape(name)
    return __salt__["cmd.run_all"](cmd).get("stdout")


def fcontext_apply_policy(name, recursive=False):
    """
    .. versionadded:: 2017.7.0

    Applies SElinux policies to filespec using `restorecon [-R]
    filespec`. Returns dict with changes if successful, the output of
    the restorecon command otherwise.

    name
        filespec of the file or directory. Regex syntax is allowed.

    recursive
        Recursively apply SELinux policies.

    CLI Example:

    .. code-block:: bash

        salt '*' selinux.fcontext_apply_policy my-policy
    """
    ret = {}
    changes_text = fcontext_policy_is_applied(name, recursive)
    cmd = "restorecon -v -F "
    if recursive:
        cmd += "-R "
    cmd += re.escape(name)
    apply_ret = __salt__["cmd.run_all"](cmd)
    ret.update(apply_ret)
    if apply_ret["retcode"] == 0:
        changes_list = re.findall(
            "restorecon reset (.*) context (.*)->(.*)$", changes_text, re.M
        )
        if len(changes_list) > 0:
            ret.update({"changes": {}})
        for item in changes_list:
            filespec = item[0]
            old = _context_string_to_dict(item[1])
            new = _context_string_to_dict(item[2])
            intersect = {}
            for key, value in six.iteritems(old):
                if new.get(key) == value:
                    intersect.update({key: value})
            for key in intersect:
                del old[key]
                del new[key]
            ret["changes"].update({filespec: {"old": old, "new": new}})
    return ret


def port_get_policy(name, sel_type=None, protocol=None, port=None):
    """
    .. versionadded:: 2019.2.0

    Returns the current entry in the SELinux policy list as a
    dictionary. Returns None if no exact match was found.

    Returned keys are:

    * sel_type (the selinux type)
    * proto (the protocol)
    * port (the port(s) and/or port range(s))

    name
        The protocol and port spec. Can be formatted as ``(tcp|udp)/(port|port-range)``.

    sel_type
        The SELinux Type.

    protocol
        The protocol for the port, ``tcp`` or ``udp``. Required if name is not formatted.

    port
        The port or port range. Required if name is not formatted.

    CLI Example:

    .. code-block:: bash

        salt '*' selinux.port_get_policy tcp/80
        salt '*' selinux.port_get_policy foobar protocol=tcp port=80
    """
    (protocol, port) = _parse_protocol_port(name, protocol, port)
    re_spacer = "[ ]+"
    re_sel_type = sel_type if sel_type else r"\w+"
    cmd_kwargs = {
        "spacer": re_spacer,
        "sel_type": re_sel_type,
        "protocol": protocol,
        "port": port,
    }
    cmd = (
        "semanage port -l | egrep "
        + "'^{sel_type}{spacer}{protocol}{spacer}((.*)*)[ ]{port}($|,)'".format(
            **cmd_kwargs
        )
    )
    port_policy = __salt__["cmd.shell"](cmd, ignore_retcode=True)
    if port_policy == "":
        return None

    parts = re.match(r"^(\w+)[ ]+(\w+)[ ]+([\d\-, ]+)", port_policy)
    return {
        "sel_type": parts.group(1).strip(),
        "protocol": parts.group(2).strip(),
        "port": parts.group(3).strip(),
    }


def port_add_policy(name, sel_type=None, protocol=None, port=None, sel_range=None):
    """
    .. versionadded:: 2019.2.0

    Adds the SELinux policy for a given protocol and port.

    Returns the result of the call to semanage.

    name
        The protocol and port spec. Can be formatted as ``(tcp|udp)/(port|port-range)``.

    sel_type
        The SELinux Type. Required.

    protocol
        The protocol for the port, ``tcp`` or ``udp``. Required if name is not formatted.

    port
        The port or port range. Required if name is not formatted.

    sel_range
        The SELinux MLS/MCS Security Range.

    CLI Example:

    .. code-block:: bash

        salt '*' selinux.port_add_policy add tcp/8080 http_port_t
        salt '*' selinux.port_add_policy add foobar http_port_t protocol=tcp port=8091
    """
    return _port_add_or_delete_policy("add", name, sel_type, protocol, port, sel_range)


def port_delete_policy(name, protocol=None, port=None):
    """
    .. versionadded:: 2019.2.0

    Deletes the SELinux policy for a given protocol and port.

    Returns the result of the call to semanage.

    name
        The protocol and port spec. Can be formatted as ``(tcp|udp)/(port|port-range)``.

    protocol
        The protocol for the port, ``tcp`` or ``udp``. Required if name is not formatted.

    port
        The port or port range. Required if name is not formatted.

    CLI Example:

    .. code-block:: bash

        salt '*' selinux.port_delete_policy tcp/8080
        salt '*' selinux.port_delete_policy foobar protocol=tcp port=8091
    """
    return _port_add_or_delete_policy("delete", name, None, protocol, port, None)


def _port_add_or_delete_policy(
    action, name, sel_type=None, protocol=None, port=None, sel_range=None
):
    """
    .. versionadded:: 2019.2.0

    Performs the action as called from ``port_add_policy`` or ``port_delete_policy``.

    Returns the result of the call to semanage.
    """
    if action not in ["add", "delete"]:
        raise SaltInvocationError(
            'Actions supported are "add" and "delete", not "{0}".'.format(action)
        )
    if action == "add" and not sel_type:
        raise SaltInvocationError("SELinux Type is required to add a policy")
    (protocol, port) = _parse_protocol_port(name, protocol, port)
    cmd = "semanage port --{0} --proto {1}".format(action, protocol)
    if sel_type:
        cmd += " --type {0}".format(sel_type)
    if sel_range:
        cmd += " --range {0}".format(sel_range)
    cmd += " {0}".format(port)
    return __salt__["cmd.run_all"](cmd)
