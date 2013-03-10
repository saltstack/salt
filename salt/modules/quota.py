'''
Module for managing quotas on posix-like systems.
'''

# Import python libs
import logging

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only work on posix-like systems
    '''
    # Disable on these platorms, specific service modules exist:
    disable = [
        'Windows',
        ]
    if __grains__['os'] in disable:
        return False
    return 'quota'


def report(mount):
    '''
    Report on quotas for a specific volume

    CLI Example::

        salt '*' quota.report /media/data
    '''
    ret = {mount: {}}
    ret[mount]['User Quotas'] = _parse_quota(mount, '-u')
    ret[mount]['Group Quotas'] = _parse_quota(mount, '-g')
    return ret


def _parse_quota(mount, opts):
    '''
    Parse the output from repquota. Requires that -u -g are passed in
    '''
    ret = {}
    cmd = 'repquota -p {0} {1}'.format(opts, mount)
    out = __salt__['cmd.run'](cmd).splitlines()
    mode = 'header'
    device = ''
    for line in out:
        if not line:
            continue
        comps = line.split()
        if mode == 'header':
            if 'Report for' in line:
                device = comps[-1:][0]
                ret[device] = {}
            elif 'Block grace time' in line:
                blockg, inodeg = line.split(';')
                blockgc = blockg.split(': ')
                inodegc = inodeg.split(': ')
                ret[device]['Block Grace Time'] = blockgc[-1:]
                ret[device]['Inode Grace Time'] = inodegc[-1:]
            elif line.startswith('-'):
                mode = 'quotas'
        elif mode == 'quotas':
            if not comps[0] in ret[device]:
                ret[device][comps[0]] = {}
            ret[device][comps[0]]['block-used'] = comps[2]
            ret[device][comps[0]]['block-soft-limit'] = comps[3]
            ret[device][comps[0]]['block-hard-limit'] = comps[4]
            ret[device][comps[0]]['block-grace'] = comps[5]
            ret[device][comps[0]]['file-used'] = comps[6]
            ret[device][comps[0]]['file-soft-limit'] = comps[7]
            ret[device][comps[0]]['file-hard-limit'] = comps[8]
            ret[device][comps[0]]['file-grace'] = comps[9]
    return ret

