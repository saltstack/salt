'''
Top level package command wrapper, used to translate the os detected by facter
to the correct package manager
'''
import subprocess
import os

factmap = {
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
    cmd = os.path.join(factmap[__facter__['operatingsystem']],
            svc + ' start')
    return not subprocess.call(cmd, shell=True)

def stop(svc):
    '''
    Stop the specified service
    '''
    cmd = os.path.join(factmap[__facter__['operatingsystem']],
            svc + ' stop')
    return not subprocess.call(cmd, shell=True)

