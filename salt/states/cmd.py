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

.. warning::

    Please be advised that on Unix systems the shell being used by python
    to run executions is /bin/sh, this requires that commands are formatted
    to execute under /bin/sh. Some capabilities of newer shells such as bash,
    zsh and ksh will not always be available on minions.

'''

import grp
import os
import pwd
from salt.exceptions import CommandExecutionError

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
        group=None,
        shell='/bin/sh',
        env=()):
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
            if not __opts__['test']:
                os.setegid(egid)
        except KeyError:
            ret['comment'] = 'The group {0} is not available'.format(group)
            return ret

    if env:
        _env = {}
        for var in env.split():
            try:
                k, v = var.split('=')
                _env[k] = v
            except ValueError:
                ret['comment'] = 'Invalid enviromental var: "{0}"'.format(var)
                return ret
        env = _env

    # Wow, we passed the test, run this sucker!
    if not __opts__['test']:
        try:
            cmd_all = __salt__['cmd.run_all'](name, cwd, runas=user,
                                              shell=shell, env=env)
        except CommandExecutionError as e:
            ret['comment'] = e
            return ret

        ret['changes'] = cmd_all
        ret['result'] = not bool(cmd_all['retcode'])
        ret['comment'] = 'Command "{0}" run'.format(name)
        os.setegid(pgid)
        return ret
    ret['result'] = False
    ret['comment'] = 'Command "{0}" would have been executed'.format(name)
    return ret

mod_watch = run
