# -*- coding: utf-8 -*-
'''
Manage the password database on Solaris systems

.. important::
    If you feel that Salt should be using this module to manage passwords on a
    minion, and it is using a different module (or gives an error similar to
    *'shadow.info' is not available*), see :ref:`here
    <module-provider-override>`.
'''
from __future__ import absolute_import

# Import python libs
import os
try:
    import spwd
    HAS_SPWD = True
except ImportError:
    # SmartOS joyent_20130322T181205Z does not have spwd
    HAS_SPWD = False
    try:
        import pwd
    except ImportError:
        pass  # We're most likely on a Windows machine.

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError
try:
    import salt.utils.pycrypto
    HAS_CRYPT = True
except ImportError:
    HAS_CRYPT = False


# Define the module's virtual name
__virtualname__ = 'shadow'


def __virtual__():
    '''
    Only work on POSIX-like systems
    '''
    if __grains__.get('kernel', '') == 'SunOS':
        return __virtualname__
    return False


def default_hash():
    '''
    Returns the default hash used for unset passwords

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.default_hash
    '''
    return '!'


def info(name):
    '''
    Return information for the specified user

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.info root
    '''
    if HAS_SPWD:
        try:
            data = spwd.getspnam(name)
            ret = {
                'name': data.sp_nam,
                'passwd': data.sp_pwd,
                'lstchg': data.sp_lstchg,
                'min': data.sp_min,
                'max': data.sp_max,
                'warn': data.sp_warn,
                'inact': data.sp_inact,
                'expire': data.sp_expire}
        except KeyError:
            ret = {
                'name': '',
                'passwd': '',
                'lstchg': '',
                'min': '',
                'max': '',
                'warn': '',
                'inact': '',
                'expire': ''}
        return ret

    # SmartOS joyent_20130322T181205Z does not have spwd, but not all is lost
    # Return what we can know
    ret = {
        'name': '',
        'passwd': '',
        'lstchg': '',
        'min': '',
        'max': '',
        'warn': '',
        'inact': '',
        'expire': ''}

    try:
        data = pwd.getpwnam(name)
        ret.update({
            'name': name
        })
    except KeyError:
        return ret

    # To compensate for lack of spwd module, read in password hash from /etc/shadow
    s_file = '/etc/shadow'
    if not os.path.isfile(s_file):
        return ret
    with salt.utils.fopen(s_file, 'rb') as ifile:
        for line in ifile:
            comps = line.strip().split(':')
            if comps[0] == name:
                ret.update({'passwd': comps[1]})

    # For SmartOS `passwd -s <username>` and the output format is:
    #   name status mm/dd/yy min max warn
    #
    # Fields:
    #  1. Name: username
    #  2. Status:
    #      - LK: locked
    #      - NL: no login
    #      - NP: No password
    #      - PS: Password
    #  3. Last password change
    #  4. Minimum age
    #  5. Maximum age
    #  6. Warning period

    output = __salt__['cmd.run_all']('passwd -s {0}'.format(name), python_shell=False)
    if output['retcode'] != 0:
        return ret

    fields = output['stdout'].split()
    if len(fields) == 2:
        # For example:
        #   root      NL
        return ret
    # We have all fields:
    #   buildbot L 05/09/2013 0 99999 7
    ret.update({
        'name': data.pw_name,
        'lstchg': fields[2],
        'min': int(fields[3]),
        'max': int(fields[4]),
        'warn': int(fields[5]),
        'inact': '',
        'expire': ''
    })
    return ret


def set_maxdays(name, maxdays):
    '''
    Set the maximum number of days during which a password is valid. See man
    passwd.

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_maxdays username 90
    '''
    pre_info = info(name)
    if maxdays == pre_info['max']:
        return True
    cmd = 'passwd -x {0} {1}'.format(maxdays, name)
    __salt__['cmd.run'](cmd, python_shell=False)
    post_info = info(name)
    if post_info['max'] != pre_info['max']:
        return post_info['max'] == maxdays


def set_mindays(name, mindays):
    '''
    Set the minimum number of days between password changes. See man passwd.

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_mindays username 7
    '''
    pre_info = info(name)
    if mindays == pre_info['min']:
        return True
    cmd = 'passwd -n {0} {1}'.format(mindays, name)
    __salt__['cmd.run'](cmd, python_shell=False)
    post_info = info(name)
    if post_info['min'] != pre_info['min']:
        return post_info['min'] == mindays
    return False


def gen_password(password, crypt_salt=None, algorithm='sha512'):
    '''
    .. versionadded:: 2015.8.8

    Generate hashed password

    .. note::

        When called this function is called directly via remote-execution,
        the password argument may be displayed in the system's process list.
        This may be a security risk on certain systems.

    password
        Plaintext password to be hashed.

    crypt_salt
        Crpytographic salt. If not given, a random 8-character salt will be
        generated.

    algorithm
        The following hash algorithms are supported:

        * md5
        * blowfish (not in mainline glibc, only available in distros that add it)
        * sha256
        * sha512 (default)

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.gen_password 'I_am_password'
        salt '*' shadow.gen_password 'I_am_password' crypt_salt='I_am_salt' algorithm=sha256
    '''
    if not HAS_CRYPT:
        raise CommandExecutionError(
                'gen_password is not available on this operating system '
                'because the "crypt" python module is not available.'
                )
    return salt.utils.pycrypto.gen_hash(crypt_salt, password, algorithm)


def del_password(name):
    '''
    .. versionadded:: 2015.8.8

    Delete the password from name user

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.del_password username
    '''
    cmd = 'passwd -d {0}'.format(name)
    __salt__['cmd.run'](cmd, python_shell=False, output_loglevel='quiet')
    uinfo = info(name)
    return not uinfo['passwd']


def set_password(name, password):
    '''
    Set the password for a named user. The password must be a properly defined
    hash, the password hash can be generated with this command:
    ``openssl passwd -1 <plaintext password>``

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_password root $1$UYCIxa628.9qXjpQCjM4a..
    '''
    s_file = '/etc/shadow'
    ret = {}
    if not os.path.isfile(s_file):
        return ret
    lines = []
    with salt.utils.fopen(s_file, 'rb') as ifile:
        for line in ifile:
            comps = line.strip().split(':')
            if comps[0] != name:
                lines.append(line)
                continue
            comps[1] = password
            line = ':'.join(comps)
            lines.append('{0}\n'.format(line))
    with salt.utils.fopen(s_file, 'w+') as ofile:
        ofile.writelines(lines)
    uinfo = info(name)
    return uinfo['passwd'] == password


def set_warndays(name, warndays):
    '''
    Set the number of days of warning before a password change is required.
    See man passwd.

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_warndays username 7
    '''
    pre_info = info(name)
    if warndays == pre_info['warn']:
        return True
    cmd = 'passwd -w {0} {1}'.format(warndays, name)
    __salt__['cmd.run'](cmd, python_shell=False)
    post_info = info(name)
    if post_info['warn'] != pre_info['warn']:
        return post_info['warn'] == warndays
    return False
