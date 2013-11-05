# -*- coding: utf-8 -*-
'''
Manage groups on Windows
'''

# Import salt libs
import salt.utils

# Define the module's virtual name
__virtualname__ = 'group'


def __virtual__():
    '''
    Set the group module if the kernel is Windows
    '''
    return __virtualname__ if salt.utils.is_windows() else False


def add(name, gid=None, system=False):
    '''
    Add the specified group

    CLI Example:

    .. code-block:: bash

        salt '*' group.add foo
    '''
    cmd = 'net localgroup {0} /add'.format(name)

    ret = __salt__['cmd.run_all'](cmd)

    return not ret['retcode']


def delete(name):
    '''
    Remove the named group

    CLI Example:

    .. code-block:: bash

        salt '*' group.delete foo
    '''
    ret = __salt__['cmd.run_all']('net localgroup {0} /delete'.format(name))

    return not ret['retcode']


def info(name):
    '''
    Return information about a group

    CLI Example:

    .. code-block:: bash

        salt '*' group.info foo
    '''
    lines = __salt__['cmd.run']('net localgroup {0}'.format(name)).splitlines()
    memberline = False
    gr_mem = []
    gr_name = ''
    for line in lines:
        if 'Alias name' in line:
            comps = line.split('  ', 1)
            gr_name = comps[1].strip()
        if 'successfully' in line:
            memberline = False
        if memberline:
            gr_mem.append(line.strip())
        if '---' in line:
            memberline = True
    if not gr_name:
        return False

    return {'name': gr_name,
            'passwd': None,
            'gid': None,
            'members': gr_mem}


def getent(refresh=False):
    '''
    Return info on all groups

    CLI Example:

    .. code-block:: bash

        salt '*' group.getent
    '''
    if 'group.getent' in __context__ and not refresh:
        return __context__['group.getent']

    ret = []
    ret2 = []
    lines = __salt__['cmd.run']('net localgroup').splitlines()
    groupline = False
    for line in lines:
        if 'successfully' in line:
            groupline = False
        if groupline:
            ret.append(line.strip('*').strip())
        if '---' in line:
            groupline = True
    for item in ret:
        members = []
        gid = __salt__['file.group_to_gid'](item)
        memberlines = __salt__['cmd.run']('net localgroup "{0}"'.format(item)).splitlines()
        memberline = False
        for line in memberlines:
            if 'successfully' in line:
                memberline = False
            if memberline:
                members.append(line.strip('*').strip())
            if '---' in line:
                memberline = True
        group = {'gid': gid,
                'members': members,
                'name': item,
                'passwd': 'x'}
        ret2.append(group)

    __context__['group.getent'] = ret2
    return ret2
