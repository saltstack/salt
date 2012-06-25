'''
Manage the shadow file
'''


def __virtual__():
    '''
    Only works on Windows systems
    '''
    if __grains__['os'] == 'Windows':
        return 'shadow'
    return False


def info(name):
    '''
    Return information for the specified user
    This is just returns dummy data so that salt states can work.

    CLI Example::

        salt '*' shadow.info root
    '''
    ret = {
            'name': name,
            'pwd': '',
            'lstchg': '',
            'min': '',
            'max': '',
            'warn': '',
            'inact': '',
            'expire': ''}
    return ret


def set_password(name, password):
    '''
    Set the password for a named user.

    CLI Example::

        salt '*' shadow.set_password root mysecretpassword
    '''
    cmd = 'net user {0} {1}'.format(name, password)
    ret = __salt__['cmd.run_all'](cmd)

    return not ret['retcode']
