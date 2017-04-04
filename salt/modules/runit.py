# -*- coding: utf-8 -*-
'''
runit service module
(http://smarden.org/runit)

This module is compatible with the :mod:`service <salt.states.service>` states,
so it can be used to maintain services using the ``provider`` argument:

.. code-block:: yaml

    myservice:
      service:
        - running
        - provider: runit

Provides virtual `service` module on systems using runit as init.


Service management rules (`sv` command):

    service $n is ENABLED   if file SERVICE_DIR/$n/run exists
    service $n is AVAILABLE if ENABLED or if file AVAIL_SVR_DIR/$n/run exists
    service $n is DISABLED  if AVAILABLE but not ENABLED

    SERVICE_DIR/$n is normally a symlink to a AVAIL_SVR_DIR/$n folder


Service auto-start/stop mechanism:

    `sv` (auto)starts/stops service as soon as SERVICE_DIR/<service> is
    created/deleted, both on service creation or a boot time.

    autostart feature is disabled if file SERVICE_DIR/<n>/down exists. This
    does not affect the current's service status (if already running) nor
    manual service management.


Service's alias:

    Service `sva` is an alias of service `svc` when `AVAIL_SVR_DIR/sva` symlinks
    to folder `AVAIL_SVR_DIR/svc`. `svc` can't be enabled if it is already
    enabled through an alias already enabled, since `sv` files are stored in
    folder `SERVICE_DIR/svc/`.

    XBPS package management uses a service's alias to provides service
    alternative(s), such as chrony and openntpd both aliased to ntpd.
'''
from __future__ import absolute_import

# Import python libs
import os
import glob
import logging
import time

log = logging.getLogger(__name__)

# Import salt libs
from salt.exceptions import CommandExecutionError
import salt.utils

# Function alias to not shadow built-ins.
__func_alias__ = {
    'reload_': 'reload'
}

# which dir sv works with
VALID_SERVICE_DIRS = [
    '/service',
    '/var/service',
    '/etc/service',
]
SERVICE_DIR = None
for service_dir in VALID_SERVICE_DIRS:
    if os.path.exists(service_dir):
        SERVICE_DIR = service_dir
        break

# available service directory(ies)
AVAIL_SVR_DIRS = []

# Define the module's virtual name
__virtualname__ = 'service'


def __virtual__():
    '''
    Virtual service only on systems using runit as init process (PID 1).
    Otherwise, use this module with the provider mechanism.
    '''
    if __grains__.get('init') == 'runit':
        if __grains__['os'] == 'Void':
            add_svc_avail_path('/etc/sv')
        return __virtualname__
    return False


def _service_path(name):
    '''
    Return SERVICE_DIR+name if possible

    name
        the service's name to work on
    '''
    if not SERVICE_DIR:
        raise CommandExecutionError('Could not find service directory.')
    return os.path.join(SERVICE_DIR, name)


#-- states.service  compatible args
def start(name):
    '''
    Start service

    name
        the service's name

    CLI Example:

    .. code-block:: bash

        salt '*' runit.start <service name>
    '''
    cmd = 'sv start {0}'.format(_service_path(name))
    return not __salt__['cmd.retcode'](cmd)


#-- states.service compatible args
def stop(name):
    '''
    Stop service

    name
        the service's name

    CLI Example:

    .. code-block:: bash

        salt '*' runit.stop <service name>
    '''
    cmd = 'sv stop {0}'.format(_service_path(name))
    return not __salt__['cmd.retcode'](cmd)


#-- states.service compatible
def reload_(name):
    '''
    Reload service

    name
        the service's name

    CLI Example:

    .. code-block:: bash

        salt '*' runit.reload <service name>
    '''
    cmd = 'sv reload {0}'.format(_service_path(name))
    return not __salt__['cmd.retcode'](cmd)


#-- states.service compatible
def restart(name):
    '''
    Restart service

    name
        the service's name

    CLI Example:

    .. code-block:: bash

        salt '*' runit.restart <service name>
    '''
    cmd = 'sv restart {0}'.format(_service_path(name))
    return not __salt__['cmd.retcode'](cmd)


