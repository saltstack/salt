'''
Top level package command wrapper, used to translate the os detected by the
grains to the correct service manager
'''
import os

grainmap = {
           'Arch': '/etc/rc.d',
           'Fedora': '/etc/init.d',
           'RedHat': '/etc/init.d',
           'Debian': '/etc/init.d',
           'Ubuntu': '/etc/init.d',
          }

def start(name):
    '''
    Start the specified service

    CLI Example:
    salt '*' service.start <service name>
    '''
    cmd = os.path.join(grainmap[__grains__['os']],
            name + ' start')
    return not __salt__['cmd.retcode'](cmd)

def stop(name):
    '''
    Stop the specified service

    CLI Example:
    salt '*' service.stop <service name>
    '''
    cmd = os.path.join(grainmap[__grains__['os']],
            name + ' stop')
    return not __salt__['cmd.retcode'](cmd)

def restart(name):
    '''
    Restart the named service
    
    CLI Example:
    salt '*' service.restart <service name>
    '''
    cmd = os.path.join(grainmap[__grains__['os']],
            name + ' restart')
    return not __salt__['cmd.retcode'](cmd)

def status(name, sig=None):
    '''
    Return the status for a service, returns the PID or an empty string if the
    service is running or not, pass a signature to use to find the service via
    ps

    CLI Example:
    salt '*' service.status <service name> [service signature]
    '''
    sig = name if not sig else sig
    cmd = "{0[ps]} | grep {1} | grep -v grep | awk '{{print $2}}'".format(
            __grains__, sig)
    return __salt__['cmd.run'](cmd).strip()
