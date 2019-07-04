# -*- coding: utf-8 -*-
'''
Manage Kerberos KDC

:configuration:
    In order to manage your KDC you will need to generate a keytab
    that can authenticate without requiring a password.

    For MIT Kerberos:

.. code-block:: bash

    # ktadd -k /root/secure.keytab kadmin/admin kadmin/changepw


For Heimdal Kerberos:

.. code-block:: bash

    # ext_keytab -k /root/secure.keytab kadmin/admin


On the KDC minion you will need to add the following to the minion
configuration file so Salt knows what keytab to use and what principal to
authenticate as. Optionally you can specify which kerberos flavor to use,
the default is MIT Kerberos if left unspecified.

.. code-block:: yaml

    auth_keytab: /root/auth.keytab
    auth_principal: kadmin/admin
    krb_flavor: heimdal
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging

# Import Salt libs
import salt.utils.path

log = logging.getLogger(__name__)


def __virtual__():
    if salt.utils.path.which('kadmin'):
        return True

    return (False, 'The kerberos execution module not loaded: kadmin not in path')


def __execute_kadmin(cmd):
    '''
    Execute kadmin commands
    '''
    ret = {}

    auth_keytab = __opts__.get('auth_keytab', None)
    auth_principal = __opts__.get('auth_principal', None)

    if __salt__['file.file_exists'](auth_keytab) and auth_principal:
        krb_flavor = __opts__.get('krb_flavor', None)
        if krb_flavor == "heimdal":
            return __salt__['cmd.run_all'](
                'kadmin -K {0} -p {1} {2}'.format(
                    auth_keytab, auth_principal, cmd
                )
            )

        else:
            return __salt__['cmd.run_all'](
                'kadmin -k -t {0} -p {1} -q "{2}"'.format(
                    auth_keytab, auth_principal, cmd
                )
            )
    else:
        log.error('Unable to find kerberos keytab/principal')
        ret['retcode'] = 1
        ret['comment'] = 'Missing authentication keytab/principal'

    return ret


def list_principals():
    '''
    Get all principals

    CLI Example:

    .. code-block:: bash

        salt 'kde.example.com' kerberos.list_principals
    '''
    ret = {}
    krb_flavor = __opts__.get('krb_flavor', None)
    if krb_flavor == "heimdal":
        krb_cmd = 'get -t "*"'
    else:
        krb_cmd = 'list_principals'

    cmd = __execute_kadmin(krb_cmd)

    if cmd['retcode'] != 0 or cmd['stderr']:
        ret['comment'] = cmd['stderr'].splitlines()[-1]
        ret['result'] = False

        return ret

    ret = {'principals': []}

    for i in cmd['stdout'].splitlines()[1:]:
        ret['principals'].append(i)

    return ret


def get_principal(name):
    '''
    Get princial details

    CLI Example:

    .. code-block:: bash

        salt 'kdc.example.com' kerberos.get_principal root/admin
    '''
    ret = {}
    krb_flavor = __opts__.get('krb_flavor', None)
    if krb_flavor == "heimdal":
        krb_cmd = 'get'
    else:
        krb_cmd = 'get_principals'

    cmd = __execute_kadmin(krb_cmd + ' {0}'.format(name))

    if cmd['retcode'] != 0 or cmd['stderr']:
        ret['comment'] = cmd['stderr'].splitlines()[-1]
        ret['result'] = False

        return ret

    for i in cmd['stdout'].splitlines()[1:]:
        (prop, val) = i.split(':', 1)

        ret[prop] = val

    return ret


def list_policies():
    '''
    List policies. Not supported by Heimdal backend.

    CLI Example:

    .. code-block:: bash

        salt 'kdc.example.com' kerberos.list_policies
    '''
    ret = {}

    cmd = __execute_kadmin('list_policies')

    if cmd['retcode'] != 0 or cmd['stderr']:
        ret['comment'] = cmd['stderr'].splitlines()[-1]
        ret['result'] = False

        return ret

    ret = {'policies': []}

    for i in cmd['stdout'].splitlines()[1:]:
        ret['policies'].append(i)

    return ret


def get_policy(name):
    '''
    Get policy details. Not supported by Heimdal backend.

    CLI Example:

    .. code-block:: bash

        salt 'kdc.example.com' kerberos.get_policy my_policy
    '''
    ret = {}

    cmd = __execute_kadmin('get_policy {0}'.format(name))

    if cmd['retcode'] != 0 or cmd['stderr']:
        ret['comment'] = cmd['stderr'].splitlines()[-1]
        ret['result'] = False

        return ret

    for i in cmd['stdout'].splitlines()[1:]:
        (prop, val) = i.split(':', 1)

        ret[prop] = val

    return ret


def get_privs():
    '''
    Current privileges

    CLI Example:

    .. code-block:: bash

        salt 'kdc.example.com' kerberos.get_privs
    '''
    ret = {}
    krb_flavor = __opts__.get('krb_flavor', None)
    if krb_flavor == "heimdal":
        krb_cmd = 'privileges'
    else:
        krb_cmd = 'get_privs'

    cmd = __execute_kadmin(krb_cmd)

    if cmd['retcode'] != 0 or cmd['stderr']:
        ret['comment'] = cmd['stderr'].splitlines()[-1]
        ret['result'] = False

        return ret

    if krb_flavor == "heimdal":
        ret["privileges"] = [i.strip() for i in cmd['stdout'].split(',')]

    else:
        for i in cmd['stdout'].splitlines()[1:]:
            (prop, val) = i.split(':', 1)

            ret[prop] = [j for j in val.split()]

    return ret


def create_principal(name, enctypes=None):
    '''
    Create Principal

    CLI Example:

    .. code-block:: bash

        salt 'kdc.example.com' kerberos.create_principal host/example.com
    '''
    ret = {}
    krb_flavor = __opts__.get('krb_flavor', None)
    if krb_flavor == "heimdal":
        krb_cmd = 'add --use-defaults --random-key'
    else:
        krb_cmd = 'addprinc -randkey'
        if enctypes:
            krb_cmd += ' -e {0}'.format(enctypes)

    krb_cmd += ' {0}'.format(name)

    cmd = __execute_kadmin(krb_cmd)

    if cmd['retcode'] != 0 or cmd['stderr']:
        if not cmd['stderr'].splitlines()[-1].startswith('WARNING:'):
            ret['comment'] = cmd['stderr'].splitlines()[-1]
            ret['result'] = False

            return ret

    return True


def delete_principal(name):
    '''
    Delete Principal

    CLI Example:

    .. code-block:: bash

        salt 'kdc.example.com' kerberos.delete_principal host/example.com@EXAMPLE.COM
    '''
    ret = {}
    krb_flavor = __opts__.get('krb_flavor', None)
    if krb_flavor == "heimdal":
        krb_cmd = 'delete'
    else:
        krb_cmd = 'delprinc -force'

    cmd = __execute_kadmin(krb_cmd + ' {0}'.format(name))

    if cmd['retcode'] != 0 or cmd['stderr']:
        ret['comment'] = cmd['stderr'].splitlines()[-1]
        ret['result'] = False

        return ret

    return True


def create_keytab(name, keytab, enctypes=None):
    '''
    Create keytab

    CLI Example:

    .. code-block:: bash

        salt 'kdc.example.com' kerberos.create_keytab host/host1.example.com host1.example.com.keytab
    '''
    ret = {}

    krb_flavor = __opts__.get('krb_flavor', None)
    if krb_flavor == "heimdal":
        krb_cmd = 'ext_keytab -k {0}'.format(keytab)
    else:
        krb_cmd = 'ktadd -k {0}'.format(keytab)
        if enctypes:
            krb_cmd += ' -e {0}'.format(enctypes)

    krb_cmd += ' {0}'.format(name)

    cmd = __execute_kadmin(krb_cmd)

    if cmd['retcode'] != 0 or cmd['stderr']:
        ret['comment'] = cmd['stderr'].splitlines()[-1]
        ret['result'] = False

        return ret

    return True
