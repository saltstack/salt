# -*- coding: utf-8 -*-
'''
Execution of arbitrary commands
===============================

The cmd state module manages the enforcement of executed commands, this
state can tell a command to run under certain circumstances.


A simple example to execute a command:

.. code-block:: yaml

    date > /tmp/salt-run:
      cmd.run

Only run if another execution failed, in this case truncate syslog if there is
no disk space:

.. code-block:: yaml

    > /var/log/messages:
      cmd.run:
        - unless: echo 'foo' > /tmp/.test && rm -f /tmp/.test

Only run if the file specified by ``creates`` does not exist, in this case
touch /tmp/foo if it does not exist.

.. code-block:: yaml

    touch /tmp/foo:
      cmd.run:
        - creates: /tmp/foo

.. note::

    The ``creates`` option was added to version 2014.7.0

Salt determines whether the ``cmd`` state is successfully enforced based on the exit
code returned by the command. If the command returns a zero exit code, then salt
determines that the state was successfully enforced. If the script returns a non-zero
exit code, then salt determines that it failed to successfully enforce the state.
If a command returns a non-zero exit code but you wish to treat this as a success,
then you must place the command in a script and explicitly set the exit code of
the script to zero.

Please note that the success or failure of the state is not affected by whether a state
change occurred nor the stateful argument.

When executing a command or script, the state (i.e., changed or not)
of the command is unknown to Salt's state system. Therefore, by default, the
``cmd`` state assumes that any command execution results in a changed state.

This means that if a ``cmd`` state is watched by another state then the
state that's watching will always be executed due to the `changed` state in
the ``cmd`` state.

Many state functions in this module now also accept a ``stateful`` argument.
If ``stateful`` is specified to be true then it is assumed that the command
or script will determine its own state and communicate it back by following
a simple protocol described below:

1. :strong:`If there's nothing in the stdout of the command, then assume no
   changes.` Otherwise, the stdout must be either in JSON or its `last`
   non-empty line must be a string of key=value pairs delimited by spaces (no
   spaces on either side of ``=``).

2. :strong:`If it's JSON then it must be a JSON object (e.g., {}).` If it's
   key=value pairs then quoting may be used to include spaces.  (Python's shlex
   module is used to parse the key=value string)

   Two special keys or attributes are recognized in the output::

    changed: bool (i.e., 'yes', 'no', 'true', 'false', case-insensitive)
    comment: str  (i.e., any string)

   So, only if ``changed`` is ``True`` then assume the command execution has
   changed the state, and any other key values or attributes in the output will
   be set as part of the changes.

3. :strong:`If there's a comment then it will be used as the comment of the
   state.`

   Here's an example of how one might write a shell script for use with a
   stateful command:

   .. code-block:: bash

       #!/bin/bash
       #
       echo "Working hard..."

       # writing the state line
       echo  # an empty line here so the next line will be the last.
       echo "changed=yes comment='something has changed' whatever=123"

   And an example SLS file using this module:

   .. code-block:: yaml

       Run myscript:
         cmd.run:
           - name: /path/to/myscript
           - cwd: /
           - stateful: True

       Run only if myscript changed something:
         cmd.wait:
           - name: echo hello
           - cwd: /
           - watch:
               - cmd: Run myscript

   Note that if the ``cmd.wait`` state also specifies ``stateful: True`` it can
   then be watched by some other states as well.

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


Should I use :mod:`cmd.run <salt.states.cmd.run>` or :mod:`cmd.wait
<salt.states.cmd.wait>`?
-------------------------------------------------------------------------------

These two states are often confused. The important thing to remember about them
is that :mod:`cmd.run <salt.states.cmd.run>` states are run each time the SLS
file that contains them is applied. If it is more desirable to have a command
that only runs after some other state changes, then :mod:`cmd.wait
<salt.states.cmd.wait>` does just that. :mod:`cmd.wait <salt.states.cmd.wait>`
is designed to :doc:`watch </ref/states/requisites>` other states, and is
executed when the state it is watching changes. Example:

.. code-block:: yaml

    /usr/local/bin/postinstall.sh:
      cmd:
        - wait
        - watch:
          - pkg: mycustompkg
      file:
        - managed
        - source: salt://utils/scripts/postinstall.sh

    mycustompkg:
      pkg:
        - installed
        - require:
          - file: /usr/local/bin/postinstall.sh

How do I create an environment from a pillar map?
-------------------------------------------------------------------------------

The map that comes from a pillar cannot be directly consumed by the env option.
To use it one must convert it to a list. Example:

.. code-block:: yaml

    printenv:
      cmd.run:
        - env:
          {% for key, value in pillar['keys'].iteritems() %}
          - '{{ key }}': '{{ value }}'
          {% endfor %}

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

# Import salt libs
from salt.exceptions import CommandExecutionError, SaltRenderError
from salt._compat import string_types

log = logging.getLogger(__name__)


def _reinterpreted_state(state):
    '''
    Re-interpret the state returned by salt.state.run using our protocol.
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
    except ValueError:
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


