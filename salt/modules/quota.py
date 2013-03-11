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
    cmd = 'repquota -p {0} {1}'.format(opts, mount)
    out = __salt__['cmd.run'](cmd).splitlines()
    mode = 'header'
    device = ''

    if '-u' in opts:
        quotatype = 'Users'
    elif '-g' in opts:
        quotatype = 'Groups'
    ret = {quotatype: {}}

    for line in out:
        if not line:
            continue
        comps = line.split()
        if mode == 'header':
            if 'Report for' in line:
                device = comps[-1:][0]
            elif 'Block grace time' in line:
                blockg, inodeg = line.split(';')
                blockgc = blockg.split(': ')
                inodegc = inodeg.split(': ')
                ret['Block Grace Time'] = blockgc[-1:]
                ret['Inode Grace Time'] = inodegc[-1:]
            elif line.startswith('-'):
                mode = 'quotas'
        elif mode == 'quotas':
            if not comps[0] in ret[quotatype]:
                ret[quotatype][comps[0]] = {}
            ret[quotatype][comps[0]]['block-used'] = comps[2]
            ret[quotatype][comps[0]]['block-soft-limit'] = comps[3]
            ret[quotatype][comps[0]]['block-hard-limit'] = comps[4]
            ret[quotatype][comps[0]]['block-grace'] = comps[5]
            ret[quotatype][comps[0]]['file-used'] = comps[6]
            ret[quotatype][comps[0]]['file-soft-limit'] = comps[7]
            ret[quotatype][comps[0]]['file-hard-limit'] = comps[8]
            ret[quotatype][comps[0]]['file-grace'] = comps[9]
    return ret


def set(device, kwargs):
    '''
    Calls out to setquota, for a specific user or group

    CLI Example::

        salt '*' quota.report /media/data user=larry softblock=1048576
        salt '*' quota.report /media/data group=painters
    '''


    return kwargs

