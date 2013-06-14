'''
A module for shelling out

Keep in mind that this module is insecure, in that it can give whomever has
access to the master root execution access to all salt minions
'''

# Import python libs
import logging
import os
import shutil
import subprocess
import functools
import sys
import json
import yaml

# Import salt libs
import salt.utils
import salt.utils.timed_subprocess
from salt.exceptions import CommandExecutionError
import salt.exceptions
import salt.grains.extra

# Only available on POSIX systems, nonfatal on windows
try:
    import pwd
    import grp
except ImportError:
    pass


# Set up logging
log = logging.getLogger(__name__)


DEFAULT_SHELL = salt.grains.extra.shell()['shell']


def __virtual__():
    '''
    Overwriting the cmd python module makes debugging modules
    with pdb a bit harder so lets do it this way instead.
    '''
    return 'cmd'


def _chugid(runas):
    uinfo = pwd.getpwnam(runas)
    supgroups = [g.gr_gid for g in grp.getgrall()
                 if uinfo.pw_name in g.gr_mem and g.gr_gid != uinfo.pw_gid]

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


def _render_cmd(cmd, cwd, template):
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
    kwargs['env'] = 'base'

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


def _run(cmd,
         cwd=None,
         stdout=subprocess.PIPE,
         stderr=subprocess.PIPE,
         quiet=False,
         runas=None,
         shell=DEFAULT_SHELL,
         env=(),
         rstrip=True,
         template=None,
         umask=None,
         timeout=None):
    '''
    Do the DRY thing and only call subprocess.Popen() once
    '''
    # Set the default working directory to the home directory
    # of the user salt-minion is running as.  Default:  /root
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

    if not salt.utils.is_windows():
        if not os.path.isfile(shell) or not os.access(shell, os.X_OK):
            msg = 'The shell {0} is not available'.format(shell)
            raise CommandExecutionError(msg)

    # munge the cmd and cwd through the template
    (cmd, cwd) = _render_cmd(cmd, cwd, template)

    ret = {}

    if not env:
        env = {}
    elif isinstance(env, basestring):
        try:
            env = yaml.safe_load(env)
        except yaml.parser.ParserError as err:
            log.error(err)
            env = {}
    if not isinstance(env, dict):
        log.error('Invalid input: {0}, must be a dict or '
                  'string - yaml represented dict'.format(env))
        env = {}

    if runas and salt.utils.is_windows():
        # TODO: Figure out the proper way to do this in windows
        msg = 'Sorry, {0} does not support runas functionality'
        raise CommandExecutionError(msg.format(__grains__['os']))

    if runas:
        # Save the original command before munging it
        try:
            pwd.getpwnam(runas)
        except KeyError:
            msg = 'User \'{0}\' is not available'.format(runas)
            raise CommandExecutionError(msg)
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
                shell=True,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE
            ).communicate(py_code)[0]
            env_json = (filter(lambda x: x.startswith('{') and x.endswith('}'),
                               env_json.splitlines()) or ['{}']).pop()
            env_runas = json.loads(env_json).get('data', {})
            env_runas.update(env)
            env = env_runas
        except ValueError:
            msg = 'Environment could not be retrieved for User \'{0}\''.format(runas)
            raise CommandExecutionError(msg)

    if not quiet:
        # Put the most common case first
        log.info(
            'Executing command {0!r} {1}in directory {2!r}'.format(
                cmd, 'as user {0!r} '.format(runas) if runas else '', cwd
            )
        )

    if not salt.utils.is_windows():
        # Default to C!
        # Salt only knows how to parse English words
        # Don't override if the user has passed LC_ALL
        env.setdefault('LC_ALL', 'C')
    else:
        # On Windows set the codepage to US English.
        cmd = 'chcp 437 > nul & ' + cmd

    run_env = os.environ.copy()
    run_env.update(env)
    kwargs = {'cwd': cwd,
              'shell': True,
              'env': run_env,
              'stdout': stdout,
              'stderr': stderr}

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
        kwargs['executable'] = shell
        kwargs['close_fds'] = True

    # This is where the magic happens
    proc = salt.utils.timed_subprocess.TimedProc(cmd, **kwargs)
    try:
        proc.wait(timeout)
    except salt.exceptions.TimedProcTimeoutError, e:
        ret['stdout'] = e.message
        ret['stderr'] = ''
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
    return ret


def _run_quiet(cmd,
               cwd=None,
               runas=None,
               shell=DEFAULT_SHELL,
               env=(),
               template=None,
               umask=None,
               timeout=None):
    '''
    Helper for running commands quietly for minion startup
    '''
    return _run(cmd,
                runas=runas,
                cwd=cwd,
                stderr=subprocess.STDOUT,
                quiet=True,
                shell=shell,
                env=env,
                template=template,
                umask=umask,
                timeout=timeout)['stdout']


