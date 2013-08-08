'''
Manage the password database on BSD systems
'''

# Import python libs
try:
    import pwd
except ImportError:
    pass


def __virtual__():
    return 'shadow' if 'BSD' in __grains__.get('os', '') else False


def default_hash():
    '''
    Returns the default hash used for unset passwords

    CLI Example::

        salt '*' shadow.default_hash
    '''
    return '*' if __grains__['os'].lower() == 'freebsd' else '*************'


def info(name):
    '''
    Return information for the specified user

    CLI Example::

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

    # Get password aging info on FreeBSD
    # TODO: Implement this for NetBSD, OpenBSD
    if __salt__['cmd.has_exec']('pw'):
        cmd = 'pw user show {0} | cut -f6,7 -d:'.format(name)
        try:
            change, expire = __salt__['cmd.run_all'](cmd)['stdout'].split(':')
        except ValueError:
            pass
        else:
            ret['change'] = change
            ret['expire'] = expire

    return ret


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

    CLI Example::

        salt '*' shadow.set_password someuser '$1$UYCIxa628.9qXjpQCjM4a..'
    '''
    if __grains__.get('os', '') == 'FreeBSD':
        cmd = 'pw user mod {0} -H 0'.format(name)
        stdin = password
    else:
        cmd = 'usermod -p \'{0}\' {1}'.format(password, name)
        stdin = None
    __salt__['cmd.run'](cmd, stdin=stdin)
    return info(name)['passwd'] == password
