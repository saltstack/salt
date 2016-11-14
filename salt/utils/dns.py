# -*- coding: utf-8 -*-
'''
Define some generic functions for dns modules
'''

# Import python libs
from __future__ import absolute_import
import itertools
import logging

# Import salt libs
import salt.utils.network
from salt._compat import ipaddress

log = logging.getLogger(__name__)


def parse_resolv(src='/etc/resolv.conf'):
    '''
    Parse a resolver configuration file (traditionally /etc/resolv.conf)
    '''

    nameservers = []
    search = []
    sortlist = []
    domain = ''
    options = []

    try:
        with salt.utils.fopen(src) as src_file:
            # pylint: disable=too-many-nested-blocks
            for line in src_file:
                line = line.strip().split()

                try:
                    (directive, arg) = (line[0].lower(), line[1:])
                    # Drop everything after # or ; (comments)
                    arg = list(itertools.takewhile(
                        lambda x: x[0] not in ('#', ';'), arg))

                    if directive == 'nameserver':
                        try:
                            ip_addr = ipaddress.ip_address(arg[0])
                            if ip_addr not in nameservers:
                                nameservers.append(ip_addr)
                        except ValueError as exc:
                            log.error('{0}: {1}'.format(src, exc))
                    elif directive == 'domain':
                        domain = arg[0]
                    elif directive == 'search':
                        search = arg
                    elif directive == 'sortlist':
                        # A sortlist is specified by IP address netmask pairs.
                        # The netmask is optional and defaults to the natural
                        # netmask of the net. The IP address and optional
                        # network pairs are separated by slashes.
                        for ip_raw in arg:
                            try:
                                ip_net = ipaddress.ip_network(ip_raw)
                            except ValueError as exc:
                                log.error('{0}: {1}'.format(src, exc))
                            else:
                                if '/' not in ip_raw:
                                    # No netmask has been provided, guess
                                    # the "natural" one
                                    if ip_net.version == 4:
                                        ip_addr = str(ip_net.network_address)
                                        # pylint: disable=protected-access
                                        mask = salt.utils.network.\
                                            natural_ipv4_netmask(ip_addr)

                                        ip_net = ipaddress.ip_network(
                                            '{0}{1}'.format(ip_addr, mask),
                                            strict=False
                                        )
                                    if ip_net.version == 6:
                                        # TODO
                                        pass

                                if ip_net not in sortlist:
                                    sortlist.append(ip_net)
                    elif directive == 'options':
                        # Options allows certain internal resolver variables to
                        # be modified.
                        if arg[0] not in options:
                            options.append(arg[0])
                except IndexError:
                    continue

        if domain and search:
            # The domain and search keywords are mutually exclusive.  If more
            # than one instance of these keywords is present, the last instance
            # will override.
            log.debug('{0}: The domain and search keywords are mutually '
                        'exclusive.'.format(src))

        return {
            'nameservers': nameservers,
            'ip4_nameservers': [ip for ip in nameservers if ip.version == 4],
            'ip6_nameservers': [ip for ip in nameservers if ip.version == 6],
            'sortlist': [ip.with_netmask for ip in sortlist],
            'domain': domain,
            'search': search,
            'options': options
        }
    except IOError:
        return {}
