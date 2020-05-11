# -*- coding: utf-8 -*-
'''
Manage ceph with salt.

.. versionadded:: 2016.11.0
'''
# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

# Import Salt Libs
import salt.utils.json
from salt.exceptions import CommandExecutionError, CommandNotFoundError


log = logging.getLogger(__name__)


def _unchanged(name, msg):
    '''
    Utility function: Return structure unchanged
    '''
    return {'name': name, 'result': True, 'comment': msg, 'changes': {}}


def _test(name, msg):
    '''
    Utility function: Return structure test
    '''
    return {'name': name, 'result': None, 'comment': msg, 'changes': {}}


def _error(name, msg):
    '''
    Utility function: Return structure error
    '''
    return {'name': name, 'result': False, 'comment': msg, 'changes': {}}


def _changed(name, msg, **changes):
    '''
    Utility function: Return structure changed
    '''
    return {'name': name, 'result': True, 'comment': msg, 'changes': changes}


def _ordereddict2dict(input_ordered_dict):
    '''
    Convert ordered dictionary to a dictionary
    '''
    return salt.utils.json.loads(salt.utils.json.dumps(input_ordered_dict))


def quorum(name, **kwargs):
    '''
    Quorum state

    This state checks the mon daemons are in quorum. It does not alter the
    cluster but can be used in formula as a dependency for many cluster
    operations.

    Example usage in sls file:

    .. code-block:: yaml

        quorum:
          sesceph.quorum:
            - require:
              - sesceph: mon_running
    '''
    parameters = _ordereddict2dict(kwargs)
    if parameters is None:
        return _error(name, "Invalid parameters:%s")

    if __opts__['test']:
        return _test(name, "cluster quorum")
    try:
        cluster_quorum = __salt__['ceph.cluster_quorum'](**parameters)
    except (CommandExecutionError, CommandNotFoundError) as err:
        return _error(name, err.strerror)
    if cluster_quorum:
        return _unchanged(name, "cluster is quorum")
    return _error(name, "cluster is not quorum")
