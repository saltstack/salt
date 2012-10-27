'''
daemontools service module. This module will create daemontools type 
service watcher. 
This module is states.service compatible so it can be used to maintain
service state via provider interface:
 
  - provider: daemontools
'''
# Import Python libs
import re

# Local variable
service_dir="/service"

def _service_path(name):
    '''
    build service path
    '''
    return '{0}/{1}'.format(service_dir,name)
	
#-- states.service  compatible args
def start(name,enable=None,sig=None):
    '''
    Starts service via daemontools

    CLI Example::
        salt '*' daemontools.start <service name>
    '''
    __salt__['file.remove']('{0}/down'.format(_service_path(name)))
    cmd = 'svc -u {0}'.format(_service_path(name))
    return not __salt__['cmd.retcode'](cmd)

	
#-- states.service compatible	
def stop(name,enable=None,sig=None):
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
def reload(name):
    '''
    Wrapper for term()
	
    CLI Example:
    salt '*' daemontools.reload <service name>
    '''
    term(name)


#-- states.service compatible
def restart(name):
    '''
    Restart service via daemontools. This will stop/start service
   
    CLI Example:
     salt '*' daemontools.restart <service name>
    '''
    ret = 'restart False'
    if stop(name) and start(name):
        ret = 'restart True'
    return ret		

	
#-- states.service compatible
def full_restart(name):		
    ''' Calls daemontools.restart() function '''
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
    m = re.search('\(pid (\d+)\)',ret)
    try:
      pid = m.group(1)
    except:
      pid = ''
    return pid


def get_all():
    '''
    Return a list of all available services

    CLI Example::
        salt '*' daemontools.get_all
    '''
    #- List all daemontools services in
    cmd = 'ls {0}/'.format(service_dir)
    all_srv = __salt__['cmd.run_stdout'](cmd)
    ret=set()
    for srv in all_srv.split():
      ret.add(srv)
    return sorted(ret) 
