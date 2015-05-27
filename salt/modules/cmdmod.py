# -*- coding: utf-8 -*-
'''
A module for shelling out.

Keep in mind that this module is insecure, in that it can give whomever has
access to the master root execution access to all salt minions.
'''
from __future__ import absolute_import

# Import python libs
import time
import functools
import glob
import logging
import os
import shutil
import subprocess
import sys
import traceback
import shlex
from salt.utils import vt

# Import salt libs
import salt.utils
import salt.utils.timed_subprocess
import salt.grains.extra
from salt.ext.six import string_types
from salt.exceptions import CommandExecutionError, TimedProcTimeoutError
from salt.log import LOG_LEVELS
import salt.ext.six as six
from salt.ext.six.moves import range

# Only available on POSIX systems, nonfatal on windows
try:
    import pwd
except ImportError:
    pass

# Define the module's virtual name
__virtualname__ = 'cmd'

# Set up logging
log = logging.getLogger(__name__)

DEFAULT_SHELL = salt.grains.extra.shell()['shell']


def __virtual__():
    '''
    Overwriting the cmd python module makes debugging modules
    with pdb a bit harder so lets do it this way instead.
    '''
    return __virtualname__


def _python_shell_default(python_shell, __pub_jid):
    '''
    Set python_shell default based on remote execution and __opts__['cmd_safe']
    '''
    try:
        # Default to python_shell=True when run directly from remote execution
        # system. Cross-module calls won't have a jid.
        if __pub_jid and python_shell is None:
            return True
        elif __opts__.get('cmd_safe', True) is False and python_shell is None:
            # Override-switch for python_shell
            return True
    except NameError:
        pass
    return python_shell


def _chroot_pids(chroot):
    pids = []
    for root in glob.glob('/proc/[0-9]*/root'):
        try:
            link = os.path.realpath(root)
            if link.startswith(chroot):
                pids.append(int(os.path.basename(
                    os.path.dirname(root)
                )))
        except OSError:
            pass
    return pids


def _render_cmd(cmd, cwd, template, saltenv='base'):
    '''
    If template is a valid template engine, process the cmd and cwd through
    that engine.
    '''
    if not template:
        return (cmd, cwd)

    # render the path as a template using path_template_engine as the engine
    if template not in salt.utils.templates.TEMPLATE_REGISTRY:
        raise CommandExecutionError(
            'Attempted to render file paths with unavailable engine '
            '{0}'.format(template)
        )

    kwargs = {}
    kwargs['salt'] = __salt__
    kwargs['pillar'] = __pillar__
    kwargs['grains'] = __grains__
    kwargs['opts'] = __opts__
    kwargs['saltenv'] = saltenv

    def _render(contents):
        # write out path to temp file
        tmp_path_fn = salt.utils.mkstemp()
        with salt.utils.fopen(tmp_path_fn, 'w+') as fp_:
            fp_.write(contents)
        data = salt.utils.templates.TEMPLATE_REGISTRY[template](
            tmp_path_fn,
            to_str=True,
            **kwargs
        )
        salt.utils.safe_rm(tmp_path_fn)
        if not data['result']:
            # Failed to render the template
            raise CommandExecutionError(
                'Failed to execute cmd with error: {0}'.format(
                    data['data']
                )
            )
        else:
            return data['data']

    cmd = _render(cmd)
    cwd = _render(cwd)
    return (cmd, cwd)


def _check_loglevel(level='info', quiet=False):
    '''
    Retrieve the level code for use in logging.Logger.log().
    '''
    def _bad_level(level):
        log.error(
            'Invalid output_loglevel {0!r}. Valid levels are: {1}. Falling '
            'back to \'info\'.'
            .format(
                level,
                ', '.join(
                    sorted(LOG_LEVELS, key=LOG_LEVELS.get, reverse=True)
                )
            )
        )
        return LOG_LEVELS['info']

    if salt.utils.is_true(quiet) or str(level).lower() == 'quiet':
        return None

    try:
        level = level.lower()
        if level not in LOG_LEVELS:
            return _bad_level(level)
    except AttributeError:
        return _bad_level(level)

    return LOG_LEVELS[level]


def _parse_env(env):
    if not env:
        env = {}
    if isinstance(env, list):
        env = salt.utils.repack_dictlist(env)
    if not isinstance(env, dict):
        env = {}
    return env


