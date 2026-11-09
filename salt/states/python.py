"""
Execution of Python code and scripts using Salt's own interpreter
==================================================================

The python state module runs Python code or scripts using the same
interpreter that is running Salt, rather than whatever ``python``/
``python3`` happens to resolve to on the target's ``PATH``.

A simple example to execute a snippet of Python code:

.. code-block:: yaml

    write-marker-file:
      python.run:
        - name: open('/tmp/salt-marker', 'w').close()

Download and run a script with the running Salt interpreter:

.. code-block:: yaml

    run-my-script:
      python.script:
        - source: salt://scripts/runme.py
        - args: arg1 arg2
"""

import copy
import logging
import os

from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

__virtualname__ = "python"


def __virtual__():
    return __virtualname__


def run(
    name,
    args=None,
    cwd=None,
    runas=None,
    password=None,
    env=None,
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
    Run a snippet of Python code, using the same interpreter that is
    running Salt, if certain circumstances are met.

    name
        The Python code to execute.

    args
        Additional arguments to pass to the interpreter (string or list).
        Only used if ``name`` should not be treated as the ``-c`` command,
        e.g. for ``-m module`` invocations.

    cwd
        The directory from which to execute the code. Defaults to the home
        directory of the user specified by ``runas`` (or the user under
        which Salt is running if ``runas`` is not specified).

    runas
        The user name (or uid) to run the code as.

    password
        Windows only. Required when specifying ``runas``. This parameter
        will be ignored on non-Windows platforms.

    env
        A list of environment variables to be set prior to execution.

    output_loglevel : debug
        Control the loglevel at which the output from the command is
        logged to the minion log.

    hide_output : False
        Suppress stdout and stderr in the state's results.

    timeout
        If the command has not terminated after timeout seconds, send the
        subprocess sigterm, and if sigterm is ignored, follow up with
        sigkill.

    ignore_timeout
        Ignore the timeout of commands, which is useful for running nohup
        processes.

    use_vt
        Use VT utils (saltstack) to stream the command output more
        interactively to the console and the logs. This is experimental.

    success_retcodes
        A list of non-zero return codes that should be considered a
        success.

    success_stdout
        A list of strings that when found in standard out should be
        considered a success.

    success_stderr
        A list of strings that when found in standard error should be
        considered a success.
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    if env is not None and not isinstance(env, (list, dict)):
        ret["comment"] = "Invalidly-formatted 'env' parameter. See documentation."
        return ret

    cmd_kwargs = copy.deepcopy(kwargs)
    cmd_kwargs.update(
        {
            "args": args,
            "cwd": cwd,
            "runas": runas,
            "password": password,
            "env": env,
            "use_vt": use_vt,
            "output_loglevel": output_loglevel,
            "hide_output": hide_output,
            "success_retcodes": success_retcodes,
            "success_stdout": success_stdout,
            "success_stderr": success_stderr,
        }
    )

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f'Python code "{name}" would have been executed'
        return ret

    if cwd and not os.path.isdir(cwd):
        ret["comment"] = f'Desired working directory "{cwd}" is not available'
        return ret

    try:
        cmd_all = __salt__["python.run"](command=name, timeout=timeout, **cmd_kwargs)
    except CommandExecutionError as err:
        ret["comment"] = str(err)
        return ret

    ret["changes"] = cmd_all
    ret["result"] = not bool(cmd_all["retcode"])
    ret["comment"] = f'Python code "{name}" run'

    if ignore_timeout:
        trigger = "Timed out after"
        if ret["changes"].get("retcode") == 1 and trigger in ret["changes"].get(
            "stdout", ""
        ):
            ret["changes"]["retcode"] = 0
            ret["result"] = True

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
    env=None,
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
    Download a Python script and execute it with the same interpreter that
    is running Salt.

    source
        The location of the script to download. If the file is located on
        the master in the directory named spam, and is called eggs, the
        source string is ``salt://spam/eggs``.

    name
        Either "script arg1 arg2 arg3..." (if ``source`` is also given) or
        a source "salt://...".

    template
        If this setting is applied then the named templating engine will
        be used to render the downloaded file. Currently jinja, mako, and
        wempy are supported.

    cwd
        The directory from which to execute the script. Defaults to the
        home directory of the user specified by ``runas`` (or the user
        under which Salt is running if ``runas`` is not specified).

    runas
        Specify an alternate user to run the script as. The default
        behavior is to run as the user under which Salt is running.

    password
        Windows only. Required when specifying ``runas``. This parameter
        will be ignored on non-Windows platforms.

    env
        A list of environment variables to be set prior to execution.

    timeout
        If the command has not terminated after timeout seconds, send the
        subprocess sigterm, and if sigterm is ignored, follow up with
        sigkill.

    use_vt
        Use VT utils (saltstack) to stream the command output more
        interactively to the console and the logs. This is experimental.

    output_loglevel : debug
        Control the loglevel at which the output from the command is
        logged to the minion log.

    hide_output : False
        Suppress stdout and stderr in the state's results.

    context
        Overrides default context variables passed to the template.

    defaults
        Default context passed to the template.

    success_retcodes
        A list of non-zero return codes that should be considered a
        success.

    success_stdout
        A list of strings that when found in standard out should be
        considered a success.

    success_stderr
        A list of strings that when found in standard error should be
        considered a success.
    """
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

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

    tmpctx = defaults if defaults else {}
    if context:
        tmpctx.update(context)

    cmd_kwargs = copy.deepcopy(kwargs)
    cmd_kwargs.update(
        {
            "runas": runas,
            "password": password,
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

    if source is None:
        source = name

    if not cmd_kwargs.get("args", None) and len(name.split()) > 1:
        cmd_kwargs.update({"args": name.split(" ", 1)[1]})

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"Python script '{name}' would have been executed"
        return ret

    if cwd and not os.path.isdir(cwd):
        ret["comment"] = f'Desired working directory "{cwd}" is not available'
        return ret

    try:
        cmd_all = __salt__["python.script"](source, **cmd_kwargs)
    except CommandExecutionError as err:
        ret["comment"] = str(err)
        return ret

    ret["changes"] = cmd_all
    ret["result"] = not bool(cmd_all["retcode"])
    if ret.get("changes", {}).get("cache_error"):
        ret["comment"] = f"Unable to cache script {source} from saltenv '{__env__}'"
    else:
        ret["comment"] = f"Python script '{name}' run"

    if __opts__["test"] and cmd_all["retcode"] == 0 and ret["changes"]:
        ret["result"] = None
    return ret
