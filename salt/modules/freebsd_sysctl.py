'''
Module for viewing and modifying sysctl parameters
'''

from salt.exceptions import CommandExecutionError

__outputter__ = {
    'assign': 'txt',
    'get': 'txt',
}


def _formatfor(name, value, config, tail=''):
    if config == '/boot/loader.conf':
        return '{0}="{1}"{2}'.format(name, value, tail)
    else:
        return '{0}={1}{2}'.format(name, value, tail)


def __virtual__():
    '''
    Only run on Linux systems
    '''
    return 'sysctl' if __grains__['os'] == 'FreeBSD' else False


def show():
    '''
    Return a list of sysctl parameters for this minion

    CLI Example::

        salt '*' sysctl.show
    '''
    roots = (
        'compat',
        'debug',
        'dev',
        'hptmv',
        'hw',
        'kern',
        'machdep',
        'net',
        'p1003_1b',
        'security',
        'user',
        'vfs',
        'vm'
    )
    cmd = 'sysctl -ae'
    ret = {}
    out = __salt__['cmd.run'](cmd).splitlines()
    for line in out:
        if line.split('.')[0] not in roots:
            comps = line.split('=')
            ret[comps[0]] += '{0}\n'.format(line)
            continue
        comps = line.split('=')
        ret[comps[0]] = comps[1]
    return ret


def get(name):
    '''
    Return a single sysctl parameter for this minion

    CLI Example::

        salt '*' sysctl.get hw.physmem
    '''
    cmd = 'sysctl -n {0}'.format(name)
    out = __salt__['cmd.run'](cmd)
    return out


def assign(name, value):
    '''
    Assign a single sysctl parameter for this minion

    CLI Example::

        salt '*' sysctl.assign net.inet.icmp.icmplim 50
    '''
    ret = {}
    cmd = 'sysctl {0}="{1}"'.format(name, value)
    data = __salt__['cmd.run_all'](cmd)

    if data['retcode'] != 0:
        raise CommandExecutionError('sysctl failed: {0}'.format(
            data['stderr']))
    new_name, new_value = data['stdout'].split(':', 1)
    ret[new_name] = new_value.split(' -> ')[-1]
    return ret


def persist(name, value, config='/etc/sysctl.conf'):
    '''
    Assign and persist a simple sysctl parameter for this minion

    CLI Example::

        salt '*' sysctl.persist net.inet.icmp.icmplim 50
        salt '*' sysctl.persist coretemp_load NO config=/boot/loader.conf
    '''
    nlines = []
    edited = False
    value = str(value)

    with open(config, 'r') as f:
        for l in f:
            if not l.startswith('{0}='.format(name)):
                nlines.append(l)
                continue
            else:
                k, rest = l.split('=', 1)
                if rest.startswith('"'):
                    z, v, rest = rest.split('"', 2)
                elif rest.startswith('\''):
                    z, v, rest = rest.split('\'', 2)
                else:
                    v = rest.split()[0]
                    rest = rest[len(v):]
                if v == value:
                    return 'Already set'
                new_line = _formatfor(k, value, config, rest)
                nlines.append(new_line)
                edited = True
    if not edited:
        nlines.append("{0}\n".format(_formatfor(name, value, config)))
    with open(config, 'w+') as f: f.writelines(nlines)
    if config != '/boot/loader.conf':
        assign(name, value)
    return 'Updated'
