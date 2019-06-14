# -*- coding: utf-8 -*-
'''
Module to provide DRBD functionality to Salt

:maintainer:    Nick Wang <nwang@suse.com>
:maturity:      alpha
:depends:       ``drbdadm`` drbd utils
:platform:      all

:configuration: This module requires drbd kernel module and drbd utils tool

.. code-block:: yaml

'''
from __future__ import absolute_import, print_function, unicode_literals

import logging

from salt.exceptions import CommandExecutionError
from salt.ext import six

import salt.utils.json
import salt.utils.path

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'drbd'

DRBD_COMMAND = 'drbdadm'


def __virtual__():  # pragma: no cover
    '''
    Only load this module if drbdadm(drbd-utils) is installed

    .. versionadded:: neon
    '''
    if bool(salt.utils.path.which(DRBD_COMMAND)):
        return __virtualname__
    return (
        False,
        'The drbd execution module failed to load: the drbdadm'
        ' binary is not available.')


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


def _is_local_all_uptodated(name):
    '''
    Check whether all local volumes are UpToDate.
    '''

    res = status(name)
    if not res:
        return False

    # Since name is not all, res only have one element
    for vol in res[0]['local volumes']:
        if vol['disk'] != 'UpToDate':
            return False

    return True


def _is_peers_uptodated(name, peernode='all'):
    '''
    Check whether all volumes of peer node are UpToDate.

    .. note::

        If peernode is not match, will return None, same as False.
    '''
    ret = None

    res = status(name)
    if not res:
        return ret

    # Since name is not all, res only have one element
    for node in res[0]['peer nodes']:
        if peernode != 'all' and node['peernode name'] != peernode:
            continue

        for vol in node['peer volumes']:
            if vol['peer-disk'] != 'UpToDate':
                return False
            else:
                # At lease one volume is 'UpToDate'
                ret = True

    return ret


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
        log.info('No status due to %s (%s).', result['stderr'], result['retcode'])
        return None

    for line in result['stdout'].splitlines():
        _line_parser(line)

    if __context__['drbd.resource']:
        __context__['drbd.statusret'].append(__context__['drbd.resource'])

    return __context__['drbd.statusret']


def createmd(name='all', force=True):
    '''
    Create the metadata of DRBD resource.

    :type name: str
    :param name:
        Resource name.

    :type force: bool
    :param force:
        Force create metadata.

    :return: result of creating metadata.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' drbd.create
        salt '*' drbd.create name=<resource name>

    .. versionadded:: neon
    '''

    cmd = 'drbdadm create-md {}'.format(name)

    if force:
        cmd += ' --force'

    return __salt__['cmd.retcode'](cmd)


def up(name='all'):
    '''
    Start of drbd resource.

    :type name: str
    :param name:
        Resource name.

    :return: result of start resource.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' drbd.up
        salt '*' drbd.up name=<resource name>

    .. versionadded:: neon
    '''

    cmd = 'drbdadm up {}'.format(name)

    return __salt__['cmd.retcode'](cmd)


def down(name='all'):
    '''
    Stop of DRBD resource.

    :type name: str
    :param name:
        Resource name.

    :return: result of stop resource.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' drbd.down
        salt '*' drbd.down name=<resource name>

    .. versionadded:: neon
    '''

    cmd = 'drbdadm down {}'.format(name)

    return __salt__['cmd.retcode'](cmd)


def primary(name='all', force=False):
    '''
    Promote the DRBD resource.

    :type name: str
    :param name:
        Resource name.

    :type force: bool
    :param force:
        Force to promote the resource.
        Needed in the initial sync.

    :return: result of promote resource.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' drbd.primary
        salt '*' drbd.primary name=<resource name>

    .. versionadded:: neon
    '''

    cmd = 'drbdadm primary {}'.format(name)

    if force:
        cmd += ' --force'

    return __salt__['cmd.retcode'](cmd)


def secondary(name='all'):
    '''
    Demote the DRBD resource.

    :type name: str
    :param name:
        Resource name.

    :return: result of demote resource.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' drbd.secondary
        salt '*' drbd.secondary name=<resource name>

    .. versionadded:: neon
    '''

    cmd = 'drbdadm secondary {}'.format(name)

    return __salt__['cmd.retcode'](cmd)


def adjust(name='all'):
    '''
    Adjust the DRBD resource while running.

    :type name: str
    :param name:
        Resource name.

    :return: result of adjust resource.
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' drbd.adjust
        salt '*' drbd.adjust name=<resource name>

    .. versionadded:: neon
    '''

    cmd = 'drbdadm adjust {}'.format(name)

    return __salt__['cmd.retcode'](cmd)


def setup_show(name='all'):
    '''
    Show the DRBD resource via drbdsetup directly.
    Only support the json format so far.

    :type name: str
    :param name:
        Resource name.

    :return: The resource configuration.
    :rtype: dict

    CLI Example:

    .. code-block:: bash

        salt '*' drbd.setup_show
        salt '*' drbd.setup_show name=<resource name>

    .. versionadded:: neon
    '''

    ret = {'name': name,
           'result': False,
           'comment': ''}

    # Only support json format
    cmd = 'drbdsetup show --json {}'.format(name)

    results = __salt__['cmd.run_all'](cmd)

    if 'retcode' not in results or results['retcode'] != 0:
        ret['comment'] = 'Error({}) happend when show resource via drbdsetup.'.format(
            results['retcode'])
        return ret

    try:
        ret = salt.utils.json.loads(results['stdout'], strict=False)
    except ValueError:
        raise CommandExecutionError('Error happens when try to load the json output.',
                                    info=results)

    return ret


def setup_status(name='all'):
    '''
    Show the DRBD running status.
    Only support enable the json format so far.

    :type name: str
    :param name:
        Resource name.

    :return: The resource configuration.
    :rtype: dict

    CLI Example:

    .. code-block:: bash

        salt '*' drbd.setup_status
        salt '*' drbd.setup_status name=<resource name>

    .. versionadded:: neon
    '''

    ret = {'name': name,
           'result': False,
           'comment': ''}

    cmd = 'drbdsetup status --json {}'.format(name)

    results = __salt__['cmd.run_all'](cmd)

    if 'retcode' not in results or results['retcode'] != 0:
        ret['comment'] = 'Error({}) happend when show resource via drbdsetup.'.format(
            results['retcode'])
        return ret

    try:
        ret = salt.utils.json.loads(results['stdout'], strict=False)
    except ValueError:
        raise CommandExecutionError('Error happens when try to load the json output.',
                                    info=results)

    return ret


def check_sync_status(name, peernode='all'):
    '''
    Query a drbd resource until fully synced for all volumes.

    :type name: str
    :param name:
        Resource name. Not support all.

    :type peernode: str
    :param peernode:
        Peer node name. Default: all

    CLI Example:

    .. code-block:: bash

        salt '*' drbd.check_sync_status <resource name> <peernode name>

    .. versionadded:: neon
    '''
    if _is_local_all_uptodated(name) and _is_peers_uptodated(
            name, peernode=peernode):
        return True

    return False