#-- states.service compatible
def full_restart(name):
    '''
    Calls runit.restart()

    name
        the service's name

    CLI Example:

    .. code-block:: bash

        salt '*' runit.full_restart <service name>
    '''
    restart(name)


#-- states.service compatible
def status(name, sig=None):
    '''
    Return ``True`` if service is running

    name
        the service's name

    sig
        signature to identify with ps

    CLI Example:

    .. code-block:: bash

        salt '*' runit.status <service name>
    '''
    if sig:
        # usual way to do by others (debian_service, netbsdservice).
        # XXX probably does not work here (check 'runsv sshd' instead of 'sshd' ?)
        return bool(__salt__['status.pid'](sig))

    svc_path = _service_path(name)
    if not os.path.exists(svc_path):
        # service does not exist
        return False

    # sv return code is not relevant to get a service status.
    # Check its output instead.
    cmd = 'sv status {0}'.format(svc_path)
    try:
        out = __salt__['cmd.run_stdout'](cmd)
        return out.startswith('run: ')
    except Exception:
        # sv (as a command) returned an error
        return False


def _is_svc(svc_path):
    '''
    Return ``True`` if directory <svc_path> is really a service:
    file <svc_path>/run exists and is executable

    svc_path
        the (absolute) directory to check for compatibility
    '''
    run_file = os.path.join(svc_path, 'run')
    if (os.path.exists(svc_path)
         and os.path.exists(run_file)
         and os.access(run_file, os.X_OK)):
        return True
    return False


def status_autostart(name):
    '''
    Return ``True`` if service <name> is autostarted by sv
    (file $service_folder/down does not exist)
    NB: return ``False`` if the service is not enabled.

    name
        the service's name

    CLI Example:

    .. code-block:: bash

        salt '*' runit.status_autostart <service name>
    '''
    return not os.path.exists(os.path.join(_service_path(name), 'down'))


def get_svc_broken_path(name='*'):
    '''
    Return list of broken path(s) in SERVICE_DIR that match ``name``

    A path is broken if it is a broken symlink or can not be a runit service

    name
        a glob for service name. default is '*'

    CLI Example:

    .. code-block:: bash

        salt '*' runit.get_svc_broken_path <service name>
    '''
    if not SERVICE_DIR:
        raise CommandExecutionError('Could not find service directory.')

    ret = set()

    for el in glob.glob(os.path.join(SERVICE_DIR, name)):
        if not _is_svc(el):
            ret.add(el)
    return sorted(ret)


def get_svc_avail_path():
    '''
    Return list of paths that may contain available services
    '''
    return AVAIL_SVR_DIRS


def add_svc_avail_path(path):
    '''
    Add a path that may contain available services.
    Return ``True`` if added (or already present), ``False`` on error.

    path
        directory to add to AVAIL_SVR_DIRS
    '''
    if os.path.exists(path):
        if path not in AVAIL_SVR_DIRS:
            AVAIL_SVR_DIRS.append(path)
        return True
    return False


def _get_svc_path(name='*', status=None):
    '''
    Return a list of paths to services with ``name`` that have the specified ``status``

    name
        a glob for service name. default is '*'

    status
        None       : all services (no filter, default choice)
        'DISABLED' : available service(s) that is not enabled
        'ENABLED'  : enabled service (whether started on boot or not)
    '''

    # This is the core routine to work with services, called by many
    # other functions of this module.
    #
    # The name of a service is the "apparent" folder's name that contains its
    # "run" script. If its "folder" is a symlink, the service is an "alias" of
    # the targeted service.

    if not SERVICE_DIR:
        raise CommandExecutionError('Could not find service directory.')

    # path list of enabled services as /AVAIL_SVR_DIRS/$service,
    # taking care of any service aliases (do not use os.path.realpath()).
    ena = set()
    for el in glob.glob(os.path.join(SERVICE_DIR, name)):
        if _is_svc(el):
            ena.add(os.readlink(el))
            log.trace('found enabled service path: {0}'.format(el))

    if status == 'ENABLED':
        return sorted(ena)

    # path list of available services as /AVAIL_SVR_DIRS/$service
    ava = set()
    for d in AVAIL_SVR_DIRS:
        for el in glob.glob(os.path.join(d, name)):
            if _is_svc(el):
                ava.add(el)
                log.trace('found available service path: {0}'.format(el))

    if status == 'DISABLED':
        # service available but not enabled
        ret = ava.difference(ena)
    else:
        # default: return available services
        ret = ava.union(ena)

    return sorted(ret)


