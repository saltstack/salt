'''
The service module for FreeBSD
'''

import os


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
                if not line.strip():
                    continue
                if line.startswith('#'):
                    continue
                if not '_enable' in line:
                    continue
                if not '=' in line:
                    continue
                comps = line.split('=')
                if 'YES' in comps[1]:
                    # Is enabled!
                    ret.append(comps[0].split('_')[0])
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
    sig = name if not sig else sig
    cmd = "{0[ps]} | grep {1} | grep -v grep | awk '{{print $2}}'".format(
            __grains__, sig)
    return __salt__['cmd.run'](cmd).strip()


