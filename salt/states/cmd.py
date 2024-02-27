"""
Execution of arbitrary commands
===============================

The cmd state module manages the enforcement of executed commands, this
state can tell a command to run under certain circumstances.


A simple example to execute a command:

.. code-block:: yaml

    # Store the current date in a file
    'date > /tmp/salt-run':
      cmd.run

Only run if another execution failed, in this case truncate syslog if there is
no disk space:

.. code-block:: yaml

    '> /var/log/messages/':
      cmd.run:
        - unless: echo 'foo' > /tmp/.test && rm -f /tmp/.test

Only run if the file specified by ``creates`` does not exist, in this case
touch /tmp/foo if it does not exist:

.. code-block:: yaml

    touch /tmp/foo:
      cmd.run:
        - creates: /tmp/foo

``creates`` also accepts a list of files, in which case this state will
run if **any** of the files do not exist:

.. code-block:: yaml

    "echo 'foo' | tee /tmp/bar > /tmp/baz":
      cmd.run:
        - creates:
          - /tmp/bar
          - /tmp/baz

.. note::

    The ``creates`` option was added to the cmd state in version 2014.7.0,
    and made a global requisite in 3001.

Sometimes when running a command that starts up a daemon, the init script
doesn't return properly which causes Salt to wait indefinitely for a response.
In situations like this try the following:

.. code-block:: yaml

    run_installer:
      cmd.run:
        - name: /tmp/installer.bin > /dev/null 2>&1

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

.. _stateful-argument:

Using the "Stateful" Argument
-----------------------------

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
         cmd.run:
           - name: echo hello
           - cwd: /
           - onchanges:
               - cmd: Run myscript

   Note that if the second ``cmd.run`` state also specifies ``stateful: True`` it can
   then be watched by some other states as well.

4. :strong:`The stateful argument can optionally include a test_name parameter.`

   This is used to specify a command to run in test mode.  This command should
   return stateful data for changes that would be made by the command in the
   name parameter.

   .. versionadded:: 2015.2.0

   .. code-block:: yaml

       Run myscript:
         cmd.run:
           - name: /path/to/myscript
           - cwd: /
           - stateful:
             - test_name: /path/to/myscript test

       Run masterscript:
         cmd.script:
           - name: masterscript
           - source: salt://path/to/masterscript
           - cwd: /
           - stateful:
             - test_name: masterscript test


Should I use :mod:`cmd.run <salt.states.cmd.run>` or :mod:`cmd.wait <salt.states.cmd.wait>`?
--------------------------------------------------------------------------------------------

.. note::

    Use :mod:`cmd.run <salt.states.cmd.run>` together with :ref:`onchanges <requisites-onchanges>`
    instead of :mod:`cmd.wait <salt.states.cmd.wait>`.

These two states are often confused. The important thing to remember about them
is that :mod:`cmd.run <salt.states.cmd.run>` states are run each time the SLS
file that contains them is applied. If it is more desirable to have a command
that only runs after some other state changes, then :mod:`cmd.wait
<salt.states.cmd.wait>` does just that. :mod:`cmd.wait <salt.states.cmd.wait>`
is designed to :ref:`watch <requisites-watch>` other states, and is
executed when the state it is watching changes. Example:

.. code-block:: yaml

    /usr/local/bin/postinstall.sh:
      cmd.wait:
        - watch:
          - pkg: mycustompkg
      file.managed:
        - source: salt://utils/scripts/postinstall.sh

    mycustompkg:
      pkg.installed:
        - require:
          - file: /usr/local/bin/postinstall.sh

``cmd.wait`` itself do not do anything; all functionality is inside its ``mod_watch``
function, which is called by ``watch`` on changes.

The preferred format is using the :ref:`onchanges Requisite <requisites-onchanges>`, which
works on ``cmd.run`` as well as on any other state. The example would then look as follows:

.. code-block:: yaml

    /usr/local/bin/postinstall.sh:
      cmd.run:
        - onchanges:
          - pkg: mycustompkg
      file.managed:
        - source: salt://utils/scripts/postinstall.sh

    mycustompkg:
      pkg.installed:
        - require:
          - file: /usr/local/bin/postinstall.sh

How do I create an environment from a pillar map?
-------------------------------------------------

The map that comes from a pillar can be directly consumed by the env option!
To use it, one may pass it like this. Example:

.. code-block:: yaml

    printenv:
      cmd.run:
        - env: {{ salt['pillar.get']('example:key', {}) }}

"""

