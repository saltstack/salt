# -*- coding: utf-8 -*-
'''
Return the minions found by looking via ipcidr
'''

# Import python libs
from __future__ import absolute_import
import logging

# Import salt libs
import salt.tgt
import salt.cache
import salt.utils.network
from salt.ext import six

# pylint: disable=import-error,no-name-in-module
if six.PY3:
    import ipaddress
else:
    import salt.ext.ipaddress as ipaddress
# pylint: enable=import-error,no-name-in-module


log = logging.getLogger(__name__)


def check_minions(expr, greedy):
    '''
    Return the minions found by looking via ipcidr
    '''
    cache = salt.cache.factory(__opts__)
    cache_enabled = __opts__.get('minion_data_cache', False)

    if greedy:
        minions = salt.tgt.pki_minions(__opts__)
    elif cache_enabled:
        minions = cache.list('minions')
    else:
        return {'minions': [],
                'missing': []}

    if cache_enabled:
        if greedy:
            cminions = cache.list('minions')
        else:
            cminions = minions
        if cminions is None:
            return {'minions': minions,
                    'missing': []}

        tgt = expr
        try:
            # Target is an address?
            tgt = ipaddress.ip_address(tgt)
        except:  # pylint: disable=bare-except
            try:
                # Target is a network?
                tgt = ipaddress.ip_network(tgt)
            except:  # pylint: disable=bare-except
                log.error('Invalid IP/CIDR target: {0}'.format(tgt))
                return {'minions': [],
                        'missing': []}
        proto = 'ipv{0}'.format(tgt.version)

        minions = set(minions)
        for id_ in cminions:
            mdata = cache.fetch('minions/{0}'.format(id_), 'data')
            if mdata is None:
                if not greedy:
                    minions.remove(id_)
                continue
            grains = mdata.get('grains')
            if grains is None or proto not in grains:
                match = False
            elif isinstance(tgt, (ipaddress.IPv4Address, ipaddress.IPv6Address)):
                match = str(tgt) in grains[proto]
            else:
                match = salt.utils.network.in_subnet(tgt, grains[proto])

            if not match and id_ in minions:
                minions.remove(id_)

    return {'minions': list(minions),
            'missing': []}
