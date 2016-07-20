# -*- coding: utf-8 -*-
'''
This roster resolves targets from a range server.

:depends: seco.range, https://github.com/ytoolshed/range

When you want to use a range query for target matching, use ``--roster range``. For example:

.. code-block:: bash

    salt-ssh --roster range '%%%example.range.cluster' test.ping

'''
from __future__ import absolute_import
import fnmatch

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
    log.debug('Range connection to \'{0}\' established'.format(__opts__['range_server']))

    hosts = []
    try:
        log.debug('Querying range for \'{0}\''.format(tgt))
        hosts = r.expand(tgt)
    except seco.range.RangeException as err:
        log.error('Range server exception: %s', err)
        return {}
    log.debug('Range responded with: \'{0}\''.format(hosts))

    # Currently we only support giving a raw range entry, no target filtering supported other than what range returns :S
    tgt_func = {
        'range': target_range,
        'glob': target_range,
        # 'glob': target_glob,
    }

    log.debug('Filtering using tgt_type: \'{0}\''.format(tgt_type))
    try:
        targeted_hosts = tgt_func[tgt_type](tgt, hosts)
    except KeyError:
        raise NotImplementedError
    log.debug('Targeting data for salt-ssh: \'{0}\''.format(targeted_hosts))

    return targeted_hosts


def target_range(tgt, hosts):
    return dict((host, {'host': host, 'user': __opts__['ssh_user']}) for host in hosts)


def target_glob(tgt, hosts):
    return dict((host, {'host': host, 'user': __opts__['ssh_user']}) for host in hosts if fnmatch.fnmatch(tgt, host))