def _run(cmd,
         cwd=None,
         stdin=None,
         stdout=subprocess.PIPE,
         stderr=subprocess.PIPE,
         output_loglevel='debug',
         runas=None,
         shell=DEFAULT_SHELL,
         python_shell=False,
         env=None,
         clean_env=False,
         rstrip=True,
         template=None,
         umask=None,
         timeout=None,
         with_communicate=True,
         reset_system_locale=True,
         ignore_retcode=False,
         saltenv='base',
         use_vt=False):
    '''
    Do the DRY thing and only call subprocess.Popen() once
    '''
    if _is_valid_shell(shell) is False:
        log.warning(
            'Attempt to run a shell command with what may be an invalid shell! '
            'Check to ensure that the shell <{0}> is valid for this user.'
            .format(shell))

    # Set the default working directory to the home directory of the user
    # salt-minion is running as. Defaults to home directory of user under which
    # the minion is running.
    if not cwd:
        cwd = os.path.expanduser('~{0}'.format('' if not runas else runas))

        # make sure we can access the cwd
        # when run from sudo or another environment where the euid is
        # changed ~ will expand to the home of the original uid and
        # the euid might not have access to it. See issue #1844
        if not os.access(cwd, os.R_OK):
            cwd = '/'
            if salt.utils.is_windows():
                cwd = os.tempnam()[:3]
    else:
        # Handle edge cases where numeric/other input is entered, and would be
        # yaml-ified into non-string types
        cwd = str(cwd)

    if not salt.utils.is_windows():
        if not os.path.isfile(shell) or not os.access(shell, os.X_OK):
            msg = 'The shell {0} is not available'.format(shell)
            raise CommandExecutionError(msg)
    if salt.utils.is_windows() and use_vt:  # Memozation so not much overhead
        raise CommandExecutionError('VT not available on windows')

    if shell.lower().strip() == 'powershell':
        # If we were called by script(), then fakeout the Windows
        # shell to run a Powershell script.
        # Else just run a Powershell command.
        stack = traceback.extract_stack(limit=2)

        # extract_stack() returns a list of tuples.
        # The last item in the list [-1] is the current method.
        # The third item[2] in each tuple is the name of that method.
        if stack[-2][2] == 'script':
            cmd = 'Powershell -executionpolicy bypass -File ' + cmd
        else:
            cmd = 'Powershell "{0}"'.format(cmd.replace('"', '\\"'))

    # munge the cmd and cwd through the template
    (cmd, cwd) = _render_cmd(cmd, cwd, template, saltenv)

    ret = {}

    env = _parse_env(env)

    for bad_env_key in (x for x, y in six.iteritems(env) if y is None):
        log.error('Environment variable {0!r} passed without a value. '
                  'Setting value to an empty string'.format(bad_env_key))
        env[bad_env_key] = ''

    if runas and salt.utils.is_windows():
        # TODO: Figure out the proper way to do this in windows
        msg = 'Sorry, {0} does not support runas functionality'
        raise CommandExecutionError(msg.format(__grains__['os']))

    if runas:
        # Save the original command before munging it
        try:
            pwd.getpwnam(runas)
        except KeyError:
            raise CommandExecutionError(
                'User {0!r} is not available'.format(runas)
            )
        try:
            # Getting the environment for the runas user
            # There must be a better way to do this.
            py_code = (
                'import os, itertools; '
                'print \"\\0\".join(itertools.chain(*os.environ.items()))'
            )
            if __grains__['os'] in ['MacOS', 'Darwin']:
                env_cmd = ('sudo', '-i', '-u', runas, '--',
                           sys.executable)
            elif __grains__['os'] in ['FreeBSD']:
                env_cmd = ('su', '-', runas, '-c',
                           "{0} -c {1}".format(shell, sys.executable))
            else:
                env_cmd = ('su', '-s', shell, '-', runas, '-c', sys.executable)
            env_encoded = subprocess.Popen(
                env_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE
            ).communicate(py_code)[0]
            import itertools
            env_runas = dict(itertools.izip(*[iter(env_encoded.split(b'\0'))]*2))
            env_runas.update(env)
            env = env_runas
            # Encode unicode kwargs to filesystem encoding to avoid a
            # UnicodeEncodeError when the subprocess is invoked.
            fse = sys.getfilesystemencoding()
            for key, val in six.iteritems(env):
                if isinstance(val, six.text_type):
                    env[key] = val.encode(fse)
        except ValueError:
            raise CommandExecutionError(
                'Environment could not be retrieved for User {0!r}'.format(
                    runas
                )
            )

    if _check_loglevel(output_loglevel) is not None:
        # Always log the shell commands at INFO unless quiet logging is
        # requested. The command output is what will be controlled by the
        # 'loglevel' parameter.
        log.info(
            'Executing command {0!r} {1}in directory {2!r}'.format(
                cmd, 'as user {0!r} '.format(runas) if runas else '', cwd
            )
        )

    if reset_system_locale is True:
        if not salt.utils.is_windows():
            # Default to C!
            # Salt only knows how to parse English words
            # Don't override if the user has passed LC_ALL
            env.setdefault('LC_ALL', 'C')
        else:
            # On Windows set the codepage to US English.
            if python_shell:
                cmd = 'chcp 437 > nul & ' + cmd

    if clean_env:
        run_env = env

    else:
        run_env = os.environ.copy()
        run_env.update(env)

    if python_shell is None:
        python_shell = False

    kwargs = {'cwd': cwd,
              'shell': python_shell,
              'env': run_env,
              'stdin': str(stdin) if stdin is not None else stdin,
              'stdout': stdout,
              'stderr': stderr,
              'with_communicate': with_communicate}

    if umask is not None:
        _umask = str(umask).lstrip('0')

        if _umask == '':
            msg = 'Zero umask is not allowed.'
            raise CommandExecutionError(msg)

        try:
            _umask = int(_umask, 8)
        except ValueError:
            msg = 'Invalid umask: \'{0}\''.format(umask)
            raise CommandExecutionError(msg)
    else:
        _umask = None

    if runas or umask:
        kwargs['preexec_fn'] = functools.partial(
            salt.utils.chugid_and_umask,
            runas,
            _umask)

    if not salt.utils.is_windows():
        # close_fds is not supported on Windows platforms if you redirect
        # stdin/stdout/stderr
        if kwargs['shell'] is True:
            kwargs['executable'] = shell
        kwargs['close_fds'] = True

    if not os.path.isabs(cwd) or not os.path.isdir(cwd):
        raise CommandExecutionError(
            'Specified cwd {0!r} either not absolute or does not exist'
            .format(cwd)
        )

    if python_shell is not True and not isinstance(cmd, list):
        posix = True
        if salt.utils.is_windows():
            posix = False
        cmd = shlex.split(cmd, posix=posix)
    if not use_vt:
        # This is where the magic happens
        try:
            proc = salt.utils.timed_subprocess.TimedProc(cmd, **kwargs)
        except (OSError, IOError) as exc:
            raise CommandExecutionError(
                'Unable to run command {0!r} with the context {1!r}, reason: {2}'
                .format(cmd, kwargs, exc)
            )

        try:
            proc.wait(timeout)
        except TimedProcTimeoutError as exc:
            ret['stdout'] = str(exc)
            ret['stderr'] = ''
            ret['retcode'] = None
            ret['pid'] = proc.process.pid
            # ok return code for timeouts?
            ret['retcode'] = 1
            return ret

        out, err = proc.stdout, proc.stderr

        if rstrip:
            if out is not None:
                out = out.rstrip()
            if err is not None:
                err = err.rstrip()
        ret['pid'] = proc.process.pid
        ret['retcode'] = proc.process.returncode
        ret['stdout'] = out
        ret['stderr'] = err
    else:
        to = ''
        if timeout:
            to = ' (timeout: {0}s)'.format(timeout)
        if _check_loglevel(output_loglevel) is not None:
            log.debug('Running {0} in VT{1}'.format(cmd, to))
        stdout, stderr = '', ''
        now = time.time()
        if timeout:
            will_timeout = now + timeout
        else:
            will_timeout = -1
        try:
            proc = vt.Terminal(cmd,
                               shell=True,
                               log_stdout=True,
                               log_stderr=True,
                               cwd=cwd,
                               preexec_fn=kwargs.get('preexec_fn', None),
                               env=run_env,
                               log_stdin_level=output_loglevel,
                               log_stdout_level=output_loglevel,
                               log_stderr_level=output_loglevel,
                               stream_stdout=True,
                               stream_stderr=True)
            ret['pid'] = proc.pid
            while proc.has_unread_data:
                try:
                    try:
                        time.sleep(0.5)
                        try:
                            cstdout, cstderr = proc.recv()
                        except IOError:
                            cstdout, cstderr = '', ''
                        if cstdout:
                            stdout += cstdout
                        else:
                            cstdout = ''
                        if cstderr:
                            stderr += cstderr
                        else:
                            cstderr = ''
                        if timeout and (time.time() > will_timeout):
                            ret['stderr'] = (
                                'SALT: Timeout after {0}s\n{1}').format(
                                    timeout, stderr)
                            ret['retcode'] = None
                            break
                    except KeyboardInterrupt:
                        ret['stderr'] = 'SALT: User break\n{0}'.format(stderr)
                        ret['retcode'] = 1
                        break
                except vt.TerminalException as exc:
                    log.error(
                        'VT: {0}'.format(exc),
                        exc_info_on_loglevel=logging.DEBUG)
                    ret = {'retcode': 1, 'pid': '2'}
                    break
                # only set stdout on success as we already mangled in other
                # cases
                ret['stdout'] = stdout
                if not proc.isalive():
                    # Process terminated, i.e., not canceled by the user or by
                    # the timeout
                    ret['stderr'] = stderr
                    ret['retcode'] = proc.exitstatus
                ret['pid'] = proc.pid
        finally:
            proc.close(terminate=True, kill=True)
    try:
        if ignore_retcode:
            __context__['retcode'] = 0
        else:
            __context__['retcode'] = ret['retcode']
    except NameError:
        # Ignore the context error during grain generation
        pass
    return ret


