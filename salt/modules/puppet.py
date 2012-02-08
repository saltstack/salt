'''
Execute puppet routines
'''

from salt.exceptions import CommandNotFoundError

__outputter__ = {
    'run':  'txt',
    'noop': 'txt',
    'fact': 'txt',
    'facts':None,
}

def _check_puppet():
    '''
    Checks if puppet is installed
    '''
    # I thought about making this a virtual module, but then I realized that I
    # would require the minion to restart if puppet was installed after the
    # minion was started, and that would be rubbish
    return __salt__['cmd.has_exec']('puppetd')

def _check_facter():
    '''
    Checks if facter is installed
    '''
    return __salt__['cmd.has_exec']('facter')

def _format_fact(output):
    try:
        fact, value = output.split(' => ', 1)
        value = value.strip()
    except ValueError:
        fact = None
        value = None
    return (fact, value)


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
    if not _check_puppet():
        raise CommandNotFoundError('puppetd not available')

    if not tags:
        cmd = 'puppetd --test'
    else:
        cmd = 'puppetd --test --tags "{0}"'.format(tags)

    return __salt__['cmd.run_all'](cmd)

def noop(tags=None):
    '''
    Execute a puppet noop run and return a dict with the stderr, stdout,
    return code, etc. If an argument is specified, it is  treated  as  a
    comma separated list of tags passed to puppetd --test --noop   --tags

    CLI Example::

        salt '*' puppet.noop

        salt '*' puppet.noop web::server,django::base
    '''
    if not _check_puppet():
        raise CommandNotFoundError('puppetd not available')

    if not tags:
        cmd = 'puppetd --test --noop'
    else:
        cmd = 'puppetd --test --tags "{0}" --noop'.format(tags)

    return __salt__['cmd.run_all'](cmd)

def facts():
    '''
    Run facter and return the results

    CLI Example::

        salt '*' puppet.facts
    '''
    if not _check_facter():
        raise CommandNotFoundError('facter not available')

    ret = {}
    output = __salt__['cmd.run']('facter')

    # Loop over the facter output and  properly
    # parse it into a nice dictionary for using
    # elsewhere
    for line in output.split('\n'):
        if not line: continue
        fact, value = _format_fact(line)
        if not fact:
            continue
        ret[fact] = value
    return ret

def fact(name):
    '''
    Run facter for a specific fact

    CLI Example::

        salt '*' puppet.fact kernel
    '''
    if not _check_facter():
        raise CommandNotFoundError('facter not available')

    ret = __salt__['cmd.run']('facter {0}'.format(name))
    if not ret:
        return ''
    return ret.rstrip()