def mod_run_check(cmd_kwargs, onlyif, unless, group, creates):
    '''
    Execute the onlyif and unless logic.
    Return a result dict if:
    * group is not available
    * onlyif failed (onlyif != 0)
    * unless succeeded (unless == 0)
    else return True
    '''
    # never use VT for onlyif/unless executions because this will lead
    # to quote problems
    cmd_kwargs = copy.deepcopy(cmd_kwargs)
    cmd_kwargs['use_vt'] = False
    if group and HAS_GRP:
        try:
            egid = grp.getgrnam(group).gr_gid
            if not __opts__['test']:
                os.setegid(egid)
        except KeyError:
            return {'comment': 'The group {0} is not available'.format(group),
                    'result': False}

    if onlyif is not None:
        if isinstance(onlyif, string_types):
            cmd = __salt__['cmd.retcode'](onlyif, ignore_retcode=True, **cmd_kwargs)
            log.debug('Last command return code: {0}'.format(cmd))
            if cmd != 0:
                return {'comment': 'onlyif execution failed',
                        'result': True}
        elif isinstance(onlyif, list):
            for entry in onlyif:
                cmd = __salt__['cmd.retcode'](entry, ignore_retcode=True, **cmd_kwargs)
                log.debug('Last command return code: {0}'.format(cmd))
                if cmd != 0:
                    return {'comment': 'onlyif execution failed',
                        'result': True}
        elif not isinstance(onlyif, string_types):
            if not onlyif:
                log.debug('Command not run: onlyif did not evaluate to string_type')
                return {'comment': 'onlyif execution failed',
                        'result': True}

    if unless is not None:
        if isinstance(unless, string_types):
            cmd = __salt__['cmd.retcode'](unless, ignore_retcode=True, **cmd_kwargs)
            log.debug('Last command return code: {0}'.format(cmd))
            if cmd == 0:
                return {'comment': 'unless execution succeeded',
                        'result': True}
        elif isinstance(unless, list):
            for entry in unless:
                cmd = __salt__['cmd.retcode'](entry, ignore_retcode=True, **cmd_kwargs)
                log.debug('Last command return code: {0}'.format(cmd))
                if cmd == 0:
                    return {'comment': 'unless execution succeeded',
                            'result': True}
        elif not isinstance(unless, string_types):
            if unless:
                log.debug('Command not run: unless did not evaluate to string_type')
                return {'comment': 'unless execution succeeded',
                        'result': True}

    if isinstance(creates, string_types) and os.path.exists(creates):
        return {'comment': '{0} exists'.format(creates),
                'result': True}
    elif isinstance(creates, list) and all([
        os.path.exists(path) for path in creates
    ]):
        return {'comment': 'All files in creates exist',
                'result': True}

    # No reason to stop, return True
    return True


