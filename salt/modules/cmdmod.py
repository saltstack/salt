# -*- coding: utf-8 -*-
'''
A module for shelling out

Keep in mind that this module is insecure, in that it can give whomever has
access to the master root execution access to all salt minions
'''

# Import python libs
import functools
import json
import logging
import os
import shutil
import subprocess
import sys
import traceback

# Import salt libs
import salt.utils
import salt.utils.timed_subprocess
import salt.grains.extra
from salt._compat import string_types
from salt.exceptions import CommandExecutionError, TimedProcTimeoutError
from salt.log import LOG_LEVELS

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


def _chugid(runas):
    uinfo = pwd.getpwnam(runas)
    supgroups_seen = set()

    # The line below used to exclude the current user's primary gid.
    # However, when root belongs to more than one group
    # this causes root's primary group of '0' to be dropped from
    # his grouplist.  On FreeBSD, at least, this makes some
    # command executions fail with 'access denied'.
    #
    # The Python documentation says that os.setgroups sets only
    # the supplemental groups for a running process.  On FreeBSD
    # this does not appear to be strictly true.

    # supgroups = [
    #     g.gr_gid for g in grp.getgrall()
    #     if uinfo.pw_name in g.gr_mem and g.gr_gid != uinfo.pw_gid
    #        and g.gr_gid not in supgroups_seen and not supgroups_seen.add(g.gr_gid)
    # ]

    group_list = __salt__['user.list_groups'](runas)
    supgroups = []
    for group_name in group_list:
        gid = __salt__['group.info'](group_name)['gid']
        if (gid not in supgroups_seen
           and not supgroups_seen.add(gid)):
            supgroups.append(gid)

    # No logging can happen on this function
    #
    # 08:46:32,161 [salt.loaded.int.module.cmdmod:276 ][DEBUG   ] stderr: Traceback (most recent call last):
    #   File "/usr/lib/python2.7/logging/__init__.py", line 870, in emit
    #     self.flush()
    #   File "/usr/lib/python2.7/logging/__init__.py", line 832, in flush
    #     self.stream.flush()
    # IOError: [Errno 9] Bad file descriptor
    # Logged from file cmdmod.py, line 59
    # 08:46:17,481 [salt.loaded.int.module.cmdmod:59  ][DEBUG   ] Switching user 0 -> 1008 and group 0 -> 1012 if needed
    #
    # apparently because we closed fd's on Popen, though if not closed, output
    # would also go to its stderr

    if os.getgid() != uinfo.pw_gid:
        try:
            os.setgid(uinfo.pw_gid)
        except OSError as err:
            raise CommandExecutionError(
                'Failed to change from gid {0} to {1}. Error: {2}'.format(
                    os.getgid(), uinfo.pw_gid, err
                )
            )

    # Set supplemental groups
    if sorted(os.getgroups()) != sorted(supgroups):
        try:
            os.setgroups(supgroups)
        except OSError as err:
            raise CommandExecutionError(
                'Failed to set supplemental groups to {0}. Error: {1}'.format(
                    supgroups, err
                )
            )

    if os.getuid() != uinfo.pw_uid:
        try:
            os.setuid(uinfo.pw_uid)
        except OSError as err:
            raise CommandExecutionError(
                'Failed to change from uid {0} to {1}. Error: {2}'.format(
                    os.getuid(), uinfo.pw_uid, err
                )
            )


