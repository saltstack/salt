# -*- coding: utf-8 -*-
"""
Simple text outputter
=====================

The ``txt`` outputter has been developed to make the output from shell commands
on minions appear as they do when the command is executed on the minion.

CLI Example:

.. code-block:: bash

    salt '*' foo.bar --out=txt
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import pprint


def output(data, **kwargs):  # pylint: disable=unused-argument
    """
    Output the data in lines, very nice for running commands
    """
    ret = ""
    if hasattr(data, "keys"):
        for key in data:
            value = data[key]
            # Don't blow up on non-strings
            try:
                for line in value.splitlines():
                    ret += "{0}: {1}\n".format(key, line)
            except AttributeError:
                ret += "{0}: {1}\n".format(key, value)
    else:
        try:
            ret += data + "\n"
        except TypeError:
            # For non-dictionary, non-string data, just use print
            ret += "{0}\n".format(pprint.pformat(data))

    return ret
