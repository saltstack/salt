'''
Return data to the host operating system's syslog facility

Required python modules: syslog, json

The syslog returner simply reuses the operating system's syslog
facility to log return data
'''

# Import python libs
import syslog
import json


def __virtual__():
    return 'syslog'


def returner(ret):
    '''
    Return data to the local syslog
    '''
    syslog.syslog(syslog.LOG_INFO, 'salt-minion: {0}'.format(json.dumps(ret)))