import copy
import logging
import os

import salt.utils.args
import salt.utils.functools
import salt.utils.json
import salt.utils.platform
from salt.exceptions import CommandExecutionError, SaltRenderError

log = logging.getLogger(__name__)


def _reinterpreted_state(state):
    """
    Re-interpret the state returned by salt.state.run using our protocol.
    """
    ret = state["changes"]
    state["changes"] = {}
    state["comment"] = ""

    out = ret.get("stdout")
    if not out:
        if ret.get("stderr"):
            state["comment"] = ret["stderr"]
        return state

    is_json = False
    try:
        data = salt.utils.json.loads(out)
        if not isinstance(data, dict):
            return _failout(
                state, "script JSON output must be a JSON object (e.g., {})!"
            )
        is_json = True
    except ValueError:
        idx = out.rstrip().rfind("\n")
        if idx != -1:
            out = out[idx + 1 :]
        data = {}
        try:
            for item in salt.utils.args.shlex_split(out):
                key, val = item.split("=")
                data[key] = val
        except ValueError:
            state = _failout(
                state,
                "Failed parsing script output! "
                "Stdout must be JSON or a line of name=value pairs.",
            )
            state["changes"].update(ret)
            return state

    changed = _is_true(data.get("changed", "no"))

    if "comment" in data:
        state["comment"] = data["comment"]
        del data["comment"]

    if changed:
        for key in ret:
            data.setdefault(key, ret[key])

        # if stdout is the state output in JSON, don't show it.
        # otherwise it contains the one line name=value pairs, strip it.
        data["stdout"] = "" if is_json else data.get("stdout", "")[:idx]
        state["changes"] = data

    # FIXME: if it's not changed but there's stdout and/or stderr then those
    #       won't be shown as the function output. (though, they will be shown
    #       inside INFO logs).
    return state


def _failout(state, msg):
    state["comment"] = msg
    state["result"] = False
    return state


def _is_true(val):
    if val and str(val).lower() in ("true", "yes", "1"):
        return True
    elif str(val).lower() in ("false", "no", "0"):
        return False
    raise ValueError(f"Failed parsing boolean value: {val}")