def _run_quiet(cmd,
               cwd=None,
               stdin=None,
               runas=None,
               shell=DEFAULT_SHELL,
               python_shell=False,
               env=None,
               template=None,
               umask=None,
               timeout=None,
               reset_system_locale=True,
               saltenv='base'):
    '''
    Helper for running commands quietly for minion startup
    '''
    return _run(cmd,
                runas=runas,
                cwd=cwd,
                stdin=stdin,
                stderr=subprocess.STDOUT,
                output_loglevel='quiet',
                shell=shell,
                python_shell=python_shell,
                env=env,
                template=template,
                umask=umask,
                timeout=timeout,
                reset_system_locale=reset_system_locale,
                saltenv=saltenv)['stdout']


def _run_all_quiet(cmd,
                   cwd=None,
                   stdin=None,
                   runas=None,
                   shell=DEFAULT_SHELL,
                   python_shell=False,
                   env=None,
                   template=None,
                   umask=None,
                   timeout=None,
                   reset_system_locale=True,
                   saltenv='base'):
    '''
    Helper for running commands quietly for minion startup.
    Returns a dict of return data
    '''
    return _run(cmd,
                runas=runas,
                cwd=cwd,
                stdin=stdin,
                shell=shell,
                python_shell=python_shell,
                env=env,
                output_loglevel='quiet',
                template=template,
                umask=umask,
                timeout=timeout,
                reset_system_locale=reset_system_locale,
                saltenv=saltenv)


