'''
Execute puppet routines
'''

from salt.exceptions import CommandNotFoundError

__outputter__ = {
    'run':  'txt',
    'noop': 'txt',
}

def _check_puppet():
    '''
    Checks if puppet is installed
    '''
    # I thought about making this a virtual module, but then I realized that I
    # would require the minion to restart if puppet was installed after the
    # minion was started, and that would be rubbish
    return __salt__['cmd.has_exec']('puppetd')


def run():
    '''
    Execute a puppet run and return a dict with the stderr,stdout,return code
    etc.

    CLI Example::

        salt '*' puppet.run
    '''
    if _check_puppet():
        return __salt__['cmd.run_all']('puppetd --test')
    else:
        raise CommandNotFoundError("puppetd not available")

def noop():
    '''
    Execute a puppet noop run and return a dict with the stderr,stdout,return code
    etc.

    CLI Example::

        salt '*' puppet.noop
    '''
    if _check_puppet():
        return __salt__['cmd.run_all']('puppetd --test --noop')
    else:
        raise CommandNotFoundError("puppetd not available")
