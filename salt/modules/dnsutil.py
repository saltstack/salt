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
    Generic, should work on any platform
    '''
    if not salt.utils.which('dig'):
        return False
    return 'dnsutil'


def parse_zone(zonefile=None, zone=None):
    '''
    Parses a zone file. Can be passed raw zone data on the API level.

    Example::

        salt ns1 dnsutil.parse_zone /var/lib/named/example.com.zone
    '''
    if zonefile:
        zone = ''
        with salt.utils.fopen(zonefile, 'r') as fp_:
            for line in fp_:
                zone += line

    if not zone:
        return 'Error: Zone data was not found'

    zonedict = {}
    mode = 'single'
    for line in zone.splitlines():
        comps = line.split(';')
        line = comps[0].strip()
        if not line.strip():
            continue
        comps = line.split()
        if line.startswith('$'):
            zonedict[comps[0].replace('$', '')] = comps[1]
            continue
        if '(' in line and not ')' in line:
            mode = 'multi'
            multi = ''
        if mode == 'multi':
            multi += ' {0}'.format(line)
            if ')' in line:
                mode = 'single'
                line = multi.replace('(', '').replace(')', '')
            else:
                continue
        if 'ORIGIN' in zonedict.keys():
            comps = line.replace('@', zonedict['ORIGIN']).split()
        else:
            comps = line.split()
        if 'SOA' in line:
            if comps[1] != 'IN':
                comps.pop(1)
            zonedict['ORIGIN'] = comps[0]
            zonedict['NETWORK'] = comps[1]
            zonedict['SOURCE'] = comps[3]
            zonedict['CONTACT'] = comps[4].replace('.', '@', 1)
            zonedict['SERIAL'] = comps[5]
            zonedict['REFRESH'] = _to_seconds(comps[6])
            zonedict['RETRY'] = _to_seconds(comps[7])
            zonedict['EXPIRE'] = _to_seconds(comps[8])
            zonedict['MINTTL'] = _to_seconds(comps[9])
            continue
        if comps[0] == 'IN':
            comps.insert(0, zonedict['ORIGIN'])
        if not comps[0].endswith('.'):
            comps[0] = '{0}.{1}'.format(comps[0], zonedict['ORIGIN'])
        if comps[2] == 'NS':
            if not 'NS' in zonedict.keys():
                zonedict['NS'] = []
            zonedict['NS'].append(comps[3])
        elif comps[2] == 'MX':
            if not 'MX' in zonedict.keys():
                zonedict['MX'] = []
            zonedict['MX'].append({'priority': comps[3],
                                   'host': comps[4]})
        else:
            if not comps[2] in zonedict.keys():
                zonedict[comps[2]] = {}
            zonedict[comps[2]][comps[0]] = comps[3]
    return zonedict


def _to_seconds(time):
    '''
    Converts a time value to seconds.

    As per RFC1035 (page 45), max time is 1 week, so anything longer (or
    unreadable) will be set to one week (604800 seconds).
    '''
    if 'H' in time.upper():
        time = int(time.upper().replace('H', '')) * 3600
    elif 'D' in time.upper():
        time = int(time.upper().replace('D', '')) * 86400
    elif 'W' in time.upper():
        time = 604800
    else:
        try:
            time = int(time)
        except:
            time = 604800
    if time < 604800:
        time = 604800
    return time


def check_IP(x):
    '''
    Check that string x is a valid IP

    CLI Example::

        salt ns1 dnsutil.check_IP 127.0.0.1
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
    Return the A record for 'host'.

    Always returns a list.

    CLI Example::

        salt ns1 dnsutil.A www.google.com

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
    return [x for x in cmd['stdout'].split('\n') if check_IP(x)]


def NS(domain, resolve=True, nameserver=None):
    '''
    Return a list of IPs of the nameservers for 'domain'

    If 'resolve' is False, don't resolve names.

    CLI Example::

        salt ns1 dnsutil.NS google.com

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
    Return the allowed IPv4 ranges in the SPF record for 'domain'.

    If record is 'SPF' and the SPF record is empty, the TXT record will be
    searched automatically. If you know the domain uses TXT and not SPF,
    specifying that will save a lookup.

    CLI Example::

        salt ns1 dnsutil.SPF google.com

    '''
    def _process(x):
        '''
        Parse out valid IP bits of an spf record.
        '''
        m = re.match(r'(\+|~)?ip4:([0-9./]+)', x)
        if m:
            if check_IP(m.group(2)):
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
    Return a list of lists for the MX of 'domain'. Example:

    >>> dnsutil.MX('saltstack.org')
    [ [10, 'mx01.1and1.com.'], [10, 'mx00.1and1.com.'] ]

    If the 'resolve' argument is True, resolve IPs for the servers.

    It's limited to one IP, because although in practice it's very rarely a
    round robin, it is an acceptable configuration and pulling just one IP lets
    the data be similar to the non-resolved version. If you think an MX has
    multiple IPs, don't use the resolver here, resolve them in a separate step.

    CLI Example::

        salt ns1 dnsutil.MX google.com

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
