# -*- coding: utf-8 -*-
'''
Support for htpasswd command

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
    return False


def useradd_all(pwfile, user, password, opts=''):
    '''
    Add an HTTP user using the htpasswd command. If the htpasswd file does not
    exist, it will be created. Valid options that can be passed are:

        n  Don't update file; display results on stdout.
        m  Force MD5 encryption of the password (default).
        d  Force CRYPT encryption of the password.
        p  Do not encrypt the password (plaintext).
        s  Force SHA encryption of the password.

    CLI Examples:

    .. code-block:: bash

        salt '*' webutil.useradd /etc/httpd/htpasswd larry badpassword
        salt '*' webutil.useradd /etc/httpd/htpasswd larry badpass opts=ns
    '''
    if not os.path.exists(pwfile):
        opts += 'c'

    cmd = ['htpasswd', '-b{0}'.format(opts), pwfile, user, password]
    return __salt__['cmd.run_all'](cmd, python_shell=False)


def useradd(pwfile, user, password, opts=''):
    '''
    Add an HTTP user using the htpasswd command. If the htpasswd file does not
    exist, it will be created. Valid options that can be passed are:

        n  Don't update file; display results on stdout.
        m  Force MD5 encryption of the password (default).
        d  Force CRYPT encryption of the password.
        p  Do not encrypt the password (plaintext).
        s  Force SHA encryption of the password.

    CLI Examples:

    .. code-block:: bash

        salt '*' webutil.useradd /etc/httpd/htpasswd larry badpassword
        salt '*' webutil.useradd /etc/httpd/htpasswd larry badpass opts=ns
    '''
    return useradd_all(pwfile, user, password, opts=opts)['out'].splitlines()


def userdel(pwfile, user):
    '''
    Delete an HTTP user from the specified htpasswd file.

    CLI Examples:

    .. code-block:: bash

        salt '*' webutil.userdel /etc/httpd/htpasswd larry
    '''
    if not os.path.exists(pwfile):
        return 'Error: The specified htpasswd file does not exist'

    cmd = ['htpasswd', '-D', pwfile, user]
    out = __salt__['cmd.run'](cmd, python_shell=False).splitlines()
    return out
