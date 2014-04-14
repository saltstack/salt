# -*- coding: utf-8 -*-
'''
Functions to perform introspection on a minion, and return data in a format
usable by Salt States
'''

import os

def running_service_owners(
        exclude=('/dev', '/home', '/media', '/proc', '/run', '/sys/', '/tmp',
                 '/var')
    ):
    '''
    Determine which packages own the currently running services. By default,
    excludes files whose full path starts with ``/dev``, ``/home``, ``/media``,
    ``/proc``, ``/run``, ``/sys``, ``/tmp`` and ``/var``. This can be
    overridden by passing in a new list to ``exclude``.

    CLI Example:

        salt myminion introspect.running_service_owners
    '''
    error = {}
    if not 'pkg.owner' in __salt__:
        error['Unsupported Package Manager'] = (
            'The module for the package manager on this system does not '
            'support looking up which package(s) owns which file(s)'
        )

    if not 'file.open_files' in __salt__:
        error['Unsupported File Module'] = (
            'The file module on this system does not '
            'support looking up open files on the system'
        )

    if error:
        return {'Error': error}

    ret = {}
    open_files = __salt__['file.open_files']()

    execs = __salt__['service.execs']()
    for path in open_files:
        ignore = False
        for bad_dir in exclude:
            if path.startswith(bad_dir):
                ignore = True

        if ignore:
            continue

        if not os.access(path, os.X_OK):
            continue

        for service in execs:
            if path == execs[service]:
                pkg = __salt__['pkg.owner'](path)
                ret[service] = pkg.values()[0]

    return ret


def enabled_service_owners():
    '''
    Return which packages own each of the services that are currently enabled.

    CLI Example:

        salt myminion introspect.enabled_service_owners
    '''
    error = {}
    if not 'pkg.owner' in __salt__:
        error['Unsupported Package Manager'] = (
            'The module for the package manager on this system does not '
            'support looking up which package(s) owns which file(s)'
        )

    if not 'service.show' in __salt__:
        error['Unsupported Service Manager'] = (
            'The module for the service manager on this system does not '
            'support showing descriptive service data'
        )

    if error:
        return {'Error': error}

    ret = {}
    services = __salt__['service.get_enabled']()

    for service in services:
        data = __salt__['service.show'](service)
        if not 'ExecStart' in data:
            continue
        start_cmd = data['ExecStart']['path']
        pkg = __salt__['pkg.owner'](start_cmd)
        ret[service] = pkg.values()[0]

    return ret
