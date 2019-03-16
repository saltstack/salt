# -*- coding: utf-8 -*-
'''
This roster resolves targets from a range server.

:depends: seco.range, https://github.com/ytoolshed/range

When you want to use a range query for target matching, use ``--roster range``. For example:

.. code-block:: bash

    salt-ssh --roster range '%%%example.range.cluster' test.ping

'''
from __future__ import absolute_import, print_function, unicode_literals
import fnmatch
import copy

import logging
log = logging.getLogger(__name__)

# Try to import range from https://github.com/ytoolshed/range
HAS_RANGE = False
try:
    import seco.range
    HAS_RANGE = True
except ImportError:
    log.error('Unable to load range library')
# pylint: enable=import-error


def __virtual__():
    return HAS_RANGE


def targets(tgt, tgt_type='range', **kwargs):
    '''
    Return the targets from a range query
    '''

    r = seco.range.Range(__opts__['range_server'])
    log.debug('Range connection to \'%s\' established', __opts__['range_server'])

    hosts = []
    try:
        log.debug('Querying range for \'%s\'', tgt)
        hosts = r.expand(tgt)
    except seco.range.RangeException as err:
        log.error('Range server exception: %s', err)
        return {}
    log.debug('Range responded with: \'%s\'', hosts)

    # Currently we only support giving a raw range entry, no target filtering supported other than what range returns :S
    tgt_func = {
        'range': target_range,
        'glob': target_range,
        # 'glob': target_glob,
    }

    log.debug('Filtering using tgt_type: \'%s\'', tgt_type)
    try:
        targeted_hosts = tgt_func[tgt_type](tgt, hosts)
    except KeyError:
        raise NotImplementedError
    log.debug('Targeting data for salt-ssh: \'%s\'', targeted_hosts)

    return targeted_hosts


def target_range(tgt, hosts):
    ret = {}
    for host in hosts:
        ret[host] = copy.deepcopy(__opts__.get('roster_defaults', {}))
        ret[host].update({'host': host})
        if __opts__.get('ssh_user'):
            ret[host].update({'user': __opts__['ssh_user']})
    return ret


def target_glob(tgt, hosts):
    ret = {}
    for host in hosts:
        if fnmatch.fnmatch(tgt, host):
            ret[host] = copy.deepcopy(__opts__.get('roster_defaults', {}))
            ret[host].update({'host': host})
            if __opts__.get('ssh_user'):
                ret[host].update({'user': __opts__['ssh_user']})
    return ret
