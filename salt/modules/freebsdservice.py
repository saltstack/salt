'''
The service module for FreeBSD
'''
# Import Python libs
import os
# Import Salt libs
import salt.utils


def __virtual__():
    '''
    Only work on systems which default to systemd
    '''
    # Disable on these platforms, specific service modules exist:
    if __grains__['os'] == 'FreeBSD':
        return 'service'
    return False


def get_enabled():
    '''
    Return what services are set to run on boot

    CLI Example::

        salt '*' service.get_enabled
    '''
    ret = []
    for rcfn in ('/etc/rc.conf', '/etc/rc.conf.local'):
        if os.path.isfile(rcfn):
            for line in open(rcfn, 'r').readlines():
                clean_line = line.split('#',1)[0].strip()
                if not '_enable=' in clean_line:
                    continue
                (service, enabled) = clean_line.split('=')
                if enabled.strip('"\'').upper() != 'YES':
                    continue
                ret.append(service.replace('_enable', ''))
    return ret


def get_disabled():
    '''
    Return what services are available but not enabled to start at boot

    CLI Example::

        salt '*' service.get_disabled
    '''
    en_ = get_enabled()
    all_ = get_all()
    return sorted(set(all_) - set(en_))


def get_all():
    '''
    Return a list of all available services

    CLI Example::

        salt '*' service.get_all
    '''
    ret = set()
    for rcdir in ('/etc/rc.d/', '/usr/local/etc/rc.d/'):
        ret.update(os.listdir(rcdir))
    rm_ = set()
    for srv in ret:
        if srv.isupper():
            rm_.add(srv)
    return sorted(ret - rm_)


def start(name):
    '''
    Start the specified service

    CLI Example::

        salt '*' service.start <service name>
    '''
    cmd = 'service {0} onestart'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def stop(name):
    '''
    Stop the specified service

    CLI Example::

        salt '*' service.stop <service name>
    '''
    cmd = 'service {0} onestop'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def restart(name):
    '''
    Restart the named service

    CLI Example::

        salt '*' service.restart <service name>
    '''
    if name == 'salt-minion':
        salt.utils.daemonize_if(__opts__)
    cmd = 'service {0} onerestart'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def status(name, sig=None):
    '''
    Return the status for a service, returns the PID or an empty string if the
    service is running or not, pass a signature to use to find the service via
    ps

    CLI Example::

        salt '*' service.status <service name> [service signature]
    '''
    return __salt__['status.pid'](sig if sig else name)