def wait(name,
         onlyif=None,
         unless=None,
         creates=None,
         cwd=None,
         user=None,
         group=None,
         shell=None,
         env=(),
         stateful=False,
         umask=None,
         output_loglevel='debug',
         use_vt=False,
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

    env
        A list of environment variables to be set prior to execution.
        Example:

        .. code-block:: yaml

            salt://scripts/foo.sh:
              cmd.script:
                - env:
                  - BATCH: 'yes'

        .. warning::

            The above illustrates a common PyYAML pitfall, that **yes**,
            **no**, **on**, **off**, **true**, and **false** are all loaded as
            boolean ``True`` and ``False`` values, and must be enclosed in
            quotes to be used as strings. More info on this (and other) PyYAML
            idiosyncrasies can be found :doc:`here
            </topics/troubleshooting/yaml_idiosyncrasies>`.

    umask
         The umask (in octal) to use when running the command.

    stateful
        The command being executed is expected to return data about executing
        a state

    creates
        Only run if the file specified by ``creates`` does not exist.

        .. versionadded:: 2014.7.0

    output_loglevel
        Control the loglevel at which the output from the command is logged.
        Note that the command being run will still be logged (loglevel: DEBUG)
        regardless, unless ``quiet`` is used for this value.

    use_vt
        Use VT utils (saltstack) to stream the command output more
        interactively to the console and the logs.
        This is experimental.
    '''
    # Ignoring our arguments is intentional.
    return {'name': name,
            'changes': {},
            'result': True,
            'comment': ''}


# Alias "cmd.watch" to "cmd.wait", as this is a common misconfiguration
watch = wait


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
                use_vt=False,
                output_loglevel='debug',
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
        A list of environment variables to be set prior to execution.
        Example:

        .. code-block:: yaml

            salt://scripts/foo.sh:
              cmd.script:
                - env:
                  - BATCH: 'yes'

        .. warning::

            The above illustrates a common PyYAML pitfall, that **yes**,
            **no**, **on**, **off**, **true**, and **false** are all loaded as
            boolean ``True`` and ``False`` values, and must be enclosed in
            quotes to be used as strings. More info on this (and other) PyYAML
            idiosyncrasies can be found :doc:`here
            </topics/troubleshooting/yaml_idiosyncrasies>`.

    umask
         The umask (in octal) to use when running the command.

    stateful
        The command being executed is expected to return data about executing
        a state

    use_vt
        Use VT utils (saltstack) to stream the command output more
        interactively to the console and the logs.
        This is experimental.

     output_loglevel
        Control the loglevel at which the output from the command is logged.
        Note that the command being run will still be logged (loglevel: DEBUG)
        regardless, unless ``quiet`` is used for this value.

    '''
    # Ignoring our arguments is intentional.
    return {'name': name,
            'changes': {},
            'result': True,
            'comment': ''}


def run(name,
        onlyif=None,
        unless=None,
        creates=None,
        cwd=None,
        user=None,
        group=None,
        shell=None,
        env=None,
        stateful=False,
        umask=None,
        output_loglevel='debug',
        quiet=False,
        timeout=None,
        use_vt=False,
        **kwargs):
    '''
    Run a command if certain circumstances are met.  Use ``cmd.wait`` if you
    want to use the ``watch`` requisite.

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
        A list of environment variables to be set prior to execution.
        Example:

        .. code-block:: yaml

            salt://scripts/foo.sh:
              cmd.script:
                - env:
                  - BATCH: 'yes'

        .. warning::

            The above illustrates a common PyYAML pitfall, that **yes**,
            **no**, **on**, **off**, **true**, and **false** are all loaded as
            boolean ``True`` and ``False`` values, and must be enclosed in
            quotes to be used as strings. More info on this (and other) PyYAML
            idiosyncrasies can be found :doc:`here
            </topics/troubleshooting/yaml_idiosyncrasies>`.

    stateful
        The command being executed is expected to return data about executing
        a state

    umask
        The umask (in octal) to use when running the command.

    output_loglevel
        Control the loglevel at which the output from the command is logged.
        Note that the command being run will still be logged (loglevel: DEBUG)
        regardless, unless ``quiet`` is used for this value.

    quiet
        The command will be executed quietly, meaning no log entries of the
        actual command or its return data. This is deprecated as of the
        **2014.1.0** release, and is being replaced with
        ``output_loglevel: quiet``.

    timeout
        If the command has not terminated after timeout seconds, send the
        subprocess sigterm, and if sigterm is ignored, follow up with sigkill

    creates
        Only run if the file specified by ``creates`` does not exist.

        .. versionadded:: 2014.7.0

    use_vt
        Use VT utils (saltstack) to stream the command output more
        interactively to the console and the logs.
        This is experimental.

    .. note::

        cmd.run supports the usage of ``reload_modules``. This functionality
        allows you to force Salt to reload all modules. You should only use
        ``reload_modules`` if your cmd.run does some sort of installation
        (such as ``pip``), if you do not reload the modules future items in
        your state which rely on the software being installed will fail.

        .. code-block:: yaml

            getpip:
              cmd.run:
                - name: /usr/bin/python /usr/local/sbin/get-pip.py
                - unless: which pip
                - require:
                  - pkg: python
                  - file: /usr/local/sbin/get-pip.py
                - reload_modules: True

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
        ret['comment'] = (
            'Desired working directory "{0}" '
            'is not available'
        ).format(cwd)
        return ret

    # Need the check for None here, if env is not provided then it falls back
    # to None and it is assumed that the environment is not being overridden.
    if env is not None and not isinstance(env, (list, dict)):
        ret['comment'] = ('Invalidly-formatted \'env\' parameter. See '
                          'documentation.')
        return ret

    if HAS_GRP:
        pgid = os.getegid()

    cmd_kwargs = {'cwd': cwd,
                  'runas': user,
                  'use_vt': use_vt,
                  'shell': shell or __grains__['shell'],
                  'env': env,
                  'umask': umask,
                  'output_loglevel': output_loglevel,
                  'quiet': quiet}

    try:
        cret = mod_run_check(cmd_kwargs, onlyif, unless, group, creates)
        if isinstance(cret, dict):
            ret.update(cret)
            return ret

        # Wow, we passed the test, run this sucker!
        if not __opts__['test']:
            try:
                cmd_all = __salt__['cmd.run_all'](
                    name, timeout=timeout, **cmd_kwargs
                )
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
           creates=None,
           cwd=None,
           user=None,
           group=None,
           shell=None,
           env=None,
           stateful=False,
           umask=None,
           timeout=None,
           use_vt=False,
           output_loglevel='debug',
           **kwargs):
    '''
    Download a script and execute it with specified arguments.

    source
        The location of the script to download. If the file is located on the
        master in the directory named spam, and is called eggs, the source
        string is salt://spam/eggs

    template
        If this setting is applied then the named templating engine will be
        used to render the downloaded file. Currently jinja, mako, and wempy
        are supported

    name
        Either "cmd arg1 arg2 arg3..." (cmd is not used) or a source
        "salt://...".

    onlyif
        Run the named command only if the command passed to the ``onlyif``
        option returns true

    unless
        Run the named command only if the command passed to the ``unless``
        option returns false

    cwd
        The current working directory to execute the command in, defaults to
        /root

    user
        The name of the user to run the command as

    group
        The group context to run the command as

    shell
        The shell to use for execution. The default is set in grains['shell']

    env
        A list of environment variables to be set prior to execution.
        Example:

        .. code-block:: yaml

            salt://scripts/foo.sh:
              cmd.script:
                - env:
                  - BATCH: 'yes'

        .. warning::

            The above illustrates a common PyYAML pitfall, that **yes**,
            **no**, **on**, **off**, **true**, and **false** are all loaded as
            boolean ``True`` and ``False`` values, and must be enclosed in
            quotes to be used as strings. More info on this (and other) PyYAML
            idiosyncrasies can be found :doc:`here
            </topics/troubleshooting/yaml_idiosyncrasies>`.

    umask
         The umask (in octal) to use when running the command.

    stateful
        The command being executed is expected to return data about executing
        a state

    timeout
        If the command has not terminated after timeout seconds, send the
        subprocess sigterm, and if sigterm is ignored, follow up with sigkill

    args
        String of command line args to pass to the script.  Only used if no
        args are specified as part of the `name` argument. To pass a string
        containing spaces in YAML, you will need to doubly-quote it:  "arg1
        'arg two' arg3"

    creates
        Only run if the file specified by ``creates`` does not exist.

        .. versionadded:: 2014.7.0

    use_vt
        Use VT utils (saltstack) to stream the command output more
        interactively to the console and the logs.
        This is experimental.

    output_loglevel
        Control the loglevel at which the output from the command is logged.
        Note that the command being run will still be logged (loglevel: DEBUG)
        regardless, unless ``quiet`` is used for this value.

    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': ''}

    if cwd and not os.path.isdir(cwd):
        ret['comment'] = (
            'Desired working directory "{0}" '
            'is not available'
        ).format(cwd)
        return ret

    # Need the check for None here, if env is not provided then it falls back
    # to None and it is assumed that the environment is not being overridden.
    if env is not None and not isinstance(env, (list, dict)):
        ret['comment'] = ('Invalidly-formatted \'env\' parameter. See '
                          'documentation.')
        return ret

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
                       'timeout': timeout,
                       'output_loglevel': output_loglevel,
                       'use_vt': use_vt,
                       'saltenv': __env__})

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
        cret = mod_run_check(
            run_check_cmd_kwargs, onlyif, unless, group, creates
        )
        if isinstance(cret, dict):
            ret.update(cret)
            return ret

        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Command {0!r} would have been ' \
                             'executed'.format(name)
            return _reinterpreted_state(ret) if stateful else ret

        # Wow, we passed the test, run this sucker!
        try:
            cmd_all = __salt__['cmd.script'](source, **cmd_kwargs)
        except (CommandExecutionError, SaltRenderError, IOError) as err:
            ret['comment'] = str(err)
            return ret

        ret['changes'] = cmd_all
        if kwargs.get('retcode', False):
            ret['result'] = not bool(cmd_all)
        else:
            ret['result'] = not bool(cmd_all['retcode'])
        if ret.get('changes', {}).get('cache_error'):
            ret['comment'] = 'Unable to cache script {0} from saltenv ' \
                             '{1!r}'.format(source, __env__)
        else:
            ret['comment'] = 'Command {0!r} run'.format(name)
        return _reinterpreted_state(ret) if stateful else ret

    finally:
        if HAS_GRP:
            os.setegid(pgid)


