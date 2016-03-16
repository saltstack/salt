# -*- coding: utf-8 -*-
'''
This module allows you to manage extended attributes on files or directories

.. code-block:: bash

    salt '*' xattr.list /path/to/file
'''
from __future__ import absolute_import

# Import Python Libs
import logging

# Import salt libs
import salt.utils.mac_utils
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)
__virtualname__ = "xattr"


def __virtual__():
    '''
    Only work on Mac OS
    '''
    if __grains__['os'] in ['MacOS', 'Darwin']:
        return __virtualname__
    return False


def list(path, hex=False):
    '''
    List all of the extended attributes on the given file/directory

    CLI Example:

    .. code-block:: bash

        salt '*' xattr.list /path/to/file
        salt '*' xattr.list /path/to/file hex=True

    path
        The file(s) to get attributes from

    hex
        Should the values be returned with forced hexadecimal values?
    '''
    hex_flag = ""
    if hex:
        hex_flag = "-x"
    cmd = 'xattr "{0}"'.format(path)
    try:
        ret = salt.utils.mac_utils.execute_return_result(cmd)
    except CommandExecutionError as msg:
        if 'No such file' in msg:
            raise CommandExecutionError('File not found')
        raise CommandExecutionError(msg)

    if not ret:
        return {}

    attrs_ids = ret.split("\n")
    attrs = {}

    for id in attrs_ids:
        attrs[id] = read(path, id, hex)

    return attrs


def read(path, attribute, hex=False):
    '''
    Read the given attributes on the given file/directory

    CLI Example:

    .. code-block:: bash

        salt '*' xattr.print /path/to/file com.test.attr
        salt '*' xattr.list /path/to/file com.test.attr hex=True

    path
        The file(s) to get the attribute from

    hex
        Should the value be returned with forced hexadecimal value?
    '''
    hex_flag = ""
    if hex:
        hex_flag = "-x"

    cmd = 'xattr -p {0} "{1}" "{2}"'.format(hex_flag, attribute, path)

    try:
        ret = salt.utils.mac_utils.execute_return_result(cmd)
    except CommandExecutionError as msg:
        if 'No such file' in msg:
            raise CommandExecutionError('File not found')
        raise CommandExecutionError(msg)

    return ret


def write(path, attribute, value, hex=False):
    '''
    Causes the given attribute name to be assigned the given value

    CLI Example:

    .. code-block:: bash

        salt '*' xattr.write /path/to/file "com.test.attr" "value"

    path
        The file(s) to get attributes from

    attribute
        The attribute name to be written to the file/directory

    value
        The value to assign to the given attribute

    hex
        Should the value be written as hexidecimal?
    '''
    hex_flag = ""
    if hex:
        hex_flag = "-x"

    cmd = 'xattr -w {0} "{1}" "{2}" "{3}"'.format(hex_flag, attribute, value, path)
    try:
        ret = salt.utils.mac_utils.execute_return_result(cmd)
    except CommandExecutionError as msg:
        if 'No such file' in msg:
            raise CommandExecutionError('File not found')
        raise CommandExecutionError(msg)

    return True


def delete(path, attribute):
    '''
    Causes the given attribute name to be removed from the given value

    CLI Example:

    .. code-block:: bash

        salt '*' xattr.delete /path/to/file "com.test.attr"

    path
        The file(s) to get attributes from

    attribute
        The attribute name to be removed to the file/directory

    '''
    cmd = 'xattr -d "{0}" "{1}"'.format(attribute, path)
    try:
        ret = salt.utils.mac_utils.execute_return_result(cmd)
    except CommandExecutionError as msg:
        if 'No such file' in msg:
            raise CommandExecutionError('File not found')
        raise CommandExecutionError(msg)

    return ret


def clear(path):
    '''
    Causes the all attributes on the file/directory to be removed

    CLI Example:

    .. code-block:: bash

        salt '*' xattr.delete /path/to/file "com.test.attr"

    path
        The file(s) to clear the attributes from

    attribute
        The attribute name to be removed to the file/directory

    '''
    cmd = 'xattr -c "{0}"'.format(path)
    try:
        ret = salt.utils.mac_utils.execute_return_result(cmd)
    except CommandExecutionError as msg:
        if 'No such file' in msg:
            raise CommandExecutionError('File not found')
        raise CommandExecutionError(msg)

    return ret