def _run_all_quiet(cmd,
                   cwd=None,
                   runas=None,
                   shell=DEFAULT_SHELL,
                   env=(),
                   template=None,
                   umask=None,
                   timeout=None):
    '''
    Helper for running commands quietly for minion startup.
    Returns a dict of return data
    '''
    return _run(cmd,
                runas=runas,
                cwd=cwd,
                shell=shell,
                env=env,
                quiet=True,
                template=template,
                umask=umask,
                timeout=timeout)


def run(cmd,
        cwd=None,
        runas=None,
        shell=DEFAULT_SHELL,
        env=(),
        template=None,
        rstrip=True,
        umask=None,
        quiet=False,
        timeout=None,
        **kwargs):
    '''
    Execute the passed command and return the output as a string

    CLI Example::

        salt '*' cmd.run "ls -l | awk '/foo/{print \$2}'"

    The template arg can be set to 'jinja' or another supported template
    engine to render the command arguments before execution.
    For example::

        salt '*' cmd.run template=jinja "ls -l /tmp/{{grains.id}} | awk '/foo/{print \$2}'"

    '''
    out = _run(cmd,
               runas=runas,
               shell=shell,
               cwd=cwd,
               stderr=subprocess.STDOUT,
               env=env,
               template=template,
               rstrip=rstrip,
               umask=umask,
               quiet=quiet,
               timeout=timeout)['stdout']
    if not quiet:
        log.debug('output: {0}'.format(out))
    return out


def run_stdout(cmd,
               cwd=None,
               runas=None,
               shell=DEFAULT_SHELL,
               env=(),
               template=None,
               rstrip=True,
               umask=None,
               quiet=False,
               timeout=None,
               **kwargs):
    '''
    Execute a command, and only return the standard out

    CLI Example::

        salt '*' cmd.run_stdout "ls -l | awk '/foo/{print \$2}'"

    The template arg can be set to 'jinja' or another supported template
    engine to render the command arguments before execution.
    For example::

        salt '*' cmd.run_stdout template=jinja "ls -l /tmp/{{grains.id}} | awk '/foo/{print \$2}'"

    '''
    stdout = _run(cmd,
                  runas=runas,
                  cwd=cwd,
                  shell=shell,
                  env=env,
                  template=template,
                  rstrip=rstrip,
                  umask=umask,
                  quiet=quiet,
                  timeout=timeout)["stdout"]
    if not quiet:
        log.debug('stdout: {0}'.format(stdout))
    return stdout


def run_stderr(cmd,
               cwd=None,
               runas=None,
               shell=DEFAULT_SHELL,
               env=(),
               template=None,
               rstrip=True,
               umask=None,
               quiet=False,
               timeout=None,
               **kwargs):
    '''
    Execute a command and only return the standard error

    CLI Example::

        salt '*' cmd.run_stderr "ls -l | awk '/foo/{print \$2}'"

    The template arg can be set to 'jinja' or another supported template
    engine to render the command arguments before execution.
    For example::

        salt '*' cmd.run_stderr template=jinja "ls -l /tmp/{{grains.id}} | awk '/foo/{print \$2}'"

    '''
    stderr = _run(cmd,
                  runas=runas,
                  cwd=cwd,
                  shell=shell,
                  env=env,
                  template=template,
                  rstrip=rstrip,
                  umask=umask,
                  quiet=quiet,
                  timeout=timeout)["stderr"]
    if not quiet:
        log.debug('stderr: {0}'.format(stderr))
    return stderr


def run_all(cmd,
            cwd=None,
            runas=None,
            shell=DEFAULT_SHELL,
            env=(),
            template=None,
            rstrip=True,
            umask=None,
            quiet=False,
            timeout=None,
            **kwargs):
    '''
    Execute the passed command and return a dict of return data

    CLI Example::

        salt '*' cmd.run_all "ls -l | awk '/foo/{print \$2}'"

    The template arg can be set to 'jinja' or another supported template
    engine to render the command arguments before execution.
    For example::

        salt '*' cmd.run_all template=jinja "ls -l /tmp/{{grains.id}} | awk '/foo/{print \$2}'"

    '''
    ret = _run(cmd,
               runas=runas,
               cwd=cwd,
               shell=shell,
               env=env,
               template=template,
               rstrip=rstrip,
               umask=umask,
               quiet=quiet,
               timeout=timeout)

    if not quiet:
        if ret['retcode'] != 0:
            rcode = ret['retcode']
            msg = 'Command \'{0}\' failed with return code: {1}'
            log.error(msg.format(cmd, rcode))
            # Don't log a blank line if there is no stderr or stdout
            if ret['stdout']:
                log.error('stdout: {0}'.format(ret['stdout']))
            if ret['stderr']:
                log.error('stderr: {0}'.format(ret['stderr']))
        else:
            # No need to always log output on success to the logs
            if ret['stdout']:
                log.debug('stdout: {0}'.format(ret['stdout']))
            if ret['stderr']:
                log.debug('stderr: {0}'.format(ret['stderr']))
    return ret