def wait(
    name,
    cwd=None,
    root=None,
    runas=None,
    shell=None,
    env=(),
    stateful=False,
    output_loglevel="debug",
    hide_output=False,
    use_vt=False,
    success_retcodes=None,
    success_stdout=None,
    success_stderr=None,
    **kwargs,
):
    """
    Run the given command only if the watch statement calls it.

    .. note::

        Use :mod:`cmd.run <salt.states.cmd.run>` together with :mod:`onchanges </ref/states/requisites#onchanges>`
        instead of :mod:`cmd.wait <salt.states.cmd.wait>`.

    name
        The command to execute, remember that the command will execute with the
        path and permissions of the salt-minion.

    cwd
        The current working directory to execute the command in, defaults to
        /root

    root
        Path to the root of the jail to use. If this parameter is set, the command
        will run inside a chroot

    runas
        The user name to run the command as

    shell
        The shell to use for execution, defaults to /bin/sh

    env
        A list of environment variables to be set prior to execution.
        Example:

        .. code-block:: yaml

            script-foo:
              cmd.wait:
                - env:
                  - BATCH: 'yes'

        .. warning::

            The above illustrates a common PyYAML pitfall, that **yes**,
            **no**, **on**, **off**, **true**, and **false** are all loaded as
            boolean ``True`` and ``False`` values, and must be enclosed in
            quotes to be used as strings. More info on this (and other) PyYAML
            idiosyncrasies can be found :ref:`here <yaml-idiosyncrasies>`.

        Variables as values are not evaluated. So $PATH in the following
        example is a literal '$PATH':

        .. code-block:: yaml

            script-bar:
              cmd.wait:
                - env: "PATH=/some/path:$PATH"

        One can still use the existing $PATH by using a bit of Jinja:

        .. code-block:: jinja

            {% set current_path = salt['environ.get']('PATH', '/bin:/usr/bin') %}

            mycommand:
              cmd.run:
                - name: ls -l /
                - env:
                  - PATH: {{ [current_path, '/my/special/bin']|join(':') }}

        .. note::
            When using environment variables on Windows, case-sensitivity
            matters, i.e. Windows uses `Path` as opposed to `PATH` for other
            systems.

    stateful
        The command being executed is expected to return data about executing
        a state. For more information, see the :ref:`stateful-argument` section.

    creates
        Only run if the file specified by ``creates`` do not exist. If you
        specify a list of files then this state will only run if **any** of
        the files do not exist.

        .. versionadded:: 2014.7.0

    output_loglevel : debug
        Control the loglevel at which the output from the command is logged to
        the minion log.

        .. note::
            The command being run will still be logged at the ``debug``
            loglevel regardless, unless ``quiet`` is used for this value.

    hide_output : False
        Suppress stdout and stderr in the state's results.

        .. note::
            This is separate from ``output_loglevel``, which only handles how
            Salt logs to the minion log.

        .. versionadded:: 2018.3.0

    use_vt
        Use VT utils (saltstack) to stream the command output more
        interactively to the console and the logs.
        This is experimental.

    success_retcodes
        This parameter allows you to specify a list of non-zero return codes
        that should be considered as successful. If the return code from the
        command matches any in the list, the state will have a ``True`` result
        instead of ``False``.

      .. versionadded:: 2019.2.0

    success_stdout: This parameter will allow a list of
        strings that when found in standard out should be considered a success.
        If stdout returned from the run matches any in the provided list,
        the return code will be overridden with zero.

      .. versionadded:: 3004

    success_stderr: This parameter will allow a list of
        strings that when found in standard error should be considered a success.
        If stderr returned from the run matches any in the provided list,
        the return code will be overridden with zero.

      .. versionadded:: 3004
    """
    # Ignoring our arguments is intentional.
    return {"name": name, "changes": {}, "result": True, "comment": ""}


# Alias "cmd.watch" to "cmd.wait", as this is a common misconfiguration
watch = salt.utils.functools.alias_function(wait, "watch")


