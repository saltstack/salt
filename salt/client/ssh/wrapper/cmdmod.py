"""
SSH wrapper module for the ``cmdmod`` execution module.

.. note::
    For consistency reasons, this wrapper currently does
    not behave the same as the execution module regarding ``saltenv``.
    The parameter defaults to ``base``, regardless of the current
    value of the minion setting.
    This is the same for the ``state`` and `cp`` wrappers.
"""

import logging
import os.path
import shlex

import salt.utils.url
from salt.exceptions import CommandExecutionError, SaltInvocationError
from salt.modules.cmdmod import _python_shell_default

log = logging.getLogger(__name__)

__virtualname__ = "cmd"


def __virtual__():
    return __virtualname__


def script(
    source,
    args=None,
    cwd=None,
    stdin=None,
    runas=None,
    group=None,
    shell=None,
    python_shell=None,
    env=None,
    template=None,
    umask=None,
    output_encoding=None,
    output_loglevel="debug",
    log_callback=None,
    hide_output=False,
    timeout=None,
    reset_system_locale=True,
    saltenv="base",
    use_vt=False,
    bg=False,
    password=None,
    success_retcodes=None,
    success_stdout=None,
    success_stderr=None,
    **kwargs
):
    """
    Download a script from a remote location and execute the script locally.
    The script can be located on the salt master file server or on an HTTP/FTP
    server.

    The script will be executed directly, so it can be written in any available
    programming language.

    :param str source: The location of the script to download. If the file is
        located on the master in the directory named spam, and is called eggs,
        the source string is salt://spam/eggs

    :param str args: String of command line args to pass to the script. Only
        used if no args are specified as part of the `name` argument. To pass a
        string containing spaces in YAML, you will need to doubly-quote it:

        .. code-block:: bash

            salt myminion cmd.script salt://foo.sh "arg1 'arg two' arg3"

    :param str cwd: The directory from which to execute the command. Defaults
        to the directory returned from Python's tempfile.mkstemp.

    :param str stdin: A string of standard input can be specified for the
        command to be run using the ``stdin`` parameter. This can be useful in
        cases where sensitive information must be read from standard input.

    :param str runas: Specify an alternate user to run the command. The default
        behavior is to run as the user under which Salt is running. If running
        on a Windows minion you must also use the ``password`` argument, and
        the target user account must be in the Administrators group.

        .. note::

            For Window's users, specifically Server users, it may be necessary
            to specify your runas user using the User Logon Name instead of the
            legacy logon name. Traditionally, logons would be in the following
            format.

                ``Domain/user``

            In the event this causes issues when executing scripts, use the UPN
            format which looks like the following.

                ``user@domain.local``

            More information <https://github.com/saltstack/salt/issues/55080>

    :param str password: Windows only. Required when specifying ``runas``. This
        parameter will be ignored on non-Windows platforms.

        .. versionadded:: 2016.3.0

    :param str group: Group to run script as. Not currently supported
      on Windows.

    :param str shell: Specify an alternate shell. Defaults to the system's
        default shell.

    :param bool python_shell: If False, let python handle the positional
        arguments. Set to True to use shell features, such as pipes or
        redirection.

    :param bool bg: If True, run script in background and do not await or
        deliver its results

    :param dict env: Environment variables to be set prior to execution.

        .. note::
            When passing environment variables on the CLI, they should be
            passed as the string representation of a dictionary.

            .. code-block:: bash

                salt myminion cmd.script 'some command' env='{"FOO": "bar"}'

        .. note::
            When using environment variables on Window's, case-sensitivity
            matters, i.e. Window's uses `Path` as opposed to `PATH` for other
            systems.

    :param str template: If this setting is applied then the named templating
        engine will be used to render the downloaded file. Currently jinja,
        mako, and wempy are supported.

    :param str umask: The umask (in octal) to use when running the command.

    :param str output_encoding: Control the encoding used to decode the
        command's output.

        .. note::
            This should not need to be used in most cases. By default, Salt
            will try to use the encoding detected from the system locale, and
            will fall back to UTF-8 if this fails. This should only need to be
            used in cases where the output of the command is encoded in
            something other than the system locale or UTF-8.

            To see the encoding Salt has detected from the system locale, check
            the `locale` line in the output of :py:func:`test.versions_report
            <salt.modules.test.versions_report>`.

        .. versionadded:: 2018.3.0

    :param str output_loglevel: Control the loglevel at which the output from
        the command is logged to the minion log.

        .. note::
            The command being run will still be logged at the ``debug``
            loglevel regardless, unless ``quiet`` is used for this value.

    :param bool ignore_retcode: If the exit code of the command is nonzero,
        this is treated as an error condition, and the output from the command
        will be logged to the minion log. However, there are some cases where
        programs use the return code for signaling and a nonzero exit code
        doesn't necessarily mean failure. Pass this argument as ``True`` to
        skip logging the output if the command has a nonzero exit code.

    :param bool hide_output: If ``True``, suppress stdout and stderr in the
        return data.

        .. note::
            This is separate from ``output_loglevel``, which only handles how
            Salt logs to the minion log.

        .. versionadded:: 2018.3.0

    :param int timeout: If the command has not terminated after timeout
        seconds, send the subprocess sigterm, and if sigterm is ignored, follow
        up with sigkill

    :param bool use_vt: Not supported via salt-ssh.

    :param list success_retcodes: This parameter will allow a list of
        non-zero return codes that should be considered a success.  If the
        return code returned from the run matches any in the provided list,
        the return code will be overridden with zero.

      .. versionadded:: 2019.2.0

    :param list success_stdout: This parameter will allow a list of
        strings that when found in standard out should be considered a success.
        If stdout returned from the run matches any in the provided list,
        the return code will be overridden with zero.

      .. versionadded:: 3004

    :param list success_stderr: This parameter will allow a list of
        strings that when found in standard error should be considered a success.
        If stderr returned from the run matches any in the provided list,
        the return code will be overridden with zero.

      .. versionadded:: 3004

    :param bool stdin_raw_newlines: False
        If ``True``, Salt will not automatically convert the characters ``\\n``
        present in the ``stdin`` value to newlines.

      .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' cmd.script salt://scripts/runme.sh
        salt '*' cmd.script salt://scripts/runme.sh 'arg1 arg2 "arg 3"'
        salt '*' cmd.script salt://scripts/windows_task.ps1 args=' -Input c:\\tmp\\infile.txt' shell='powershell'


    .. code-block:: bash

        salt '*' cmd.script salt://scripts/runme.sh stdin='one\\ntwo\\nthree\\nfour\\nfive\\n'
    """

    def _cleanup_tempfile(path):
        try:
            __salt__["file.remove"](path)
        except (SaltInvocationError, CommandExecutionError) as exc:
            log.error(
                "cmd.script: Unable to clean tempfile '%s': %s",
                path,
                exc,
                exc_info_on_loglevel=logging.DEBUG,
            )

    if shell is None:
        shell = __grains__.get("shell", "/bin/sh")
    python_shell = _python_shell_default(python_shell, kwargs.get("__pub_jid", ""))

    if "__env__" in kwargs:
        # "env" is not supported; Use "saltenv".
        kwargs.pop("__env__")

    path = __salt__["temp.file"](
        suffix=os.path.splitext(salt.utils.url.split_env(source)[0])[1], parent=cwd
    )
    try:
        if template:
            if "pillarenv" in kwargs or "pillar" in kwargs:
                pillarenv = kwargs.get("pillarenv", __opts__.get("pillarenv"))
                kwargs["pillar"] = _gather_pillar(pillarenv, kwargs.get("pillar"))
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
            __salt__["file.copy"](fn_, path)
        __salt__["file.set_mode"](path, "0500")
        __salt__["file.chown"](path, runas, -1)

        cmd_path = shlex.quote(path)
        # We should remove the pillar from kwargs (cmd.run_all ignores it anyways)
        # (it might also leak secrets in logs or break MAX_ARG)
        kwargs.pop("pillar", None)

        return __salt__["cmd.run_all"](
            cmd_path + " " + str(args) if args else cmd_path,
            cwd=cwd,
            stdin=stdin,
            output_encoding=output_encoding,
            output_loglevel=output_loglevel,
            log_callback=log_callback,
            runas=runas,
            group=group,
            shell=shell,
            python_shell=python_shell,
            env=env,
            umask=umask,
            timeout=timeout,
            reset_system_locale=reset_system_locale,
            saltenv=saltenv,
            use_vt=False,
            bg=bg,
            password=password,
            success_retcodes=success_retcodes,
            success_stdout=success_stdout,
            success_stderr=success_stderr,
            hide_output=hide_output,
            **kwargs
        )
    finally:
        _cleanup_tempfile(path)


