'''
Execution of arbitrary commands.
================================

The cmd state module manages the enforcement of executed commands, this
state can tell a command to run under certain circumstances.


A simple example to execute a command:

    .. code-block:: yaml

        date > /tmp/salt-run:
        cmd:
            - run

Only run if another execution failed, in this case truncate
syslog if there is no disk space:

.. code-block:: yaml

    > /var/log/messages:
      cmd.run:
        - unless: echo 'foo' > /tmp/.test

Note that when executing a command or script, the state (i.e., changed or not)
of the command is unknown to Salt's state system. Therefore, by default, the
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

    If it's JSON then it must be a JSON object (e.g., {}).
    If it's key=value pairs then quoting may be used to include spaces.
    (Python's shlex module is used to parse the key=value string)

    Two special keys or attributes are recognized in the output::

      changed: bool (i.e., 'yes', 'no', 'true', 'false', case-insensitive)
      comment: str  (i.e., any string)

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
      echo "changed=yes comment='something has changed' whatever=123"


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

    Note that if the ``cmd.wait`` state also specifies ``stateful: true``
    it can then be watched by some other states as well.

``cmd.wait`` is not restricted to watching only cmd states. For example
it can also watch a git state for changes

.. code-block:: yaml

    # Watch for changes to a git repo and rebuild the project on updates
    my-project:
      git.latest:
        - name: git@github.com/repo/foo
        - target: /opt/foo
        - rev: master
      cmd.wait:
        - name: make install
        - cwd: /opt/foo
        - watch:
          - git: my-project


'''

# Import python libs
# Windows platform has no 'grp' module
HAS_GRP = False
try:
    import grp
    HAS_GRP = True
except ImportError:
    pass
import os
import copy
import json
import shlex
import logging
import yaml

# Import salt libs
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)


def _reinterpreted_state(state):
    '''
    Re-interpret the state returned by salt.sate.run using our protocol.
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
        data = json.loads(out)
        if not isinstance(data, dict):
            return _failout(
                state,
                'script JSON output must be a JSON object (e.g., {})!'
            )
        is_json = True
    except Exception:
        idx = out.rstrip().rfind('\n')
        if idx != -1:
            out = out[idx + 1:]
        data = {}
        try:
            for item in shlex.split(out):
                key, val = item.split('=')
                data[key] = val
        except ValueError:
            return _failout(
                state,
                'Failed parsing script output! '
                'Stdout must be JSON or a line of name=value pairs.'
            )

    changed = _is_true(data.get('changed', 'no'))

    if 'comment' in data:
        state['comment'] = data['comment']
        del data['comment']

    if changed:
        for key in ret:
            data.setdefault(key, ret[key])

        # if stdout is the state output in JSON, don't show it.
        # otherwise it contains the one line name=value pairs, strip it.
        data['stdout'] = '' if is_json else data.get('stdout', '')[:idx]
        state['changes'] = data

    #FIXME: if it's not changed but there's stdout and/or stderr then those
    #       won't be shown as the function output. (though, they will be shown
    #       inside INFO logs).
    return state


def _failout(state, msg):
    state['comment'] = msg
    state['result'] = False
    return state


def _is_true(val):
    if val and str(val).lower() in ('true', 'yes', '1'):
        return True
    elif str(val).lower() in ('false', 'no', '0'):
        return False
    raise ValueError('Failed parsing boolean value: {0}'.format(val))


def _run_check(cmd_kwargs, onlyif, unless, group):
    '''
    Execute the onlyif and unless logic.
    Return a result dict if:
    * group is not available
    * onlyif failed (onlyif != 0)
    * unless succeeded (unless == 0)
    else return True
    '''
    if group and HAS_GRP:
        try:
            egid = grp.getgrnam(group).gr_gid
            if not __opts__['test']:
                os.setegid(egid)
        except KeyError:
            return {'comment': 'The group {0} is not available'.format(group),
                    'result': False}

    if onlyif:
        if __salt__['cmd.retcode'](onlyif, **cmd_kwargs) != 0:
            return {'comment': 'onlyif execution failed',
                    'result': True}

    if unless:
        if __salt__['cmd.retcode'](unless, **cmd_kwargs) == 0:
            return {'comment': 'unless execution succeeded',
                    'result': True}

    # No reason to stop, return True
    return True


def wait(name,
         onlyif=None,
         unless=None,
         cwd=None,
         user=None,
         group=None,
         shell=None,
         stateful=False,
         umask=None,
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

    umask
         The umask (in octal) to use when running the command.

    stateful
        The command being executed is expected to return data about executing
        a state
    '''
    # Ignoring our arguments is intentional.
    return {'name': name,
            'changes': {},
            'result': True,
            'comment': ''}


