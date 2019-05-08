# -*- coding: utf-8 -*-
'''
Module to provide DRBD functionality to Salt

.. versionadded:: pending

:maintainer:    Nick Wang <nwang@suse.com>
:maturity:      alpha
:depends:       ``drbdadm`` drbd utils
:platform:      all

:configuration: This module requires drbd kernel module and drbd utils tool

.. code-block:: yaml

'''
from __future__ import absolute_import, print_function, unicode_literals

import logging
from salt.ext import six

LOGGER = logging.getLogger(__name__)


def _analyse_overview_field(content):
    '''
    Split the field in drbd-overview
    '''
    if "(" in content:
        # Output like "Connected(2*)" or "UpToDate(2*)"
        return content.split("(")[0], content.split("(")[0]
    elif "/" in content:
        # Output like "Primar/Second" or "UpToDa/UpToDa"
        return content.split("/")[0], content.split("/")[1]

    return content, ""


def _count_spaces_startswith(line):
    '''
    Count the number of spaces before the first character
    '''
    if line.split('#')[0].strip() == "":
        return None

    spaces = 0
    for i in line:
        if i.isspace():
            spaces += 1
        else:
            return spaces


def _analyse_status_type(line):
    '''
    Figure out the sections in drbdadm status
    '''
    spaces = _count_spaces_startswith(line)

    if spaces is None:
        return ''

    switch = {
        0: 'RESOURCE',
        2: {' disk:': 'LOCALDISK', ' role:': 'PEERNODE', ' connection:': 'PEERNODE'},
        4: {' peer-disk:': 'PEERDISK'}
    }

    ret = switch.get(spaces, 'UNKNOWN')

    # isinstance(ret, str) only works when run directly, calling need unicode(six)
    if isinstance(ret, six.text_type):
        return ret

    for x in ret:
        if x in line:
            return ret[x]


def _add_res(line):
    '''
    Analyse the line of local resource of ``drbdadm status``
    '''
    fields = line.strip().split()

    if __context__['drbd.resource']:
        __context__['drbd.statusret'].append(__context__['drbd.resource'])
        __context__['drbd.resource'] = {}

    resource = {}
    resource["resource name"] = fields[0]
    resource["local role"] = fields[1].split(":")[1]
    resource["local volumes"] = []
    resource["peer nodes"] = []

    __context__['drbd.resource'] = resource


def _add_volume(line):
    '''
    Analyse the line of volumes of ``drbdadm status``
    '''
    section = _analyse_status_type(line)
    fields = line.strip().split()

    volume = {}
    for field in fields:
        volume[field.split(':')[0]] = field.split(':')[1]

    if section == 'LOCALDISK':
        if 'drbd.resource' not in __context__:  # pragma: no cover
            # Should always be called after _add_res
            __context__['drbd.resource'] = {}
            __context__['drbd.resource']['local volumes'] = []

        __context__['drbd.resource']['local volumes'].append(volume)
    else:
        # 'PEERDISK'
        if 'drbd.lastpnodevolumes' not in __context__:  # pragma: no cover
            # Insurance refer to:
            # https://docs.saltstack.com/en/latest/topics/development/modules/developing.html#context
            # Should always be called after _add_peernode
            __context__['drbd.lastpnodevolumes'] = []

        __context__['drbd.lastpnodevolumes'].append(volume)


def _add_peernode(line):
    '''
    Analyse the line of peer nodes of ``drbdadm status``
    '''
    fields = line.strip().split()

    peernode = {}
    peernode["peernode name"] = fields[0]
    #Could be role or connection:
    peernode[fields[1].split(":")[0]] = fields[1].split(":")[1]
    peernode["peer volumes"] = []

    if 'drbd.resource' not in __context__:  # pragma: no cover
        # Should always be called after _add_res
        __context__['drbd.resource'] = {}
        __context__['drbd.resource']['peer nodes'] = []

    __context__['drbd.resource']["peer nodes"].append(peernode)

    __context__['drbd.lastpnodevolumes'] = peernode["peer volumes"]


def _empty(dummy):
    '''
    Action of empty line of ``drbdadm status``
    '''


def _unknown_parser(line):
    '''
    Action of unsupported line of ``drbdadm status``
    '''
    __context__['drbd.statusret'] = {"Unknown parser": line}


