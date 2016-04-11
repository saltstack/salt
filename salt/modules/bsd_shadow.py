# -*- coding: utf-8 -*-
'''
Manage the password database on BSD systems

.. important::
    If you feel that Salt should be using this module to manage passwords on a
    minion, and it is using a different module (or gives an error similar to
    *'shadow.info' is not available*), see :ref:`here
    <module-provider-override>`.
'''

# Import python libs
from __future__ import absolute_import
try:
    import pwd
except ImportError:
    pass

# Define the module's virtual name
__virtualname__ = 'shadow'


def __virtual__():
    return __virtualname__ if 'BSD' in __grains__.get('os', '') else False


def default_hash():
    '''
    Returns the default hash used for unset passwords

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.default_hash
    '''
    return '*' if __grains__['os'].lower() == 'freebsd' else '*************'


def info(name):
    '''
    Return information for the specified user

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.info someuser
    '''
    try:
        data = pwd.getpwnam(name)
        ret = {
            'name': data.pw_name,
            'passwd': data.pw_passwd}
    except KeyError:
        return {
            'name': '',
            'passwd': ''}

    cmd = ""
    if __salt__['cmd.has_exec']('pw'):
        cmd = 'pw user show {0}'.format(name)
    elif __grains__['kernel'] in ('NetBSD', 'OpenBSD'):
        cmd = 'grep "^{0}:" /etc/master.passwd'.format(name)

    if cmd:
        cmd += '| cut -f6,7 -d:'
        try:
            change, expire = __salt__['cmd.run_all'](cmd, python_shell=True)['stdout'].split(':')
        except ValueError:
            pass
        else:
            ret['change'] = int(change)
            ret['expire'] = int(expire)

    return ret


def set_change(name, change):
    '''
    Sets the time at which the password expires (in seconds since the EPOCH).
    See man usermod on NetBSD and OpenBSD or man pw on FreeBSD.
    "0" means the password never expires.

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_change username 1419980400
    '''
    pre_info = info(name)
    if change == pre_info['change']:
        return True
    if __grains__['kernel'] == 'FreeBSD':
        cmd = 'pw user mod {0} -f {1}'.format(name, change)
    else:
        cmd = 'usermod -f {0} {1}'.format(change, name)
    __salt__['cmd.run'](cmd)
    post_info = info(name)
    if post_info['change'] != pre_info['change']:
        return post_info['change'] == change


def set_expire(name, expire):
    '''
    Sets the time at which the account expires (in seconds since the EPOCH).
    See man usermod on NetBSD and OpenBSD or man pw on FreeBSD.
    "0" means the account never expires.

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_expire username 1419980400
    '''
    pre_info = info(name)
    if expire == pre_info['expire']:
        return True
    if __grains__['kernel'] == 'FreeBSD':
        cmd = 'pw user mod {0} -e {1}'.format(name, expire)
    else:
        cmd = 'usermod -e {0} {1}'.format(expire, name)
    __salt__['cmd.run'](cmd)
    post_info = info(name)
    if post_info['expire'] != pre_info['expire']:
        return post_info['expire'] == expire


def del_password(name):
    '''
    .. versionadded:: 2015.8.2

    Delete the password from name user

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.del_password username
    '''
    cmd = 'pw user mod {0} -w none'.format(name)
    __salt__['cmd.run'](cmd, python_shell=False, output_loglevel='quiet')
    uinfo = info(name)
    return not uinfo['passwd']


def set_password(name, password):
    '''
    Set the password for a named user. The password must be a properly defined
    hash. The password hash can be generated with this command:

    ``python -c "import crypt; print crypt.crypt('password', ciphersalt)"``

    :strong:`NOTE:` When constructing the ``ciphersalt`` string, you must
    escape any dollar signs, to avoid them being interpolated by the shell.

    ``'password'`` is, of course, the password for which you want to generate
    a hash.

    ``ciphersalt`` is a combination of a cipher identifier, an optional number
    of rounds, and the cryptographic salt. The arrangement and format of these
    fields depends on the cipher and which flavor of BSD you are using. For
    more information on this, see the manpage for ``crpyt(3)``. On NetBSD,
    additional information is available in ``passwd.conf(5)``.

    It is important to make sure that a supported cipher is used.

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_password someuser '$1$UYCIxa628.9qXjpQCjM4a..'
    '''
    if __grains__.get('os', '') == 'FreeBSD':
        cmd = 'pw user mod {0} -H 0'.format(name)
        stdin = password
    else:
        cmd = 'usermod -p {0!r} {1}'.format(password, name)
        stdin = None
    __salt__['cmd.run'](cmd, stdin=stdin, output_loglevel='quiet')
    return info(name)['passwd'] == password
