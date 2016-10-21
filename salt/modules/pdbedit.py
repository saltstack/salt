# -*- coding: utf-8 -*-
'''
Module for Samba's pdbedit tool
'''
from __future__ import absolute_import

# Import Python libs
import logging
import hashlib
import binascii
try:
    from shlex import quote as _quote_args  # pylint: disable=e0611
except ImportError:
    from pipes import quote as _quote_args

# Import Salt libs
import salt.utils

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'pdbedit'

# Function aliases
__func_alias__ = {
    'list_users': 'list',
    'get_user': 'get',
}


def __virtual__():
    '''
    Provides pdbedit if available
    '''
    if salt.utils.which('pdbedit'):
        return __virtualname__
    return (
        False,
        '{0} module can only be loaded when pdbedit is available'.format(
            __virtualname__
        )
    )


def generate_nt_hash(password):
    '''
    Generate a NT HASH
    '''
    return binascii.hexlify(
        hashlib.new(
            'md4',
            password.encode('utf-16le')
        ).digest()
    ).upper()


def list_users(verbose=True, hashes=False):
    '''
    List user accounts

    verbose : boolean
        return all information
    hashes : boolean
        include NTHASH and LMHASH in verbose output

    CLI Example:

    .. code-block:: bash

        salt '*' pdbedit.list
    '''
    users = {} if verbose else []

    if verbose:
        ## parse detailed user data
        res = __salt__['cmd.run_all'](
            'pdbedit --list --verbose {hashes}'.format(hashes="--smbpasswd-style" if hashes else ""),
        )

        if res['retcode'] > 0:
            log.error(res['stderr'] if 'stderr' in res else res['stdout'])
        else:
            user_data = {}
            for user in res['stdout'].splitlines():
                if user.startswith('-'):
                    if len(user_data) > 0:
                        users[user_data['unix username']] = user_data
                    user_data = {}
                else:
                    label = user[:user.index(':')].strip().lower()
                    data = user[(user.index(':')+1):].strip()
                    user_data[label] = data

            if len(user_data) > 0:
                users[user_data['unix username']] = user_data
    else:
        ## list users
        res = __salt__['cmd.run_all']('pdbedit --list')

        if res['retcode'] > 0:
            return {'Error': res['stderr'] if 'stderr' in res else res['stdout']}
        else:
            for user in res['stdout'].splitlines():
                users.append(user.split(':')[0])

    return users


def get_user(login, hashes=False):
    '''
    Get user account details

    login : string
        login name
    hashes : boolean
        include NTHASH and LMHASH in verbose output

    CLI Example:

    .. code-block:: bash

        salt '*' pdbedit.get kaylee
    '''
    users = list_users(verbose=True, hashes=hashes)
    return users[login] if login in users else {}


def delete(login):
    '''
    Delete user account

    login : string
        login name

    CLI Example:

    .. code-block:: bash

        salt '*' pdbedit.delete wash
    '''
    if login in list_users(False):
        res = __salt__['cmd.run_all'](
            'pdbedit --delete {login}'.format(login=_quote_args(login)),
        )

        if res['retcode'] > 0:
            return {'Error': res['stderr'] if 'stderr' in res else res['stdout']}

    return True


def create(login, password, password_hashed=False, machine_account=False):
    '''
    Create user account

    login : string
        login name
    password : string
        password
    password_hashed : boolean
        set if password is a nt hash instead of plain text
    machine_account : boolean
        set to create a machine trust account instead

    CLI Example:

    .. code-block:: bash

        salt '*' pdbedit.create zoe 9764951149F84E770889011E1DC4A927 nthash
        salt '*' pdbedit.create river  1sw4ll0w3d4bug
    '''
    ## generate nt hash if needed
    if password_hashed:
        password_hash = password.upper()
        password = ""  # wipe password
    else:
        password_hash = generate_nt_hash(password)

    ## create user
    if login not in list_users(False):
        # NOTE: --create requires a password, even if blank
        res = __salt__['cmd.run_all'](
            cmd='pdbedit --create --user {login} -t {machine}'.format(
                login=_quote_args(login),
                machine="--machine" if machine_account else "",
            ),
            stdin="{password}\n{password}\n".format(password=password),
        )

        if res['retcode'] > 0:
            return {'Error': res['stderr'] if 'stderr' in res else res['stdout']}

    ## update password if needed
    user = get_user(login, True)
    if user['nt hash'] != password_hash:
        res = __salt__['cmd.run_all'](
            'pdbedit --modify --user {login} --set-nt-hash={nthash}'.format(
                login=_quote_args(login),
                nthash=_quote_args(password_hash)
            ),
        )

        if res['retcode'] > 0:
            return {'Error': res['stderr'] if 'stderr' in res else res['stdout']}

    return True


def modify(
    login, password=None, password_hashed=False,
    domain=None, profile=None, script=None,
    drive=None, homedir=None, fullname=None,
    account_desc=None, machine_sid=None, user_sid=None,
):
    '''
    Modify user account

    login : string
        login name
    password : string
        password
    password_hashed : boolean
        set if password is a nt hash instead of plain text
    domain : string
        users domain
    profile : string
        profile path
    script : string
        logon script
    drive : string
        home drive
    homedir : string
        home directory
    fullname : string
        full name
    account_desc : string
        account description
    machine_sid : string
        specify the machines new primary group SID or rid
    user_sid : string
        specify the users new primary group SID or rid

    CLI Example:

    .. code-block:: bash

        salt '*' pdbedit.modify inara fullname='Inara Serra'
        salt '*' pdbedit.modify simon password=r1v3r
        salt '*' pdbedit.modify jane drive='V:' homedir='\\\\serenity\\jane\\profile'
    '''
    ## flag mapping
    flags = {
        'domain': '--domain=',
        'full name': '--fullname=',
        'account desc': '--account-desc=',
        'home directory': '--homedir=',
        'homedir drive': '--drive=',
        'profile path': '--profile=',
        'logon script': '--script=',
        'user sid': '-U ',
        'machine sid': '-M ',
    }

    ## field mapping
    provided = {
        'domain': domain,
        'full name': fullname,
        'account desc': account_desc,
        'home directory': homedir,
        'homedir drive': drive,
        'profile path': profile,
        'logon script': script,
        'user sid': user_sid,
        'machine sid': machine_sid,
    }

    ## update password
    if password:
        res = create(login, password, password_hashed)
        if not isinstance(res, bool):
            return res

    ## check for changes
    current = get_user(login, hashes=True)
    changes = {}
    for key, val in provided.items():
        if key in ['user sid', 'machine sid']:
            if val is not None and key in current and not current[key].endswith(str(val)):
                changes[key] = str(val)
        else:
            if val is not None and key in current and current[key] != val:
                changes[key] = val

    if len(changes) > 0:
        cmds = []
        for change in changes:
            cmds.append('{flag}{value}'.format(
                flag=flags[change],
                value=_quote_args(changes[change]),
            ))

        res = __salt__['cmd.run_all'](
            'pdbedit --modify --user {login} {changes}'.format(
                login=_quote_args(login),
                changes=" ".join(cmds),
            ),
        )

        if res['retcode'] > 0:
            return {'Error': res['stderr'] if 'stderr' in res else res['stdout']}

    return True

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