def wait_script(
    name,
    source=None,
    template=None,
    cwd=None,
    runas=None,
    shell=None,
    env=None,
    stateful=False,
    use_vt=False,
    output_loglevel="debug",
    hide_output=False,
    success_retcodes=None,
    success_stdout=None,
    success_stderr=None,
    **kwargs,
):
    """
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

    cwd
        The current working directory to execute the command in, defaults to
        /root

    runas
        The user name to run the command as

    shell
        The shell to use for execution, defaults to the shell grain

    env
        A list of environment variables to be set prior to execution.
        Example:

        .. code-block:: yaml

            salt://scripts/foo.sh:
              cmd.wait_script:
                - env:
                  - BATCH: 'yes'

        .. warning::

            The above illustrates a common PyYAML pitfall, that **yes**,
            **no**, **on**, **off**, **true**, and **false** are all loaded as
            boolean ``True`` and ``False`` values, and must be enclosed in
            quotes to be used as strings. More info on this (and other) PyYAML
            idiosyncrasies can be found :ref:`here <yaml-idiosyncrasies>`.

        Variables as values are not evaluated. So $PATH in the following
        example is a literal '$PATH':

        .. code-block:: yaml

            salt://scripts/bar.sh:
              cmd.wait_script:
                - env: "PATH=/some/path:$PATH"

        One can still use the existing $PATH by using a bit of Jinja:

        .. code-block:: jinja

            {% set current_path = salt['environ.get']('PATH', '/bin:/usr/bin') %}

            mycommand:
              cmd.run:
                - name: ls -l /
                - env:
                  - PATH: {{ [current_path, '/my/special/bin']|join(':') }}

        .. note::
            When using environment variables on Windows, case-sensitivity
            matters, i.e. Windows uses `Path` as opposed to `PATH` for other
            systems.

    stateful
        The command being executed is expected to return data about executing
        a state. For more information, see the :ref:`stateful-argument` section.

    use_vt
        Use VT utils (saltstack) to stream the command output more
        interactively to the console and the logs.
        This is experimental.

    output_loglevel : debug
        Control the loglevel at which the output from the command is logged to
        the minion log.

        .. note::
            The command being run will still be logged at the ``debug``
            loglevel regardless, unless ``quiet`` is used for this value.

    hide_output : False
        Suppress stdout and stderr in the state's results.

        .. note::
            This is separate from ``output_loglevel``, which only handles how
            Salt logs to the minion log.

        .. versionadded:: 2018.3.0

    success_retcodes
        This parameter allows you to specify a list of non-zero return codes
        that should be considered as successful. If the return code from the
        command matches any in the list, the state will have a ``True`` result
        instead of ``False``.

      .. versionadded:: 2019.2.0

    success_stdout: This parameter will allow a list of
        strings that when found in standard out should be considered a success.
        If stdout returned from the run matches any in the provided list,
        the return code will be overridden with zero.

      .. versionadded:: 3004

    success_stderr: This parameter will allow a list of
        strings that when found in standard error should be considered a success.
        If stderr returned from the run matches any in the provided list,
        the return code will be overridden with zero.

      .. versionadded:: 3004
    """
    # Ignoring our arguments is intentional.
    return {"name": name, "changes": {}, "result": True, "comment": ""}