def run(cmd,
        cwd=None,
        stdin=None,
        runas=None,
        shell=DEFAULT_SHELL,
        python_shell=None,
        env=None,
        clean_env=False,
        template=None,
        rstrip=True,
        umask=None,
        output_loglevel='debug',
        timeout=None,
        reset_system_locale=True,
        ignore_retcode=False,
        saltenv='base',
        use_vt=False,
        **kwargs):
    '''
    Execute the passed command and return the output as a string

    Note that ``env`` represents the environment variables for the command, and
    should be formatted as a dict, or a YAML string which resolves to a dict.

    *************************************************************************
    WARNING: This function does not process commands through a shell
    unless the python_shell flag is set to True. This means that any
    shell-specific functionality such as 'echo' or the use of pipes,
    redirection or &&, should either be migrated to cmd.shell or
    have the python_shell=True flag set here.

    The use of python_shell=True means that the shell will accept _any_ input
    including potentially malicious commands such as 'good_command;rm -rf /'.
    Be absolutely certain that you have sanitized your input prior to using
    python_shell=True
    *************************************************************************

    CLI Example:

    .. code-block:: bash

        salt '*' cmd.run "ls -l | awk '/foo/{print \\$2}'"

    The template arg can be set to 'jinja' or another supported template
    engine to render the command arguments before execution.
    For example:

    .. code-block:: bash

        salt '*' cmd.run template=jinja "ls -l /tmp/{{grains.id}} | awk '/foo/{print \\$2}'"

    Specify an alternate shell with the shell parameter:

    .. code-block:: bash

        salt '*' cmd.run "Get-ChildItem C:\\ " shell='powershell'

    A string of standard input can be specified for the command to be run using
    the ``stdin`` parameter. This can be useful in cases where sensitive
    information must be read from standard input.:

    .. code-block:: bash

        salt '*' cmd.run "grep f" stdin='one\\ntwo\\nthree\\nfour\\nfive\\n'

    If an equal sign (``=``) appears in an argument to a Salt command it is
    interpreted as a keyword argument in the format ``key=val``. That
    processing can be bypassed in order to pass an equal sign through to the
    remote shell command by manually specifying the kwarg:

    .. code-block:: bash

        salt '*' cmd.run cmd='sed -e s/=/:/g'
    '''
    python_shell = _python_shell_default(python_shell,
                                         kwargs.get('__pub_jid', ''))
    ret = _run(cmd,
               runas=runas,
               shell=shell,
               python_shell=python_shell,
               cwd=cwd,
               stdin=stdin,
               stderr=subprocess.STDOUT,
               env=env,
               clean_env=clean_env,
               template=template,
               rstrip=rstrip,
               umask=umask,
               output_loglevel=output_loglevel,
               timeout=timeout,
               reset_system_locale=reset_system_locale,
               ignore_retcode=ignore_retcode,
               saltenv=saltenv,
               use_vt=use_vt)

    if 'pid' in ret and '__pub_jid' in kwargs:
        # Stuff the child pid in the JID file
        try:
            proc_dir = os.path.join(__opts__['cachedir'], 'proc')
            jid_file = os.path.join(proc_dir, kwargs['__pub_jid'])
            if os.path.isfile(jid_file):
                serial = salt.payload.Serial(__opts__)
                with salt.utils.fopen(jid_file, 'rb') as fn_:
                    jid_dict = serial.load(fn_)

                if 'child_pids' in jid_dict:
                    jid_dict['child_pids'].append(ret['pid'])
                else:
                    jid_dict['child_pids'] = [ret['pid']]
                # Rewrite file
                with salt.utils.fopen(jid_file, 'w+b') as fn_:
                    fn_.write(serial.dumps(jid_dict))
        except (NameError, TypeError):
            # Avoids errors from msgpack not being loaded in salt-ssh
            pass

    lvl = _check_loglevel(output_loglevel)
    if lvl is not None:
        if not ignore_retcode and ret['retcode'] != 0:
            if lvl < LOG_LEVELS['error']:
                lvl = LOG_LEVELS['error']
            log.error(
                'Command {0!r} failed with return code: {1}'
                .format(cmd, ret['retcode'])
            )
        log.log(lvl, 'output: {0}'.format(ret['stdout']))
    return ret['stdout']


def shell(cmd,
        cwd=None,
        stdin=None,
        runas=None,
        shell=DEFAULT_SHELL,
        env=None,
        clean_env=False,
        template=None,
        rstrip=True,
        umask=None,
        output_loglevel='debug',
        quiet=False,
        timeout=None,
        reset_system_locale=True,
        ignore_retcode=False,
        saltenv='base',
        use_vt=False,
        **kwargs):
    '''
    Execute the passed command and return the output as a string.

    .. versionadded:: 2015.5.0

    ************************************************************
    WARNING: This passes the cmd argument directly to the shell
    without any further processing! Be absolutely sure that you
    have properly santized the command passed to this function
    and do not use untrusted inputs.
    ************************************************************

    Note that ``env`` represents the environment variables for the command, and
    should be formatted as a dict, or a YAML string which resolves to a dict.

    CLI Example:

    .. code-block:: bash

        salt '*' cmd.shell "ls -l | awk '/foo/{print \\$2}'"

    The template arg can be set to 'jinja' or another supported template
    engine to render the command arguments before execution.
    For example:

    .. code-block:: bash

        salt '*' cmd.shell template=jinja "ls -l /tmp/{{grains.id}} | awk '/foo/{print \\$2}'"

    Specify an alternate shell with the shell parameter:

    .. code-block:: bash

        salt '*' cmd.shell "Get-ChildItem C:\\ " shell='powershell'

    A string of standard input can be specified for the command to be run using
    the ``stdin`` parameter. This can be useful in cases where sensitive
    information must be read from standard input.:

    .. code-block:: bash

        salt '*' cmd.shell "grep f" stdin='one\\ntwo\\nthree\\nfour\\nfive\\n'

    If an equal sign (``=``) appears in an argument to a Salt command it is
    interpreted as a keyword argument in the format ``key=val``. That
    processing can be bypassed in order to pass an equal sign through to the
    remote shell command by manually specifying the kwarg:

    .. code-block:: bash

        salt '*' cmd.shell cmd='sed -e s/=/:/g'
    '''
    if 'python_shell' in kwargs:
        python_shell = kwargs.pop('python_shell')
    else:
        python_shell = True
    return run(cmd,
        cwd=cwd,
        stdin=stdin,
        runas=runas,
        shell=shell,
        env=env,
        clean_env=clean_env,
        template=template,
        rstrip=rstrip,
        umask=umask,
        output_loglevel=output_loglevel,
        quiet=quiet,
        timeout=timeout,
        reset_system_locale=reset_system_locale,
        ignore_retcode=ignore_retcode,
        saltenv=saltenv,
        use_vt=use_vt,
        python_shell=python_shell,
        **kwargs)


