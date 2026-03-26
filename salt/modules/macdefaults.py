"""
Set defaults settings on macOS.

This module uses defaults cli under the hood to import and export defaults on macOS.

However, it uses the plistlib package to handle the conversion between the defaults
output and Python dictionaries. It is also used to create the plist files to import
the defaults.

Read plistlib documentation for more information on how the conversion is done:
https://docs.python.org/3/library/plistlib.html

"""

import logging
import plistlib
import re
import tempfile
from datetime import datetime

import salt.utils.files
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


def write(
    domain,
    key,
    value,
    vtype=None,
    user=None,
    key_separator=None,
    dict_merge=False,
    array_add=False,
    type=None,
):
    """
    Write a default to the system

    CLI Example:

    .. code-block:: bash

        salt '*' macdefaults.write com.apple.Finder DownloadsFolderListViewSettingsVersion 1

        salt '*' macdefaults.write com.apple.Finder ComputerViewSettings.CustomViewStyle "icnv" key_separator='.'

        salt '*' macdefaults.write com.apple.Dock lastShowIndicatorTime 737720347.089987 vtype=date

        salt '*' macdefaults.write NSGlobalDomain com.apple.sound.beep.sound "/System/Library/Sounds/Blow.aiff"

    domain
        The name of the domain to write to

    key
        The key of the given domain to write to.
        It can be a nested key/index separated by `key_separator`.

    key_separator
        The separator to use when splitting the key into a list of keys.
        If None, the key will not be split (Default).

        .. versionadded:: 3008.0

    value
        The value to write to the given key.
        Dates should be in the format 'YYYY-MM-DDTHH:MM:SSZ'

    vtype
        The type of value to be written.

        Valid types are string, int[eger], float, bool[ean], date and data.

        dict and array are also valid types but are only used for validation.

        dict-add and array-add are supported too.
        They will behave as their counterparts dict and array but will set
        their corresponding sibling options dict_merge and array_add to True.

        This parameter is optional. It will be used to cast the values to the
        specified type before writing them to the system. If not provided, the
        type will be inferred from the value.

        Useful when writing values such as dates or binary data.

    type
        Deprecated! Use vtype instead
        type collides with Python's built-in type() function
        This parameter will be removed in 3009

    user
        The user to write the defaults to

    dict_merge
        Merge the value into the existing dictionary.
        If current value is not a dictionary this option will be ignored.
        This option will be set to True if vtype is dict-add.

        .. versionadded:: 3008.0

    array_add
        Append the value to the array.
        If current value is not a list this option will be ignored.
        This option will be set to True if vtype is array-add.

        .. versionadded:: 3008.0

    Raises:
        KeyError: When the key is not found in the domain
        IndexError: When the key is not a valid array index

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

    plist = _load_plist(domain, user=user) or {}
    keys = [key] if key_separator is None else key.split(key_separator)
    last_key = keys[-1]

    # Traverse the plist
    container = _traverse_keys(plist, keys[:-1])
    if container is None:
        raise KeyError(f"Key not found: {key} for domain: {domain}")

    current_value = None
    if isinstance(container, dict):
        current_value = container.get(last_key)
    elif isinstance(container, list) and last_key.isdigit():
        last_key = int(last_key)
        if -len(container) <= last_key < len(container):
            current_value = container[last_key]
        else:
            raise IndexError(f"Index {last_key} is out of range for domain: {domain}")

    # Write/Update the new value
    if vtype is not None:
        if vtype == "array-add":
            array_add = True
        elif vtype == "dict-add":
            dict_merge = True
        value = cast_value_to_vtype(value, vtype)

    if isinstance(current_value, dict) and isinstance(value, dict) and dict_merge:
        container[last_key].update(value)
    elif isinstance(current_value, list) and array_add:
        if isinstance(value, list):
            container[last_key].extend(value)
        else:
            container[last_key].append(value)
    else:
        container[last_key] = value

    return _save_plist(domain, plist, user=user)


def read(domain, key, user=None, key_separator=None):
    """
    Read a default from the system

    CLI Example:

    .. code-block:: bash

        salt '*' macdefaults.read NSGlobalDomain ApplePersistence

        salt '*' macdefaults.read NSGlobalDomain key.with.dots-subKey key_separator="-"

        salt '*' macdefaults.read com.apple.Dock persistent-apps.1.title-data.file-label key_separator='.'

    domain
        The name of the domain to read from

    key
        The key of the given domain to read from.
        It can be a nested key/index separated by `key_separator`.

    key_separator
        The separator to use when splitting the key into a list of keys.
        If None, the key will not be split (Default).

        .. versionadded:: 3008.0

    user
        The user to read the defaults from

    Returns:
        The current value for the given key, or None if the key does not exist.

    """
    plist = _load_plist(domain, user)
    if plist is None:
        return None

    keys = [key] if key_separator is None else key.split(key_separator)

    return _traverse_keys(plist, keys)


def delete(domain, key, user=None, key_separator=None):
    """
    Delete a default from the system

    CLI Example:

    .. code-block:: bash

        salt '*' macdefaults.delete com.apple.CrashReporter DialogType

        salt '*' macdefaults.delete NSGlobalDomain ApplePersistence

        salt '*' macdefaults.delete NSGlobalDomain key.with.dots key_separator='.'

    domain
        The name of the domain to delete from

    key
        The key of the given domain to delete.
        It can be a nested key separated by `key_separator`.

    key_separator
        The separator to use when splitting the key into a list of keys.
        If None, the key will not be split (Default).

        .. versionadded:: 3008.0

    user
        The user to delete the defaults with

    """
    plist = _load_plist(domain, user=user)
    if plist is None:
        return None

    keys = [key] if key_separator is None else key.split(key_separator)

    # Traverse the plist til the penultimate key.
    # Last key must be handled separately since we
    # need the parent dictionary to delete that key.
    target = _traverse_keys(plist, keys[:-1])
    if target is None:
        return None

    # Delete the last key if it exists and update defaults
    last_key = keys[-1]
    key_in_plist = False
    if isinstance(target, dict) and last_key in target:
        key_in_plist = True

    elif (
        isinstance(target, list)
        and last_key.isdigit()
        and -len(target) <= int(last_key) < len(target)
    ):
        key_in_plist = True
        last_key = int(last_key)

    if not key_in_plist:
        return None

    del target[last_key]
    return _save_plist(domain, plist, user=user)


def cast_value_to_vtype(value, vtype):
    """
    Convert the value to the specified vtype.
    If the value cannot be converted, a ValueError is raised.

    CLI Example:

    .. code-block:: bash

        salt '*' macdefaults.cast_value_to_vtype "1.35" "float"

        salt '*' macdefaults.cast_value_to_vtype "2024-06-23T09:33:44Z" "date"

        salt '*' macdefaults.cast_value_to_vtype "737720347.089987" "date"

    value
        The value to be converted

    vtype
        The type to convert the value to.
        Valid types are string, int[eger], float, bool[ean], date, data,
        array, array-add, dict, dict-add

    Raises:
        ValueError: When the value cannot be converted to the specified type

    Returns:
        The converted value

    .. versionadded:: 3008.0
    """
    # Boolean
    if vtype in ("bool", "boolean"):
        if isinstance(value, str):
            if value.lower() in ("true", "yes", "1"):
                value = True
            elif value.lower() in ("false", "no", "0"):
                value = False
            else:
                raise ValueError(f"Invalid value for boolean: '{value}'")
        elif value in (0, 1):
            value = bool(value)
        elif not isinstance(value, bool):
            raise ValueError(f"Invalid value for boolean: '{value}'")
    # String
    elif vtype == "string":
        if isinstance(value, bool):
            value = "YES" if value else "NO"
        elif isinstance(value, (int, float)):
            value = str(value)
        elif isinstance(value, datetime):
            value = value.strftime("%Y-%m-%dT%H:%M:%SZ")
        elif isinstance(value, bytes):
            value = value.decode()
    # Integer
    elif vtype in ("int", "integer"):
        value = int(value)
    # Float
    elif vtype == "float":
        value = float(value)
    # Date
    elif vtype == "date":
        if not isinstance(value, datetime):
            try:
                value = datetime.fromtimestamp(float(value))
            except ValueError as e:
                if re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value):
                    value = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
                else:
                    raise ValueError(f"Invalid date format: '{value}'") from e
    # Data
    elif vtype == "data":
        if isinstance(value, str):
            value = value.encode()
        elif not isinstance(value, bytes):
            raise ValueError(f"Invalid value for data: '{value}'")
    # Dictionary
    elif vtype in ("dict", "dict-add"):
        if not isinstance(value, dict):
            raise ValueError(f"Invalid value for dictionary: '{value}'")
    # Array
    elif vtype in ("array", "array-add"):
        if not isinstance(value, list):
            raise ValueError(f"Invalid value for array: '{value}'")
    else:
        raise ValueError(f"Invalid type: '{vtype}'")

    return value


def _load_plist(domain, user=None):
    """
    Load a plist from the system and return it as a dictionary

    domain
        The name of the domain to read from

    user
        The user to read the defaults as. Defaults to root (None).

    Raises:
        CommandExecutionError: When the defaults command fails
        Other exceptions thrown by plistlib.loads

    Returns:
        A dictionary with the plist contents, or None if the domain does not exist.
    """
    cmd = f'export "{domain}" -'
    ret = _run_defaults_cmd(cmd, runas=user)

    if ret["retcode"] != 0:
        raise CommandExecutionError(f"Failed to export defaults: {ret['stderr']}")

    plist = plistlib.loads(ret["stdout"].encode())
    if not plist:
        return None

    return plist


def _save_plist(domain, plist, user=None):
    """
    Save a plist dictionary to the system

    domain
        The name of the domain to read from

    plist
        The dictionary to export as a plist

    user
        The user to export the defaults to. Defaults to root (None).

    Raises:
        CommandExecutionError: When the defaults command fails
        Other exceptions thrown by plistlib.dump

    Returns:
        A dictionary with the defaults command result
    """
    with tempfile.TemporaryDirectory(prefix="salt_macdefaults") as tempdir:
        # File must exist until the defaults command is run.
        # That's why a temporary directory is used instead of a temporary file.
        # NOTE: Starting with Python 3.12 NamedTemporaryFile has the parameter
        # delete_on_close which can be set to False. It would simplify this method.
        file_name = __salt__["file.join"](tempdir, f"{domain}.plist")
        with salt.utils.files.fopen(file_name, "wb") as fp:
            plistlib.dump(plist, fp)
        if user is not None:
            __salt__["file.chown"](tempdir, user, None)
            __salt__["file.chown"](file_name, user, None)
        cmd = f'import "{domain}" "{file_name}"'
        return _run_defaults_cmd(cmd, runas=user)


def _traverse_keys(plist, keys):
    """
    Returns the value of the given keys in the plist

    plist
        The plist dictionary to retrieve the value from

    keys
        An array with the sequence of keys to traverse

    Returns:
        The value of the given keys in the plist, or None if the keys do not exist.
    """
    value = plist
    for k in keys:
        if isinstance(value, dict):
            value = value.get(k)
        elif (
            isinstance(value, list)
            and k.isdigit()
            and -len(value) <= int(k) < len(value)
        ):
            value = value[int(k)]
        else:
            value = None

        if value is None:
            return None

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
