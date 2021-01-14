# -*- coding: utf-8 -*-
"""
Support for htpasswd command. Requires the apache2-utils package for Debian-based distros.

.. versionadded:: 2014.1.0

The functions here will load inside the webutil module. This allows other
functions that don't use htpasswd to use the webutil module name.
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import os

# Import salt libs
import salt.utils.path

log = logging.getLogger(__name__)

__virtualname__ = "webutil"


def __virtual__():
    """
    Only load the module if htpasswd is installed
    """
    if salt.utils.path.which("htpasswd"):
        return __virtualname__
    return (
        False,
        "The htpasswd execution mdule cannot be loaded: htpasswd binary not in path.",
    )


def useradd(pwfile, user, password, opts="", runas=None):
    """
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
    """
    if not os.path.exists(pwfile):
        opts += "c"

    cmd = ["htpasswd", "-b{0}".format(opts), pwfile, user, password]
    return __salt__["cmd.run_all"](cmd, runas=runas, python_shell=False)


def userdel(pwfile, user, runas=None, all_results=False):
    """
    Delete a user from the specified htpasswd file.

    pwfile
        Path to htpasswd file

    user
        User name

    runas
        The system user to run htpasswd command with

    all_results
        Return stdout, stderr, and retcode, not just stdout

    CLI Examples:

    .. code-block:: bash

        salt '*' webutil.userdel /etc/httpd/htpasswd larry
    """
    if not os.path.exists(pwfile):
        return "Error: The specified htpasswd file does not exist"

    cmd = ["htpasswd", "-D", pwfile, user]

    if all_results:
        out = __salt__["cmd.run_all"](cmd, runas=runas, python_shell=False)
    else:
        out = __salt__["cmd.run"](cmd, runas=runas, python_shell=False).splitlines()

    return out


def verify(pwfile, user, password, opts="", runas=None):
    """
    Return True if the htpasswd file exists, the user has an entry, and their
    password matches.

    pwfile
        Fully qualified path to htpasswd file

    user
        User name

    password
        User password

    opts
        Valid options that can be passed are:

            - `m`  Force MD5 encryption of the password (default).
            - `d`  Force CRYPT encryption of the password.
            - `p`  Do not encrypt the password (plaintext).
            - `s`  Force SHA encryption of the password.

    runas
        The system user to run htpasswd command with

    CLI Examples:

    .. code-block:: bash

        salt '*' webutil.verify /etc/httpd/htpasswd larry maybepassword
        salt '*' webutil.verify /etc/httpd/htpasswd larry maybepassword opts=ns
    """
    if not os.path.exists(pwfile):
        return False

    cmd = ["htpasswd", "-bv{0}".format(opts), pwfile, user, password]
    ret = __salt__["cmd.run_all"](cmd, runas=runas, python_shell=False)
    log.debug("Result of verifying htpasswd for user %s: %s", user, ret)

    return ret["retcode"] == 0