def run(
    name,
    cwd=None,
    root=None,
    runas=None,
    shell=None,
    env=None,
    prepend_path=None,
    stateful=False,
    output_loglevel="debug",
    hide_output=False,
    timeout=None,
    ignore_timeout=False,
    use_vt=False,
    success_retcodes=None,
    success_stdout=None,
    success_stderr=None,
    **kwargs,
):
    """
    Run a command if certain circumstances are met.  Use ``cmd.wait`` if you
    want to use the ``watch`` requisite.

    .. note::

       The ``**kwargs`` of ``cmd.run`` are passed down to one of the following
       exec modules:

       * ``cmdmod.run_all``: If used with default ``runas``
       * ``cmdmod.run_chroot``: If used with non-``root`` value for ``runas``

       For more information on what args are available for either of these,
       refer to the :ref:`cmdmod documentation <cmdmod-module>`.

    name
        The command to execute, remember that the command will execute with the
        path and permissions of the salt-minion.

    cwd
        The current working directory to execute the command in, defaults to
        /root

    root
        Path to the root of the jail to use. If this parameter is set, the command
        will run inside a chroot

    runas
        The user name (or uid) to run the command as

    shell
        The shell to use for execution, defaults to the shell grain

    env
        A list of environment variables to be set prior to execution.
        Example:

        .. code-block:: yaml

            script-foo:
              cmd.run:
                - env:
                  - BATCH: 'yes'

        .. warning::

            The above illustrates a common PyYAML pitfall, that **yes**,
            **no**, **on**, **off**, **true**, and **false** are all loaded as
            boolean ``True`` and ``False`` values, and must be enclosed in
            quotes to be used as strings. More info on this (and other) PyYAML
            idiosyncrasies can be found :ref:`here <yaml-idiosyncrasies>`.

        Variables as values are not evaluated. So $PATH in the following
        example is a literal '$PATH':

        .. code-block:: yaml

            script-bar:
              cmd.run:
                - env: "PATH=/some/path:$PATH"

        One can still use the existing $PATH by using a bit of Jinja:

        .. code-block:: jinja

            {% set current_path = salt['environ.get']('PATH', '/bin:/usr/bin') %}

            mycommand:
              cmd.run:
                - name: ls -l /
                - env:
                  - PATH: {{ [current_path, '/my/special/bin']|join(':') }}

        .. note::
            When using environment variables on Windows, case-sensitivity
            matters, i.e. Windows uses `Path` as opposed to `PATH` for other
            systems.

    prepend_path
        $PATH segment to prepend (trailing ':' not necessary) to $PATH. This is
        an easier alternative to the Jinja workaround.

        .. versionadded:: 2018.3.0

    stateful
        The command being executed is expected to return data about executing
        a state. For more information, see the :ref:`stateful-argument` section.

    output_loglevel : debug
        Control the loglevel at which the output from the command is logged to
        the minion log.

        .. note::
            The command being run will still be logged at the ``debug``
            loglevel regardless, unless ``quiet`` is used for this value.

    hide_output : False
        Suppress stdout and stderr in the state's results.

        .. note::
            This is separate from ``output_loglevel``, which only handles how
            Salt logs to the minion log.

        .. versionadded:: 2018.3.0

    timeout
        If the command has not terminated after timeout seconds, send the
        subprocess sigterm, and if sigterm is ignored, follow up with sigkill

    ignore_timeout
        Ignore the timeout of commands, which is useful for running nohup
        processes.

        .. versionadded:: 2015.8.0

    creates
        Only run if the file specified by ``creates`` do not exist. If you
        specify a list of files then this state will only run if **any** of
        the files do not exist.

        .. versionadded:: 2014.7.0

    use_vt : False
        Use VT utils (saltstack) to stream the command output more
        interactively to the console and the logs.
        This is experimental.

    bg : False
        If ``True``, run command in background and do not await or deliver its
        results.

        .. versionadded:: 2016.3.6

    success_retcodes
        This parameter allows you to specify a list of non-zero return codes
        that should be considered as successful. If the return code from the
        command matches any in the list, the state will have a ``True`` result
        instead of ``False``.

      .. versionadded:: 2019.2.0

    success_stdout: This parameter will allow a list of
        strings that when found in standard out should be considered a success.
        If stdout returned from the run matches any in the provided list,
        the return code will be overridden with zero.

      .. versionadded:: 3004

    success_stderr: This parameter will allow a list of
        strings that when found in standard error should be considered a success.
        If stderr returned from the run matches any in the provided list,
        the return code will be overridden with zero.

      .. versionadded:: 3004

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

    """
    ### NOTE: The keyword arguments in **kwargs are passed directly to the
    ###       ``cmd.run_all`` function and cannot be removed from the function
    ###       definition, otherwise the use of unsupported arguments in a
    ###       ``cmd.run`` state will result in a traceback.

    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    test_name = None
    if not isinstance(stateful, list):
        stateful = stateful is True
    elif isinstance(stateful, list) and "test_name" in stateful[0]:
        test_name = stateful[0]["test_name"]
    if __opts__["test"] and test_name:
        name = test_name

    # Need the check for None here, if env is not provided then it falls back
    # to None and it is assumed that the environment is not being overridden.
    if env is not None and not isinstance(env, (list, dict)):
        ret["comment"] = "Invalidly-formatted 'env' parameter. See documentation."
        return ret

    cmd_kwargs = copy.deepcopy(kwargs)
    cmd_kwargs.update(
        {
            "cwd": cwd,
            "root": root,
            "runas": runas,
            "use_vt": use_vt,
            "shell": shell or __grains__["shell"],
            "env": env,
            "prepend_path": prepend_path,
            "output_loglevel": output_loglevel,
            "hide_output": hide_output,
            "success_retcodes": success_retcodes,
            "success_stdout": success_stdout,
            "success_stderr": success_stderr,
        }
    )

    if __opts__["test"] and not test_name:
        ret["result"] = None
        ret["comment"] = f'Command "{name}" would have been executed'
        ret["changes"] = {"cmd": name}
        return _reinterpreted_state(ret) if stateful else ret

    if cwd and not os.path.isdir(cwd):
        ret["comment"] = f'Desired working directory "{cwd}" is not available'
        return ret

    # Wow, we passed the test, run this sucker!
    try:
        run_cmd = "cmd.run_all" if not root else "cmd.run_chroot"
        cmd_all = __salt__[run_cmd](
            cmd=name, timeout=timeout, python_shell=True, **cmd_kwargs
        )
    except Exception as err:  # pylint: disable=broad-except
        ret["comment"] = str(err)
        return ret

    ret["changes"] = cmd_all
    ret["result"] = not bool(cmd_all["retcode"])
    ret["comment"] = f'Command "{name}" run'

    # Ignore timeout errors if asked (for nohups) and treat cmd as a success
    if ignore_timeout:
        trigger = "Timed out after"
        if ret["changes"].get("retcode") == 1 and trigger in ret["changes"].get(
            "stdout"
        ):
            ret["changes"]["retcode"] = 0
            ret["result"] = True

    if stateful:
        ret = _reinterpreted_state(ret)
    if __opts__["test"] and cmd_all["retcode"] == 0 and ret["changes"]:
        ret["result"] = None
    return ret