def run_stdout(cmd,
               cwd=None,
               stdin=None,
               runas=None,
               shell=DEFAULT_SHELL,
               python_shell=None,
               env=None,
               clean_env=False,
               template=None,
               rstrip=True,
               umask=None,
               output_loglevel='debug',
               timeout=None,
               reset_system_locale=True,
               ignore_retcode=False,
               saltenv='base',
               use_vt=False,
               **kwargs):
    '''
    Execute a command, and only return the standard out

    Note that ``env`` represents the environment variables for the command, and
    should be formatted as a dict, or a YAML string which resolves to a dict.

    CLI Example:

    .. code-block:: bash

        salt '*' cmd.run_stdout "ls -l | awk '/foo/{print \\$2}'"

    The template arg can be set to 'jinja' or another supported template
    engine to render the command arguments before execution.
    For example:

    .. code-block:: bash

        salt '*' cmd.run_stdout template=jinja "ls -l /tmp/{{grains.id}} | awk '/foo/{print \\$2}'"

    A string of standard input can be specified for the command to be run using
    the ``stdin`` parameter. This can be useful in cases where sensitive
    information must be read from standard input.:

    .. code-block:: bash

        salt '*' cmd.run_stdout "grep f" stdin='one\\ntwo\\nthree\\nfour\\nfive\\n'
    '''
    python_shell = _python_shell_default(python_shell,
                                         kwargs.get('__pub_jid', ''))
    ret = _run(cmd,
               runas=runas,
               cwd=cwd,
               stdin=stdin,
               shell=shell,
               python_shell=python_shell,
               env=env,
               clean_env=clean_env,
               template=template,
               rstrip=rstrip,
               umask=umask,
               output_loglevel=output_loglevel,
               timeout=timeout,
               reset_system_locale=reset_system_locale,
               ignore_retcode=ignore_retcode,
               saltenv=saltenv,
               use_vt=use_vt)

    lvl = _check_loglevel(output_loglevel)
    if lvl is not None:
        if not ignore_retcode and ret['retcode'] != 0:
            if lvl < LOG_LEVELS['error']:
                lvl = LOG_LEVELS['error']
            log.error(
                'Command {0!r} failed with return code: {1}'
                .format(cmd, ret['retcode'])
            )
        if ret['stdout']:
            log.log(lvl, 'stdout: {0}'.format(ret['stdout']))
        if ret['stderr']:
            log.log(lvl, 'stderr: {0}'.format(ret['stderr']))
        if ret['retcode']:
            log.log(lvl, 'retcode: {0}'.format(ret['retcode']))
    return ret['stdout']


def run_stderr(cmd,
               cwd=None,
               stdin=None,
               runas=None,
               shell=DEFAULT_SHELL,
               python_shell=None,
               env=None,
               clean_env=False,
               template=None,
               rstrip=True,
               umask=None,
               output_loglevel='debug',
               timeout=None,
               reset_system_locale=True,
               ignore_retcode=False,
               saltenv='base',
               use_vt=False,
               **kwargs):
    '''
    Execute a command and only return the standard error

    Note that ``env`` represents the environment variables for the command, and
    should be formatted as a dict, or a YAML string which resolves to a dict.

    CLI Example:

    .. code-block:: bash

        salt '*' cmd.run_stderr "ls -l | awk '/foo/{print \\$2}'"

    The template arg can be set to 'jinja' or another supported template
    engine to render the command arguments before execution.
    For example:

    .. code-block:: bash

        salt '*' cmd.run_stderr template=jinja "ls -l /tmp/{{grains.id}} | awk '/foo/{print \\$2}'"

    A string of standard input can be specified for the command to be run using
    the ``stdin`` parameter. This can be useful in cases where sensitive
    information must be read from standard input.:

    .. code-block:: bash

        salt '*' cmd.run_stderr "grep f" stdin='one\\ntwo\\nthree\\nfour\\nfive\\n'
    '''
    python_shell = _python_shell_default(python_shell,
                                         kwargs.get('__pub_jid', ''))
    ret = _run(cmd,
               runas=runas,
               cwd=cwd,
               stdin=stdin,
               shell=shell,
               python_shell=python_shell,
               env=env,
               clean_env=clean_env,
               template=template,
               rstrip=rstrip,
               umask=umask,
               output_loglevel=output_loglevel,
               timeout=timeout,
               reset_system_locale=reset_system_locale,
               ignore_retcode=ignore_retcode,
               use_vt=use_vt,
               saltenv=saltenv)

    lvl = _check_loglevel(output_loglevel)
    if lvl is not None:
        if not ignore_retcode and ret['retcode'] != 0:
            if lvl < LOG_LEVELS['error']:
                lvl = LOG_LEVELS['error']
            log.error(
                'Command {0!r} failed with return code: {1}'
                .format(cmd, ret['retcode'])
            )
        if ret['stdout']:
            log.log(lvl, 'stdout: {0}'.format(ret['stdout']))
        if ret['stderr']:
            log.log(lvl, 'stderr: {0}'.format(ret['stderr']))
        if ret['retcode']:
            log.log(lvl, 'retcode: {0}'.format(ret['retcode']))
    return ret['stderr']


