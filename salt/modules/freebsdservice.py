'''
The service module for FreeBSD
'''

# Import python libs
import os

# Import salt libs
import salt.utils
from salt.exceptions import CommandNotFoundError


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
    service = salt.utils.which('service')
    if not service:
        raise CommandNotFoundError
    for svc in __salt__['cmd.run']('{0} -e'.format(service)).splitlines():
        ret.append(os.path.basename(svc))
    return sorted(ret)


def get_disabled():
    '''
    Return what services are available but not enabled to start at boot

    CLI Example::

        salt '*' service.get_disabled
    '''
    en_ = get_enabled()
    all_ = get_all()
    return sorted(set(all_) - set(en_))


def _switch(name,                   # pylint: disable-msg=C0103
            on,                     # pylint: disable-msg=C0103
            config='/etc/rc.conf',
            **kwargs):
    '''
    '''
    nlines = []
    edited = False

    if on:
        val = "YES"
    else:
        val = "NO"

    if os.path.exists(config):
        with salt.utils.fopen(config, 'r') as ifile:
            for line in ifile:
                if not line.startswith('{0}_enable='.format(name)):
                    nlines.append(line)
                    continue
                rest = line[len(line.split()[0]):]  # keep comments etc
                nlines.append('{0}_enable="{1}"{2}'.format(name, val, rest))
                edited = True
    if not edited:
        nlines.append("{0}_enable=\"{1}\"\n".format(name, val))
    with salt.utils.fopen(config, 'w') as ofile:
        ofile.writelines(nlines)
    return True


def enable(name, config='/etc/rc.conf', **kwargs):
    '''
    Enable the named service to start at boot

    CLI Example::

        salt '*' service.enable <service name>
    '''
    return _switch(name, True, config, **kwargs)


def disable(name, config='/etc/rc.conf', **kwargs):
    '''
    Disable the named service to start at boot

    CLI Example::

        salt '*' service.disable <service name>
    '''
    return _switch(name, False, config, **kwargs)


def enabled(name):
    '''
    Return True if the named servioce is enabled, false otherwise

    CLI Example::

        salt '*' service.enabled <service name>
    '''
    return name in get_enabled()


def disabled(name):
    '''
    Return True if the named servioce is enabled, false otherwise

    CLI Example::

        salt '*' service.disabled <service name>
    '''
    return name in get_disabled()


def get_all():
    '''
    Return a list of all available services

    CLI Example::

        salt '*' service.get_all
    '''
    ret = []
    service = salt.utils.which('service')
    if not service:
        raise CommandNotFoundError
    for svc in __salt__['cmd.run']('{0} -r'.format(service)).splitlines():
        srv = os.path.basename(svc)
        if not srv.isupper():
            ret.append(srv)
    return sorted(ret)


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


def reload(name):
    '''
    Restart the named service

    CLI Example::

        salt '*' service.reload <service name>
    '''
    cmd = 'service {0} onereload'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def status(name, sig=None):
    '''
    Return the status for a service (True or False).

    name
        Name of service.

    sig : None
        Signature. If sig is passed use as service name instead of
        name argument.


    CLI Example::

        salt '*' service.status <service name>
    '''
    cmd = 'service {0} onestatus'.format(sig if sig else name)
    return not __salt__['cmd.retcode'](cmd)
