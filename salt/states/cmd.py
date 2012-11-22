'''
Execution of arbitrary commands.
================================

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
      cmd.run:
        - unless: echo 'foo' > /tmp/.test

Note that when executing a command or script, the state(ie, changed or not) of
the command is unknown to Salt's state system. Therefore, by default, the
``cmd`` state assumes that any command execution results in a changed state. 

This means that if a ``cmd`` state is watched by another state then the
state that's watching will always be executed due to the `changed` state in
the ``cmd`` state.

Many state functions in this module now also accept a ``stateful`` argument.
If ``stateful`` is specified to be true then it is assumed that the command
or script will determine its own state and communicate it back by following
a simple protocol described below:

    If there's nothing in the stdout of the command, then assume no changes.
    Otherwise, the stdout must be either in JSON or its `last` non-empty line
    must be a string of key=value pairs delimited by spaces(no spaces on the
    sides of ``=``).

    If it's JSON then it must be a JSON object(ie, {}). 
    If it's key=value pairs then quoting may be used to include spaces.
    (Python's shlex module is used to parse the key=value string)

    Two special keys or attributes are recognized in the output::

      changed: bool (ie, 'yes', 'no', 'true', 'false', case-insensitive)
      comment: str  (ie, any string)

    So, only if 'changed' is true then assume the command execution has changed
    the state, and any other key values or attributes in the output will be set
    as part of the changes.

    If there's a comment then it will be used as the comment of the state.

    Here's an example of how one might write a shell script for use with a
    stateful command::

      #!/bin/bash
      #
      echo "Working hard..."

      # writing the state line
      echo  # an empty line here so the next line will be the last.
      echo "changed=yes comment=\"something's changed!\" whatever=123"


    And an example salt file using this module::

        Run myscript:
          cmd.run:
            - name: /path/to/myscript
            - cwd: /
            - stateful: true
        
        Run only if myscript changed something:
          cmd.wait:
            - name: echo hello
            - cwd: /
            - watch:
              - cmd: Run myscript

    Note that if the ``cmd.wait`` state also specfies ``stateful: true``
    it can then be watched by some other states as well.


'''

# Import python libs
import grp
import os
import copy
import json
import shlex
import logging

# Import salt libs
from salt.exceptions import CommandExecutionError
import salt.state

log = logging.getLogger(__name__)


def _reinterpreted_state(state):
    '''
    Re-interpret the state return by salt.sate.run using our protocol.
    '''
    ret = state['changes']
    state['changes'] = {}
    state['comment'] = ''

    out = ret.get('stdout')
    if not out:
        if ret.get('stderr'):
            state['comment'] = ret['stderr'] 
        return state

    is_json = False
    try:
        d = json.loads(out)
        if not isinstance(d, dict):
            return _failout(state,
                       'script JSON output must be a JSON object(ie, {})!')
        is_json = True
    except Exception:
        idx = out.rstrip().rfind('\n')
        if idx != -1:
            out = out[idx+1:]
        d = {}
        try:
            for item in shlex.split(out):
                k, v = item.split('=')
                d[k] = v
        except ValueError:
            return _failout(state,
                'Failed parsing script output! '
                'Stdout must be JSON or a line of name=value pairs.')

    changed = _is_true(d.get('changed', 'no'))
    
    if 'comment' in d:
        state['comment'] = d['comment']
        del d['comment']

    if changed:
        for k in ret:
            d.setdefault(k, ret[k])

        # if stdout is the state output in json, don't show it.
        # otherwise it contains the one line name=value pairs, strip it.
        d['stdout'] = '' if is_json else d.get('stdout', '')[:idx]
        state['changes'] = d

    #FIXME: if it's not changed but there's stdout and/or stderr then those
    #       won't be shown as the function output. (though, they will be shown
    #       inside INFO logs).
    return state        


def _failout(state, msg):
    state['comment'] = msg
    state['result'] = False
    return state


def _is_true(v):
    if v and str(v).lower() in ('true', 'yes', '1'):
        return True
    elif str(v).lower() in ('false', 'no', '0'):
        return False
    raise ValueError('Failed parsing boolean value: {0}'.format(v))


def _run_check(cmd_kwargs, onlyif, unless, cwd, user, group, shell):
    '''
    Execute the onlyif logic and return data if the onlyif fails
    '''
    ret = {}

    if group:
        try:
            egid = grp.getgrnam(group).gr_gid
            if not __opts__['test']:
                os.setegid(egid)
        except KeyError:
            ret['comment'] = 'The group {0} is not available'.format(group)
            return {'comment': 'The group {0} is not available'.format(group),
                    'result': False}

    if onlyif:
        if __salt__['cmd.retcode'](onlyif, **cmd_kwargs) != 0:
            ret['comment'] = 'onlyif exec failed'
            ret['result'] = True
            return {'comment': 'onlyif exec failed',
                    'result': True}

    if unless:
        if __salt__['cmd.retcode'](unless, **cmd_kwargs) == 0:
            return {'comment': 'unless executed successfully',
                    'result': True}
    # No reason to stop, return True
    return True