def run_all(cmd,
            cwd=None,
            stdin=None,
            runas=None,
            shell=DEFAULT_SHELL,
            python_shell=None,
            env=None,
            clean_env=False,
            template=None,
            rstrip=True,
            umask=None,
            output_loglevel='debug',
            timeout=None,
            reset_system_locale=True,
            ignore_retcode=False,
            saltenv='base',
            use_vt=False,
            **kwargs):
    '''
    Execute the passed command and return a dict of return data

    Note that ``env`` represents the environment variables for the command, and
    should be formatted as a dict, or a YAML string which resolves to a dict.

    CLI Example:

    .. code-block:: bash

        salt '*' cmd.run_all "ls -l | awk '/foo/{print \\$2}'"

    The template arg can be set to 'jinja' or another supported template
    engine to render the command arguments before execution.
    For example:

    .. code-block:: bash

        salt '*' cmd.run_all template=jinja "ls -l /tmp/{{grains.id}} | awk '/foo/{print \\$2}'"

    A string of standard input can be specified for the command to be run using
    the ``stdin`` parameter. This can be useful in cases where sensitive
    information must be read from standard input.:

    .. code-block:: bash

        salt '*' cmd.run_all "grep f" stdin='one\\ntwo\\nthree\\nfour\\nfive\\n'
    '''
    python_shell = _python_shell_default(python_shell,
                                         kwargs.get('__pub_jid', ''))
    ret = _run(cmd,
               runas=runas,
               cwd=cwd,
               stdin=stdin,
               shell=shell,
               python_shell=python_shell,
               env=env,
               clean_env=clean_env,
               template=template,
               rstrip=rstrip,
               umask=umask,
               output_loglevel=output_loglevel,
               timeout=timeout,
               reset_system_locale=reset_system_locale,
               ignore_retcode=ignore_retcode,
               saltenv=saltenv,
               use_vt=use_vt)

    lvl = _check_loglevel(output_loglevel)
    if lvl is not None:
        if not ignore_retcode and ret['retcode'] != 0:
            if lvl < LOG_LEVELS['error']:
                lvl = LOG_LEVELS['error']
            log.error(
                'Command {0!r} failed with return code: {1}'
                .format(cmd, ret['retcode'])
            )
        if ret['stdout']:
            log.log(lvl, 'stdout: {0}'.format(ret['stdout']))
        if ret['stderr']:
            log.log(lvl, 'stderr: {0}'.format(ret['stderr']))
        if ret['retcode']:
            log.log(lvl, 'retcode: {0}'.format(ret['retcode']))
    return ret


def retcode(cmd,
            cwd=None,
            stdin=None,
            runas=None,
            shell=DEFAULT_SHELL,
            python_shell=None,
            env=None,
            clean_env=False,
            template=None,
            umask=None,
            output_loglevel='debug',
            timeout=None,
            reset_system_locale=True,
            ignore_retcode=False,
            saltenv='base',
            use_vt=False,
            **kwargs):
    '''
    Execute a shell command and return the command's return code.

    Note that ``env`` represents the environment variables for the command, and
    should be formatted as a dict, or a YAML string which resolves to a dict.

    :rtype: int
    :rtype: None
    :returns: Return Code as an int or None if there was an exception.

    CLI Example:

    .. code-block:: bash

        salt '*' cmd.retcode "file /bin/bash"

    The template arg can be set to 'jinja' or another supported template
    engine to render the command arguments before execution.
    For example:

    .. code-block:: bash

        salt '*' cmd.retcode template=jinja "file {{grains.pythonpath[0]}}/python"

    A string of standard input can be specified for the command to be run using
    the ``stdin`` parameter. This can be useful in cases where sensitive
    information must be read from standard input.:

    .. code-block:: bash

        salt '*' cmd.retcode "grep f" stdin='one\\ntwo\\nthree\\nfour\\nfive\\n'
    '''
    ret = _run(cmd,
              runas=runas,
              cwd=cwd,
              stdin=stdin,
              stderr=subprocess.STDOUT,
              shell=shell,
              python_shell=python_shell,
              env=env,
              clean_env=clean_env,
              template=template,
              umask=umask,
              output_loglevel=output_loglevel,
              timeout=timeout,
              reset_system_locale=reset_system_locale,
              ignore_retcode=ignore_retcode,
              saltenv=saltenv,
              use_vt=use_vt)

    lvl = _check_loglevel(output_loglevel)
    if lvl is not None:
        if not ignore_retcode and ret['retcode'] != 0:
            if lvl < LOG_LEVELS['error']:
                lvl = LOG_LEVELS['error']
            log.error(
                'Command {0!r} failed with return code: {1}'
                .format(cmd, ret['retcode'])
            )
        log.log(lvl, 'output: {0}'.format(ret['stdout']))
    return ret['retcode']


def _retcode_quiet(cmd,
                   cwd=None,
                   stdin=None,
                   runas=None,
                   shell=DEFAULT_SHELL,
                   python_shell=False,
                   env=None,
                   clean_env=False,
                   template=None,
                   umask=None,
                   output_loglevel='quiet',
                   timeout=None,
                   reset_system_locale=True,
                   ignore_retcode=False,
                   saltenv='base',
                   use_vt=False,
                   **kwargs):
    '''
    Helper for running commands quietly for minion startup.
    Returns same as retcode
    '''
    return retcode(cmd,
                   cwd=cwd,
                   stdin=stdin,
                   runas=runas,
                   shell=shell,
                   python_shell=python_shell,
                   env=env,
                   clean_env=clean_env,
                   template=template,
                   umask=umask,
                   output_loglevel=output_loglevel,
                   timeout=timeout,
                   reset_system_locale=reset_system_locale,
                   ignore_retcode=ignore_retcode,
                   saltenv=saltenv,
                   use_vt=use_vt,
                   **kwargs)


