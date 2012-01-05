'''
Execute puppet routines
'''


def _check_puppet():
    '''
    Checks if puppet is installed
    '''
    # I thought about making this a virtual module, but then I realized that I
    # would require the minion to restart if puppet was installed after the
    # minion was started, and that would be rubbish
    return __salt__['cmd.has_exec']('puppet')


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
        return {}
