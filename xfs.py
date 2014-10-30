# -*- coding: utf-8 -*-
#
# The MIT License (MIT)
# Copyright (C) 2014 SUSE Linux Products GmbH
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions: 
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software. 
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE. 

'''
Module for managing XFS file systems.
'''

import os
import re
import logging

import salt.utils
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only work on POSIX-like systems
    '''
    return not salt.utils.is_windows()


def _get_xfs_devices():
    '''
    Get xfs devices
    '''

def _xfs_info_get_kv(serialized):
    '''
    Parse one line of the XFS info output.
    '''
    # No need to know sub-elements here
    if serialized.startswith("="):
        serialized = serialized[1:].strip()

    serialized = serialized.replace(" = ", "=*** ").replace(" =", "=")

    # Keywords has no spaces, values do
    opt = []
    for tkn in serialized.split(" "):
        if not opt or "=" in tkn:
            opt.append(tkn)
        else:
            opt[len(opt) - 1] = opt[len(opt) - 1] + " " + tkn

    # Preserve ordering
    return [tuple(items.split("=")) for items in opt]


def _parse_xfs_info(data):
    '''
    Parse output from "xfs_info" or "xfs_growfs -n".
    '''
    ret = {}
    s = re.compile("\s+")
    section = {}
    entry = None
    for line in [s.sub(" ", l).strip().replace(", ", " ") for l in data.split("\n")]:
        if not line: continue
        nfo = _xfs_info_get_kv(line)
        if not line.startswith("="):
            entry = nfo.pop(0)
            ret[entry[0]] = {'section' : entry[(entry[1] != '***' and 1 or 0)]}
        ret[entry[0]].update(dict(nfo))

    return ret


def info(device):
    '''
    Get filesystem geometry information.

    CLI Example:

    .. code-block:: bash

        salt '*' xfs.info /dev/sda1
    '''
    return _parse_xfs_info(__salt__['cmd.run']("xfs_info {0}".format(device)))