def _get_svc_list(name='*', status=None):
    '''
    Return list of services that have the specified service ``status``

    name
        a glob for service name. default is '*'

    status
        None       : all services (no filter, default choice)
        'DISABLED' : available service that is not enabled
        'ENABLED'  : enabled service (whether started on boot or not)
    '''
    return sorted([os.path.basename(el) for el in _get_svc_path(name, status)])


def get_svc_alias():
    '''
    Returns the list of service's name that are aliased and their alias path(s)
    '''

    ret = {}
    for d in AVAIL_SVR_DIRS:
        for el in glob.glob(os.path.join(d, '*')):
            if not os.path.islink(el):
                continue
            psvc = os.readlink(el)
            if not os.path.isabs(psvc):
                psvc = os.path.join(d, psvc)
            nsvc = os.path.basename(psvc)
            if nsvc not in ret:
                ret[nsvc] = []
            ret[nsvc].append(el)
    return ret


def available(name):
    '''
    Returns ``True`` if the specified service is available, otherwise returns
    ``False``.

    name
        the service's name

    CLI Example:

    .. code-block:: bash

        salt '*' runit.available <service name>
    '''
    return name in _get_svc_list(name)


def missing(name):
    '''
    The inverse of runit.available.
    Returns ``True`` if the specified service is not available, otherwise returns
    ``False``.

    name
        the service's name

    CLI Example:

    .. code-block:: bash

        salt '*' runit.missing <service name>
    '''
    return name not in _get_svc_list(name)


def get_all():
    '''
    Return a list of all available services

    CLI Example:

    .. code-block:: bash

        salt '*' runit.get_all
    '''
    return _get_svc_list()


def get_enabled():
    '''
    Return a list of all enabled services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_enabled
    '''
    return _get_svc_list(status='ENABLED')


def get_disabled():
    '''
    Return a list of all disabled services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_disabled
    '''
    return _get_svc_list(status='DISABLED')


def enabled(name):
    '''
    Return ``True`` if the named service is enabled, ``False`` otherwise

    name
        the service's name

    CLI Example:

    .. code-block:: bash

        salt '*' service.enabled <service name>
    '''
    # exhaustive check instead of (only) os.path.exists(_service_path(name))
    return name in _get_svc_list(name, 'ENABLED')


def disabled(name):
    '''
    Return ``True`` if the named service is disabled, ``False``  otherwise

    name
        the service's name

    CLI Example:

    .. code-block:: bash

        salt '*' service.disabled <service name>
    '''
    # return True for a non-existent service
    return name not in _get_svc_list(name, 'ENABLED')


def show(name):
    '''
    Show properties of one or more units/jobs or the manager

    name
        the service's name

    CLI Example:

        salt '*' service.show <service name>
    '''
    ret = {}
    ret['enabled'] = False
    ret['disabled'] = True
    ret['running'] = False
    ret['service_path'] = None
    ret['autostart'] = False
    ret['command_path'] = None

    ret['available'] = available(name)
    if not ret['available']:
        return ret

    ret['enabled'] = enabled(name)
    ret['disabled'] = not ret['enabled']
    ret['running'] = status(name)
    ret['autostart'] = status_autostart(name)
    ret['service_path'] = _get_svc_path(name)[0]
    if ret['service_path']:
        ret['command_path'] = os.path.join(ret['service_path'], 'run')

    # XXX provide info about alias ?

    return ret