def _line_parser(line):
    '''
    Call action for different lines
    '''
    # Should always be called via status()
    section = _analyse_status_type(line)

    switch = {
        '': _empty,
        'RESOURCE': _add_res,
        'PEERNODE': _add_peernode,
        'LOCALDISK': _add_volume,
        'PEERDISK': _add_volume,
    }

    func = switch.get(section, _unknown_parser)

    func(line)


def overview():
    '''
    Show status of the DRBD devices, support two nodes only.
    drbd-overview is removed since drbd-utils-9.6.0,
    use status instead.

    CLI Example:

    .. code-block:: bash

        salt '*' drbd.overview
    '''
    cmd = 'drbd-overview'
    for line in __salt__['cmd.run'](cmd).splitlines():
        ret = {}
        fields = line.strip().split()
        minnum = fields[0].split(':')[0]
        device = fields[0].split(':')[1]
        connstate, _ = _analyse_overview_field(fields[1])
        localrole, partnerrole = _analyse_overview_field(fields[2])
        localdiskstate, partnerdiskstate = _analyse_overview_field(fields[3])
        if localdiskstate.startswith("UpTo"):
            if partnerdiskstate.startswith("UpTo"):
                if len(fields) >= 5:
                    mountpoint = fields[4]
                    fs_mounted = fields[5]
                    totalsize = fields[6]
                    usedsize = fields[7]
                    remainsize = fields[8]
                    perc = fields[9]
                    ret = {
                        'minor number': minnum,
                        'device': device,
                        'connection state': connstate,
                        'local role': localrole,
                        'partner role': partnerrole,
                        'local disk state': localdiskstate,
                        'partner disk state': partnerdiskstate,
                        'mountpoint': mountpoint,
                        'fs': fs_mounted,
                        'total size': totalsize,
                        'used': usedsize,
                        'remains': remainsize,
                        'percent': perc,
                    }
                else:
                    ret = {
                        'minor number': minnum,
                        'device': device,
                        'connection state': connstate,
                        'local role': localrole,
                        'partner role': partnerrole,
                        'local disk state': localdiskstate,
                        'partner disk state': partnerdiskstate,
                    }
            else:
                syncbar = fields[4]
                synced = fields[6]
                syncedbytes = fields[7]
                sync = synced+syncedbytes
                ret = {
                    'minor number': minnum,
                    'device': device,
                    'connection state': connstate,
                    'local role': localrole,
                    'partner role': partnerrole,
                    'local disk state': localdiskstate,
                    'partner disk state': partnerdiskstate,
                    'synchronisation: ': syncbar,
                    'synched': sync,
                }
    return ret


def status(name='all'):
    '''
    Using drbdadm to show status of the DRBD devices,
    available in the latest DRBD9.
    Support multiple nodes, multiple volumes.

    :type name: str
    :param name:
        Resource name.

    :return: DRBD status of resource.
    :rtype: list(dict(res))

    CLI Example:

    .. code-block:: bash

        salt '*' drbd.status
        salt '*' drbd.status name=<resource name>
    '''

    # Initialize for multiple times test cases
    __context__['drbd.statusret'] = []
    __context__['drbd.resource'] = {}

    cmd = 'drbdadm status {}'.format(name)

    #One possible output: (number of resource/node/vol are flexible)
    #resource role:Secondary
    #  volume:0 disk:Inconsistent
    #  volume:1 disk:Inconsistent
    #  drbd-node1 role:Primary
    #    volume:0 replication:SyncTarget peer-disk:UpToDate done:10.17
    #    volume:1 replication:SyncTarget peer-disk:UpToDate done:74.08
    #  drbd-node2 role:Secondary
    #    volume:0 peer-disk:Inconsistent resync-suspended:peer
    #    volume:1 peer-disk:Inconsistent resync-suspended:peer

    result = __salt__['cmd.run_all'](cmd)
    if result['retcode'] != 0:
        LOGGER.info('No status due to %s (%s).', result['stderr'], result['retcode'])
        return None

    for line in result['stdout'].splitlines():
        _line_parser(line)

    if __context__['drbd.resource']:
        __context__['drbd.statusret'].append(__context__['drbd.resource'])

    return __context__['drbd.statusret']
