'''
Manage groups on Linux
'''

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

def delete(name):
    '''
    Remove the named group

    CLI Example:
    salt '*' group.del foo
    '''
    ret = __salt__['cmd.run_all']('groupdel {0}'.format(name))

    return not ret['retcode']

def chgid(name, gid):
    '''
    Change the default shell of the user

    CLI Example:
    salt '*' user.chshell foo /bin/zsh
    '''
    pre_gid = __salt__['file.group_to_gid'](name)
    if gid == pre_gid:
        return True
    cmd = 'groupmod -g {0} {1}'.format(gid, name)
    __salt__['cmd.run'](cmd)
    post_info = __salt__['file.group_to_gid'](name)
    if post_info != pre_info:
        if post_info == gid:
            return True
    return False