def script(source,
           args=None,
           cwd=None,
           stdin=None,
           runas=None,
           shell=DEFAULT_SHELL,
           python_shell=None,
           env=None,
           template=None,
           umask=None,
           output_loglevel='debug',
           quiet=False,
           timeout=None,
           reset_system_locale=True,
           __env__=None,
           saltenv='base',
           use_vt=False,
           **kwargs):
    '''
    Download a script from a remote location and execute the script locally.
    The script can be located on the salt master file server or on an HTTP/FTP
    server.

    The script will be executed directly, so it can be written in any available
    programming language.

    The script can also be formatted as a template, the default is jinja.
    Arguments for the script can be specified as well.

    CLI Example:

    .. code-block:: bash

        salt '*' cmd.script salt://scripts/runme.sh
        salt '*' cmd.script salt://scripts/runme.sh 'arg1 arg2 "arg 3"'
        salt '*' cmd.script salt://scripts/windows_task.ps1 args=' -Input c:\\tmp\\infile.txt' shell='powershell'

    A string of standard input can be specified for the command to be run using
    the ``stdin`` parameter. This can be useful in cases where sensitive
    information must be read from standard input.:

    .. code-block:: bash

        salt '*' cmd.script salt://scripts/runme.sh stdin='one\\ntwo\\nthree\\nfour\\nfive\\n'
    '''
    python_shell = _python_shell_default(python_shell,
                                         kwargs.get('__pub_jid', ''))

    def _cleanup_tempfile(path):
        try:
            os.remove(path)
        except (IOError, OSError) as exc:
            log.error('cmd.script: Unable to clean tempfile {0!r}: {1}'
                      .format(path, exc))

    if isinstance(__env__, string_types):
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' not '
            '\'__env__\'. This functionality will be removed in Salt Boron.'
        )
        # Backwards compatibility
        saltenv = __env__

    path = salt.utils.mkstemp(dir=cwd, suffix=os.path.splitext(source)[1])

    if template:
        fn_ = __salt__['cp.get_template'](source,
                                          path,
                                          template,
                                          saltenv,
                                          **kwargs)
        if not fn_:
            _cleanup_tempfile(path)
            return {'pid': 0,
                    'retcode': 1,
                    'stdout': '',
                    'stderr': '',
                    'cache_error': True}
    else:
        fn_ = __salt__['cp.cache_file'](source, saltenv)
        if not fn_:
            _cleanup_tempfile(path)
            return {'pid': 0,
                    'retcode': 1,
                    'stdout': '',
                    'stderr': '',
                    'cache_error': True}
        shutil.copyfile(fn_, path)
    if not salt.utils.is_windows():
        os.chmod(path, 320)
        os.chown(path, __salt__['file.user_to_uid'](runas), -1)
    ret = _run(path + ' ' + str(args) if args else path,
               cwd=cwd,
               stdin=stdin,
               output_loglevel=output_loglevel,
               runas=runas,
               shell=shell,
               python_shell=python_shell,
               env=env,
               umask=umask,
               timeout=timeout,
               reset_system_locale=reset_system_locale,
               saltenv=saltenv,
               use_vt=use_vt)
    _cleanup_tempfile(path)
    return ret


def script_retcode(source,
                   args=None,
                   cwd=None,
                   stdin=None,
                   runas=None,
                   shell=DEFAULT_SHELL,
                   python_shell=None,
                   env=None,
                   template='jinja',
                   umask=None,
                   timeout=None,
                   reset_system_locale=True,
                   __env__=None,
                   saltenv='base',
                   output_loglevel='debug',
                   use_vt=False,
                   **kwargs):
    '''
    Download a script from a remote location and execute the script locally.
    The script can be located on the salt master file server or on an HTTP/FTP
    server.

    The script will be executed directly, so it can be written in any available
    programming language.

    The script can also be formatted as a template, the default is jinja.

    Only evaluate the script return code and do not block for terminal output

    CLI Example:

    .. code-block:: bash

        salt '*' cmd.script_retcode salt://scripts/runme.sh
        salt '*' cmd.script_retcode salt://scripts/runme.sh 'arg1 arg2 "arg 3"'
        salt '*' cmd.script_retcode salt://scripts/windows_task.ps1 args=' -Input c:\\tmp\\infile.txt' shell='powershell'

    A string of standard input can be specified for the command to be run using
    the ``stdin`` parameter. This can be useful in cases where sensitive
    information must be read from standard input.:

    .. code-block:: bash

        salt '*' cmd.script_retcode salt://scripts/runme.sh stdin='one\\ntwo\\nthree\\nfour\\nfive\\n'
    '''
    python_shell = _python_shell_default(python_shell,
                                         kwargs.get('__pub_jid', ''))
    if isinstance(__env__, string_types):
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' not '
            '\'env\'. This functionality will be removed in Salt Boron.'
        )
        # Backwards compatibility
        saltenv = __env__

    return script(source=source,
                  args=args,
                  cwd=cwd,
                  stdin=stdin,
                  runas=runas,
                  shell=shell,
                  python_shell=python_shell,
                  env=env,
                  template=template,
                  umask=umask,
                  timeout=timeout,
                  reset_system_locale=reset_system_locale,
                  saltenv=saltenv,
                  output_loglevel=output_loglevel,
                  use_vt=use_vt,
                  **kwargs)['retcode']


def which(cmd):
    '''
    Returns the path of an executable available on the minion, None otherwise

    CLI Example:

    .. code-block:: bash

        salt '*' cmd.which cat
    '''
    return salt.utils.which(cmd)


def which_bin(cmds):
    '''
    Returns the first command found in a list of commands

    CLI Example:

    .. code-block:: bash

        salt '*' cmd.which_bin '[pip2, pip, pip-python]'
    '''
    return salt.utils.which_bin(cmds)


def has_exec(cmd):
    '''
    Returns true if the executable is available on the minion, false otherwise

    CLI Example:

    .. code-block:: bash

        salt '*' cmd.has_exec cat
    '''
    return which(cmd) is not None


def exec_code(lang, code, cwd=None):
    '''
    Pass in two strings, the first naming the executable language, aka -
    python2, python3, ruby, perl, lua, etc. the second string containing
    the code you wish to execute. The stdout will be returned.

    CLI Example:

    .. code-block:: bash

        salt '*' cmd.exec_code ruby 'puts "cheese"'
    '''
    return exec_code_all(lang, code, cwd)['stdout']


