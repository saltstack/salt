# -*- coding: utf-8 -*-
'''
Use the minion cache on the master to derive IP addresses based on minion ID.

Currently only contains logic to return an IPv4 address; does not handle IPv6,
or authentication (passwords, keys, etc).

It is possible to configure this roster to prefer a particular type of IP over
another. To configure the order, set the roster_order in the master config
file. The default for this is:

.. code-block:: yaml

    roster_order:
      - public
      - private
      - local
'''
from __future__ import absolute_import

# Import python libs
import os.path
import msgpack

# Import Salt libs
import salt.loader
import salt.utils
import salt.utils.cloud
import salt.utils.validate.net
from salt import syspaths


def targets(tgt, tgt_type='glob', **kwargs):  # pylint: disable=W0613
    '''
    Return the targets from the flat yaml file, checks opts for location but
    defaults to /etc/salt/roster
    '''
    cache = os.path.join(syspaths.CACHE_DIR, 'master', 'minions', tgt, 'data.p')

    if not os.path.exists(cache):
        return {}

    roster_order = __opts__.get('roster_order', (
        'public', 'private', 'local'
    ))

    with salt.utils.fopen(cache, 'r') as fh_:
        cache_data = msgpack.load(fh_)

    ipv4 = cache_data.get('grains', {}).get('ipv4', [])
    preferred_ip = extract_ipv4(roster_order, ipv4)
    if preferred_ip is None:
        return {}

    return {
        tgt: {
            'host': preferred_ip,
        }
    }


def extract_ipv4(roster_order, ipv4):
    '''
    Extract the preferred IP address from the ipv4 grain
    '''
    for ip_type in roster_order:
        for ip_ in ipv4:
            if not salt.utils.validate.net.ipv4_addr(ip_):
                continue
            if ip_type == 'local' and ip_.startswith('127.'):
                return ip_
            elif ip_type == 'private' and not salt.utils.cloud.is_public_ip(ip_):
                return ip_
            elif ip_type == 'public' and salt.utils.cloud.is_public_ip(ip_):
                return ip_
    return None
