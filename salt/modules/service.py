'''
Top level package command wrapper, used to translate the os detected by the
grains to the correct service manager
'''
import subprocess
import os

grainmap = {
           'Archlinux': '/etc/rc.d',
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
    return not subprocess.call(cmd, shell=True)

def stop(name):
    '''
    Stop the specified service

    CLI Example:
    salt '*' service.stop <service name>
    '''
    cmd = os.path.join(grainmap[__grains__['os']],
            name + ' stop')
    return not subprocess.call(cmd, shell=True)

#def status(name, sig=None):
#    '''
#    Return the status for a service, returns True or False if the service
#    is running or not, pass a signiture to use to find the service via ps
#
#    CLI Example:
#    salt '*' service.status <service name> [service signature]
#    '''

