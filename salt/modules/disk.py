'''
Module for gathering disk information
'''


def usage():
    '''
    Return usage information for volumes mounted on this minion

    CLI Example::

        salt '*' disk.usage
    '''
    cmd = 'df -P'
    ret = {}
    out = __salt__['cmd.run'](cmd).split('\n')
    for line in out:
        if not line.count(' '):
            continue
        if line.startswith('Filesystem'):
            continue
        comps = line.split()
        ret[comps[0]] = {
            '1K-blocks': comps[1],
            'available': comps[3],
            'capacity': comps[4],
            'mountpoint': comps[5],
            'used': comps[2]
        }
    return ret
