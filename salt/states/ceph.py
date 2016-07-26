# -*- coding: utf-8 -*-
'''
Manage ceph with salt.

.. versionadded:: Carbon
'''
# Import Python Libs
from __future__ import absolute_import
import logging
import json

# Import Salt Libs
from salt.exceptions import CommandExecutionError, CommandNotFoundError

try:
    import ceph_cfg
    HAS_CEPH_CFG = True
except ImportError:
    HAS_CEPH_CFG = False

log = logging.getLogger(__name__)


def _unchanged(name, msg):
    return {'name': name, 'result': True, 'comment': msg, 'changes': {}}


def _test(name, msg):
    return {'name': name, 'result': None, 'comment': msg, 'changes': {}}


def _error(name, msg):
    return {'name': name, 'result': False, 'comment': msg, 'changes': {}}


def _changed(name, msg, **changes):
    return {'name': name, 'result': True, 'comment': msg, 'changes': changes}


def _ordereddict2dict(input_ordered_dict):
    return json.loads(json.dumps(input_ordered_dict))


def quorum(name, **kwargs):
    '''
    Quorum state

    This state checks the mon daemons are in quorum. It does not alter the
    cluster but can be used in formula as a dependency for many cluster
    operations.

    Example usage in sls file:

    . code-block:: yaml

        quorum:
          sesceph.quorum:
            - require:
              - sesceph: mon_running
    '''
    paramters = _ordereddict2dict(kwargs)
    if paramters is None:
        return _error(name, "Invalid paramters:%s")

    if __opts__['test']:
        return _test(name, "cluster quorum")
    try:
        cluster_quorum = __salt__['ceph.cluster_quorum'](**paramters)
    except (CommandExecutionError, CommandNotFoundError) as e:
        return _error(name, e.message)
    if cluster_quorum:
        return _unchanged(name, "cluster is quorum")
    return _error(name, "cluster is not quorum")
