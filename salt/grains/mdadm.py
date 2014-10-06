# -*- coding: utf-8 -*-
'''
    Detect MDADM RAIDs
'''

# Import python libs
import logging

log = logging.getLogger(__name__)


def mdadm():
    '''
    Return list of mdadm devices
    '''
    mdadms = []
    try:
        mdstat = open('/proc/mdstat', 'r')
    except IOError:
        log.debug('MDADM: cannot open /proc/mdstat')

    for line in mdstat:
        if line.startswith('Personalities : '):
            continue
        if line.startswith('unused devices:'):
            continue
        if ' : ' in line:
            mdadms.append(line.split(' : ')[0])
    log.debug('MDADM: {0}'.format(mdadms))

    return {'mdadm': mdadms}
