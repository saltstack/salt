"""
Set defaults settings on macOS.

This module uses defaults cli under the hood to read and write defaults on macOS.

Thus, the module is limited to the capabilities of the defaults command.

Read macOS defaults help page for more information on defaults command.

"""

import logging
import re

import salt.utils.data
import salt.utils.platform
import salt.utils.versions
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)
__virtualname__ = "macdefaults"


def __virtual__():
    """
    Only works on macOS

    """
    if salt.utils.platform.is_darwin():
        return __virtualname__
    return False


def write(domain, key, value, vtype=None, user=None, type=None):
    """
    Write a default to the system

    Limitations:
      - There is no multi-level support for arrays and dictionaries
      - Internal values types for arrays and dictionaries cannot be specified

    CLI Example:

    .. code-block:: bash

        salt '*' macdefaults.write com.apple.CrashReporter DialogType Server

        salt '*' macdefaults.write NSGlobalDomain ApplePersistence True vtype=bool

    domain
        The name of the domain to write to

    key
        The key of the given domain to write to

    value
        The value to write to the given key

    vtype
        The type of value to be written, valid types are string, data, int[eger],
        float, bool[ean], date, array, array-add, dict, dict-add

    type
        Deprecated! Use vtype instead
        type collides with Python's built-in type() function
        This parameter will be removed in 3009

    user
        The user to write the defaults to

    """
    if type is not None:
        salt.utils.versions.warn_until(
            3009,
            "The 'type' argument in macdefaults.write is deprecated. Use 'vtype' instead.",
        )
        if vtype is None:
            vtype = type
        else:
            log.warning(
                "The 'vtype' argument in macdefaults.write takes precedence over 'type'."
            )

    if vtype is None:
        vtype = "string"

    if vtype in ("bool", "boolean"):
        value = _convert_to_defaults_boolean(value)

    if isinstance(value, dict):
        value = list((k, v) for k, v in value.items())
        value = salt.utils.data.flatten(value)
    elif isinstance(value, (int, float, bool, str)):
        value = [value]
    elif not isinstance(value, list):
        raise ValueError("Value must be a list, dict, int, float, bool, or string")

    # Quote values that are neither integers nor floats
    value = map(lambda v: str(v) if isinstance(v, (int, float)) else f'"{v}"', value)

    cmd = f'write "{domain}" "{key}" -{vtype} {" ".join(value)}'
    return _run_defaults_cmd(cmd, runas=user)


def read(domain, key, user=None):
    """
    Read a default from the system

    CLI Example:

    .. code-block:: bash

        salt '*' macdefaults.read com.apple.CrashReporter DialogType

        salt '*' macdefaults.read NSGlobalDomain ApplePersistence

    domain
        The name of the domain to read from

    key
        The key of the given domain to read from

    user
        The user to read the defaults as

    """
    cmd = f'read "{domain}" "{key}"'
    ret = _run_defaults_cmd(cmd, runas=user)

    if ret["retcode"] != 0:
        if "does not exist" in ret["stderr"]:
            return None
        raise CommandExecutionError(f"Failed to read default: {ret['stderr']}")

    # Type cast the value
    try:
        vtype = read_type(domain, key, user)
    except CommandExecutionError:
        vtype = None

    return _default_to_python(ret["stdout"].strip(), vtype)


def delete(domain, key, user=None):
    """
    Delete a default from the system

    CLI Example:

    .. code-block:: bash

        salt '*' macdefaults.delete com.apple.CrashReporter DialogType

        salt '*' macdefaults.delete NSGlobalDomain ApplePersistence

    domain
        The name of the domain to delete from

    key
        The key of the given domain to delete

    user
        The user to delete the defaults with

    """
    cmd = f'delete "{domain}" "{key}"'
    return _run_defaults_cmd(cmd, runas=user)


