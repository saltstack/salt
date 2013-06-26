'''
Manage the password database on FreeBSD systems
'''

# Import python libs
import os
try:
    import pwd
except ImportError:
    pass

# Import salt libs
import salt.utils


def __virtual__():
    return 'shadow' if __grains__.get('os', '') == 'FreeBSD' else False


def info(name):
    '''
    Return information for the specified user

    CLI Example::

        salt '*' shadow.info root
    '''
    try:
        data = pwd.getpwnam(name)
        ret = {
            'name': data.pw_name,
            'passwd': data.pw_passwd if data.pw_passwd != '*' else '',
            'change': '',
            'expire': ''}
    except KeyError:
        return {
            'name': '',
            'passwd': '',
            'change': '',
            'expire': ''}

    # Get password aging info
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

    ``python -c "import crypt; print crypt.crypt('password',
    '$6$SALTsalt')"``

    ``SALTsalt`` is the 8-character crpytographic salt. Valid characters in the
    salt are ``.``, ``/``, and any alphanumeric character.

    Keep in mind that the $6 represents a sha512 hash, if your OS is using a
    different hashing algorithm this needs to be changed accordingly

    CLI Example::

        salt '*' shadow.set_password root '$1$UYCIxa628.9qXjpQCjM4a..'
    '''
    __salt__['cmd.run']('pw user mod {0} -H 0'.format(name), stdin=password)
    uinfo = info(name)
    return uinfo['passwd'] == password
