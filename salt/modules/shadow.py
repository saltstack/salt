# -*- coding: utf-8 -*-
'''
Manage the shadow file on Linux systems

.. important::
    If you feel that Salt should be using this module to manage passwords on a
    minion, and it is using a different module (or gives an error similar to
    *'shadow.info' is not available*), see :ref:`here
    <module-provider-override>`.
'''
from __future__ import absolute_import

# Import python libs
import os
import datetime
try:
    import spwd
except ImportError:
    pass

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError
try:
    import salt.utils.pycrypto
    HAS_CRYPT = True
except ImportError:
    HAS_CRYPT = False


def __virtual__():
    return __grains__.get('kernel', '') == 'Linux'


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
        return {
            'name': '',
            'passwd': '',
            'lstchg': '',
            'min': '',
            'max': '',
            'warn': '',
            'inact': '',
            'expire': ''}
    return ret


def set_inactdays(name, inactdays):
    '''
    Set the number of days of inactivity after a password has expired before
    the account is locked. See man chage.

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_inactdays username 7
    '''
    pre_info = info(name)
    if inactdays == pre_info['inact']:
        return True
    cmd = 'chage -I {0} {1}'.format(inactdays, name)
    __salt__['cmd.run'](cmd, python_shell=False)
    post_info = info(name)
    if post_info['inact'] != pre_info['inact']:
        return post_info['inact'] == inactdays
    return False


def set_maxdays(name, maxdays):
    '''
    Set the maximum number of days during which a password is valid.
    See man chage.

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_maxdays username 90
    '''
    pre_info = info(name)
    if maxdays == pre_info['max']:
        return True
    cmd = 'chage -M {0} {1}'.format(maxdays, name)
    __salt__['cmd.run'](cmd, python_shell=False)
    post_info = info(name)
    if post_info['max'] != pre_info['max']:
        return post_info['max'] == maxdays
    return False


def set_mindays(name, mindays):
    '''
    Set the minimum number of days between password changes. See man chage.

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_mindays username 7
    '''
    pre_info = info(name)
    if mindays == pre_info['min']:
        return True
    cmd = 'chage -m {0} {1}'.format(mindays, name)
    __salt__['cmd.run'](cmd, python_shell=False)
    post_info = info(name)
    if post_info['min'] != pre_info['min']:
        return post_info['min'] == mindays
    return False


def gen_password(password, crypt_salt=None, algorithm='sha512'):
    '''
    .. versionadded:: 2014.7.0

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
    .. versionadded:: 2014.7.0

    Delete the password from name user

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.del_password username
    '''
    cmd = 'passwd -d {0}'.format(name)
    __salt__['cmd.run'](cmd, python_shell=False, output_loglevel='quiet')
    uinfo = info(name)
    return not uinfo['passwd'] and uinfo['name'] == name


def lock_password(name):
    '''
    .. versionadded:: 2016.11.0

    Lock the password from name user

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.lock_password username
    '''
    pre_info = info(name)
    if pre_info['name'] == '':
        return False
    if pre_info['passwd'][0] == '!':
        return True

    cmd = 'passwd -l {0}'.format(name)
    __salt__['cmd.run'](cmd, python_shell=False)

    post_info = info(name)

    return post_info['passwd'][0] == '!'


def unlock_password(name):
    '''
    .. versionadded:: 2016.11.0

    Unlock the password from name user

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.unlock_password username
    '''
    pre_info = info(name)
    if pre_info['name'] == '':
        return False
    if pre_info['passwd'][0] != '!':
        return True

    cmd = 'passwd -u {0}'.format(name)
    __salt__['cmd.run'](cmd, python_shell=False)

    post_info = info(name)

    return post_info['passwd'][0] != '!'


def set_password(name, password, use_usermod=False):
    '''
    Set the password for a named user. The password must be a properly defined
    hash. The password hash can be generated with this command:

    ``python -c "import crypt; print crypt.crypt('password',
    '\\$6\\$SALTsalt')"``

    ``SALTsalt`` is the 8-character crpytographic salt. Valid characters in the
    salt are ``.``, ``/``, and any alphanumeric character.

    Keep in mind that the $7 represents a sha512 hash, if your OS is using a
    different hashing algorithm this needs to be changed accordingly

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_password root '$1$UYCIxa628.9qXjpQCjM4a..'
    '''
    if not salt.utils.is_true(use_usermod):
        # Edit the shadow file directly
        # ALT Linux uses tcb to store password hashes. More information found
        # in manpage (http://docs.altlinux.org/manpages/tcb.5.html)
        if __grains__['os'] == 'ALT':
            s_file = '/etc/tcb/{0}/shadow'.format(name)
        else:
            s_file = '/etc/shadow'
        ret = {}
        if not os.path.isfile(s_file):
            return ret
        lines = []
        with salt.utils.fopen(s_file, 'rb') as fp_:
            for line in fp_:
                line = salt.utils.to_str(line)
                comps = line.strip().split(':')
                if comps[0] != name:
                    lines.append(line)
                    continue
                changed_date = datetime.datetime.today() - datetime.datetime(1970, 1, 1)
                comps[1] = password
                comps[2] = str(changed_date.days)
                line = ':'.join(comps)
                lines.append('{0}\n'.format(line))
        with salt.utils.fopen(s_file, 'w+') as fp_:
            fp_.writelines(lines)
        uinfo = info(name)
        return uinfo['passwd'] == password
    else:
        # Use usermod -p (less secure, but more feature-complete)
        cmd = 'usermod -p {0} {1}'.format(password, name)
        __salt__['cmd.run'](cmd, python_shell=False, output_loglevel='quiet')
        uinfo = info(name)
        return uinfo['passwd'] == password


def set_warndays(name, warndays):
    '''
    Set the number of days of warning before a password change is required.
    See man chage.

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_warndays username 7
    '''
    pre_info = info(name)
    if warndays == pre_info['warn']:
        return True
    cmd = 'chage -W {0} {1}'.format(warndays, name)
    __salt__['cmd.run'](cmd, python_shell=False)
    post_info = info(name)
    if post_info['warn'] != pre_info['warn']:
        return post_info['warn'] == warndays
    return False


def set_date(name, date):
    '''
    Sets the value for the date the password was last changed to days since the
    epoch (January 1, 1970). See man chage.

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_date username 0
    '''
    cmd = 'chage -d {0} {1}'.format(date, name)
    return not __salt__['cmd.run'](cmd, python_shell=False)


def set_expire(name, expire):
    '''
    .. versionchanged:: 2014.7.0

    Sets the value for the date the account expires as days since the epoch
    (January 1, 1970). Using a value of -1 will clear expiration. See man
    chage.

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_expire username -1
    '''
    cmd = 'chage -E {0} {1}'.format(expire, name)
    return not __salt__['cmd.run'](cmd, python_shell=False)