def _chugid_and_umask(runas, umask):
    '''
    Helper method for for subprocess.Popen to initialise uid/gid and umask
    for the new process.
    '''
    if runas is not None:
        _chugid(runas)
    if umask is not None:
        os.umask(umask)


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
                'Failed to cmd with error: {0}'.format(
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

    try:
        level = level.lower()
        if level not in LOG_LEVELS:
            return _bad_level(level)
    except AttributeError:
        return _bad_level(level)

    if salt.utils.is_true(quiet) or level == 'quiet':
        return None
    return LOG_LEVELS[level]


def _run(cmd,
         cwd=None,
         stdin=None,
         stdout=subprocess.PIPE,
         stderr=subprocess.PIPE,
         output_loglevel='info',
         quiet=False,
         runas=None,
         shell=DEFAULT_SHELL,
         python_shell=True,
         env=None,
         clean_env=False,
         rstrip=True,
         template=None,
         umask=None,
         timeout=None,
         with_communicate=True,
         reset_system_locale=True,
         saltenv='base'):
    '''
    Do the DRY thing and only call subprocess.Popen() once
    '''
    if salt.utils.is_true(quiet):
        salt.utils.warn_until(
            'Lithium',
            'The \'quiet\' option is deprecated and will be removed in the '
            '\'Lithium\' Salt release. Please use output_loglevel=quiet '
            'instead.'
        )

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

    if not env:
        env = {}
    if isinstance(env, list):
        env = salt.utils.repack_dictlist(env)

    for bad_env_key in (x for x, y in env.iteritems() if y is None):
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
            py_code = 'import os, json;' \
                      'print(json.dumps(os.environ.__dict__))'
            if __grains__['os'] in ['MacOS', 'Darwin']:
                env_cmd = ('sudo -i -u {1} -- "{2}"'
                           ).format(shell, runas, sys.executable)
            elif __grains__['os'] in ['FreeBSD']:
                env_cmd = ('su - {1} -c "{0} -c \'{2}\'"'
                           ).format(shell, runas, sys.executable)
            else:
                env_cmd = ('su -s {0} - {1} -c "{2}"'
                           ).format(shell, runas, sys.executable)
            env_json = subprocess.Popen(
                env_cmd,
                shell=python_shell,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE
            ).communicate(py_code)[0]
            env_json = (filter(lambda x: x.startswith('{') and x.endswith('}'),
                               env_json.splitlines()) or ['{}']).pop()
            env_runas = json.loads(env_json).get('data', {})
            env_runas.update(env)
            env = env_runas
        except ValueError:
            raise CommandExecutionError(
                'Environment could not be retrieved for User {0!r}'.format(
                    runas
                )
            )

    if _check_loglevel(output_loglevel, quiet) is not None:
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
            cmd = 'chcp 437 > nul & ' + cmd

    if clean_env:
        run_env = env

    else:
        run_env = os.environ.copy()
        run_env.update(env)

    kwargs = {'cwd': cwd,
              'shell': python_shell,
              'env': run_env,
              'stdin': str(stdin) if stdin is not None else stdin,
              'stdout': stdout,
              'stderr': stderr,
              'with_communicate': with_communicate}

    if umask:
        try:
            _umask = int(str(umask).lstrip('0'), 8)
            if not _umask:
                raise ValueError('Zero umask not allowed.')
        except ValueError:
            msg = 'Invalid umask: \'{0}\''.format(umask)
            raise CommandExecutionError(msg)
    else:
        _umask = None

    if runas or umask:
        kwargs['preexec_fn'] = functools.partial(
                _chugid_and_umask,
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

    ret['stdout'] = out
    ret['stderr'] = err
    ret['pid'] = proc.process.pid
    ret['retcode'] = proc.process.returncode
    try:
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
               python_shell=True,
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
                   python_shell=True,
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
        python_shell=True,
        env=None,
        clean_env=False,
        template=None,
        rstrip=True,
        umask=None,
        output_loglevel='info',
        quiet=False,
        timeout=None,
        reset_system_locale=True,
        ignore_retcode=False,
        saltenv='base',
        **kwargs):
    '''
    Execute the passed command and return the output as a string

    Note that ``env`` represents the environment variables for the command, and
    should be formatted as a dict, or a YAML string which resolves to a dict.

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
    '''
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
               quiet=quiet,
               timeout=timeout,
               reset_system_locale=reset_system_locale,
               saltenv=saltenv)

    if 'pid' in ret and '__pub_jid' in kwargs:
        # Stuff the child pid in the JID file
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

    lvl = _check_loglevel(output_loglevel, quiet)
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


