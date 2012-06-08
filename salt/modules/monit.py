'''
Salt module to manage monit
'''

def version():
    '''
    List monit version

    Cli Example::

        salt '*' monit.version
    '''

    cmd = 'monit -V'
    res = __salt__['cmd.run'](cmd)
    return res.split("\n")[0]


def status():
    '''
    Monit status

    CLI Example::

        salt '*' monit.status
    '''
    cmd = 'monit status'
    res = __salt__['cmd.run'](cmd)
    return res.split("\n")


def start():
    '''
    Starts monit

    CLI Example::

        salt '*' monit.start
    *Note need to add check to insure its running*
    `ps ax | grep monit | grep -v grep or something`
    '''
    cmd = 'monit'
    res = __salt__['cmd.run'](cmd)
    return "Monit started"


def stop():
    '''
    Stop monit

    CLI Example::

        salt '*' monit.stop
        *Note Needs check as above*
    '''
    def _is_bsd():
        return True if __grains__['os'] == 'FreeBSD' else False

    if _is_bsd():
        cmd = "/usr/local/etc/rc.d/monit stop"
    else:
        cmd = "/etc/init.d/monit stop"
    res = __salt__['cmd.run'](cmd)
    return "Monit Stopped"


def monitor_all():
    '''
    Initializing all monit modules.
    '''
    cmd = 'monit monitor all'
    res = __salt__['cmd.run'](cmd)
    if res:
        return "All Services initaialized"
    return "Issue starting monitoring on all services"


def unmonitor_all():
    '''
    unmonitor all services.
    '''
    cmd = 'monit unmonitor all'
    res = __salt__['cmd.run'](cmd)
    if res:
        return "All Services unmonitored"
    return "Issue unmonitoring all services"
