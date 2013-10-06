# -*- coding: utf-8 -*-
'''
Manage PHP pecl extensions.
'''

# Import python libs
import re
import logging

# Import salt libs
import salt.utils

__opts__ = {}
__pillar__ = {}

__func_alias__ = {
    'list_': 'list'
}

log = logging.getLogger(__name__)


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


def install(pecls, defaults=False, force=False):
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
    if force:
        return _pecl('install -f {0}'.format(pecls), defaults=defaults)
    else:
        return _pecl('install {0}'.format(pecls), defaults=defaults)


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


def list_():
    '''
    List installed pecl extensions.

    CLI Example:

    .. code-block:: bash

        salt '*' pecl.list
    '''
    pecls = {}
    lines = _pecl('list').splitlines()
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