def wait_script(name,
                source=None,
                template=None,
                onlyif=None,
                unless=None,
                cwd=None,
                user=None,
                group=None,
                shell=None,
                env=None,
                stateful=False,
                umask=None,
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

    umask
         The umask (in octal) to use when running the command.

    stateful
        The command being executed is expected to return data about executing
        a state
    '''
    # Ignoring our arguments is intentional.
    return {'name': name,
            'changes': {},
            'result': True,
            'comment': ''}


def run(name,
        onlyif=None,
        unless=None,
        cwd=None,
        user=None,
        group=None,
        shell=None,
        env=(),
        stateful=False,
        umask=None,
        quiet=False,
        timeout=None,
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
        Pass in a list or dict of environment variables to be applied to the
        command upon execution

    stateful
        The command being executed is expected to return data about executing
        a state

    umask
        The umask (in octal) to use when running the command.

    quiet
        The command will be executed quietly, meaning no log entries of the
        actual command or its return data

    timeout
        If the command has not terminated after timeout seconds, send the
        subprocess sigterm, and if sigterm is ignored, follow up with sigkill
    '''
    ### NOTE: The keyword arguments in **kwargs are ignored in this state, but
    ###       cannot be removed from the function definition, otherwise the use
    ###       of unsupported arguments in a cmd.run state will result in a
    ###       traceback.

    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    if cwd and not os.path.isdir(cwd):
        ret['comment'] = 'Desired working directory is not available'
        return ret

    if env:
        if isinstance(env, basestring):
            try:
                env = yaml.safe_load(env)
            except Exception:
                _env = {}
                for var in env.split():
                    try:
                        key, val = var.split('=')
                        _env[key] = val
                    except ValueError:
                        ret['comment'] = \
                            'Invalid environmental var: "{0}"'.format(var)
                        return ret
                env = _env
        elif isinstance(env, dict):
            pass

        elif isinstance(env, list):
            _env = {}
            for comp in env:
                try:
                    if isinstance(comp, basestring):
                        _env.update(yaml.safe_load(comp))
                    if isinstance(comp, dict):
                        _env.update(comp)
                    else:
                        ret['comment'] = \
                            'Invalid environmental var: "{0}"'.format(env)
                        return ret
                except Exception:
                    _env = {}
                    for var in comp.split():
                        try:
                            key, val = var.split('=')
                            _env[key] = val
                        except ValueError:
                            ret['comment'] = \
                                'Invalid environmental var: "{0}"'.format(var)
                            return ret
            env = _env

    if HAS_GRP:
        pgid = os.getegid()

    cmd_kwargs = {'cwd': cwd,
                  'runas': user,
                  'shell': shell or __grains__['shell'],
                  'env': env,
                  'umask': umask,
                  'quiet': quiet}

    try:
        cret = _run_check(cmd_kwargs, onlyif, unless, group)
        if isinstance(cret, dict):
            ret.update(cret)
            return ret

        # Wow, we passed the test, run this sucker!
        if not __opts__['test']:
            try:
                cmd_all = __salt__['cmd.run_all'](name, timeout=timeout, **cmd_kwargs)
            except CommandExecutionError as err:
                ret['comment'] = str(err)
                return ret

            ret['changes'] = cmd_all
            ret['result'] = not bool(cmd_all['retcode'])
            ret['comment'] = 'Command "{0}" run'.format(name)
            return _reinterpreted_state(ret) if stateful else ret
        ret['result'] = None
        ret['comment'] = 'Command "{0}" would have been executed'.format(name)
        return _reinterpreted_state(ret) if stateful else ret

    finally:
        if HAS_GRP:
            os.setegid(pgid)


def script(name,
           source=None,
           template=None,
           onlyif=None,
           unless=None,
           cwd=None,
           user=None,
           group=None,
           shell=None,
           env=None,
           stateful=False,
           umask=None,
           timeout=None,
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

    umask
         The umask (in octal) to use when running the command.

    stateful
        The command being executed is expected to return data about executing
        a state

    timeout
        If the command has not terminated after timeout seconds, send the
        subprocess sigterm, and if sigterm is ignored, follow up with sigkill

    '''
    ret = {'changes': {},
           'comment': '',
           'name': name,
           'result': False}

    if cwd and not os.path.isdir(cwd):
        ret['comment'] = 'Desired working directory is not available'
        return ret

    if env is None:
        env = kwargs.get('__env__', 'base')

    if HAS_GRP:
        pgid = os.getegid()

    cmd_kwargs = copy.deepcopy(kwargs)
    cmd_kwargs.update({'runas': user,
                       'shell': shell or __grains__['shell'],
                       'env': env,
                       'onlyif': onlyif,
                       'unless': unless,
                       'user': user,
                       'group': group,
                       'cwd': cwd,
                       'template': template,
                       'umask': umask,
                       'timeout': timeout})

    run_check_cmd_kwargs = {
        'cwd': cwd,
        'runas': user,
        'shell': shell or __grains__['shell']
    }

    # Change the source to be the name arg if it is not specified
    if source is None:
        source = name

    # If script args present split from name and define args
    if len(name.split()) > 1:
        cmd_kwargs.update({'args': name.split(' ', 1)[1]})

    try:
        cret = _run_check(
            run_check_cmd_kwargs, onlyif, unless, group
        )
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
        except CommandExecutionError as err:
            ret['comment'] = str(err)
            return ret

        ret['changes'] = cmd_all
        if kwargs.get('retcode', False):
            ret['result'] = not bool(cmd_all)
        else:
            ret['result'] = not bool(cmd_all['retcode'])
        ret['comment'] = 'Command "{0}" run'.format(name)
        return _reinterpreted_state(ret) if stateful else ret

    finally:
        if HAS_GRP:
            os.setegid(pgid)


def call(name, func, args=(), kws=None,
         onlyif=None,
         unless=None,
         **kwargs):
    '''
    Invoke a pre-defined Python function with arguments specified in the state
    declaration. This function is mainly used by the
    :mod:`salt.renderers.pydsl` renderer.

    The interpretation of `onlyif` and `unless` arguments are identical to
    those of :func:`salt.states.cmd.run`, and all other arguments(`cwd`,
    `runas`, ...) allowed by `cmd.run` are allowed here, except that their
    effects apply only to the commands specified in `onlyif` and `unless`
    rather than to the function to be invoked.

    In addition the `stateful` argument has no effects here.

    The return value of the invoked function will be interpreted as follows.

    If it's a dictionary then it will be passed through to the state system,
    which expects it to have the usual structure returned by any salt state
    function.

    Otherwise, the return value(denoted as ``result`` in the code below) is
    expected to be a JSON serializable object, and this dictionary is returned:

    .. code-block:: python

        { 'changes': { 'retval': result },
          'result': True if result is None else bool(result),
          'comment': result if isinstance(result, basestring) else ''
        }
    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    cmd_kwargs = {'cwd': kwargs.get('cwd'),
                  'runas': kwargs.get('user'),
                  'shell': kwargs.get('shell') or __grains__['shell'],
                  'env': kwargs.get('env'),
                  'umask': kwargs.get('umask')}
    if HAS_GRP:
        pgid = os.getegid()
    try:
        cret = _run_check(cmd_kwargs, onlyif, unless, None)
        if isinstance(cret, dict):
            ret.update(cret)
            return ret
    finally:
        if HAS_GRP:
            os.setegid(pgid)
    if not kws:
        kws = {}
    result = func(*args, **kws)
    if isinstance(result, dict):
        ret.update(result)
        return ret
    else:
        # result must be JSON serializable else we get an error
        ret['changes'] = {'retval': result}
        ret['result'] = True if result is None else bool(result)
        if isinstance(result, basestring):
            ret['comment'] = result
        return ret


def wait_call(name,
              func,
              args=(),
              kws=None,
              onlyif=None,
              unless=None,
              stateful=False,
              **kwargs):
    # Ignoring our arguments is intentional.
    return {'name': name,
            'changes': {},
            'result': True,
            'comment': ''}


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

    elif kwargs['sfun'] == 'wait_call' or kwargs['sfun'] == 'call':
        return call(name, **kwargs)

    return {'name': name,
            'changes': {},
            'comment': 'cmd.{0[sfun]} does not work with the watch requisite, '
                       'please use cmd.wait or cmd.wait_script'.format(kwargs),
            'result': False}
