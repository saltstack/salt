"""
This module allows you to manage extended attributes on files or directories

.. code-block:: bash

    salt '*' xattr.list /path/to/file
"""

import logging

import salt.utils.args
import salt.utils.mac_utils
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

__virtualname__ = "xattr"
__func_alias__ = {
    "list_": "list",
}


def __virtual__():
    """
    Only work on Mac OS
    """
    if __grains__["os"] in ["MacOS", "Darwin"]:
        return __virtualname__
    return (False, "Only available on Mac OS systems")


def list_(path, **kwargs):
    """
    List all of the extended attributes on the given file/directory

    :param str path: The file(s) to get attributes from

    :param bool hex: Return the values with forced hexadecimal values

    :return: A dictionary containing extended attributes and values for the
        given file
    :rtype: dict

    :raises: CommandExecutionError on file not found or any other unknown error

    CLI Example:

    .. code-block:: bash

        salt '*' xattr.list /path/to/file
        salt '*' xattr.list /path/to/file hex=True
    """
    kwargs = salt.utils.args.clean_kwargs(**kwargs)
    hex_ = kwargs.pop("hex", False)
    if kwargs:
        salt.utils.args.invalid_kwargs(kwargs)

    cmd = ["xattr", path]
    try:
        ret = salt.utils.mac_utils.execute_return_result(cmd)
    except CommandExecutionError as exc:
        if "No such file" in exc.strerror:
            raise CommandExecutionError("File not found: {}".format(path))
        raise CommandExecutionError("Unknown Error: {}".format(exc.strerror))

    if not ret:
        return {}

    attrs_ids = ret.split("\n")
    attrs = {}

    for id_ in attrs_ids:
        attrs[id_] = read(path, id_, **{"hex": hex_})

    return attrs


def read(path, attribute, **kwargs):
    """
    Read the given attributes on the given file/directory

    :param str path: The file to get attributes from

    :param str attribute: The attribute to read

    :param bool hex: Return the values with forced hexadecimal values

    :return: A string containing the value of the named attribute
    :rtype: str

    :raises: CommandExecutionError on file not found, attribute not found, and
        any other unknown error

    CLI Example:

    .. code-block:: bash

        salt '*' xattr.read /path/to/file com.test.attr
        salt '*' xattr.read /path/to/file com.test.attr hex=True
    """
    kwargs = salt.utils.args.clean_kwargs(**kwargs)
    hex_ = kwargs.pop("hex", False)
    if kwargs:
        salt.utils.args.invalid_kwargs(kwargs)

    cmd = ["xattr", "-p"]
    if hex_:
        cmd.append("-x")
    cmd.extend([attribute, path])

    try:
        ret = salt.utils.mac_utils.execute_return_result(cmd)
    except CommandExecutionError as exc:
        if "No such file" in exc.strerror:
            raise CommandExecutionError("File not found: {}".format(path))
        if "No such xattr" in exc.strerror:
            raise CommandExecutionError("Attribute not found: {}".format(attribute))
        raise CommandExecutionError("Unknown Error: {}".format(exc.strerror))

    return ret


def write(path, attribute, value, **kwargs):
    """
    Causes the given attribute name to be assigned the given value

    :param str path: The file(s) to get attributes from

    :param str attribute: The attribute name to be written to the file/directory

    :param str value: The value to assign to the given attribute

    :param bool hex: Set the values with forced hexadecimal values

    :return: True if successful, otherwise False
    :rtype: bool

    :raises: CommandExecutionError on file not found or any other unknown error

    CLI Example:

    .. code-block:: bash

        salt '*' xattr.write /path/to/file "com.test.attr" "value"

    """
    kwargs = salt.utils.args.clean_kwargs(**kwargs)
    hex_ = kwargs.pop("hex", False)
    if kwargs:
        salt.utils.args.invalid_kwargs(kwargs)

    cmd = ["xattr", "-w"]
    if hex_:
        cmd.append("-x")
    cmd.extend([attribute, value, path])

    try:
        salt.utils.mac_utils.execute_return_success(cmd)
    except CommandExecutionError as exc:
        if "No such file" in exc.strerror:
            raise CommandExecutionError("File not found: {}".format(path))
        raise CommandExecutionError("Unknown Error: {}".format(exc.strerror))

    return read(path, attribute, **{"hex": hex_}) == value


def delete(path, attribute):
    """
    Removes the given attribute from the file

    :param str path: The file(s) to get attributes from

    :param str attribute: The attribute name to be deleted from the
        file/directory

    :return: True if successful, otherwise False
    :rtype: bool

    :raises: CommandExecutionError on file not found, attribute not found, and
        any other unknown error

    CLI Example:

    .. code-block:: bash

        salt '*' xattr.delete /path/to/file "com.test.attr"
    """
    cmd = 'xattr -d "{}" "{}"'.format(attribute, path)
    try:
        salt.utils.mac_utils.execute_return_success(cmd)
    except CommandExecutionError as exc:
        if "No such file" in exc.strerror:
            raise CommandExecutionError("File not found: {}".format(path))
        if "No such xattr" in exc.strerror:
            raise CommandExecutionError("Attribute not found: {}".format(attribute))
        raise CommandExecutionError("Unknown Error: {}".format(exc.strerror))

    return attribute not in list_(path)


def clear(path):
    """
    Causes the all attributes on the file/directory to be removed

    :param str path: The file(s) to get attributes from

    :return: True if successful, otherwise False

    :raises: CommandExecutionError on file not found or any other unknown error

    CLI Example:

    .. code-block:: bash

        salt '*' xattr.delete /path/to/file "com.test.attr"
    """
    cmd = 'xattr -c "{}"'.format(path)
    try:
        salt.utils.mac_utils.execute_return_success(cmd)
    except CommandExecutionError as exc:
        if "No such file" in exc.strerror:
            raise CommandExecutionError("File not found: {}".format(path))
        raise CommandExecutionError("Unknown Error: {}".format(exc.strerror))

    return list_(path) == {}