def script_retcode(
    source,
    args=None,
    cwd=None,
    stdin=None,
    runas=None,
    group=None,
    shell=None,
    python_shell=None,
    env=None,
    template="jinja",
    umask=None,
    timeout=None,
    reset_system_locale=True,
    saltenv="base",
    output_encoding=None,
    output_loglevel="debug",
    log_callback=None,
    use_vt=False,
    password=None,
    success_retcodes=None,
    success_stdout=None,
    success_stderr=None,
    **kwargs
):
    """
    Download a script from a remote location and execute the script locally.
    The script can be located on the salt master file server or on an HTTP/FTP
    server.

    The script will be executed directly, so it can be written in any available
    programming language.

    The script can also be formatted as a template, the default is jinja.

    Only evaluate the script return code and do not block for terminal output

    :param str source: The location of the script to download. If the file is
        located on the master in the directory named spam, and is called eggs,
        the source string is salt://spam/eggs

    :param str args: String of command line args to pass to the script. Only
        used if no args are specified as part of the `name` argument. To pass a
        string containing spaces in YAML, you will need to doubly-quote it:
        "arg1 'arg two' arg3"

    :param str cwd: The directory from which to execute the command. Defaults
        to the home directory of the user specified by ``runas`` (or the user
        under which Salt is running if ``runas`` is not specified).

    :param str stdin: A string of standard input can be specified for the
        command to be run using the ``stdin`` parameter. This can be useful in
        cases where sensitive information must be read from standard input.

    :param str runas: Specify an alternate user to run the command. The default
        behavior is to run as the user under which Salt is running. If running
        on a Windows minion you must also use the ``password`` argument, and
        the target user account must be in the Administrators group.

    :param str password: Windows only. Required when specifying ``runas``. This
        parameter will be ignored on non-Windows platforms.

        .. versionadded:: 2016.3.0

    :param str group: Group to run script as. Not currently supported
      on Windows.

    :param str shell: Specify an alternate shell. Defaults to the system's
        default shell.

    :param bool python_shell: If False, let python handle the positional
        arguments. Set to True to use shell features, such as pipes or
        redirection.

    :param dict env: Environment variables to be set prior to execution.

        .. note::
            When passing environment variables on the CLI, they should be
            passed as the string representation of a dictionary.

            .. code-block:: bash

                salt myminion cmd.script_retcode 'some command' env='{"FOO": "bar"}'

        .. note::
            When using environment variables on Window's, case-sensitivity
            matters, i.e. Window's uses `Path` as opposed to `PATH` for other
            systems.

    :param str template: If this setting is applied then the named templating
        engine will be used to render the downloaded file. Currently jinja,
        mako, and wempy are supported.

    :param str umask: The umask (in octal) to use when running the command.

    :param str output_encoding: Control the encoding used to decode the
        command's output.

        .. note::
            This should not need to be used in most cases. By default, Salt
            will try to use the encoding detected from the system locale, and
            will fall back to UTF-8 if this fails. This should only need to be
            used in cases where the output of the command is encoded in
            something other than the system locale or UTF-8.

            To see the encoding Salt has detected from the system locale, check
            the `locale` line in the output of :py:func:`test.versions_report
            <salt.modules.test.versions_report>`.

        .. versionadded:: 2018.3.0

    :param str output_loglevel: Control the loglevel at which the output from
        the command is logged to the minion log.

        .. note::
            The command being run will still be logged at the ``debug``
            loglevel regardless, unless ``quiet`` is used for this value.

    :param bool ignore_retcode: If the exit code of the command is nonzero,
        this is treated as an error condition, and the output from the command
        will be logged to the minion log. However, there are some cases where
        programs use the return code for signaling and a nonzero exit code
        doesn't necessarily mean failure. Pass this argument as ``True`` to
        skip logging the output if the command has a nonzero exit code.

    :param int timeout: If the command has not terminated after timeout
        seconds, send the subprocess sigterm, and if sigterm is ignored, follow
        up with sigkill

    :param bool use_vt: Use VT utils (saltstack) to stream the command output
        more interactively to the console and the logs. This is experimental.

    :param list success_retcodes: This parameter will allow a list of
        non-zero return codes that should be considered a success.  If the
        return code returned from the run matches any in the provided list,
        the return code will be overridden with zero.

      .. versionadded:: 2019.2.0

    :param list success_stdout: This parameter will allow a list of
        strings that when found in standard out should be considered a success.
        If stdout returned from the run matches any in the provided list,
        the return code will be overridden with zero.

      .. versionadded:: 3004

    :param list success_stderr: This parameter will allow a list of
        strings that when found in standard error should be considered a success.
        If stderr returned from the run matches any in the provided list,
        the return code will be overridden with zero.

      .. versionadded:: 3004

    :param bool stdin_raw_newlines: False
        If ``True``, Salt will not automatically convert the characters ``\\n``
        present in the ``stdin`` value to newlines.

      .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' cmd.script_retcode salt://scripts/runme.sh
        salt '*' cmd.script_retcode salt://scripts/runme.sh 'arg1 arg2 "arg 3"'
        salt '*' cmd.script_retcode salt://scripts/windows_task.ps1 args=' -Input c:\\tmp\\infile.txt' shell='powershell'

    A string of standard input can be specified for the command to be run using
    the ``stdin`` parameter. This can be useful in cases where sensitive
    information must be read from standard input.

    .. code-block:: bash

        salt '*' cmd.script_retcode salt://scripts/runme.sh stdin='one\\ntwo\\nthree\\nfour\\nfive\\n'
    """
    if "__env__" in kwargs:
        # "env" is not supported; Use "saltenv".
        kwargs.pop("__env__")

    return script(
        source=source,
        args=args,
        cwd=cwd,
        stdin=stdin,
        runas=runas,
        group=group,
        shell=shell,
        python_shell=python_shell,
        env=env,
        template=template,
        umask=umask,
        timeout=timeout,
        reset_system_locale=reset_system_locale,
        saltenv=saltenv,
        output_encoding=output_encoding,
        output_loglevel=output_loglevel,
        log_callback=log_callback,
        use_vt=use_vt,
        password=password,
        success_retcodes=success_retcodes,
        success_stdout=success_stdout,
        success_stderr=success_stderr,
        **kwargs
    )["retcode"]


def _gather_pillar(pillarenv, pillar_override):
    """
    The opts used during pillar rendering should contain the master
    opts in the root namespace. self.opts is the modified minion opts,
    containing the original master opts in __master_opts__.
    """
    popts = {}
    # Pillar compilation needs the master opts primarily,
    # same as during regular operation.
    popts.update(__opts__)
    popts.update(__opts__.get("__master_opts__", {}))
    pillar = salt.pillar.get_pillar(
        popts,
        __grains__.value(),
        __salt__.kwargs["id_"],
        __opts__["saltenv"] or "base",
        pillar_override=pillar_override,
        pillarenv=pillarenv,
    )
    return pillar.compile_pillar()