def exec_code_all(lang, code, cwd=None):
    '''
    Pass in two strings, the first naming the executable language, aka -
    python2, python3, ruby, perl, lua, etc. the second string containing
    the code you wish to execute. All cmd artifacts (stdout, stderr, retcode, pid)
    will be returned.

    CLI Example:

    .. code-block:: bash

        salt '*' cmd.exec_code_all ruby 'puts "cheese"'
    '''
    codefile = salt.utils.mkstemp()
    with salt.utils.fopen(codefile, 'w+t') as fp_:
        fp_.write(code)
    cmd = [lang, codefile]
    ret = run_all(cmd, cwd=cwd, python_shell=False)
    os.remove(codefile)
    return ret


def tty(device, echo=None):
    '''
    Echo a string to a specific tty

    CLI Example:

    .. code-block:: bash

        salt '*' cmd.tty tty0 'This is a test'
        salt '*' cmd.tty pts3 'This is a test'
    '''
    if device.startswith('tty'):
        teletype = '/dev/{0}'.format(device)
    elif device.startswith('pts'):
        teletype = '/dev/{0}'.format(device.replace('pts', 'pts/'))
    else:
        return {'Error': 'The specified device is not a valid TTY'}
    try:
        with salt.utils.fopen(teletype, 'wb') as tty_device:
            tty_device.write(echo)
        return {
            'Success': 'Message was successfully echoed to {0}'.format(teletype)
        }
    except IOError:
        return {
            'Error': 'Echoing to {0} returned error'.format(teletype)
        }


def run_chroot(root,
               cmd,
               cwd=None,
               stdin=None,
               runas=None,
               shell=DEFAULT_SHELL,
               python_shell=True,
               env=None,
               clean_env=False,
               template=None,
               rstrip=True,
               umask=None,
               output_loglevel='quiet',
               quiet=False,
               timeout=None,
               reset_system_locale=True,
               ignore_retcode=False,
               saltenv='base',
               use_vt=False,
               **kwargs):
    '''
    .. versionadded:: 2014.7.0

    This function runs :mod:`cmd.run_all <salt.modules.cmdmod.run_all>` wrapped
    within a chroot, with dev and proc mounted in the chroot

    stdin : None
        Standard input to be used for the command

        .. versionadded:: 2014.7.1

    output_loglevel : debug
        Level at which to log the output from the command. Set to ``quiet`` to
        suppress logging.

        .. versionadded:: 2014.7.1

    CLI Example:

    .. code-block:: bash

        salt '*' cmd.run_chroot /var/lib/lxc/container_name/rootfs 'sh /tmp/bootstrap.sh'
    '''
    __salt__['mount.mount'](
        os.path.join(root, 'dev'),
        'udev',
        fstype='devtmpfs')
    __salt__['mount.mount'](
        os.path.join(root, 'proc'),
        'proc',
        fstype='proc')

    # Execute chroot routine
    sh_ = '/bin/sh'
    if os.path.isfile(os.path.join(root, 'bin/bash')):
        sh_ = '/bin/bash'

    if isinstance(cmd, (list, tuple)):
        cmd = ' '.join([str(i) for i in cmd])
    cmd = 'chroot {0} {1} -c {2!r}'.format(root, sh_, cmd)

    run_func = __context__.pop('cmd.run_chroot.func', run_all)

    ret = run_func(cmd,
                   runas=runas,
                   cwd=cwd,
                   stdin=stdin,
                   shell=shell,
                   python_shell=python_shell,
                   env=env,
                   clean_env=clean_env,
                   template=template,
                   rstrip=rstrip,
                   umask=umask,
                   output_loglevel=output_loglevel,
                   quiet=quiet,
                   timeout=timeout,
                   reset_system_locale=reset_system_locale,
                   ignore_retcode=ignore_retcode,
                   saltenv=saltenv,
                   use_vt=use_vt)

    # Kill processes running in the chroot
    for i in range(6):
        pids = _chroot_pids(root)
        if not pids:
            break
        for pid in pids:
            # use sig 15 (TERM) for first 3 attempts, then 9 (KILL)
            sig = 15 if i < 3 else 9
            os.kill(pid, sig)

    if _chroot_pids(root):
        log.error('Processes running in chroot could not be killed, '
                  'filesystem will remain mounted')

    __salt__['mount.umount'](os.path.join(root, 'proc'))
    __salt__['mount.umount'](os.path.join(root, 'dev'))
    return ret


def _is_valid_shell(shell):
    '''
    Attempts to search for valid shells on a system and
    see if a given shell is in the list
    '''
    if salt.utils.is_windows():
        return True  # Don't even try this for Windows
    shells = '/etc/shells'
    available_shells = []
    if os.path.exists(shells):
        try:
            with salt.utils.fopen(shells, 'r') as shell_fp:
                lines = shell_fp.read().splitlines()
            for line in lines:
                if line.startswith('#'):
                    continue
                else:
                    available_shells.append(line)
        except OSError:
            return True
    else:
        # No known method of determining available shells
        return None
    if shell in available_shells:
        return True
    else:
        return False


def shells():
    '''
    Lists the valid shells on this system via the /etc/shells file

    .. versionadded:: 2015.5.0

    CLI Example::

        salt '*' cmd.shells
    '''
    shells_fn = '/etc/shells'
    ret = []
    if os.path.exists(shells_fn):
        try:
            with salt.utils.fopen(shells_fn, 'r') as shell_fp:
                lines = shell_fp.read().splitlines()
            for line in lines:
                line = line.strip()
                if line.startswith('#'):
                    continue
                elif not line:
                    continue
                else:
                    ret.append(line)
        except OSError:
            log.error("File '{0}' was not found".format(shells_fn))
    return ret
