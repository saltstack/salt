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
import time
import logging

import salt.utils
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only work on POSIX-like systems
    '''
    return not salt.utils.is_windows()


def _verify_run(out, cmd=None):
    '''
    Crash to the log if command execution was not successful.
    '''
    if out.get("retcode", 0) and out['stderr']:
        if cmd:
            log.debug('Command: "{0}"'.format(cmd))

        log.debug('Return code: {0}'.format(out.get('retcode')))
        log.debug('Error output:\n{0}'.format(out.get('stderr', "N/A")))

        raise CommandExecutionError(out['stderr'])


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
    out = __salt__['cmd.run_all']("xfs_info {0}".format(device))
    if out.get('stderr'):
        raise CommandExecutionError(out['stderr'].replace("xfs_info:", "").strip())
    return _parse_xfs_info(out['stdout'])


def _xfsdump_output(data):
    '''
    Parse CLI output of the xfsdump utility.
    '''
    out = {}
    summary = []
    summary_block = False

    for line in [l.strip() for l in data.split("\n") if l.strip()]:
        line = re.sub("^xfsdump: ", "", line)
        if line.startswith("session id:"):
            out['Session ID'] = line.split(" ")[-1]
        elif line.startswith("session label:"):
            out['Session label'] = re.sub("^session label: ", "", line)
        elif line.startswith("media file size"):
            out['Media size'] = re.sub("^media file size\s+", "", line)
        elif line.startswith("dump complete:"):
            out['Dump complete'] = re.sub("^dump complete:\s+", "", line)
        elif line.startswith("Dump Status:"):
            out['Status'] = re.sub("^Dump Status:\s+", "", line)
        elif line.startswith("Dump Summary:"):
            summary_block = True
            continue

        if line.startswith(" ") and summary_block:
            summary.append(line.strip())
        elif not line.startswith(" ") and summary_block:
            summary_block = False

    if summary:
        out['Summary'] = ' '.join(summary)

    return out


def dump(device, destination, level=0, label=None, noerase=None):
    '''
    Dump filesystem device to the media (file, tape etc).

    Required parameters:

    * **device**: XFS device, content of which to be dumped.
    * **destination**: Specifies a dump destination.

    Valid options are:

    * **label**: Label of the dump. Otherwise automatically generated label is used.
    * **level**: Specifies a dump level of 0 to 9.
    * **noerase**: Pre-erase media.

    Other options are not used in order to let ``xfsdump`` use its default
    values, as they are most optimal. See the ``xfsdump(8)`` manpage for
    a more complete description of these options.

    CLI Example:

    .. code-block:: bash

        salt '*' xfs.dump /dev/sda1 /detination/on/the/client
        salt '*' xfs.dump /dev/sda1 /detination/on/the/client label='Company accountancy'
        salt '*' xfs.dump /dev/sda1 /detination/on/the/client noerase=True
    '''
    if not salt.utils.which("xfsdump"):
        raise CommandExecutionError("Utility \"xfsdump\" has to be installed or missing.")

    label = label and label or time.strftime("XFS dump for \"{0}\" of %Y.%m.%d, %H:%M".format(device), 
                                             time.localtime())
    cmd = "xfsdump -F -E -L '{0}' -l {1} -f {2} {3}".format(label.replace("'", '"'), level, destination, device)
    out = __salt__['cmd.run_all'](cmd)
    _verify_run(out)

    return  _xfsdump_output(out['stdout'])


def _blkid_output(out):
    '''
    Parse blkid output.
    '''
    getval = lambda v: "=" in v and v.split("=")[-1].replace('"', "") or v
    data = {}
    for line in [l.strip() for l in out.split("\n") if l.strip()]:
        d_name, d_uuid, d_type, d_partuid = line.split(" ")
        if getval(d_type) == "xfs":
            data[d_name.replace(":", "")] = {
                'uuid': getval(d_uuid),
                'partuuid': getval(d_partuid),
            }

    return data


def devices():
    '''
    Get known XFS formatted devices on the system.

    CLI Example:

    .. code-block:: bash

        salt '*' xfs.devices
    '''
    out = __salt__['cmd.run_all']("blkid")
    _verify_run(out)

    return _blkid_output(out['stdout'])
    

def _xfs_estimate_output(out):
    '''
    Parse xfs_estimate output.
    '''
    s = re.compile("\s+")
    data = {}
    for line in [l for l in out.split("\n") if l.strip()][1:]:
        directory, bsize, blocks, megabytes, logsize = s.sub(" ", line).split(" ")
        data[directory] = {
            'block _size': bsize,
            'blocks': blocks,
            'megabytes': megabytes,
            'logsize': logsize,
        }

    return data


def estimate(path):
    '''
    Estimate the space that an XFS filesystem will take.
    For each directory estimate the space that directory would take
    if it were copied to an XFS filesystem.
    Estimation does not cross mount points.

    CLI Example:

    .. code-block:: bash

        salt '*' xfs.estimate /path/to/file
        salt '*' xfs.estimate /path/to/dir/*
    '''
    if not os.path.exists(path):
        raise CommandExecutionError("Path \"{0}\" was not found.".format(path))

    out = __salt__['cmd.run_all']("xfs_estimate -v {0}".format(path))
    _verify_run(out)

    return _xfs_estimate_output(out["stdout"])


def mkfs(device, label=None, bso=None, gmo=None, ds=None):
    '''
    Create a file system on the specified device

    Valid options are:

    * **ds**: Data section options. These options specify the location, size, and other parameters of the data section of the filesystem.
    * **bso**: Block size options.
    * **gmo**: Global metadata options.

    See the ``mkfs.xfs(8)`` manpage for a more complete description of corresponding options description.

    CLI Example:

    .. code-block:: bash

        salt '*' xfs.mkfs /dev/sda1 opts='acl,noexec'
    '''
    ds = ds and ("=" in ds) and ("," in ds) and ds or None
    getopts = lambda ds: ds and map(lambda kw: kw.split("="), ds.split(",")) or None

    cmd = ["mkfs.xfs"]
    if label:
        cmd.append("-L")
        cmd.append("'{0}'".format(label))

    for switch, opts in [("-b", bso), ("-m", gmo), ("-d", ds)]:
        if getopts(opts):
            cmd.append(switch)
            cmd.append(opts)

    cmd.append("-f")
    cmd.append(device)

    out = __salt__['cmd.run_all'](' '.join(cmd))
    _verify_run(out)

    return _parse_xfs_info(out['stdout'])
