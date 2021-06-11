# -*- coding: utf-8 -*-
"""
Manage Kerberos KDC

:configuration:
    In order to manage your KDC you will need to generate a keytab
    that can authenticate without requiring a password.

.. code-block:: bash

    # ktadd -k /root/secure.keytab kadmin/admin kadmin/changepw

On the KDC minion you will need to add the following to the minion
configuration file so Salt knows what keytab to use and what principal to
authenticate as.

.. code-block:: yaml

    auth_keytab: /root/auth.keytab
    auth_principal: kadmin/admin
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import Salt libs
import salt.utils.path

log = logging.getLogger(__name__)


def __virtual__():
    if salt.utils.path.which("kadmin"):
        return True

    return (False, "The kerberos execution module not loaded: kadmin not in path")


def __execute_kadmin(cmd):
    """
    Execute kadmin commands
    """
    ret = {}

    auth_keytab = __opts__.get("auth_keytab", None)
    auth_principal = __opts__.get("auth_principal", None)

    if __salt__["file.file_exists"](auth_keytab) and auth_principal:
        return __salt__["cmd.run_all"](
            'kadmin -k -t {0} -p {1} -q "{2}"'.format(auth_keytab, auth_principal, cmd)
        )
    else:
        log.error("Unable to find kerberos keytab/principal")
        ret["retcode"] = 1
        ret["comment"] = "Missing authentication keytab/principal"

    return ret


def list_principals():
    """
    Get all principals

    CLI Example:

    .. code-block:: bash

        salt 'kde.example.com' kerberos.list_principals
    """
    ret = {}

    cmd = __execute_kadmin("list_principals")

    if cmd["retcode"] != 0 or cmd["stderr"]:
        ret["comment"] = cmd["stderr"].splitlines()[-1]
        ret["result"] = False

        return ret

    ret = {"principals": []}

    for i in cmd["stdout"].splitlines()[1:]:
        ret["principals"].append(i)

    return ret


def get_principal(name):
    """
    Get princial details

    CLI Example:

    .. code-block:: bash

        salt 'kdc.example.com' kerberos.get_principal root/admin
    """
    ret = {}

    cmd = __execute_kadmin("get_principal {0}".format(name))

    if cmd["retcode"] != 0 or cmd["stderr"]:
        ret["comment"] = cmd["stderr"].splitlines()[-1]
        ret["result"] = False

        return ret

    for i in cmd["stdout"].splitlines()[1:]:
        (prop, val) = i.split(":", 1)

        ret[prop] = val

    return ret


def list_policies():
    """
    List policies

    CLI Example:

    .. code-block:: bash

        salt 'kdc.example.com' kerberos.list_policies
    """
    ret = {}

    cmd = __execute_kadmin("list_policies")

    if cmd["retcode"] != 0 or cmd["stderr"]:
        ret["comment"] = cmd["stderr"].splitlines()[-1]
        ret["result"] = False

        return ret

    ret = {"policies": []}

    for i in cmd["stdout"].splitlines()[1:]:
        ret["policies"].append(i)

    return ret


def get_policy(name):
    """
    Get policy details

    CLI Example:

    .. code-block:: bash

        salt 'kdc.example.com' kerberos.get_policy my_policy
    """
    ret = {}

    cmd = __execute_kadmin("get_policy {0}".format(name))

    if cmd["retcode"] != 0 or cmd["stderr"]:
        ret["comment"] = cmd["stderr"].splitlines()[-1]
        ret["result"] = False

        return ret

    for i in cmd["stdout"].splitlines()[1:]:
        (prop, val) = i.split(":", 1)

        ret[prop] = val

    return ret


def get_privs():
    """
    Current privileges

    CLI Example:

    .. code-block:: bash

        salt 'kdc.example.com' kerberos.get_privs
    """
    ret = {}

    cmd = __execute_kadmin("get_privs")

    if cmd["retcode"] != 0 or cmd["stderr"]:
        ret["comment"] = cmd["stderr"].splitlines()[-1]
        ret["result"] = False

        return ret

    for i in cmd["stdout"].splitlines()[1:]:
        (prop, val) = i.split(":", 1)

        ret[prop] = [j for j in val.split()]

    return ret


def create_principal(name, enctypes=None):
    """
    Create Principal

    CLI Example:

    .. code-block:: bash

        salt 'kdc.example.com' kerberos.create_principal host/example.com
    """
    ret = {}

    krb_cmd = "addprinc -randkey"

    if enctypes:
        krb_cmd += " -e {0}".format(enctypes)

    krb_cmd += " {0}".format(name)

    cmd = __execute_kadmin(krb_cmd)

    if cmd["retcode"] != 0 or cmd["stderr"]:
        if not cmd["stderr"].splitlines()[-1].startswith("WARNING:"):
            ret["comment"] = cmd["stderr"].splitlines()[-1]
            ret["result"] = False

            return ret

    return True


def delete_principal(name):
    """
    Delete Principal

    CLI Example:

    .. code-block:: bash

        salt 'kdc.example.com' kerberos.delete_principal host/example.com@EXAMPLE.COM
    """
    ret = {}

    cmd = __execute_kadmin("delprinc -force {0}".format(name))

    if cmd["retcode"] != 0 or cmd["stderr"]:
        ret["comment"] = cmd["stderr"].splitlines()[-1]
        ret["result"] = False

        return ret

    return True


def create_keytab(name, keytab, enctypes=None):
    """
    Create keytab

    CLI Example:

    .. code-block:: bash

        salt 'kdc.example.com' kerberos.create_keytab host/host1.example.com host1.example.com.keytab
    """
    ret = {}

    krb_cmd = "ktadd -k {0}".format(keytab)

    if enctypes:
        krb_cmd += " -e {0}".format(enctypes)

    krb_cmd += " {0}".format(name)

    cmd = __execute_kadmin(krb_cmd)

    if cmd["retcode"] != 0 or cmd["stderr"]:
        ret["comment"] = cmd["stderr"].splitlines()[-1]
        ret["result"] = False

        return ret

    return True
