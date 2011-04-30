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

def start(svc):
    '''
    Start the specified service
    '''
    cmd = os.path.join(grainmap[__grains__['os']],
            svc + ' start')
    return not subprocess.call(cmd, shell=True)

def stop(svc):
    '''
    Stop the specified service
    '''
    cmd = os.path.join(grainmap[__grains__['os']],
            svc + ' stop')
    return not subprocess.call(cmd, shell=True)

