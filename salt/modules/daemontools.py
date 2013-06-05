'''
daemontools service module. This module will create daemontools type
service watcher.
This module is states.service compatible so it can be used to maintain
service state via provider interface:

  - provider: daemontools
'''

# Import python libs
import os
import re

# Function alias to not shadow built-ins.
__func_alias__ = {
    'reload_': 'reload'
}

if os.path.exists('/service'):
    SERVICE_DIR = "/service"
elif os.path.exists('/var/service'):
    SERVICE_DIR = "/var/service"


def _service_path(name):
    '''
    build service path
    '''
    return '{0}/{1}'.format(SERVICE_DIR, name)


#-- states.service  compatible args
def start(name):
    '''
    Starts service via daemontools

    CLI Example::

        salt '*' daemontools.start <service name>
    '''
    __salt__['file.remove']('{0}/down'.format(_service_path(name)))
    cmd = 'svc -u {0}'.format(_service_path(name))
    return not __salt__['cmd.retcode'](cmd)


#-- states.service compatible args
def stop(name):
    '''
    Stops service via daemontools

    CLI Example::

        salt '*' daemontools.stop <service name>
    '''
    __salt__['file.touch']('{0}/down'.format(_service_path(name)))
    cmd = 'svc -d {0}'.format(_service_path(name))
    return not __salt__['cmd.retcode'](cmd)


def term(name):
    '''
    Send a TERM to service via daemontools

    CLI Example::

        salt '*' daemontools.term <service name>
    '''
    cmd = 'svc -t {0}'.format(_service_path(name))
    return not __salt__['cmd.retcode'](cmd)


#-- states.service compatible
def reload_(name):
    '''
    Wrapper for term()

    CLI Example::

        salt '*' daemontools.reload <service name>
    '''
    term(name)


#-- states.service compatible
def restart(name):
    '''
    Restart service via daemontools. This will stop/start service

    CLI Example::

        salt '*' daemontools.restart <service name>
    '''
    ret = 'restart False'
    if stop(name) and start(name):
        ret = 'restart True'
    return ret


#-- states.service compatible
def full_restart(name):
    '''
    Calls daemontools.restart() function

    CLI Example::

        salt '*' daemontools.full_restart <service name>
    '''
    restart(name)


#-- states.service compatible
def status(name, sig=None):
    '''
    Return the status for a service via daemontools, return pid if running

    CLI Example::

        salt '*' daemontools.status <service name>
    '''
    cmd = 'svstat {0}'.format(_service_path(name))
    ret = __salt__['cmd.run_stdout'](cmd)
    match = re.search(r'\(pid (\d+)\)', ret)
    try:
        pid = match.group(1)
    except Exception:
        pid = ''
    return pid


def get_all():
    '''
    Return a list of all available services

    CLI Example::

        salt '*' daemontools.get_all
    '''
    #- List all daemontools services in
    return sorted(os.listdir(SERVICE_DIR))
