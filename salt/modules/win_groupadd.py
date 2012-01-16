'''
Manage groups on Windows
'''

def __virtual__():
    '''
    Set the group module if the kernel is Windows
    '''
    return 'group' if __grains__['kernel'] == 'Windows' else False


def add(name):
    '''
    Add the specified group

    CLI Example::

        salt '*' group.add foo 
    '''
    cmd = 'net localgroup {0} /add'.format(name)

    ret = __salt__['cmd.run_all'](cmd)

    return not ret['retcode']


def delete(name):
    '''
    Remove the named group

    CLI Example::

        salt '*' group.delete foo
    '''
    ret = __salt__['cmd.run_all']('net localgroup {0} /delete'.format(name))

    return not ret['retcode']


def info(name):
    '''
    Return information about a group

    CLI Example::

        salt '*' group.info foo
    '''
    lines = __salt__['cmd.run']('net localgroup {0}'.format(name)).split('\n')
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


def getent():
    '''
    Return info on all groups

    CLI Example::

        salt '*' group.getent
    '''
    ret = []
    lines = __salt__['cmd.run']('net localgroup').split('\n')
    groupline = False
    for line in lines:
        if 'successfully' in line:
            groupline = False
        if groupline:
            ret.append(line.strip('*').strip())    
        if '---' in line:
            groupline = True

    return ret
