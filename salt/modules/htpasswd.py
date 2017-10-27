# -*- coding: utf-8 -*-
'''
Support for htpasswd command. Requires the apache2-utils package for Debian-based distros.

.. versionadded:: 2014.1.0

The functions here will load inside the webutil module. This allows other
functions that don't use htpasswd to use the webutil module name.
'''
from __future__ import absolute_import

# Import python libs
import os
import logging

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)

__virtualname__ = 'webutil'


def __virtual__():
    '''
    Only load the module if htpasswd is installed
    '''
    if salt.utils.which('htpasswd'):
        return __virtualname__
    return (False, 'The htpasswd execution mdule cannot be loaded: htpasswd binary not in path.')


def useradd_all(pwfile, user, password, opts='', runas=None):
    '''
    Add a user to htpasswd file using the htpasswd command. If the htpasswd
    file does not exist, it will be created.

    .. deprecated:: 2016.3.0

    pwfile
        Path to htpasswd file

    user
        User name

    password
        User password

    opts
        Valid options that can be passed are:

            - `n`  Don't update file; display results on stdout.
            - `m`  Force MD5 encryption of the password (default).
            - `d`  Force CRYPT encryption of the password.
            - `p`  Do not encrypt the password (plaintext).
            - `s`  Force SHA encryption of the password.

    runas
        The system user to run htpasswd command with

    CLI Examples:

    .. code-block:: bash

        salt '*' webutil.useradd /etc/httpd/htpasswd larry badpassword
        salt '*' webutil.useradd /etc/httpd/htpasswd larry badpass opts=ns
    '''
    salt.utils.warn_until('Nitrogen',
                          '\'htpasswd.useradd_all\' has been deprecated in favor of \'htpasswd.useradd\'. '
                          'It\'s functionality will be removed in Salt Nitrogen. '
                          'Please migrate to using \'useradd\' instead of \'useradd_all\'.')

    return useradd(pwfile, user, password, opts=opts, runas=runas)


def useradd(pwfile, user, password, opts='', runas=None):
    '''
    Add a user to htpasswd file using the htpasswd command. If the htpasswd
    file does not exist, it will be created.

    pwfile
        Path to htpasswd file

    user
        User name

    password
        User password

    opts
        Valid options that can be passed are:

            - `n`  Don't update file; display results on stdout.
            - `m`  Force MD5 encryption of the password (default).
            - `d`  Force CRYPT encryption of the password.
            - `p`  Do not encrypt the password (plaintext).
            - `s`  Force SHA encryption of the password.

    runas
        The system user to run htpasswd command with

    CLI Examples:

    .. code-block:: bash

        salt '*' webutil.useradd /etc/httpd/htpasswd larry badpassword
        salt '*' webutil.useradd /etc/httpd/htpasswd larry badpass opts=ns
    '''
    if not os.path.exists(pwfile):
        opts += 'c'

    cmd = ['htpasswd', '-b{0}'.format(opts), pwfile, user, password]
    return __salt__['cmd.run_all'](cmd, runas=runas, python_shell=False)


def userdel(pwfile, user, runas=None):
    '''
    Delete a user from the specified htpasswd file.

    pwfile
        Path to htpasswd file

    user
        User name

    runas
        The system user to run htpasswd command with

    CLI Examples:

    .. code-block:: bash

        salt '*' webutil.userdel /etc/httpd/htpasswd larry
    '''
    if not os.path.exists(pwfile):
        return 'Error: The specified htpasswd file does not exist'

    cmd = ['htpasswd', '-D', pwfile, user]
    out = __salt__['cmd.run'](cmd, runas=runas,
                              python_shell=False).splitlines()
    return out
