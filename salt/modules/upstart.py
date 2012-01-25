'''
Provide the services module for upstart
'''

import os


def __virtual__():
    '''
    Only works on systems which default to upstart
    '''
    enable = [
               'Ubuntu',
               'Fedora',
               'Debian',
              ]
    if __grains__['os'] in enable and os.path.isfile('/sbin/initctl'):
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
        enabled = status(serv)
        if enabled:
            ret.append(serv)
    return ret

def get_disabled():
    '''
    Return a list of all disabled services

    CLI Example::

        salt '*' service.get_disabled
    '''
    ret = []
    for serv in get_all():
        enabled = status(serv)
        if not enabled:
            ret.append(serv)
    return ret

def get_all():
    '''
    Return a list of all available services

    CLI Example::

        salt '*' service.get_all
    '''
    cmd = 'initctl list'
    ret = __salt__['cmd.run'](cmd)
    services = ret.split('\n')

    serv = []
    for service in services:
        name = service.split(' ')[0]
        if name:
            serv.append(name)
    return serv

def reload_config():
    '''
    Reload the service.configuration

    CLI Example::

        salt '*' service.reload_config
    '''
    cmd = 'initctl start {0}'.format(name)
    return not __salt__['cmd.retcode'](cmd)

def start(name):
    '''
    Start the specified service with upstart

    CLI Example::

        salt '*' service.start <service.name>
    '''
    cmd = 'initctl start {0}'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def stop(name):
    '''
    Stop the specifed service with upstart

    CLI Example::

    salt '*' service.stop <service.name>
    '''
    cmd = 'initctl stop {0}'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def restart(name):
    '''
    Retart the specified service with upstart

    CLI Example::

        salt '*' service.restart <service.name>
    '''
    cmd = 'initctl restart {0}'.format(name)
    return not __salt__['cmd.retcode'](cmd)

def reload(name):
    '''
    Reload the specified service with upstart

    CLI Example::

        salt '*' service.reload <service.name>
    ''' 
    cmd = 'initctl reload {0}'.format(name)
    return not __salt__['cmd.retcode'](cmd)

# The unused sig argument is required to maintain consistency in the state
# system
def status(name, sig=None):
    '''
    Return the status for a service via upstart, returns the PID if the service
    is running or an empty string if the service is not running

    CLI Example::

        salt '*' service.status <service.name>
    '''
    cmd = 'initctl status {0}'.format(name)
    ret = __salt__['cmd.run'](cmd)
    running = ret.find('running')
    index1 = ret.find('process')
    index2 = ret.find('\n')
    mainpid = ret[index1+8:index2]
    if not 'running' in ret:
        return ''
    return mainpid


def enabled(name):
    '''
    Return if the named service is running
    
    CLI Example::

        salt '*' service.enabled <service.name>
    '''
    enabled = status(name)
    if enabled:
        return True

def disabled(name):
    '''
    Return if the named service is stopped

    CLI Example::

        salt '*' service.disabled <service.name>
    '''
    enabled = status(name)
    if not enabled:
        return True
