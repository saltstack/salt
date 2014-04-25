# -*- coding: utf-8 -*-
'''
Return data to the host operating system's syslog facility

Required python modules: syslog, json

The syslog returner simply reuses the operating system's syslog
facility to log return data

To use the syslog returner, append '--return syslog' to the salt command. ex:

    salt '*' test.ping --return syslog

'''

# Import python libs
import json
try:
    import syslog
    HAS_SYSLOG = True
except ImportError:
    HAS_SYSLOG = False

# Define the module's virtual name
__virtualname__ = 'syslog'


def __virtual__():
    if not HAS_SYSLOG:
        return False
    return __virtualname__


def returner(ret):
    '''
    Return data to the local syslog
    '''
    syslog.syslog(syslog.LOG_INFO, 'salt-minion: {0}'.format(json.dumps(ret)))