def enable(name, start=False, **kwargs):
    '''
    Start service ``name`` at boot.
    Returns ``True`` if operation is successful

    name
        the service's name

    start
        ``False`` : Do not start the service once enabled. Default mode.
                    (consistent with other service management)
        ``True``  : also start the service at the same time (default sv mode)

    CLI Example:

    .. code-block:: bash

        salt '*' service.enable <name> [start=True]
    '''

    # non-existent service
    if not available(name):
        return False

    # if service is aliased, refuse to enable it
    alias = get_svc_alias()
    if name in alias:
        log.error('This service is aliased, enable its alias instead')
        return False

    # down_file: file that disables sv autostart
    svc_realpath = _get_svc_path(name)[0]
    down_file = os.path.join(svc_realpath, 'down')

    # if service already enabled, remove down_file to
    # let service starts on boot (as requested)
    if enabled(name):
        if os.path.exists(down_file):
            try:
                os.unlink(down_file)
            except OSError:
                log.error('Unable to remove file {0}'.format(down_file))
                return False
        return True

    # let's enable the service

    if not start:
        # create a temp 'down' file BEFORE enabling service.
        # will prevent sv from starting this service automatically.
        log.trace('need a temporary file {0}'.format(down_file))
        if not os.path.exists(down_file):
            try:
                salt.utils.fopen(down_file, "w").close()  # pylint: disable=resource-leakage
            except IOError:
                log.error('Unable to create file {0}'.format(down_file))
                return False

    # enable the service
    try:
        os.symlink(svc_realpath, _service_path(name))

    except IOError:
        # (attempt to) remove temp down_file anyway
        log.error('Unable to create symlink {0}'.format(down_file))
        if not start:
            os.unlink(down_file)
        return False

    # ensure sv is aware of this new service before continuing.
    # if not, down_file might be removed too quickly,
    # before 'sv' have time to take care about it.
    # Documentation indicates that a change is handled within 5 seconds.
    cmd = 'sv status {0}'.format(_service_path(name))
    retcode_sv = 1
    count_sv = 0
    while retcode_sv != 0 and count_sv < 10:
        time.sleep(0.5)
        count_sv += 1
        call = __salt__['cmd.run_all'](cmd)
        retcode_sv = call['retcode']

    # remove the temp down_file in any case.
    if (not start) and os.path.exists(down_file):
        try:
            os.unlink(down_file)
        except OSError:
            log.error('Unable to remove temp file {0}'.format(down_file))
            retcode_sv = 1

    # if an error happened, revert our changes
    if retcode_sv != 0:
        os.unlink(os.path.join([_service_path(name), name]))
        return False
    return True


def disable(name, stop=False, **kwargs):
    '''
    Don't start service ``name`` at boot
    Returns ``True`` if operation is successfull

    name
        the service's name

    stop
        if True, also stops the service

    CLI Example:

    .. code-block:: bash

        salt '*' service.disable <name> [stop=True]
    '''

    # non-existent as registrered service
    if not enabled(name):
        return False

    # down_file: file that prevent sv autostart
    svc_realpath = _get_svc_path(name)[0]
    down_file = os.path.join(svc_realpath, 'down')

    if stop:
        stop(name)

    if not os.path.exists(down_file):
        try:
            salt.utils.fopen(down_file, "w").close()  # pylint: disable=resource-leakage
        except IOError:
            log.error('Unable to create file {0}'.format(down_file))
            return False

    return True


def remove(name):
    '''
    Remove the service <name> from system.
    Returns ``True`` if operation is successfull.
    The service will be also stopped.

    name
        the service's name

    CLI Example:

    .. code-block:: bash

        salt '*' service.remove <name>
    '''

    if not enabled(name):
        return False

    svc_path = _service_path(name)
    if not os.path.islink(svc_path):
        log.error('{0} is not a symlink: not removed'.format(svc_path))
        return False

    if not stop(name):
        log.error('Failed to stop service {0}'.format(name))
        return False
    try:
        os.remove(svc_path)
    except IOError:
        log.error('Unable to remove symlink {0}'.format(svc_path))
        return False
    return True


# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
