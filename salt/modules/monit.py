'''
Monit service module. This module will create a monit type 
service watcher.
'''

import os

def start(name):
    '''
   
    CLI Example::
    salt '*' monit.start <service name>
    '''
    cmd = "monit start {0}".format(name)

    return not __salt__['cmd.retcode'](cmd)


def stop(name):
    '''
    Stops service via monit

    CLI Example::

        salt '*' monit.stop <service name>
    '''
    cmd = "monit stop {0}".format(name)


    return not __salt__['cmd.retcode'](cmd)


def restart(name):
    '''
    Restart service via monit

    CLI Example::

        salt '*' monit.restart <service name>
    '''
    cmd = "monit restart {0}".format(name)

    return not __salt__['cmd.retcode'](cmd)

