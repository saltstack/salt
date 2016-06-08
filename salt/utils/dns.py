# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import itertools

# Import salt libs
import salt.utils.network


def parse_resolv(fp='/etc/resolv.conf'):
    ns4 = []
    ns6 = []
    search = []
    domain = ''

    try:
        with salt.utils.fopen(fp) as f:
            for line in f:
                line = line.strip().split()

                try:
                    (directive, arg) = (line[0].lower(), line[1:])
                    if directive == 'nameserver':
                        ip_addr = arg[0]
                        if (salt.utils.network.is_ipv4(ip_addr) and
                                ip_addr not in ns4):
                            ns4.append(ip_addr)
                        elif (salt.utils.network.is_ipv6(ip_addr) and
                                ip_addr not in ns6):
                            ns6.append(ip_addr)
                    elif directive == 'domain':
                        domain = arg[0]
                    elif directive == 'search':
                        search = list(itertools.takewhile(
                            lambda x: x[0] not in ('#', ';'), arg))
                except (IndexError, RuntimeError):
                    continue

        return {
            'nameservers': ns4 + ns6,
            'ip4_nameservers': ns4,
            'ip6_nameservers': ns6,
            'domain': domain,
            'search': search
        }
    except IOError:
        return {}
