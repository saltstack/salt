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
from __future__ import absolute_import, print_function, unicode_literals
try:
    import pwd
except ImportError:
    pass

# Import salt libs
from salt.ext import six
import salt.utils.files
import salt.utils.stringutils
from salt.exceptions import SaltInvocationError

# Define the module's virtual name
__virtualname__ = 'shadow'


def __virtual__():
    if 'BSD' in __grains__.get('os', ''):
        return __virtualname__
    return (False, 'The bsd_shadow execution module cannot be loaded: '
            'only available on BSD family systems.')


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

    if not isinstance(name, six.string_types):
        name = six.text_type(name)
    if ':' in name:
        raise SaltInvocationError('Invalid username \'{0}\''.format(name))

    if __salt__['cmd.has_exec']('pw'):
        change, expire = __salt__['cmd.run_stdout'](
            ['pw', 'user', 'show', name],
            python_shell=False).split(':')[5:7]
    elif __grains__['kernel'] in ('NetBSD', 'OpenBSD'):
        try:
            with salt.utils.files.fopen('/etc/master.passwd', 'r') as fp_:
                for line in fp_:
                    line = salt.utils.stringutils.to_unicode(line)
                    if line.startswith('{0}:'.format(name)):
                        key = line.split(':')
                        change, expire = key[5:7]
                        ret['passwd'] = six.text_type(key[1])
                        break
        except IOError:
            change = expire = None
    else:
        change = expire = None

    try:
        ret['change'] = int(change)
    except ValueError:
        pass

    try:
        ret['expire'] = int(expire)
    except ValueError:
        pass

    return ret


def set_change(name, change):
    '''
    Sets the time at which the password expires (in seconds since the UNIX
    epoch). See ``man 8 usermod`` on NetBSD and OpenBSD or ``man 8 pw`` on
    FreeBSD.

    A value of ``0`` sets the password to never expire.

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_change username 1419980400
    '''
    pre_info = info(name)
    if change == pre_info['change']:
        return True
    if __grains__['kernel'] == 'FreeBSD':
        cmd = ['pw', 'user', 'mod', name, '-f', change]
    else:
        cmd = ['usermod', '-f', change, name]
    __salt__['cmd.run'](cmd, python_shell=False)
    post_info = info(name)
    if post_info['change'] != pre_info['change']:
        return post_info['change'] == change


def set_expire(name, expire):
    '''
    Sets the time at which the account expires (in seconds since the UNIX
    epoch). See ``man 8 usermod`` on NetBSD and OpenBSD or ``man 8 pw`` on
    FreeBSD.

    A value of ``0`` sets the account to never expire.

    CLI Example:

    .. code-block:: bash

        salt '*' shadow.set_expire username 1419980400
    '''
    pre_info = info(name)
    if expire == pre_info['expire']:
        return True
    if __grains__['kernel'] == 'FreeBSD':
        cmd = ['pw', 'user', 'mod', name, '-e', expire]
    else:
        cmd = ['usermod', '-e', expire, name]
    __salt__['cmd.run'](cmd, python_shell=False)
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

    .. note::
        When constructing the ``ciphersalt`` string, you must escape any dollar
        signs, to avoid them being interpolated by the shell.

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
        cmd = ['pw', 'user', 'mod', name, '-H', '0']
        stdin = password
    else:
        cmd = ['usermod', '-p', password, name]
        stdin = None
    __salt__['cmd.run'](cmd,
                        stdin=stdin,
                        output_loglevel='quiet',
                        python_shell=False)
    return info(name)['passwd'] == password