def script(
    name,
    source=None,
    template=None,
    cwd=None,
    runas=None,
    password=None,
    shell=None,
    env=None,
    stateful=False,
    timeout=None,
    use_vt=False,
    output_loglevel="debug",
    hide_output=False,
    defaults=None,
    context=None,
    success_retcodes=None,
    success_stdout=None,
    success_stderr=None,
    **kwargs,
):
    """
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

    cwd
        The current working directory to execute the command in, defaults to
        /root

    runas
        Specify an alternate user to run the command. The default
        behavior is to run as the user under which Salt is running. If running
        on a Windows minion you must also use the ``password`` argument, and
        the target user account must be in the Administrators group.

        .. note::

            For Windows users, specifically Server users, it may be necessary
            to specify your runas user using the User Logon Name instead of the
            legacy logon name. Traditionally, logons would be in the following
            format.

                ``Domain/user``

            In the event this causes issues when executing scripts, use the UPN
            format which looks like the following.

                ``user@domain.local``

            More information <https://github.com/saltstack/salt/issues/55080>

    password

    .. versionadded:: 3000

        Windows only. Required when specifying ``runas``. This
        parameter will be ignored on non-Windows platforms.

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
            idiosyncrasies can be found :ref:`here <yaml-idiosyncrasies>`.

        Variables as values are not evaluated. So $PATH in the following
        example is a literal '$PATH':

        .. code-block:: yaml

            salt://scripts/bar.sh:
              cmd.script:
                - env: "PATH=/some/path:$PATH"

        One can still use the existing $PATH by using a bit of Jinja:

        .. code-block:: jinja

            {% set current_path = salt['environ.get']('PATH', '/bin:/usr/bin') %}

            mycommand:
              cmd.run:
                - name: ls -l /
                - env:
                  - PATH: {{ [current_path, '/my/special/bin']|join(':') }}

        .. note::
            When using environment variables on Windows, case-sensitivity
            matters, i.e. Windows uses `Path` as opposed to `PATH` for other
            systems.

    saltenv : ``base``
        The Salt environment to use

    stateful
        The command being executed is expected to return data about executing
        a state. For more information, see the :ref:`stateful-argument` section.

    timeout
        If the command has not terminated after timeout seconds, send the
        subprocess sigterm, and if sigterm is ignored, follow up with sigkill

    args
        String of command line args to pass to the script.  Only used if no
        args are specified as part of the `name` argument. To pass a string
        containing spaces in YAML, you will need to doubly-quote it:  "arg1
        'arg two' arg3"

    creates
        Only run if the file specified by ``creates`` do not exist. If you
        specify a list of files then this state will only run if **any** of
        the files do not exist.

        .. versionadded:: 2014.7.0

    use_vt
        Use VT utils (saltstack) to stream the command output more
        interactively to the console and the logs.
        This is experimental.

    context
        .. versionadded:: 2016.3.0

        Overrides default context variables passed to the template.

    defaults
        .. versionadded:: 2016.3.0

        Default context passed to the template.

    output_loglevel : debug
        Control the loglevel at which the output from the command is logged to
        the minion log.

        .. note::
            The command being run will still be logged at the ``debug``
            loglevel regardless, unless ``quiet`` is used for this value.

    hide_output : False
        Suppress stdout and stderr in the state's results.

        .. note::
            This is separate from ``output_loglevel``, which only handles how
            Salt logs to the minion log.

        .. versionadded:: 2018.3.0

    success_retcodes
        This parameter allows you to specify a list of non-zero return codes
        that should be considered as successful. If the return code from the
        command matches any in the list, the state will have a ``True`` result
        instead of ``False``.

      .. versionadded:: 2019.2.0

    success_stdout: This parameter will allow a list of
        strings that when found in standard out should be considered a success.
        If stdout returned from the run matches any in the provided list,
        the return code will be overridden with zero.

      .. versionadded:: 3004

    success_stderr: This parameter will allow a list of
        strings that when found in standard error should be considered a success.
        If stderr returned from the run matches any in the provided list,
        the return code will be overridden with zero.

      .. versionadded:: 3004
    """
    test_name = None
    if not isinstance(stateful, list):
        stateful = stateful is True
    elif isinstance(stateful, list) and "test_name" in stateful[0]:
        test_name = stateful[0]["test_name"]
    if __opts__["test"] and test_name:
        name = test_name

    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    # Need the check for None here, if env is not provided then it falls back
    # to None and it is assumed that the environment is not being overridden.
    if env is not None and not isinstance(env, (list, dict)):
        ret["comment"] = "Invalidly-formatted 'env' parameter. See documentation."
        return ret

    if context and not isinstance(context, dict):
        ret["comment"] = (
            "Invalidly-formatted 'context' parameter. Must be formed as a dict."
        )
        return ret
    if defaults and not isinstance(defaults, dict):
        ret["comment"] = (
            "Invalidly-formatted 'defaults' parameter. Must be formed as a dict."
        )
        return ret

    if runas and salt.utils.platform.is_windows() and not password:
        ret["comment"] = "Must supply a password if runas argument is used on Windows."
        return ret

    tmpctx = defaults if defaults else {}
    if context:
        tmpctx.update(context)

    cmd_kwargs = copy.deepcopy(kwargs)
    cmd_kwargs.update(
        {
            "runas": runas,
            "password": password,
            "shell": shell or __grains__["shell"],
            "env": env,
            "cwd": cwd,
            "template": template,
            "timeout": timeout,
            "output_loglevel": output_loglevel,
            "hide_output": hide_output,
            "use_vt": use_vt,
            "context": tmpctx,
            "saltenv": __env__,
            "success_retcodes": success_retcodes,
            "success_stdout": success_stdout,
            "success_stderr": success_stderr,
        }
    )

    run_check_cmd_kwargs = {
        "cwd": cwd,
        "runas": runas,
        "shell": shell or __grains__["shell"],
    }

    # Change the source to be the name arg if it is not specified
    if source is None:
        source = name

    # If script args present split from name and define args
    if not cmd_kwargs.get("args", None) and len(name.split()) > 1:
        cmd_kwargs.update({"args": name.split(" ", 1)[1]})

    if __opts__["test"] and not test_name:
        ret["result"] = None
        ret["comment"] = f"Command '{name}' would have been executed"
        return _reinterpreted_state(ret) if stateful else ret

    if cwd and not os.path.isdir(cwd):
        ret["comment"] = f'Desired working directory "{cwd}" is not available'
        return ret

    # Wow, we passed the test, run this sucker!
    try:
        cmd_all = __salt__["cmd.script"](source, python_shell=True, **cmd_kwargs)
    except (CommandExecutionError, SaltRenderError, OSError) as err:
        ret["comment"] = str(err)
        return ret

    ret["changes"] = cmd_all
    if kwargs.get("retcode", False):
        ret["result"] = not bool(cmd_all)
    else:
        ret["result"] = not bool(cmd_all["retcode"])
    if ret.get("changes", {}).get("cache_error"):
        ret["comment"] = "Unable to cache script {} from saltenv '{}'".format(
            source, __env__
        )
    else:
        ret["comment"] = f"Command '{name}' run"
    if stateful:
        ret = _reinterpreted_state(ret)
    if __opts__["test"] and cmd_all["retcode"] == 0 and ret["changes"]:
        ret["result"] = None
    return ret


