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


def run(tags=None):
    '''
    Execute a puppet run and return a dict with the stderr, stdout,
    return code, etc. If an argument is specified, it is treated as
    a comma separated list of tags passed to puppetd --test --tags:
    http://projects.puppetlabs.com/projects/1/wiki/Using_Tags

    CLI Examples::

        salt '*' puppet.run

        salt '*' puppet.run basefiles::edit,apache::server
    '''
    if not tags:
        cmd = 'puppetd --test'
    else:
        cmd = 'puppetd --test --tags "{0}"'.format(tags)

    if _check_puppet():
        return __salt__['cmd.run_all'](cmd)
    else:
        raise CommandNotFoundError('puppetd not available')

def noop(tags=None):
    '''
    Execute a puppet noop run and return a dict with the stderr, stdout,
    return code, etc. If an argument is specified, it is  treated  as  a
    comma separated list of tags passed to puppetd --test --noop   --tags

    CLI Example::

        salt '*' puppet.noop

        salt '*' puppet.noop web::server,django::base
    '''
    if not tags:
        cmd = 'puppetd --test --noop'
    else:
        cmd = 'puppetd --test --tags "{0}" --noop'.format(tags)

    if _check_puppet():
        return __salt__['cmd.run_all'](cmd)
    else:
        raise CommandNotFoundError('puppetd not available')