def call(name,
         func,
         args=(),
         kws=None,
         onlyif=None,
         unless=None,
         creates=None,
         output_loglevel='debug',
         use_vt=False,
         **kwargs):
    '''
    Invoke a pre-defined Python function with arguments specified in the state
    declaration. This function is mainly used by the
    :mod:`salt.renderers.pydsl` renderer.

    The interpretation of ``onlyif`` and ``unless`` arguments are identical to
    those of :mod:`cmd.run <salt.states.cmd.run>`, and all other
    arguments(``cwd``, ``runas``, ...) allowed by :mod:`cmd.run
    <salt.states.cmd.run>` are allowed here, except that their effects apply
    only to the commands specified in `onlyif` and `unless` rather than to the
    function to be invoked.

    In addition, the ``stateful`` argument has no effects here.

    The return value of the invoked function will be interpreted as follows.

    If it's a dictionary then it will be passed through to the state system,
    which expects it to have the usual structure returned by any salt state
    function.

    Otherwise, the return value (denoted as ``result`` in the code below) is
    expected to be a JSON serializable object, and this dictionary is returned:

    .. code-block:: python

        {
            'name': name
            'changes': {'retval': result},
            'result': True if result is None else bool(result),
            'comment': result if isinstance(result, string_types) else ''
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
                  'use_vt': use_vt,
                  'output_loglevel': output_loglevel,
                  'umask': kwargs.get('umask')}
    if HAS_GRP:
        pgid = os.getegid()
    try:
        cret = mod_run_check(cmd_kwargs, onlyif, unless, None, creates)
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
        if isinstance(result, string_types):
            ret['comment'] = result
        return ret


def wait_call(name,
              func,
              args=(),
              kws=None,
              onlyif=None,
              unless=None,
              creates=None,
              stateful=False,
              use_vt=False,
              output_loglevel='debug',
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
    if kwargs['sfun'] in ('wait', 'run', 'watch'):
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
        if kwargs.get('func'):
            func = kwargs.pop('func')
            return call(name, func, **kwargs)
        else:
            return {'name': name,
                    'changes': {},
                    'comment': (
                        'cmd.{0[sfun]} needs a named parameter func'
                    ).format(kwargs),
                    'result': False}

    return {'name': name,
            'changes': {},
            'comment': 'cmd.{0[sfun]} does not work with the watch requisite, '
                       'please use cmd.wait or cmd.wait_script'.format(kwargs),
            'result': False}
