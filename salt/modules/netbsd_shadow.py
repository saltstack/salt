'''
Manage the password database on NetBSD systems
'''

# Import python libs
import logging
try:
    import pwd
except ImportError:
    pass

# Import salt libs
import salt.utils

# Set up logging
log = logging.getLogger(__name__)


def __virtual__():
    return 'shadow' if __grains__.get('os', '') == 'NetBSD' else False


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
            'passwd': data.pw_passwd if data.pw_passwd != '*************'
                else ''}
    except KeyError:
        return {
            'name': '',
            'passwd': ''}
    return ret


def set_password(name, password):
    '''
    Set the password for a named user. The password must be a properly defined
    hash. The password hash can be generated with this command:

    ``python -c "import crypt; print crypt.crypt('password',
    '$sha1$numrounds$SALTsalt')"``

    ``numrounds`` is the number of rounds. See ``man passwd.conf`` as this
    option is not used for all ciphers.

    ``SALTsalt`` is the 8-character crpytographic salt. Valid characters in the
    salt are ``.``, ``/``, and any alphanumeric character.

    CLI Example::

        salt '*' shadow.set_password root
        '$sha1$22295$f8s.YafO$eRQSGyI4BP98Kj/hIohuXCmatl7L'
    '''
    cmd = 'usermod -p \'{0}\' {1}'.format(password, name)
    log.info('Setting password for user {0}'.format(name))
    # Don't log this command, to keep hash out of the log
    __salt__['cmd.run'](cmd, quiet=True)
    uinfo = info(name)
    return uinfo['passwd'] == password