def wait(name,
        onlyif=None,
        unless=None,
        cwd='/root',
        user=None,
        group=None,
        shell=None,
        stateful=False,
        **kwargs):
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

    shell
        The shell to use for execution, defaults to /bin/sh
    
    stateful
        The command being executed is expected to return data about executing
        a state
    '''
    return {'name': name,
            'changes': {},
            'result': True,
            'comment': ''}


def wait_script(name,
        source=None,
        template=None,
        onlyif=None,
        unless=None,
        cwd='/root',
        user=None,
        group=None,
        shell=None,
        env=None,
        stateful=False,
        **kwargs):
    '''
    Download a script from a remote source and execute it only if a watch
    statement calls it.
    
    source
        The source script being downloaded to the minion, this source script is
        hosted on the salt master server.  If the file is located on the master 
        in the directory named spam, and is called eggs, the source string is 
        salt://spam/eggs
    
    template
        If this setting is applied then the named templating engine will be
        used to render the downloaded file, currently jinja, mako, and wempy
        are supported
    
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

    shell
        The shell to use for execution, defaults to the shell grain
    
    env
        The root directory of the environment for the referencing script. The
        environments are defined in the master config file.
    
    stateful
        The command being executed is expected to return data about executing
        a state
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
        shell=None,
        env=(),
        stateful=False,
        **kwargs):
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

    shell
        The shell to use for execution, defaults to the shell grain
    
    env
        The root directory of the environment for the referencing script. The
        environments are defined in the master config file.

    stateful
        The command being executed is expected to return data about executing
        a state
    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    if not os.path.isdir(cwd):
        ret['comment'] = 'Desired working directory is not available'
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

    pgid = os.getegid()

    cmd_kwargs = {'cwd': cwd,
                  'runas': user,
                  'shell': shell or __grains__['shell'],
                  'env': env}

    try:
        cret = _run_check(cmd_kwargs, onlyif, unless, cwd, user, group, shell)
        if isinstance(cret, dict):
            ret.update(cret)
            return ret

        # Wow, we passed the test, run this sucker!
        if not __opts__['test']:
            try:
                cmd_all = __salt__['cmd.run_all'](name, **cmd_kwargs)
            except CommandExecutionError as e:
                ret['comment'] = str(e)
                return ret

            ret['changes'] = cmd_all
            ret['result'] = not bool(cmd_all['retcode'])
            ret['comment'] = 'Command "{0}" run'.format(name)
            return _reinterpreted_state(ret) if stateful else ret
        ret['result'] = None
        ret['comment'] = 'Command "{0}" would have been executed'.format(name)
        return _reinterpreted_state(ret) if stateful else ret

    finally:
        os.setegid(pgid)


def script(name,
        source=None,
        template=None,
        onlyif=None,
        unless=None,
        cwd='/root',
        user=None,
        group=None,
        shell=None,
        env=None,
        stateful=False,
        **kwargs):
    '''
    Download a script from a remote source and execute it. The name can be the
    source or the source value can be defined.
    source
        The source script being downloaded to the minion, this source script is
        hosted on the salt master server.  If the file is located on the master 
        in the directory named spam, and is called eggs, the source string is 
        salt://spam/eggs
    
    template
        If this setting is applied then the named templating engine will be
        used to render the downloaded file, currently jinja, mako, and wempy
        are supported
    
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

    shell
        The shell to use for execution, defaults to the shell grain
    
    env
        The root directory of the environment for the referencing script. The
        environments are defined in the master config file.
    
    stateful
        The command being executed is expected to return data about executing
        a state
    '''
    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': False}

    if not os.path.isdir(cwd):
        ret['comment'] = 'Desired working directory is not available'
        return ret

    if env is None:
        env = kwargs.get('__env__', 'base')

    pgid = os.getegid()

    cmd_kwargs = copy.deepcopy(kwargs)
    cmd_kwargs.update({'cwd': cwd,
                  'runas': user,
                  'shell': shell or __grains__['shell'],
                  'env': env,
                  'onlyif': onlyif,
                  'unless': unless,
                  'user': user,
                  'group': group,
                  'cwd': cwd,
                  'template': template})

    run_check_cmd_kwargs = {'cwd': cwd,
                  'runas': user,
                  'shell': shell or __grains__['shell'], }

    # Change the source to be the name arg if it is not specified
    if source is None:
        source = name

    try:
        cret = _run_check(run_check_cmd_kwargs, onlyif, unless, cwd, user, group, shell)
        if isinstance(cret, dict):
            ret.update(cret)
            return ret

        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Command "{0}" would have been executed'
            ret['comment'] = ret['comment'].format(name)
            return _reinterpreted_state(ret) if stateful else ret

        # Wow, we passed the test, run this sucker!
        try:
            cmd_all = __salt__['cmd.script'](source, **cmd_kwargs)
        except CommandExecutionError as e:
            ret['comment'] = str(e)
            return ret

        ret['changes'] = cmd_all
        if kwargs.get('retcode', False):
            ret['result'] = not bool(cmd_all)
        else:
            ret['result'] = not bool(cmd_all['retcode'])
        ret['comment'] = 'Command "{0}" run'.format(name)
        return _reinterpreted_state(ret) if stateful else ret

    finally:
        os.setegid(pgid)

def mod_watch(name, **kwargs):
    '''
    Execute a cmd function based on a watch call
    '''
    if kwargs['sfun'] == 'wait' or kwargs['sfun'] == 'run':
        if kwargs.get('stateful'):
            kwargs.pop('stateful')
            return _reinterpreted_state(run(name, **kwargs))
        return run(name, **kwargs)

    elif kwargs['sfun'] == 'wait_script' or kwargs['sfun'] == 'script':
        if kwargs.get('stateful'):
            kwargs.pop('stateful')
            return _reinterpreted_state(script(name, **kwargs))
        return script(name, **kwargs)

    return {'name': name,
            'changes': {},
            'comment': ('cmd.{0} does not work with the watch requisite, '
                       'please use cmd.wait of cmd.wait_script').format(
                           kwargs['sfun']
                           ),
            'result': False}

