'''
Command Executions
==================

The cmd state module manages the enforcement of executed commands, this
state can tell a command to run under certain circumstances.

Available Functions
-------------------

The cmd state only has a single function, the ``run`` function

run
    Execute a command given certain conditions

    A simple example:

    .. code-block:: yaml

        date > /tmp/salt-run:
        cmd:
            - run

Only run if another execution returns successfully, in this case truncate
syslog if there is no disk space:

.. code-block:: yaml

    > /var/log/messages:
      cmd:
        - run
        - unless: echo 'foo' > /tmp/.test

'''

import grp
import os
import pwd


def wait(name,
        onlyif=None,
        unless=None,
        cwd='/root',
        user=None,
        group=None):
    '''
    Run the given command only if the watch statement calls it

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
    return {'name': name,
            'changes': {},
            'result': True,
            'comment': ''}

def run(name,
        onlyif=None,
        unless=None,
        cwd='/root',
        user=None,
        group=None):
    '''
    Run a command if certain circumstances are met

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

    pgid = os.getegid()

    if group:
        try:
            egid = grp.getgrnam(group).gr_gid
            os.setegid(egid)
        except KeyError:
            ret['comment'] = 'The group ' + group + ' is not available'
            return ret

    # Wow, we passed the test, run this sucker!
    try:
        cmd_all = __salt__['cmd.run_all'](name, cwd, runas=user)
    except CommandExecutionError as e:
        ret['comment'] = e
        return ret

    ret['changes'] = cmd_all
    ret['result'] = not bool(cmd_all['retcode'])
    ret['comment'] = 'Command "' + name + '" run'
    os.setegid(pgid)
    return ret

watcher = run
