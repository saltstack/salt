'''
Monit service module. This module will create a monit type 
service watcher.
'''


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


def unmonitor(name):
    '''
    Unmonitor service via monit

    CLI Example::

        salt '*' monit.unmonitor <service name>
    '''
    cmd = "monit unmonitor {0}".format(name)

    return not __salt__['cmd.retcode'](cmd)


def monitor(name):
    '''
    monitor service via monit

    CLI Example::

        salt '*' monit.monitor <service name>
    '''
    cmd = "monit monitor {0}".format(name)

    return not __salt__['cmd.retcode'](cmd)