def retcode(cmd,
            cwd=None,
            runas=None,
            shell=DEFAULT_SHELL,
            env=(),
            template=None,
            umask=None,
            quiet=False,
            timeout=None):
    '''
    Execute a shell command and return the command's return code.

    CLI Example::

        salt '*' cmd.retcode "file /bin/bash"

    The template arg can be set to 'jinja' or another supported template
    engine to render the command arguments before execution.
    For example::

        salt '*' cmd.retcode template=jinja "file {{grains.pythonpath[0]}}/python"

    '''
    return _run(
            cmd,
            runas=runas,
            cwd=cwd,
            shell=shell,
            env=env,
            template=template,
            umask=umask,
            quiet=quiet,
            timeout=timeout)['retcode']


def script(
        source,
        args=None,
        cwd=None,
        runas=None,
        shell=DEFAULT_SHELL,
        env='base',
        template='jinja',
        umask=None,
        timeout=None,
        **kwargs):
    '''
    Download a script from a remote location and execute the script locally.
    The script can be located on the salt master file server or on an HTTP/FTP
    server.

    The script will be executed directly, so it can be written in any available
    programming language.

    The script can also be formated as a template, the default is jinja.
    Arguments for the script can be specified as well.

    CLI Example::

        salt '*' cmd.script salt://scripts/runme.sh
        salt '*' cmd.script salt://scripts/runme.sh 'arg1 arg2 "arg 3"'
    '''
    if not salt.utils.is_windows():
        path = salt.utils.mkstemp(dir=cwd)
    else:
        path = __salt__['cp.cache_file'](source, env)
    if template:
        __salt__['cp.get_template'](source, path, template, env, **kwargs)
    else:
        if not salt.utils.is_windows():
            fn_ = __salt__['cp.cache_file'](source, env)
            shutil.copyfile(fn_, path)
    if not salt.utils.is_windows():
        os.chmod(path, 320)
        os.chown(path, __salt__['file.user_to_uid'](runas), -1)
    ret = _run(
            path + ' ' + args if args else path,
            cwd=cwd,
            quiet=kwargs.get('quiet', False),
            runas=runas,
            shell=shell,
            umask=umask,
            timeout=timeout
            )
    os.remove(path)
    return ret


def script_retcode(
        source,
        cwd=None,
        runas=None,
        shell=DEFAULT_SHELL,
        env='base',
        template='jinja',
        umask=None,
        timeout=None,
        **kwargs):
    '''
    Download a script from a remote location and execute the script locally.
    The script can be located on the salt master file server or on an HTTP/FTP
    server.

    The script will be executed directly, so it can be written in any available
    programming language.

    The script can also be formated as a template, the default is jinja.

    Only evaluate the script return code and do not block for terminal output

    CLI Example::

        salt '*' cmd.script_retcode salt://scripts/runme.sh
    '''
    return script(
            source,
            cwd,
            runas,
            shell,
            env,
            template,
            umask=umask,
            timeout=timeout,
            **kwargs)['retcode']


def which(cmd):
    '''
    Returns the path of an executable available on the minion, None otherwise

    CLI Example::

        salt '*' cmd.which cat
    '''
    return salt.utils.which(cmd)


def which_bin(cmds):
    '''
    Returns the first command found in a list of commands

    CLI Example::

        salt '*' cmd.which_bin '[pip2, pip, pip-python]'
    '''
    return salt.utils.which_bin(cmds)


def has_exec(cmd):
    '''
    Returns true if the executable is available on the minion, false otherwise

    CLI Example::

        salt '*' cmd.has_exec cat
    '''
    return bool(which(cmd))


def exec_code(lang, code, cwd=None):
    '''
    Pass in two strings, the first naming the executable language, aka -
    python2, python3, ruby, perl, lua, etc. the second string containing
    the code you wish to execute. The stdout and stderr will be returned

    CLI Example::

        salt '*' cmd.exec_code ruby 'puts "cheese"'
    '''
    codefile = salt.utils.mkstemp()
    with salt.utils.fopen(codefile, 'w+') as fp_:
        fp_.write(code)

    cmd = '{0} {1}'.format(lang, codefile)
    ret = run(cmd, cwd=cwd)
    os.remove(codefile)
    return ret
