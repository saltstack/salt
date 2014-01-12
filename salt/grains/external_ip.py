# -*- coding: utf-8 -*-
'''
    :codeauthor: Jeff Frost
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.


    salt.grains.external_ip
    ~~~~~~~~~~~~~~~~~~~~~~~

    Return the external IP address reported by one of the following providers:

        * ipecho.net
        * externalip.net
        * ident.me

    Which ever reports a valid IP first
'''

# Import Python Libs
import urllib2
import contextlib

# Import salt libs
from salt.utils.validate.net import ipv4_addr as _ipv4_addr


def external_ip():
    '''
    Return the external IP address
    '''
    check_ips = ('http://ipecho.net/plain',
                 'http://api.externalip.net/ip',
                 'http://v4.ident.me')

    for url in check_ips:
        try:
            with contextlib.closing(urllib2.urlopen(url, timeout=3)) as req:
                ip_ = req.read().strip()
                if not _ipv4_addr(ip_):
                    continue
            return {'external_ip': ip_}
        except (urllib2.HTTPError, urllib2.URLError):
            continue

    # Return an empty value as a last resort
    return {'external_ip': []}
