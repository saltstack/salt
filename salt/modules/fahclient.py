'''
Support for FAHClient
'''

import os
import salt.utils

def __virtual__():
    '''
    Only load the module if FAHClient is installed
    '''
    if salt.utils.which('FAHClient'):
        return 'fahclient'
    return False


def version():
    '''
    Return FAHClient version
    
    CLI Example::

        salt '*' fahclient.version
    '''
    cmd = 'FAHClient --version'
    ret = __salt__['cmd.run'](cmd)
    return ret


def user(name):
    '''
    Configure FAHClient username
    
    CLI Example::

        salt '*' fahclient.username <username>
    '''
    filename = '/etc/fahclient/config.xml'
    if os.path.exists(filename):
        __salt__['file.sed'](filename, '<user value=".*"/>', 
            '<user value="{0}"/>'.format(name))
    return name
    

def team(team):
    '''
    Configure FAHClient team
    
    CLI Example::

        salt '*' fahclient.team <team number>
    '''
    filename = '/etc/fahclient/config.xml'
    if os.path.exists(filename):
        __salt__['file.sed'](filename, '<team value=".*"/>', 
            '<team value="{0}"/>'.format(team))
    return team


def passkey(passkey):
    '''
    Configure FAHClient passkey
    
    CLI Example::
    
        salt '*' fahclient.passkey <passkey>
    '''
    filename = '/etc/fahclient/config.xml'
    if os.path.exists(filename):
        __salt__['file.sed'](filename, '<passkey value=".*"/>', 
            '<passkey value="{0}"/>'.format(passkey))
    return key


def power(power):
    '''
    Configure FAHClient power setting
    
    CLI Example::
    
        salt '*' fahclient.power [<off>|<idle light>|<idle>|<light>|<medium>|<full>]
    '''
    filename = '/etc/fahclient/config.xml'
    if os.path.exists(filename):
        __salt__['file.sed'](filename, '<power value=".*"/>', 
            '<power value="{0}"/>'.format(power))
    return power


def start():
    '''
    Start the FAHClient
    
    CLI Example::

	    salt '*' fahclient.start
    '''
    ret = __salt__['service.start']('FAHClient')
    return ret


def stop():
    '''
    Stop the FAHClient
    
    CLI Example::

        salt '*' fahclient.stop
    '''
    ret = __salt__['service.stop']('FAHClient')
    return ret


def restart():
    '''
    Restart the FAHClient
    
    CLI Example::

        salt '*' fahclient.restart
    '''
    ret = __salt__['service.restart']('FAHClient')
    return ret


def reload():
    '''
    Restart the FAHClient
    
    CLI Example::

        salt '*' fahclient.reload
    '''
    ret = __salt__['service.reload']('FAHClient')
    return ret


def status():
    '''
    Restart the FAHClient
    
    CLI Example::

        salt '*' fahclient.status
    '''
    ret = __salt__['service.status']('FAHClient')
    return ret
