'''
Compendium of generic DNS utilities
'''

# Import salt libs
import salt.utils

# Import python libs
import logging

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Generic, should work on any platform
    '''
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
            zonedict[comps[0].replace('$','')] = comps[1]
            continue
        if '(' in line and not ')' in line:
            mode = 'multi'
            multi = ''
        if mode == 'multi':
            multi += ' {0}'.format(line)
            if ')' in line:
                mode = 'single'
                line = multi.replace('(','').replace(')','')
            else:
                continue
        if 'ORIGIN' in zonedict.keys():
            comps = line.replace('@',zonedict['ORIGIN']).split()
        else:
            comps = line.split()
        if 'SOA' in line:
            if comps[1] != 'IN':
                comps.pop(1)
            zonedict['ORIGIN'] = comps[0]
            zonedict['NETWORK'] = comps[1]
            zonedict['SOURCE'] = comps[3]
            zonedict['CONTACT'] = comps[4].replace('.','@',1)
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
        time = int(time.upper().replace('H','')) * 3600
    elif 'D' in time.upper():
        time = int(time.upper().replace('D','')) * 86400
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


