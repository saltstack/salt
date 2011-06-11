'''
Manage users with the useradd command
'''

import pwd

def __virtual__():
    '''
    Set the user module if the kernel is Linux
    '''
    return 'user' if __grains__['kernel'] == 'Linux' else False

def add(name,
        uid=None,
        gid=None,
        groups=None,
        home=False,
        shell='/bin/false'):
    '''
    Add a user to the minion

    CLI Example:
    salt '*' user.add name <uid> <gid> <groups> <home> <password> <shell>
    '''
    cmd = 'useradd -s {0} '.format(shell)
    if uid:
        cmd += '-u {0} '.format(uid)
    if gid:
        cmd += '-g {0} '.format(gid)
    if groups:
        cmd += '-G {0} '.format(groups)
    if home:
        cmd += '-m '
    
    ret = __salt__['cmd.run_all'](cmd)

    return not ret['retcode']

def del(name, remove=False, force=False):
    '''
    Remove a user from the minion

    CLI Example:
    salt '*' user.del name True True
    '''
    cmd = 'userdel '
    if remove:
        cmd += '-r '
    if force:
        cmd += '-f '

    ret = __salt__['cmd.run_all'](cmd)

    return not ret['retcode']

def info(name):
    '''
    Return user information

    CLI Example:
    salt '*' user.info root
    '''
    ret = {}
    data = pwd.getpwnam(name)
    ret['name'] = data.pw_name
    ret['passwd'] = data.pw_paswd
    ret['uid'] = data.pw_uid
    ret['gid'] = data.pw_gid
    ret['home'] = data.pw_dir
    ret['shell'] = data.pw_shell
    return ret
