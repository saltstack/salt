'''
Provide the service module for systemd
'''

import os


def __virtual__():
    '''
    Only work on systems which default to systemd
    '''
    if __grains__['os'] == 'Fedora' and __grains__['osrelease'] > 15:
        return 'service'
    return False


def get_enabled():
    '''
    Return a list of all enabled services

    CLI Example::

        salt '*' service.get_enabled
    '''
    ret = []
    for serv in get_all():
        cmd = 'systemctl is-enabled {0}.service'.format(serv)
        if not __salt__['cmd.retcode'](cmd):
            ret.append(serv)
    return sorted(ret)

def get_disabled():
    '''
    Return a list of all disabled services

    CLI Example::

        salt '*' service.get_disabled
    '''
    ret = []
    for serv in get_all():
        cmd = 'systemctl is-enabled {0}.service'.format(serv)
        if __salt__['cmd.retcode'](cmd):
            ret.append(serv)
    return sorted(ret)

def get_all():
    '''
    Return a list of all available services

    CLI Example::

        salt '*' service.get_all
    '''
    ret = set()
    sdir = '/lib/systemd/system'
    if not os.path.isdir('/lib/systemd/system'):
        return []
    for fn_ in os.listdir(sdir):
        if fn_.endswith('.service'):
            ret.add(fn_[:fn_.rindex('.')])
    return sorted(list(ret))

def start(name):
    '''
    Start the specified service with systemd

    CLI Example::

        salt '*' service.start <service name>
    '''
    cmd = 'systemctl start {0}.service'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def stop(name):
    '''
    Stop the specifed service with systemd

    CLI Example::

        salt '*' service.stop <service name>
    '''
    cmd = 'systemctl stop {0}.service'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def restart(name):
    '''
    Start the specified service with systemd

    CLI Example::

        salt '*' service.start <service name>
    '''
    cmd = 'systemctl restart {0}.service'.format(name)
    return not __salt__['cmd.retcode'](cmd)


# The unused sig argument is required to maintain consistency in the state
# system
def status(name, sig=None):
    '''
    Return the status for a service via systemd, returns the PID if the service
    is running or an empty string if the service is not running

    CLI Example::

        salt '*' service.status <service name>
    '''
    cmd = 'systemctl show {0}.service'.format(name)
    ret = __salt__['cmd.run'](cmd)
    index1 = ret.find('\nMainPID=')
    index2 = ret.find('\n', index1+9)
    mainpid = ret[index1+9:index2]
    if mainpid == '0':
        return ''
    return mainpid


def enable(name):
    '''
    Enable the named service to start when the system boots

    CLI Example::

        salt '*' service.enable <service name>
    '''
    cmd = 'systemctl enable {0}.service'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def disable(name):
    '''
    Disable the named service to not start when the system boots

    CLI Example::

        salt '*' service.disable <service name>
    '''
    cmd = 'systemctl disable {0}.service'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def enabled(name):
    '''
    Return if the named service is enabled to start on boot
    
    CLI Example::

        salt '*' service.enabled <service name>
    '''
    cmd = 'systemctl is-enabled {0}.service'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def disabled(name):
    '''
    Return if the named service is disabled to start on boot

    CLI Example::

        salt '*' service.disabled <service name>
    '''
    cmd = 'systemctl is-enabled {0}.service'.format(name)
    return bool(__salt__['cmd.retcode'](cmd))
