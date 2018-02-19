# -*- coding: utf-8 -*-
'''
Manage GPFS Clusters
====================

Salt can manage a client node in a GPFS cluster, for example, the following
block checks to see if the minion is joined to the cluster. If however, the
minion is not joined, then it will attempt to join to the cluster.

.. code-block:: yaml

    gpfs.cluster:
      gpfs.joined:
        - cluster: gpfs.cluster
        - master: storage01

The following block ensures, that gpfs daemon is started, and is able to
connect to gpfs

.. code-block:: yaml

    gpfs.start:
      gpfs.started
'''
from __future__ import absolute_import

# Import python libs
import logging

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if GPFS is installed.
    '''
    return 'gpfs.start_cluster' in __salt__


def joined(cluster,
           master,
           runas=None,
           **kwargs):
    '''
    Ensure the current node is joined to the cluster

    cluster
        Name of the GPFS cluster
    master
        Name of the GPFS master to join from
    runas
        The user to run the GPFS command as
    '''

    result = __salt__['gpfs.cluster_member'](cluster, runas=runas)
    changes = {}
    ret = {'name': cluster}

    if not result:
        res1 = __salt__['gpfs.cluster_configured'](runas=runas)
        if not res1:
            if __opts__['test']:
                ret['result'] = None
                ret['comment'] = "Would join gpfs cluster: " + cluster
            else:
                res2 = __salt__['gpfs.join_cluster'](master, runas=runas)
                if res2:
                    changes['old'] = 'no cluster member'
                    changes['new'] = 'joined via: ' + master
                    ret['result'] = True
                    ret['comment'] = 'Joined GPFS cluster ' + cluster
                else:
                    ret['result'] = False
                    ret['comment'] = 'Could not join the cluster'
        else:
            ret['result'] = False
            ret['comment'] = 'Member of existing GPFS cluster'
    else:
        ret['result'] = True
        ret['comment'] = 'Already member of this GPFS cluster'

    ret['changes'] = changes

    return ret


def started(runas=None,
            **kwargs):

    '''
    Ensure the current node has started gpfs

    runas
        The user to run the GPFS command as
    '''

    result = __salt__['gpfs.cluster_started'](runas=runas)
    changes = {}
    ret = {'name': __grains__['host']}

    if not result:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = "GPFS would be started"
        else:
            res1 = __salt__['gpfs.start_cluster'](runas=runas)
            if not res1:
                ret['result'] = False
                ret['comment'] = "There was an error start GPFS"
            else:
                changes['old'] = 'gpfs down'
                changes['new'] = 'gpfs started'
                ret['result'] = True
                ret['comment'] = 'GPFS was started'
    else:
        ret['result'] = True
        ret['comment'] = 'GPFS is already active'

    ret['changes'] = changes

    return ret
