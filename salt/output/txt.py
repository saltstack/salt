"""
Simple text outputter
=====================

The ``txt`` outputter has been developed to make the output from shell commands
on minions appear as they do when the command is executed on the minion.

CLI Example:

.. code-block:: bash

    salt '*' foo.bar --out=txt
"""

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
                    ret += f"{key}: {line}\n"
            except AttributeError:
                ret += f"{key}: {value}\n"
    else:
        try:
            ret += data + "\n"
        except TypeError:
            # For non-dictionary, non-string data, just use print
            ret += f"{pprint.pformat(data)}\n"

    return ret
