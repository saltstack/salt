# -*- coding: utf-8 -*-
'''
Manage PHP pecl extensions.
'''

# Import python libs
import re
import logging

# Import salt libs
import salt.utils

__func_alias__ = {
    'list_': 'list'
}

log = logging.getLogger(__name__)


def __virtual__():
    return True if salt.utils.which('pecl') else False


def _pecl(command, defaults=False):
    '''
    Execute the command passed with pecl
    '''
    cmdline = 'pecl {0}'.format(command)
    if salt.utils.is_true(defaults):
        cmdline = "printf '\n' | " + cmdline

    ret = __salt__['cmd.run_all'](cmdline)

    if ret['retcode'] == 0:
        return ret['stdout']
    else:
        log.error('Problem running pecl. Is php-pear installed?')
        return ''


def install(pecls, defaults=False, force=False, preferred_state='stable'):
    '''
    Installs one or several pecl extensions.

    pecls
        The pecl extensions to install.

    defaults
        Use default answers for extensions such as pecl_http which ask
        questions before installation. Without this option, the pecl.installed
        state will hang indefinitely when trying to install these extensions.

    force
        Whether to force the installed version or not

    .. note::
        The ``defaults`` option will be available in version 0.17.0.

    CLI Example:

    .. code-block:: bash

        salt '*' pecl.install fuse
    '''
    preferred_state = '-d preferred_state={0}'.format(preferred_state)
    if force:
        return _pecl('{0} install -f {1}'.format(preferred_state, pecls),
                     defaults=defaults)
    else:
        _pecl('{0} install {1}'.format(preferred_state, pecls),
              defaults=defaults)
        if not isinstance(pecls, list):
            pecls = [pecls]
        for pecl in pecls:
            found = False
            if '/' in pecl:
                channel, pecl = pecl.split('/')
            else:
                channel = None
            installed_pecls = list_(channel)
            for pecl in installed_pecls:
                installed_pecl_with_version = '{0}-{1}'.format(
                    pecl,
                    installed_pecls.get(pecl)[0]
                )
                if pecl in installed_pecl_with_version:
                    found = True
            if not found:
                return False
        return True


def uninstall(pecls):
    '''
    Uninstall one or several pecl extensions.

    pecls
        The pecl extensions to uninstall.

    CLI Example:

    .. code-block:: bash

        salt '*' pecl.uninstall fuse
    '''
    return _pecl('uninstall {0}'.format(pecls))


def update(pecls):
    '''
    Update one or several pecl extensions.

    pecls
        The pecl extensions to update.

    CLI Example:

    .. code-block:: bash

        salt '*' pecl.update fuse
    '''
    return _pecl('install -U {0}'.format(pecls))


def list_(channel=None):
    '''
    List installed pecl extensions.

    CLI Example:

    .. code-block:: bash

        salt '*' pecl.list
    '''
    pecls = {}
    command = 'list'
    if channel:
        command = '{0} -c {1}'.format(command, channel)
    lines = _pecl(command).splitlines()
    lines.pop(0)
    # Only one line if no package installed:
    # (no packages installed from channel pecl.php.net)
    if not lines:
        return pecls

    lines.pop(0)
    lines.pop(0)

    for line in lines:
        match = re.match('^([^ ]+)[ ]+([^ ]+)[ ]+([^ ]+)', line)
        if match:
            pecls[match.group(1)] = [match.group(2), match.group(3)]

    return pecls
