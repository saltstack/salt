# -*- coding: utf-8 -*-
'''
Module to provide GPFS compatibility to Salt.
'''
from __future__ import absolute_import

# Import python libs
import logging
import os.path

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Verify gpfs is installed.
    '''
    return os.path.isfile('/usr/lpp/mmfs/bin/mmgetstate')


def cluster_configured(runas=None):
    '''
    Return whether the node is configured in a cluster

    CLI Example:

    .. code-block:: bash

        salt '*' gpfs.cluster_configured
    '''
    ret = True
    res = __salt__['cmd.run']('/usr/lpp/mmfs/bin/mmlscluster',
                              runas=runas, shell='/bin/bash')
    for line in res.splitlines():
        if 'node does not belong' in line:
            ret = False

    return ret


def cluster_member(clustername, runas=None):
    '''
    Returns wheter the node is joined to the cluster

    CLI Example:

    .. code-block:: bash

        salt '*' gpfs.cluster_joined gpfs.cluster
    '''
    ret = False
    res = __salt__['cmd.run']('/usr/lpp/mmfs/bin/mmlscluster',
                              runas=runas, shell='/bin/bash')
    for line in res.splitlines():
        if 'GPFS cluster name' in line:
            parts = line.split(':')
            if len(parts) < 2:
                continue
            cluster = parts[1].strip()
            if cluster == clustername:
                ret = True

    return ret


def join_cluster(master, runas=None):
    '''
    Joins a GPFS cluster via the specified master

    CLI Example:

    .. code-block:: bash
        salt '*' gpfs.join_cluster server1
    '''
    ret = False
    res = __salt__['cmd.run']('/usr/lpp/mmfs/bin/mmsdrrestore -p {0} -R /usr/bin/scp'.format(master),
                              runas=runas, shell='/bin/bash')
    for line in res.splitlines():
        if 'successfully restored' in line:
            ret = True
            __salt__['cmd.run']('/usr/lpp/mmfs/bin/mmstartup',
                                runas=runas, shell='/bin/bash')
    if not ret:
        res2 = __salt__['cmd.run']('/usr/bin/ssh {0} /usr/lpp/mmfs/bin/mmaddnode -N {1}'.format(master, __grains__['host']),
                                   runas=runas, shell='/bin/bash')
        for line in res2.splitlines():
            if 'Command successfully completed' in line:
                ret = True
                __salt__['cmd.run']('/usr/lpp/mmfs/bin/mmchlicense client --accept -N {0}'.format(__grains__['host']),
                                    runas=runas, shell='/bin/bash')
                __salt__['cmd.run']('/usr/lpp/mmfs/bin/mmstartup',
                                    runas=runas, shell='/bin/bash')
    return ret


def cluster_started(runas=None):
    '''
    Checks to see if the GPFS cluster has been started

    CLI Example:

    .. code-block:: bash
        salt '*' gpfs.cluster_started
    '''
    ret = False
    res = __salt__['cmd.run']('/usr/lpp/mmfs/bin/mmgetstate',
                              runas=runas, shell='/bin/bash')
    for line in res.splitlines():
        if __grains__['host'] in line:
            parts = line.split()
            started = parts[2].strip()
            if started == "active":
                ret = True

    return ret


def start_cluster(runas=None):
    '''
    Starts GPFS on the node

    CLI Example:

    .. code-block:: bash
        salt '*' gpfs.start_cluster
    '''
    ret = False
    res = __salt__['cmd.run']('/usr/lpp/mmfs/bin/mmstartup',
                              runas=runas, shell='/bin/bash')
    for line in res.splitlines():
        if 'mmstartup: Starting GPFS ...' in line:
            ret = True
    return ret
