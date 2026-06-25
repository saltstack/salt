"""
Module for managing logrotate.
"""

import logging
import os

import salt.utils.files
import salt.utils.platform
import salt.utils.stringutils
from salt.exceptions import SaltInvocationError

_LOG = logging.getLogger(__name__)
_DEFAULT_CONF = "/etc/logrotate.conf"

# Directives that introduce a multi-line shell script body terminated by
# ``endscript``. The body must be kept opaque (not parsed as key/value
# settings) so that lines like ``invoke-rc.d syslog-ng reload`` or repeated
# ``endscript`` terminators do not collapse into bogus dict keys. See
# the logrotate(8) manpage for the full list of script directives.
_SCRIPT_DIRECTIVES = (
    "firstaction",
    "lastaction",
    "prerotate",
    "postrotate",
    "preremove",
)


# Define a function alias in order not to shadow built-in's
__func_alias__ = {"set_": "set"}


def __virtual__():
    """
    Only work on POSIX-like systems
    """
    if salt.utils.platform.is_windows():
        return (
            False,
            "The logrotate execution module cannot be loaded: only available "
            "on non-Windows systems.",
        )
    return True


def _convert_if_int(value):
    """
    Convert to an int if necessary.

    :param str value: The value to check/convert.

    :return: The converted or passed value.
    :rtype: bool|int|str
    """
    try:
        value = int(str(value))
    except ValueError:
        pass
    return value


def _parse_conf(conf_file=_DEFAULT_CONF):
    """
    Parse a logrotate configuration file.

    Includes will also be parsed, and their configuration will be stored in the
    return dict, as if they were part of the main config file. A dict of which
    configs came from which includes will be stored in the 'include files' dict
    inside the return dict, for later reference by the user or module.
    """
    ret = {}
    mode = "single"
    multi_names = []
    multi = {}
    prev_comps = None
    # When inside a ``prerotate``/``postrotate``/... block, collect the raw
    # script body lines here and stash them on the enclosing dict under the
    # script directive name once ``endscript`` is seen.
    script_directive = None
    script_body = []

    with salt.utils.files.fopen(conf_file, "r") as ifile:
        for line in ifile:
            line = salt.utils.stringutils.to_unicode(line).rstrip("\r\n")
            stripped = line.strip()

            if script_directive is not None:
                # Inside a script block: lines are opaque shell content until
                # the ``endscript`` terminator. Do not strip comments or skip
                # blank lines — they are part of the script.
                if stripped == "endscript":
                    target = multi if mode == "multi" else ret
                    target[script_directive] = list(script_body)
                    script_directive = None
                    script_body = []
                    continue
                script_body.append(stripped)
                continue

            line = stripped
            if not line:
                continue
            if line.startswith("#"):
                continue

            comps = line.split()
            if "{" in line and "}" not in line:
                mode = "multi"
                if len(comps) == 1 and prev_comps:
                    multi_names = prev_comps
                else:
                    multi_names = comps
                    multi_names.pop()
                continue
            if "}" in line:
                mode = "single"
                for multi_name in multi_names:
                    ret[multi_name] = multi
                multi_names = []
                multi = {}
                continue

            if mode == "single":
                key = ret
            else:
                key = multi

            if comps[0] == "include":
                if "include files" not in ret:
                    ret["include files"] = {}
                for include in os.listdir(comps[1]):
                    if include not in ret["include files"]:
                        ret["include files"][include] = []

                    include_path = os.path.join(comps[1], include)
                    include_conf = _parse_conf(include_path)

                    for file_key in include_conf:
                        ret[file_key] = include_conf[file_key]
                        ret["include files"][include].append(file_key)

            # Recognize the start of a script block. The body that follows
            # (up to ``endscript``) is kept opaque so embedded shell commands
            # don't get parsed as settings and so a second script block's
            # ``endscript`` is not lost to a duplicate-key collision.
            if comps[0] in _SCRIPT_DIRECTIVES and len(comps) == 1:
                script_directive = comps[0]
                script_body = []
                continue

            prev_comps = comps
            if len(comps) > 2:
                key[comps[0]] = " ".join(comps[1:])
            elif len(comps) > 1:
                key[comps[0]] = _convert_if_int(comps[1])
            else:
                key[comps[0]] = True
    return ret


