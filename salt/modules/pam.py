# -*- coding: utf-8 -*-
"""
Support for pam
"""
from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import python libs
import os

# Import salt libs
import salt.utils.files

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "pam"


def __virtual__():
    """
    Set the virtual name for the module
    """
    return __virtualname__


def _parse(contents=None, file_name=None):
    """
    Parse a standard pam config file
    """
    if contents:
        pass
    elif file_name and os.path.exists(file_name):
        with salt.utils.files.fopen(file_name, "r") as ifile:
            contents = salt.utils.stringutils.to_unicode(ifile.read())
    else:
        log.error('File "%s" does not exist', file_name)
        return False

    rules = []
    for line in contents.splitlines():
        if not line:
            continue
        if line.startswith("#"):
            continue
        control_flag = ""
        module = ""
        arguments = []
        comps = line.split()
        interface = comps[0]
        position = 1
        if comps[1].startswith("["):
            control_flag = comps[1].replace("[", "")
            for part in comps[2:]:
                position += 1
                if part.endswith("]"):
                    control_flag += " {0}".format(part.replace("]", ""))
                    position += 1
                    break
                else:
                    control_flag += " {0}".format(part)
        else:
            control_flag = comps[1]
            position += 1
        module = comps[position]
        if len(comps) > position:
            position += 1
            arguments = comps[position:]
        rules.append(
            {
                "interface": interface,
                "control_flag": control_flag,
                "module": module,
                "arguments": arguments,
            }
        )
    return rules


def read_file(file_name):
    """
    This is just a test function, to make sure parsing works

    CLI Example:

    .. code-block:: bash

        salt '*' pam.read_file /etc/pam.d/login
    """
    return _parse(file_name=file_name)