def run_stdout(cmd,
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
               output_loglevel='info',
               quiet=False,
               timeout=None,
               reset_system_locale=True,
               ignore_retcode=False,
               saltenv='base',
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
               quiet=quiet,
               timeout=timeout,
               reset_system_locale=reset_system_locale,
               saltenv=saltenv)

    lvl = _check_loglevel(output_loglevel, quiet)
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
               python_shell=True,
               env=None,
               clean_env=False,
               template=None,
               rstrip=True,
               umask=None,
               output_loglevel='info',
               quiet=False,
               timeout=None,
               reset_system_locale=True,
               ignore_retcode=False,
               saltenv='base',
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
               quiet=quiet,
               timeout=timeout,
               reset_system_locale=reset_system_locale,
               saltenv=saltenv)

    lvl = _check_loglevel(output_loglevel, quiet)
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
            python_shell=True,
            env=None,
            clean_env=False,
            template=None,
            rstrip=True,
            umask=None,
            output_loglevel='info',
            quiet=False,
            timeout=None,
            reset_system_locale=True,
            ignore_retcode=False,
            saltenv='base',
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
               quiet=quiet,
               timeout=timeout,
               reset_system_locale=reset_system_locale,
               saltenv=saltenv)

    lvl = _check_loglevel(output_loglevel, quiet)
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
            python_shell=True,
            env=None,
            clean_env=False,
            template=None,
            umask=None,
            output_loglevel='info',
            quiet=False,
            timeout=None,
            reset_system_locale=True,
            ignore_retcode=False,
            saltenv='base',
            **kwargs):
    '''
    Execute a shell command and return the command's return code.

    Note that ``env`` represents the environment variables for the command, and
    should be formatted as a dict, or a YAML string which resolves to a dict.

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
              quiet=quiet,
              timeout=timeout,
              reset_system_locale=reset_system_locale,
              saltenv=saltenv)

    lvl = _check_loglevel(output_loglevel, quiet)
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
                   python_shell=True,
                   env=None,
                   clean_env=False,
                   template=None,
                   umask=None,
                   output_loglevel='quiet',
                   quiet=True,
                   timeout=None,
                   reset_system_locale=True,
                   ignore_retcode=False,
                   saltenv='base',
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
                   **kwargs)


def script(source,
           args=None,
           cwd=None,
           stdin=None,
           runas=None,
           shell=DEFAULT_SHELL,
           python_shell=True,
           env=None,
           template='jinja',
           umask=None,
           output_loglevel='info',
           quiet=False,
           timeout=None,
           reset_system_locale=True,
           __env__=None,
           saltenv='base',
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
               quiet=quiet,
               runas=runas,
               shell=shell,
               python_shell=python_shell,
               env=env,
               umask=umask,
               timeout=timeout,
               reset_system_locale=reset_system_locale,
               saltenv=saltenv)
    _cleanup_tempfile(path)
    return ret


def script_retcode(source,
                   cwd=None,
                   stdin=None,
                   runas=None,
                   shell=DEFAULT_SHELL,
                   python_shell=True,
                   env=None,
                   template='jinja',
                   umask=None,
                   timeout=None,
                   reset_system_locale=True,
                   __env__=None,
                   saltenv='base',
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

    A string of standard input can be specified for the command to be run using
    the ``stdin`` parameter. This can be useful in cases where sensitive
    information must be read from standard input.:

    .. code-block:: bash

        salt '*' cmd.script_retcode salt://scripts/runme.sh stdin='one\\ntwo\\nthree\\nfour\\nfive\\n'
    '''
    if isinstance(__env__, string_types):
        salt.utils.warn_until(
            'Boron',
            'Passing a salt environment should be done using \'saltenv\' not '
            '\'env\'. This functionality will be removed in Salt Boron.'
        )
        # Backwards compatibility
        saltenv = __env__

    return script(source=source,
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
    the code you wish to execute. The stdout and stderr will be returned

    CLI Example:

    .. code-block:: bash

        salt '*' cmd.exec_code ruby 'puts "cheese"'
    '''
    codefile = salt.utils.mkstemp()
    with salt.utils.fopen(codefile, 'w+') as fp_:
        fp_.write(code)

    cmd = '{0} {1}'.format(lang, codefile)
    ret = run(cmd, cwd=cwd)
    os.remove(codefile)
    return ret
