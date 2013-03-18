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
    cmd = 'repquota -vp {0} {1}'.format(opts, mount)
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
            if len(comps) < 8:
                continue
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


def set(device, **kwargs):
    '''
    Calls out to setquota, for a specific user or group

    CLI Example::

        salt '*' quota.set /media/data user=larry block-soft-limit=1048576
        salt '*' quota.set /media/data group=painters file-hard-limit=1000
    '''
    empty = {'block-soft-limit': 0, 'block-hard-limit': 0,
             'file-soft-limit': 0, 'file-hard-limit': 0}

    current = None
    cmd = 'setquota'
    if 'user' in kwargs:
        cmd += ' -u {0} '.format(kwargs['user'])
        parsed = _parse_quota(device, '-u')
        if kwargs['user'] in parsed:
            current = parsed['Users'][kwargs['user']]
        else:
            current = empty
        ret = 'User: {0}'.format(kwargs['user'])

    if 'group' in kwargs:
        if 'user' in kwargs:
            return {'Error': 'Please specify a user or group, not both.'}
        cmd += ' -g {0} '.format(kwargs['group'])
        parsed = _parse_quota(device, '-g')
        if kwargs['user'] in parsed:
            current = parsed['Groups'][kwargs['group']]
        else:
            current = empty
        ret = 'Group: {0}'.format(kwargs['group'])

    if not current:
        return {'Error': 'A valid user or group was not found'}

    for limit in ('block-soft-limit', 'block-hard-limit',
                  'file-soft-limit', 'file-hard-limit'):
        if limit in kwargs:
            current[limit] = kwargs[limit]

    cmd += '{0} {1} {2} {3} {4}'.format(current['block-soft-limit'],
                                        current['block-hard-limit'],
                                        current['file-soft-limit'],
                                        current['file-hard-limit'],
                                        device)
    out = __salt__['cmd.run'](cmd).splitlines()

    return {ret: current}


def warn():
    '''
    Runs the warnquota command, to send warning emails to users who
    are over their quota limit.

    CLI Example::

        salt '*' quota.warn
    '''
    __salt__['cmd.run']('quotawarn')


def stats():
    '''
    Runs the quotastats command, and returns the parsed output

    CLI Example::

        salt '*' quota.stats
    '''
    ret = {}
    out = __salt__['cmd.run']('quotastats').splitlines()
    for line in out:
        if not line:
            continue
        comps = line.split(': ')
        ret[comps[0]] = comps[1]

    return ret


def on(device):
    '''
    Turns on the quota system

    CLI Example::

        salt '*' quota.on
    '''
    cmd = 'quotaon {0}'.format(device)
    __salt__['cmd.run'](cmd)


def off(device):
    '''
    Turns off the quota system

    CLI Example::

        salt '*' quota.off
    '''
    cmd = 'quotaoff {0}'.format(device)
    __salt__['cmd.run'](cmd)


