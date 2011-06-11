'''
Manage groups on Linux
'''
# Import python libs


def __virtual__():
    '''
    Set the user module if the kernel is Linux
    '''
    return 'group' if __grains__['kernel'] == 'Linux' else False

def add(name, gid=None):
    '''
    Add the specified group

    CLI Example:
    salt '*' group.add foo 3456
    '''
    cmd = 'groupadd '
    if gid:
        cmd += '-g {0} '.format(gid)
    cmd += name
    
    ret = __salt__['cmd.run_all'](cmd)

    return not ret['retcode']

def del(name):
    '''
    Remove the named group

    CLI Example:
    salt '*' group.del foo
    '''
    ret = __salt__['cmd.run_all']('groupdel {0}'.format(name))

    return not ret['retcode']
    