def show_conf(conf_file=_DEFAULT_CONF):
    """
    Show parsed configuration

    :param str conf_file: The logrotate configuration file.

    :return: The parsed configuration.
    :rtype: dict

    CLI Example:

    .. code-block:: bash

        salt '*' logrotate.show_conf
    """
    return _parse_conf(conf_file)


def get(key, value=None, conf_file=_DEFAULT_CONF):
    """
    Get the value for a specific configuration line.

    :param str key: The command or stanza block to configure.
    :param str value: The command value or command of the block specified by the key parameter.
    :param str conf_file: The logrotate configuration file.

    :return: The value for a specific configuration line.
    :rtype: bool|int|str

    CLI Example:

    .. code-block:: bash

        salt '*' logrotate.get rotate

        salt '*' logrotate.get /var/log/wtmp rotate /etc/logrotate.conf
    """
    current_conf = _parse_conf(conf_file)
    stanza = current_conf.get(key, False)

    if value:
        if stanza:
            return stanza.get(value, False)
        _LOG.debug("Block '%s' not present or empty.", key)
    return stanza


def set_(key, value, setting=None, conf_file=_DEFAULT_CONF):
    """
    Set a new value for a specific configuration line.

    :param str key: The command or block to configure.
    :param str value: The command value or command of the block specified by the key parameter.
    :param str setting: The command value for the command specified by the value parameter.
    :param str conf_file: The logrotate configuration file.

    :return: A boolean representing whether all changes succeeded.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' logrotate.set rotate 2

    Can also be used to set a single value inside a multiline configuration
    block. For instance, to change rotate in the following block:

    .. code-block:: text

        /var/log/wtmp {
            monthly
            create 0664 root root
            rotate 1
        }

    Use the following command:

    .. code-block:: bash

        salt '*' logrotate.set /var/log/wtmp rotate 2

    This module also has the ability to scan files inside an include directory,
    and make changes in the appropriate file.
    """
    conf = _parse_conf(conf_file)
    for include in conf["include files"]:
        if key in conf["include files"][include]:
            conf_file = os.path.join(conf["include"], include)

    new_line = ""
    kwargs = {
        "flags": 8,
        "backup": False,
        "path": conf_file,
        "pattern": f"^{key}.*",
        "show_changes": False,
    }

    if setting is None:
        current_value = conf.get(key, False)

        if isinstance(current_value, dict):
            raise SaltInvocationError(
                "Error: {} includes a dict, and a specific setting inside the "
                "dict was not declared".format(key)
            )

        if value == current_value:
            _LOG.debug("Command '%s' already has: %s", key, value)
            return True

        # This is the new config line that will be set
        if value is True:
            new_line = key
        elif value:
            new_line = f"{key} {value}"

        kwargs.update({"prepend_if_not_found": True})
    else:
        stanza = conf.get(key, dict())

        if stanza and not isinstance(stanza, dict):
            error_msg = (
                "Error: A setting for a dict was declared, but the "
                "configuration line given is not a dict"
            )
            raise SaltInvocationError(error_msg)

        if setting == stanza.get(value, False):
            _LOG.debug("Command '%s' already has: %s", value, setting)
            return True

        # We're going to be rewriting an entire stanza
        if setting:
            stanza[value] = setting
        else:
            del stanza[value]

        new_line = _dict_to_stanza(key, stanza)

        kwargs.update(
            {
                "pattern": f"^{key}.*?{{.*?}}",
                "flags": 24,
                "append_if_not_found": True,
            }
        )

    kwargs.update({"repl": new_line})
    _LOG.debug("Setting file '%s' line: %s", conf_file, new_line)

    return __salt__["file.replace"](**kwargs)


def _dict_to_stanza(key, stanza):
    """
    Convert a dict to a multi-line stanza
    """
    ret = ""
    for skey in stanza:
        value = stanza[skey]
        # Script directives (``prerotate``/``postrotate``/...) are stored as
        # a list of opaque body lines; emit them as a script block followed
        # by an ``endscript`` terminator. Without this, a stanza containing
        # both ``prerotate`` and ``postrotate`` would lose the second
        # ``endscript`` on round-trip — see issue #68293.
        if skey in _SCRIPT_DIRECTIVES and isinstance(value, list):
            ret += f"    {skey}\n"
            for body_line in value:
                ret += f"        {body_line}\n"
            ret += "    endscript\n"
            continue
        if value is True:
            value = ""
            stanza[skey] = ""
        ret += f"    {skey} {value}\n"
    return f"{key} {{\n{ret}}}"
