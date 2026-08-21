"""
Run commands and scripts using the same Python interpreter that is running
Salt itself.

Salt's packages bundle their own "onedir" Python build, separate from
whatever Python (if any) is installed on the system. :py:func:`python.run
<salt.modules.python.run>` and :py:func:`python.script
<salt.modules.python.script>` always target that interpreter -
:py:data:`sys.executable` - rather than whatever ``python``/``python3``
happens to resolve to on ``PATH``.
"""

import logging
import os
import shutil
import sys

import salt.utils.args
import salt.utils.files
import salt.utils.platform
import salt.utils.url
from salt.exceptions import SaltInvocationError

log = logging.getLogger(__name__)

__virtualname__ = "python"


def __virtual__():
    return __virtualname__


def _get_python_executable():
    """
    Return the path to the Python interpreter currently running Salt.
    """
    return os.path.normpath(sys.executable)


def run(
    command=None,
    args=None,
    cwd=None,
    stdin=None,
    runas=None,
    group=None,
    env=None,
    clean_env=False,
    rstrip=True,
    umask=None,
    output_encoding=None,
    output_loglevel="debug",
    log_callback=None,
    hide_output=False,
    timeout=None,
    reset_system_locale=True,
    ignore_retcode=False,
    use_vt=False,
    bg=False,
    password=None,
    success_retcodes=None,
    success_stdout=None,
    success_stderr=None,
    **kwargs,
):
    """
    Run a snippet of Python code, or pass raw arguments to the interpreter,
    using the same Python that is running Salt.

    command
        A string of Python code to execute, passed to the interpreter as
        ``-c command``.

    args
        Additional arguments to pass to the interpreter. Can be a list, or a
        string which will be split using shell-like syntax. If ``command``
        is not specified, ``args`` is used as the full argument list handed
        to the interpreter, which makes it possible to invoke things like
        ``-m some_module``.

    cwd
        The directory from which to execute the command. Defaults to the
        home directory of the user specified by ``runas`` (or the user
        under which Salt is running if ``runas`` is not specified).

    stdin
        A string of standard input can be specified for the command to be
        run using the ``stdin`` parameter.

    runas
        Specify an alternate user to run the command. The default behavior
        is to run as the user under which Salt is running.

    group
        Group to run the command as. Not currently supported on Windows.

    password
        Windows only. Required when specifying ``runas``. This parameter
        will be ignored on non-Windows platforms.

    env
        Environment variables to be set prior to execution.

    clean_env
        Attempt to clean out all other Salt-related environment variables.

    rstrip
        Strip all whitespace off the end of output before it is returned.

    umask
        The umask (in octal) to use when running the command.

    output_encoding
        Control the encoding used to decode the command's output.

    output_loglevel : debug
        Control the loglevel at which the output from the command is
        logged to the minion log.

    log_callback
        A callback function that can be used to further process the
        output/return message of the command.

    hide_output : False
        If ``True``, suppress stdout and stderr in the return data.

    timeout
        If the command has not terminated after timeout seconds, send the
        subprocess sigterm, and if sigterm is ignored, follow up with
        sigkill.

    reset_system_locale
        Resets the system locale prior to executing the command.

    ignore_retcode
        If the exit code of the command is nonzero, this is treated as an
        error condition, and the output from the command will be logged to
        the minion log. Pass this argument as ``True`` to skip logging the
        output if the command has a nonzero exit code.

    use_vt
        Use VT utils (saltstack) to stream the command output more
        interactively to the console and the logs. This is experimental.

    bg
        If ``True``, run command in background and do not await or deliver
        its results.

    success_retcodes
        A list of non-zero return codes that should be considered a
        success. If the return code matches any in the list, it will be
        overridden with zero.

    success_stdout
        A list of strings that when found in standard out should be
        considered a success.

    success_stderr
        A list of strings that when found in standard error should be
        considered a success.

    CLI Example:

    .. code-block:: bash

        salt '*' python.run command="print('hello world')"
        salt '*' python.run args="-m json.tool foo.json"
    """
    python_exe = _get_python_executable()

    if isinstance(args, str):
        args = salt.utils.args.shlex_split(args)

    cmd_list = [python_exe]
    if command is not None:
        cmd_list.extend(["-c", command])
    if args:
        cmd_list.extend(args)

    if len(cmd_list) == 1:
        raise SaltInvocationError("Must specify either 'command' or 'args'")

    return __salt__["cmd.run_all"](
        cmd_list,
        cwd=cwd,
        stdin=stdin,
        runas=runas,
        group=group,
        python_shell=False,
        env=env,
        clean_env=clean_env,
        rstrip=rstrip,
        umask=umask,
        output_encoding=output_encoding,
        output_loglevel=output_loglevel,
        log_callback=log_callback,
        hide_output=hide_output,
        timeout=timeout,
        reset_system_locale=reset_system_locale,
        ignore_retcode=ignore_retcode,
        use_vt=use_vt,
        bg=bg,
        password=password,
        success_retcodes=success_retcodes,
        success_stdout=success_stdout,
        success_stderr=success_stderr,
        **kwargs,
    )


