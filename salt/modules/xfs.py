# -*- coding: utf-8 -*-
#
# The MIT License (MIT)
# Copyright (C) 2014 SUSE LLC
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

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import re
import time
import logging

# Import Salt libs
import salt.utils.files
import salt.utils.path
import salt.utils.platform
import salt.utils.data
from salt.exceptions import CommandExecutionError

# Import 3rd-party libs
from salt.ext import six
from salt.ext.six.moves import range  # pylint: disable=import-error,no-name-in-module,redefined-builtin

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only work on POSIX-like systems
    '''
    return not salt.utils.platform.is_windows() \
        and __grains__.get('kernel') == 'Linux'


def _verify_run(out, cmd=None):
    '''
    Crash to the log if command execution was not successful.
    '''
    if out.get("retcode", 0) and out['stderr']:
        if cmd:
            log.debug('Command: "%s"', cmd)

        log.debug('Return code: %s', out.get('retcode'))
        log.debug('Error output:\n%s', out.get('stderr', "N/A"))

        raise CommandExecutionError(out['stderr'])


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
    spr = re.compile(r'\s+')
    entry = None
    for line in [spr.sub(" ", l).strip().replace(", ", " ") for l in data.split("\n")]:
        if not line:
            continue
        nfo = _xfs_info_get_kv(line)
        if not line.startswith("="):
            entry = nfo.pop(0)
            ret[entry[0]] = {'section': entry[(entry[1] != '***' and 1 or 0)]}
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
            out['Media size'] = re.sub(r"^media file size\s+", "", line)
        elif line.startswith("dump complete:"):
            out['Dump complete'] = re.sub(r"^dump complete:\s+", "", line)
        elif line.startswith("Dump Status:"):
            out['Status'] = re.sub(r"^Dump Status:\s+", "", line)
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
    if not salt.utils.path.which("xfsdump"):
        raise CommandExecutionError("Utility \"xfsdump\" has to be installed or missing.")

    label = label and label or time.strftime("XFS dump for \"{0}\" of %Y.%m.%d, %H:%M".format(device),
                                             time.localtime()).replace("'", '"')
    cmd = ["xfsdump"]
    cmd.append("-F")                          # Force
    if not noerase:
        cmd.append("-E")                      # pre-erase
    cmd.append("-L '{0}'".format(label))      # Label
    cmd.append("-l {0}".format(level))        # Dump level
    cmd.append("-f {0}".format(destination))  # Media destination
    cmd.append(device)                        # Device

    cmd = ' '.join(cmd)
    out = __salt__['cmd.run_all'](cmd)
    _verify_run(out, cmd=cmd)

    return _xfsdump_output(out['stdout'])


def _xr_to_keyset(line):
    '''
    Parse xfsrestore output keyset elements.
    '''
    tkns = [elm for elm in line.strip().split(":", 1) if elm]
    if len(tkns) == 1:
        return "'{0}': ".format(tkns[0])
    else:
        key, val = tkns
        return "'{0}': '{1}',".format(key.strip(), val.strip())


def _xfs_inventory_output(out):
    '''
    Transform xfsrestore inventory data output to a Python dict source and evaluate it.
    '''
    data = []
    out = [line for line in out.split("\n") if line.strip()]

    # No inventory yet
    if len(out) == 1 and 'restore status' in out[0].lower():
        return {'restore_status': out[0]}

    ident = 0
    data.append("{")
    for line in out[:-1]:
        if len([elm for elm in line.strip().split(":") if elm]) == 1:
            n_ident = len(re.sub("[^\t]", "", line))
            if ident > n_ident:
                for step in range(ident):
                    data.append("},")
            ident = n_ident
            data.append(_xr_to_keyset(line))
            data.append("{")
        else:
            data.append(_xr_to_keyset(line))
    for step in range(ident + 1):
        data.append("},")
    data.append("},")

    # We are evaling into a python dict, a json load
    # would be safer
    data = eval('\n'.join(data))[0]  # pylint: disable=W0123
    data['restore_status'] = out[-1]

    return data


def inventory():
    '''
    Display XFS dump inventory without restoration.

    CLI Example:

    .. code-block:: bash

        salt '*' xfs.inventory
    '''
    out = __salt__['cmd.run_all']("xfsrestore -I")
    _verify_run(out)

    return _xfs_inventory_output(out['stdout'])


def _xfs_prune_output(out, uuid):
    '''
    Parse prune output.
    '''
    data = {}
    cnt = []
    cutpoint = False
    for line in [l.strip() for l in out.split("\n") if l]:
        if line.startswith("-"):
            if cutpoint:
                break
            else:
                cutpoint = True
                continue

        if cutpoint:
            cnt.append(line)

    for kset in [e for e in cnt[1:] if ':' in e]:
        key, val = [t.strip() for t in kset.split(":", 1)]
        data[key.lower().replace(" ", "_")] = val

    return data.get('uuid') == uuid and data or {}


def prune_dump(sessionid):
    '''
    Prunes the dump session identified by the given session id.

    CLI Example:

    .. code-block:: bash

        salt '*' xfs.prune_dump b74a3586-e52e-4a4a-8775-c3334fa8ea2c

    '''
    out = __salt__['cmd.run_all']("xfsinvutil -s {0} -F".format(sessionid))
    _verify_run(out)

    data = _xfs_prune_output(out['stdout'], sessionid)
    if data:
        return data

    raise CommandExecutionError("Session UUID \"{0}\" was not found.".format(sessionid))


def _blkid_output(out):
    '''
    Parse blkid output.
    '''
    flt = lambda data: [el for el in data if el.strip()]
    data = {}
    for dev_meta in flt(out.split("\n\n")):
        dev = {}
        for items in flt(dev_meta.strip().split("\n")):
            key, val = items.split("=", 1)
            dev[key.lower()] = val
        if dev.pop("type") == "xfs":
            dev['label'] = dev.get('label')
            data[dev.pop("devname")] = dev

    mounts = _get_mounts()
    for device in six.iterkeys(mounts):
        if data.get(device):
            data[device].update(mounts[device])

    return data


def devices():
    '''
    Get known XFS formatted devices on the system.

    CLI Example:

    .. code-block:: bash

        salt '*' xfs.devices
    '''
    out = __salt__['cmd.run_all']("blkid -o export")
    _verify_run(out)

    return _blkid_output(out['stdout'])


def _xfs_estimate_output(out):
    '''
    Parse xfs_estimate output.
    '''
    spc = re.compile(r"\s+")
    data = {}
    for line in [l for l in out.split("\n") if l.strip()][1:]:
        directory, bsize, blocks, megabytes, logsize = spc.sub(" ", line).split(" ")
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


def mkfs(device, label=None, ssize=None, noforce=None,
         bso=None, gmo=None, ino=None, lso=None, rso=None, nmo=None, dso=None):
    '''
    Create a file system on the specified device. By default wipes out with force.

    General options:

    * **label**: Specify volume label.
    * **ssize**: Specify the fundamental sector size of the filesystem.
    * **noforce**: Do not force create filesystem, if disk is already formatted.

    Filesystem geometry options:

    * **bso**: Block size options.
    * **gmo**: Global metadata options.
    * **dso**: Data section options. These options specify the location, size,
               and other parameters of the data section of the filesystem.
    * **ino**: Inode options to specify the inode size of the filesystem, and other inode allocation parameters.
    * **lso**: Log section options.
    * **nmo**: Naming options.
    * **rso**: Realtime section options.

    See the ``mkfs.xfs(8)`` manpage for a more complete description of corresponding options description.

    CLI Example:

    .. code-block:: bash

        salt '*' xfs.mkfs /dev/sda1
        salt '*' xfs.mkfs /dev/sda1 dso='su=32k,sw=6' noforce=True
        salt '*' xfs.mkfs /dev/sda1 dso='su=32k,sw=6' lso='logdev=/dev/sda2,size=10000b'
    '''

    getopts = lambda args: dict(((args and ("=" in args)
                                  and args or None)) and [kw.split("=") for kw in args.split(",")] or [])
    cmd = ["mkfs.xfs"]
    if label:
        cmd.append("-L")
        cmd.append("'{0}'".format(label))

    if ssize:
        cmd.append("-s")
        cmd.append(ssize)

    for switch, opts in [("-b", bso), ("-m", gmo), ("-n", nmo), ("-i", ino),
                         ("-d", dso), ("-l", lso), ("-r", rso)]:
        try:
            if getopts(opts):
                cmd.append(switch)
                cmd.append(opts)
        except Exception:
            raise CommandExecutionError("Wrong parameters \"{0}\" for option \"{1}\"".format(opts, switch))

    if not noforce:
        cmd.append("-f")
    cmd.append(device)

    cmd = ' '.join(cmd)
    out = __salt__['cmd.run_all'](cmd)
    _verify_run(out, cmd=cmd)

    return _parse_xfs_info(out['stdout'])


def modify(device, label=None, lazy_counting=None, uuid=None):
    '''
    Modify parameters of an XFS filesystem.

    CLI Example:

    .. code-block:: bash

        salt '*' xfs.modify /dev/sda1 label='My backup' lazy_counting=False
        salt '*' xfs.modify /dev/sda1 uuid=False
        salt '*' xfs.modify /dev/sda1 uuid=True
    '''
    if not label and lazy_counting is None and uuid is None:
        raise CommandExecutionError("Nothing specified for modification for \"{0}\" device".format(device))

    cmd = ['xfs_admin']
    if label:
        cmd.append("-L")
        cmd.append("'{0}'".format(label))

    if lazy_counting is False:
        cmd.append("-c")
        cmd.append("0")
    elif lazy_counting:
        cmd.append("-c")
        cmd.append("1")

    if uuid is False:
        cmd.append("-U")
        cmd.append("nil")
    elif uuid:
        cmd.append("-U")
        cmd.append("generate")
    cmd.append(device)

    cmd = ' '.join(cmd)
    _verify_run(__salt__['cmd.run_all'](cmd), cmd=cmd)

    out = __salt__['cmd.run_all']("blkid -o export {0}".format(device))
    _verify_run(out)

    return _blkid_output(out['stdout'])


def _get_mounts():
    '''
    List mounted filesystems.
    '''
    mounts = {}
    with salt.utils.files.fopen("/proc/mounts") as fhr:
        for line in salt.utils.data.decode(fhr.readlines()):
            device, mntpnt, fstype, options, fs_freq, fs_passno = line.strip().split(" ")
            if fstype != 'xfs':
                continue
            mounts[device] = {
                'mount_point': mntpnt,
                'options': options.split(","),
            }

    return mounts


def defragment(device):
    '''
    Defragment mounted XFS filesystem.
    In order to mount a filesystem, device should be properly mounted and writable.

    CLI Example:

    .. code-block:: bash

        salt '*' xfs.defragment /dev/sda1
    '''
    if device == '/':
        raise CommandExecutionError("Root is not a device.")

    if not _get_mounts().get(device):
        raise CommandExecutionError("Device \"{0}\" is not mounted".format(device))

    out = __salt__['cmd.run_all']("xfs_fsr {0}".format(device))
    _verify_run(out)

    return {
        'log': out['stdout']
    }
