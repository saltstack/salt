'''
Command Executions
==================

The cmd state module manages the enforcement of executed commands, this
state can tell a command to run under certian circumstances.

Available Functions
-------------------

The cmd state only has a single function, the ``run`` function

run
    Execute a command given certian conditions

    A simple exampe:

    .. code-block:: yaml

        date > /tmp/salt-run:
        cmd:
            - run

Only run if another execution returns sucessfully, in this case truncate
syslog if there is no disk space:

.. code-block:: yaml

    > /var/log/messages:
      cmd:
        - run
        - unless: echo 'foo' > /tmp/.test

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
    Run a command if certian circumstances are met

    name
        The command to execute, remember that the command will execute with the
        path and permissions of the salt-minion.

    onlyif
        A command to run as a check, run the named command only if the command
        passed to the ``onlyif`` option returns true

    unless
        A command to run as a check, only run the named command if the command
        passed to the ``unless`` option returns false

    cwd
        The current working directory to execute the command in, defaults to
        /root

    user
        The user name to run the command as

    group
        The group context to run the command as
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

watcher = run
