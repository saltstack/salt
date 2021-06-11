# -*- coding: utf-8 -*-
"""
This runner is designed to mirror the execution module config.py, but for
master settings
"""
from __future__ import absolute_import, print_function, unicode_literals

import salt.utils.data
import salt.utils.sdb


def get(key, default="", delimiter=":"):
    """
    Retrieve master config options, with optional nesting via the delimiter
    argument.

    **Arguments**

    default

        If the key is not found, the default will be returned instead

    delimiter

        Override the delimiter used to separate nested levels of a data
        structure.

    CLI Example:

    .. code-block:: bash

        salt-run config.get gitfs_remotes
        salt-run config.get file_roots:base
        salt-run config.get file_roots,base delimiter=','
    """
    ret = salt.utils.data.traverse_dict_and_list(
        __opts__, key, default="_|-", delimiter=delimiter
    )
    if ret == "_|-":
        return default
    else:
        return salt.utils.sdb.sdb_get(ret, __opts__)