def read_type(domain, key, user=None):
    """
    Read a default type from the system
    If the key is not found, None is returned.

    CLI Example:

    .. code-block:: bash

        salt '*' macdefaults.read_type com.apple.CrashReporter DialogType

        salt '*' macdefaults.read_type NSGlobalDomain ApplePersistence

    domain
        The name of the domain to read from

    key
        The key of the given domain to read the type of

    user
        The user to read the defaults as

    """
    cmd = f'read-type "{domain}" "{key}"'
    ret = _run_defaults_cmd(cmd, runas=user)

    if ret["retcode"] != 0:
        if "does not exist" in ret["stderr"]:
            return None
        raise CommandExecutionError(f"Failed to read type: {ret['stderr']}")

    return re.sub(r"^Type is ", "", ret["stdout"].strip())


def _default_to_python(value, vtype=None):
    """
    Cast the value returned by the defaults command in vytpe to Python type

    value
        The value to cast

    vtype
        The type to cast the value to

    """
    if vtype in ["integer", "int"]:
        return int(value)
    if vtype == "float":
        return float(value)
    if vtype in ["boolean", "bool"]:
        return value in ["1", "TRUE", "YES"]
    if vtype == "array":
        return _parse_defaults_array(value)
    if vtype in ["dict", "dictionary"]:
        return _parse_defaults_dict(value)
    return value


def _parse_defaults_array(value):
    """
    Parse an array from a string returned by `defaults read`
    and returns the array content as a list

    value
        A multiline string with the array content, including the surrounding parenthesis

    """
    lines = value.splitlines()
    if not re.match(r"\s*\(", lines[0]) or not re.match(r"\s*\)", lines[-1]):
        raise ValueError("Invalid array format")

    lines = lines[1:-1]

    # Remove leading and trailing spaces
    lines = list(map(lambda line: line.strip(), lines))

    # Remove trailing commas
    lines = list(map(lambda line: re.sub(r",?$", "", line), lines))

    # Remove quotes
    lines = list(map(lambda line: line.strip('"'), lines))

    # Convert to numbers if possible
    lines = list(map(_convert_to_number_if_possible, lines))

    return lines


def _parse_defaults_dict(value):
    """
    Parse a dictionary from a string returned by `defaults read`
    and returns the dictionary content as a Python dictionary

    value (str):
        A multiline string with the dictionary content, including the surrounding curly braces

    """
    lines = value.splitlines()
    if not re.match(r"\s*\{", lines[0]) or not re.match(r"\s*\}", lines[-1]):
        raise ValueError("Invalid dictionary format")

    contents = {}
    lines = list(map(lambda line: line.strip(), lines[1:-1]))
    for line in lines:
        key, value = re.split(r"\s*=\s*", line.strip())
        if re.match(r"\s*(\(|\{)", value):
            raise ValueError("Nested arrays and dictionaries are not supported")

        value = re.sub(r";?$", "", value)
        contents[key] = _convert_to_number_if_possible(value.strip('"'))

    return contents


def _convert_to_number_if_possible(value):
    """
    Convert a string to a number if possible

    value
        The string to convert

    """
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


def _convert_to_defaults_boolean(value):
    """
    Convert a boolean to a string that can be used with the defaults command

    value
        The boolean value to convert

    """
    if value in (True, 1):
        return "TRUE"
    if value in (False, 0):
        return "FALSE"

    BOOLEAN_ALLOWED_VALUES = ["TRUE", "YES", "FALSE", "NO"]
    if value not in BOOLEAN_ALLOWED_VALUES:
        msg = "Value must be a boolean or a string of "
        msg += ", ".join(BOOLEAN_ALLOWED_VALUES)
        raise ValueError(msg)

    return value


def _run_defaults_cmd(action, runas=None):
    """
    Run the 'defaults' command with the given action

    action
        The action to perform with all of its parameters
        Example: 'write com.apple.CrashReporter DialogType "Server"'

    runas
        The user to run the command as

    """
    ret = __salt__["cmd.run_all"](f"defaults {action}", runas=runas)

    # Remove timestamp from stderr if found
    if ret["retcode"] != 0:
        ret["stderr"] = _remove_timestamp(ret["stderr"])

    return ret


def _remove_timestamp(text):
    """
    Remove the timestamp from the output of the defaults command if found

    text
        The text to remove the timestamp from

    """
    pattern = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d{3})?\s+defaults\[\d+\:\d+\]"
    if re.match(pattern, text):
        text_lines = text.strip().splitlines()
        return "\n".join(text_lines[1:])

    return text