def call(
    name,
    func,
    args=(),
    kws=None,
    output_loglevel="debug",
    hide_output=False,
    use_vt=False,
    **kwargs,
):
    """
    Invoke a pre-defined Python function with arguments specified in the state
    declaration. This function is mainly used by the
    :mod:`salt.renderers.pydsl` renderer.

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
            'comment': result if isinstance(result, str) else ''
        }
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    cmd_kwargs = {
        "cwd": kwargs.get("cwd"),
        "runas": kwargs.get("user"),
        "shell": kwargs.get("shell") or __grains__["shell"],
        "env": kwargs.get("env"),
        "use_vt": use_vt,
        "output_loglevel": output_loglevel,
        "hide_output": hide_output,
    }

    if not kws:
        kws = {}
    result = func(*args, **kws)
    if isinstance(result, dict):
        ret.update(result)
        return ret
    else:
        # result must be JSON serializable else we get an error
        ret["changes"] = {"retval": result}
        ret["result"] = True if result is None else bool(result)
        if isinstance(result, str):
            ret["comment"] = result
        return ret


def wait_call(
    name,
    func,
    args=(),
    kws=None,
    stateful=False,
    use_vt=False,
    output_loglevel="debug",
    hide_output=False,
    **kwargs,
):
    # Ignoring our arguments is intentional.
    return {"name": name, "changes": {}, "result": True, "comment": ""}


def mod_watch(name, **kwargs):
    """
    Execute a cmd function based on a watch call

    .. note::
        This state exists to support special handling of the ``watch``
        :ref:`requisite <requisites>`. It should not be called directly.

        Parameters for this function should be set by the state being triggered.
    """
    if kwargs["sfun"] in ("wait", "run", "watch"):
        if kwargs.get("stateful"):
            kwargs.pop("stateful")
            return _reinterpreted_state(run(name, **kwargs))
        return run(name, **kwargs)

    elif kwargs["sfun"] == "wait_script" or kwargs["sfun"] == "script":
        if kwargs.get("stateful"):
            kwargs.pop("stateful")
            return _reinterpreted_state(script(name, **kwargs))
        return script(name, **kwargs)

    elif kwargs["sfun"] == "wait_call" or kwargs["sfun"] == "call":
        if kwargs.get("func"):
            func = kwargs.pop("func")
            return call(name, func, **kwargs)
        else:
            return {
                "name": name,
                "changes": {},
                "comment": "cmd.{0[sfun]} needs a named parameter func".format(kwargs),
                "result": False,
            }

    return {
        "name": name,
        "changes": {},
        "comment": (
            "cmd.{0[sfun]} does not work with the watch requisite, "
            "please use cmd.wait or cmd.wait_script".format(kwargs)
        ),
        "result": False,
    }
