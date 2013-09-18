# -*- coding: utf-8 -*-
'''
Compendium of generic DNS utilities
'''

# Import salt libs
import salt.utils

# Import python libs
import logging
import re

log = logging.getLogger(__name__)


def __virtual__():
    '''
    DNS functions which are based on dig
    '''
    if not salt.utils.which('dig'):
        return False
    return 'dig'


def check_ip(x):
    '''
    Check that string x is a valid IP

    CLI Example:

    .. code-block:: bash

        salt ns1 dig.check_ip 127.0.0.1
    '''
    # This is probably validating. Tacked on the CIDR bit myself.
    ip_regex = (
        r'(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}'
        r'([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])'
        r'(/([0-9]|[12][0-9]|3[0-2]))?$'
    )
    return bool(re.match(ip_regex, x))


def A(host, nameserver=None):
    '''
    Return the A record for ``host``.

    Always returns a list.

    CLI Example:

    .. code-block:: bash

        salt ns1 dig.A www.google.com
    '''
    dig = ['dig', '+short', str(host), 'A']

    if nameserver is not None:
        dig.append('@{0}'.format(nameserver))

    cmd = __salt__['cmd.run_all'](' '.join(dig))
    # In this case, 0 is not the same as False
    if cmd['retcode'] != 0:
        log.warn(
            'dig returned exit code \'{0}\'. Returning empty list as '
            'fallback.'.format(
                cmd['retcode']
            )
        )
        return []

    # make sure all entries are IPs
    return [x for x in cmd['stdout'].split('\n') if check_ip(x)]


def NS(domain, resolve=True, nameserver=None):
    '''
    Return a list of IPs of the nameservers for ``domain``

    If ``resolve`` is False, don't resolve names.

    CLI Example:

    .. code-block:: bash

        salt ns1 dig.NS google.com
    '''
    dig = ['dig', '+short', str(domain), 'NS']

    if nameserver is not None:
        dig.append('@{0}'.format(nameserver))

    cmd = __salt__['cmd.run_all'](' '.join(dig))
    # In this case, 0 is not the same as False
    if cmd['retcode'] != 0:
        log.warn(
            'dig returned exit code \'{0}\'. Returning empty list as '
            'fallback.'.format(
                cmd['retcode']
            )
        )
        return []

    if resolve:
        ret = []
        for ns in cmd['stdout'].split('\n'):
            for a in A(ns, nameserver):
                ret.append(a)
        return ret

    return cmd['stdout'].split('\n')


def SPF(domain, record='SPF', nameserver=None):
    '''
    Return the allowed IPv4 ranges in the SPF record for ``domain``.

    If record is ``SPF`` and the SPF record is empty, the TXT record will be
    searched automatically. If you know the domain uses TXT and not SPF,
    specifying that will save a lookup.

    CLI Example:

    .. code-block:: bash

        salt ns1 dig.SPF google.com
    '''
    def _process(x):
        '''
        Parse out valid IP bits of an spf record.
        '''
        m = re.match(r'(\+|~)?ip4:([0-9./]+)', x)
        if m:
            if check_ip(m.group(2)):
                return m.group(2)
        return None

    dig = ['dig', '+short', str(domain), record]

    if nameserver is not None:
        dig.append('@{0}'.format(nameserver))

    cmd = __salt__['cmd.run_all'](' '.join(dig))
    # In this case, 0 is not the same as False
    if cmd['retcode'] != 0:
        log.warn(
            'dig returned exit code \'{0}\'. Returning empty list as '
            'fallback.'.format(
                cmd['retcode']
            )
        )
        return []

    stdout = cmd['stdout']
    if stdout == '' and record == 'SPF':
        # empty string is successful query, but nothing to return. So, try TXT
        # record.
        return SPF(domain, 'TXT', nameserver)

    stdout = re.sub('"', '', stdout).split()
    if len(stdout) == 0 or stdout[0] != 'v=spf1':
        return []

    return [x for x in map(_process, stdout) if x is not None]


def MX(domain, resolve=False, nameserver=None):
    '''
    Return a list of lists for the MX of ``domain``.

    If the ``resolve`` argument is True, resolve IPs for the servers.

    It's limited to one IP, because although in practice it's very rarely a
    round robin, it is an acceptable configuration and pulling just one IP lets
    the data be similar to the non-resolved version. If you think an MX has
    multiple IPs, don't use the resolver here, resolve them in a separate step.

    CLI Example:

    .. code-block:: bash

        salt ns1 dig.MX google.com
    '''
    dig = ['dig', '+short', str(domain), 'MX']

    if nameserver is not None:
        dig.append('@{0}'.format(nameserver))

    cmd = __salt__['cmd.run_all'](' '.join(dig))
    # In this case, 0 is not the same as False
    if cmd['retcode'] != 0:
        log.warn(
            'dig returned exit code \'{0}\'. Returning empty list as '
            'fallback.'.format(
                cmd['retcode']
            )
        )
        return []

    stdout = [x.split() for x in cmd['stdout'].split('\n')]

    if resolve:
        return [
            (lambda x: [x[0], A(x[1], nameserver)[0]])(x) for x in stdout
        ]

    return stdout
