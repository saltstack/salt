# -*- coding: utf-8 -*-
'''
Support for freebsd-update utility on FreeBSD.

:maintainer:    George Mamalakis <mamalos@gmail.com>
:maturity:      new
:platform:      FreeBSD
'''

from __future__ import absolute_import


# Import python libs
import logging

# Import salt libs
import salt
import salt.utils.decorators as decorators
from salt.exceptions import CommandNotFoundError


log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'freebsd-update'


def __virtual__():
    '''
    .. versionadded:: 2016.3.4

    Only work on FreeBSD RELEASEs >= 6.2, where freebsd-update was introduced.
    '''
    if __grains__['os'] != 'FreeBSD':
        return (False, 'The freebsd_update execution module cannot be loaded: only available on FreeBSD systems.')
    if float(__grains__['osrelease']) < 6.2:
        return (False, 'freebsd_update is only available on FreeBSD versions >= 6.2-RELESE')
    if 'release' not in __grains__['kernelrelease'].lower():
        return (False, 'freebsd_update is only available on FreeBSD RELEASES')
    return __virtualname__


def _cmd(**kwargs):
    '''
    .. versionadded:: 2016.3.4

    '''
    update_cmd = salt.utils.which('freebsd-update')
    if not update_cmd:
        raise CommandNotFoundError('"freebsd-update" command not found')

    params = []
    if 'basedir' in kwargs:
        params.append('-b {0}'.format(kwargs['basedir']))
    if 'workdir' in kwargs:
        params.append('-d {0}'.format(kwargs['workdir']))
    if 'conffile' in kwargs:
        params.append('-f {0}'.format(kwargs['conffile']))
    if 'force' in kwargs:
        params.append('-F')
    if 'key' in kwargs:
        params.append('-k {0}'.format(kwargs['key']))
    if 'newrelease' in kwargs:
        params.append('-r {0}'.format(kwargs['newrelease']))
    if 'server' in kwargs:
        params.append('-s {0}'.format(kwargs['server']))
    if 'address' in kwargs:
        params.append('-t {0}'.format(kwargs['address']))

    return '{0} {1}'.format(update_cmd, ' '.join(params))


def _wrapper(orig, pre='', post='', err_=None, run_args={}, **kwargs):
    '''
    Helper function that wraps the execution of freebsd-update command.

    orig:
        Originating function that called _wrapper().

    pre:
        String that will be prepended to freebsd-update command.

    post:
        String that will be appended to freebsd-update command.

    err_:
        Dictionary on which return codes and stout/stderr are copied.

    run_args:
        Arguments to be passed on cmd.run_all.

    kwargs:
        Parameters of freebsd-update command.
    '''

    cmd = _cmd(**kwargs)
    res = __salt__['cmd.run_all']('{0} {1} {2} {3}'.format(pre, cmd, post, orig), **run_args)
    if err_ is not None: # copy return values if asked to
        for k, v in res.items():
            err_[k] = v

    if 'retcode' in res and res['retcode'] != 0:
        log.error('Unable to run "{0} {1} {2} {3}". Error: {1}'.format(pre, cmd, post, orig, res['stderr']))
        return res
    return res['stdout']


def fetch(pre='', post='', err_=None, run_args={}, **kwargs):
    '''
    .. versionadded:: 2016.3.4

    freebsd-update fetch wrapper. Based on the currently installed world and the
    configuration options set, fetch all available binary updates.

    pre:
        String that will be prepended to freebsd-update command.

    post:
        String that will be appended to freebsd-update command.

    err_:
        Dictionary on which return codes and stout/stderr are copied.

    run_args:
        Arguments to be passed on cmd.run_all.

    kwargs:
        Parameters of freebsd-update command.
    '''
    # fetch continues when no controlling terminal is present
    if float(__grains__['osrelease']) >= 10.2:
        post += '--not-running-from-cron'
    else:
        pre += ' env PAGER=cat'
        run_args['python_shell'] = True
    return _wrapper('fetch', pre=pre, post=post, err_=err_, run_args=run_args, **kwargs)


def install(pre='', post='', err_=None, run_args={}, **kwargs):
    '''
    .. versionadded:: 2016.3.4

    freebsd-update install wrapper.

    pre:
        String that will be prepended to freebsd-update command.

    post:
        String that will be appended to freebsd-update command.

    err_:
        Dictionary on which return codes and stout/stderr are copied.

    run_args:
        Arguments to be passed on cmd.run_all.

    kwargs:
        Parameters of freebsd-update command.
    '''
    return _wrapper('install', err_=err_, **kwargs)


def rollback(pre='', post='', err_=None, run_args={}, **kwargs):
    '''
    .. versionadded:: 2016.3.4

    freebsd-update rollback wrapper. Uninstalls the most recently installed
    updates.

    pre:
        String that will be prepended to freebsd-update command.

    post:
        String that will be appended to freebsd-update command.

    err_:
        Dictionary on which return codes and stout/stderr are copied.

    run_args:
        Arguments to be passed on cmd.run_all.

    kwargs:
        Parameters of freebsd-update command.
    '''
    return _wrapper('rollback', err_=err_, **kwargs)


def update(pre='', post='', err_=None, run_args={}, **kwargs):
    '''
    .. versionadded:: 2016.3.4

    Command that simplifies freebsd-update by running freebsd-update fetch first
    and then freebsd-update install.

    pre:
        String that will be prepended to freebsd-update command.

    post:
        String that will be appended to freebsd-update command.

    err_:
        Dictionary on which return codes and stout/stderr are copied.

    run_args:
        Arguments to be passed on cmd.run_all.

    kwargs:
        Parameters of freebsd-update command.
    '''
    stdout = {}
    for name, fun in zip(('fetch', 'install'), (fetch, install)):
        fun(err_=err_, **kwargs)
        if err_ is not None and 'retcode' in err_ and err_['retcode'] != 0:
            return err_
        if err_ is not None and 'stdout' in err_:
            stdout[name] = err_['stdout']
    return '\n'.join(['{0}: {1}'.format(k, v) for (k, v) in stdout.items()])


def ids(pre='', post='', err_=None, run_args={}, **kwargs):
    '''
    .. versionadded:: 2016.3.4

    freebsd-update IDS wrapper function. Compares the system against a "known
    good" index of the installed release.

    pre:
        String that will be prepended to freebsd-update command.

    post:
        String that will be appended to freebsd-update command.

    err_:
        Dictionary on which return codes and stout/stderr are copied.

    run_args:
        Arguments to be passed on cmd.run_all.

    kwargs:
        Parameters of freebsd-update command.
    '''
    return _wrapper('IDS', err_=err_, **kwargs)


def upgrade(pre='', post='', err_=None, run_args={}, **kwargs):
    '''
    .. versionadded:: 2016.3.4

    Dummy function used only to print a message that upgrade is not available.
    The reason is that upgrade needs manual intervention and reboot, so even if
    used with:

       yes | freebsd-upgrade -r VERSION

    the additional freebsd-update install that needs to run after the reboot
    cannot be implemented easily.

    pre:
        String that will be prepended to freebsd-update command.

    post:
        String that will be appended to freebsd-update command.

    err_:
        Dictionary on which return codes and stout/stderr are copied.

    run_args:
        Arguments to be passed on cmd.run_all.

    kwargs:
        Parameters of freebsd-update command.
    '''
    msg = 'freebsd-update upgrade not yet implemented.'
    log.warning(msg)
    return msg