def script(
    source,
    args=None,
    cwd=None,
    stdin=None,
    runas=None,
    group=None,
    env=None,
    template=None,
    umask=None,
    output_encoding=None,
    output_loglevel="debug",
    log_callback=None,
    hide_output=False,
    timeout=None,
    reset_system_locale=True,
    saltenv=None,
    use_vt=False,
    bg=False,
    password=None,
    success_retcodes=None,
    success_stdout=None,
    success_stderr=None,
    **kwargs,
):
    """
    Download a Python script from the master (or another supported
    location) and execute it with the same Python interpreter that is
    running Salt, regardless of the script's shebang line, executable bit,
    or what ``python``/``python3`` resolves to on ``PATH``.

    source
        The location of the script to download. If the file is located on
        the master in the directory named spam, and is called eggs, the
        source string is ``salt://spam/eggs``.

    args
        String or list of command line args to pass to the script.

    cwd
        The directory from which to execute the command. Defaults to the
        home directory of the user specified by ``runas`` (or the user
        under which Salt is running if ``runas`` is not specified).

    stdin
        A string of standard input can be specified for the command to be
        run using the ``stdin`` parameter.

    runas
        Specify an alternate user to run the script as. The default
        behavior is to run as the user under which Salt is running.

    group
        Group to run the script as. Not currently supported on Windows.

    password
        Windows only. Required when specifying ``runas``. This parameter
        will be ignored on non-Windows platforms.

    env
        Environment variables to be set prior to execution.

    template
        If this setting is applied then the named templating engine will
        be used to render the downloaded file. Currently jinja, mako, and
        wempy are supported.

    umask
        The umask (in octal) to use when running the command.

    output_encoding
        Control the encoding used to decode the command's output.

    output_loglevel : debug
        Control the loglevel at which the output from the command is
        logged to the minion log.

    log_callback
        A callback function that can be used to further process the
        output/return message of the command.

    hide_output : False
        If ``True``, suppress stdout and stderr in the return data.

    timeout
        If the command has not terminated after timeout seconds, send the
        subprocess sigterm, and if sigterm is ignored, follow up with
        sigkill.

    reset_system_locale
        Resets the system locale prior to executing the command.

    saltenv : base
        The Salt environment to use to resolve ``source``.

    use_vt
        Use VT utils (saltstack) to stream the command output more
        interactively to the console and the logs. This is experimental.

    bg
        If ``True``, run command in background and do not await or deliver
        its results.

    success_retcodes
        A list of non-zero return codes that should be considered a
        success. If the return code matches any in the list, it will be
        overridden with zero.

    success_stdout
        A list of strings that when found in standard out should be
        considered a success.

    success_stderr
        A list of strings that when found in standard error should be
        considered a success.

    CLI Example:

    .. code-block:: bash

        salt '*' python.script salt://scripts/runme.py
        salt '*' python.script salt://scripts/runme.py 'arg1 arg2 "arg 3"'
    """
    if saltenv is None:
        try:
            saltenv = __opts__.get("saltenv", "base")
        except NameError:
            saltenv = "base"

    def _cleanup_tempfile(path):
        try:
            __salt__["file.remove"](path)
        except Exception as exc:  # pylint: disable=broad-except
            log.error("python.script: Unable to clean tempfile '%s': %s", path, exc)

    path = salt.utils.files.mkstemp(
        dir=cwd, suffix=os.path.splitext(salt.utils.url.split_env(source)[0])[1]
    )

    if template:
        fn_ = __salt__["cp.get_template"](source, path, template, saltenv, **kwargs)
        if not fn_:
            _cleanup_tempfile(path)
            return {
                "pid": 0,
                "retcode": 1,
                "stdout": "",
                "stderr": "",
                "cache_error": True,
            }
    else:
        fn_ = __salt__["cp.cache_file"](source, saltenv)
        if not fn_:
            _cleanup_tempfile(path)
            return {
                "pid": 0,
                "retcode": 1,
                "stdout": "",
                "stderr": "",
                "cache_error": True,
            }
        shutil.copyfile(fn_, path)

    if not salt.utils.platform.is_windows() and runas:
        os.chown(path, __salt__["file.user_to_uid"](runas), -1)

    if isinstance(args, str):
        args = salt.utils.args.shlex_split(args)

    python_exe = _get_python_executable()
    cmd_list = [python_exe, path]
    if args:
        cmd_list.extend(args)

    ret = __salt__["cmd.run_all"](
        cmd_list,
        cwd=cwd,
        stdin=stdin,
        runas=runas,
        group=group,
        python_shell=False,
        env=env,
        umask=umask,
        output_encoding=output_encoding,
        output_loglevel=output_loglevel,
        log_callback=log_callback,
        timeout=timeout,
        reset_system_locale=reset_system_locale,
        use_vt=use_vt,
        bg=bg,
        password=password,
        success_retcodes=success_retcodes,
        success_stdout=success_stdout,
        success_stderr=success_stderr,
        **kwargs,
    )
    _cleanup_tempfile(path)

    if hide_output:
        ret["stdout"] = ret["stderr"] = ""
    return ret
