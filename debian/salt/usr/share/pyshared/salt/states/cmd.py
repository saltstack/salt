'''
Manage command executions cron a state perspective
'''

import os
import pwd
import grp

def run(name,
        onlyif=None,
        unless=None,
        cwd='/root',
        user=None,
        group=None):
    '''
    Ensure that the named command is executed

    Arguments:
    name -- The command to run

    Keyword Argument:
    onlyif -- Only run the main command if this command returns true
    unless -- Only run the main command if this command returns False
    cwd -- Run the command from this directory, defaults to /root
    user -- Run the command as this user
    group -- run the command as this group
    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}
    if onlyif:
        if __salt__['cmd.retcode'](onlyif) != 0:
            ret['comment'] = 'onlyif exec failed'
            ret['result'] = True
            return ret
    if unless:
        if __salt__['cmd.retcode'](unless) == 0:
            ret['comment'] = 'unless executed successfully'
            ret['result'] = True
            return ret
    if not os.path.isdir(cwd):
        ret['comment'] = 'Desired working directory is not available'
        return ret
    puid = os.geteuid()
    pgid = os.getegid()
    if group:
        try:
            egid = grp.getgrnam(group).gr_gid
            os.setegid(egid)
        except KeyError:
            ret['comment'] = 'The group ' + group + ' is not available'
            return ret
    if user:
        try:
            euid = pwd.getpwnam(user).pw_uid
            os.seteuid(euid)
        except KeyError:
            ret['comment'] = 'The user ' + user + ' is not available'
            return ret
    # Wow, we pased the test, run this sucker!
    cmd_all = __salt__['cmd.run_all'](name, cwd)
    ret['changes'] = cmd_all
    ret['result'] = not bool(cmd_all['retcode'])
    ret['comment'] = 'Command "' + name + '" run'
    os.seteuid(puid)
    os.setegid(pgid)
    return ret

