"""
A module for shelling out.

Keep in mind that this module is insecure, in that it can give whomever has
access to the master root execution access to all salt minions.
"""

import base64
import fnmatch
import functools
import glob
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback

import salt.grains.extra
import salt.utils.args
import salt.utils.data
import salt.utils.files
import salt.utils.json
import salt.utils.path
import salt.utils.pkg
import salt.utils.platform
import salt.utils.powershell
import salt.utils.stringutils
import salt.utils.templates
import salt.utils.timed_subprocess
import salt.utils.url
import salt.utils.user
import salt.utils.versions
import salt.utils.vt
import salt.utils.win_chcp
import salt.utils.win_dacl
import salt.utils.win_reg
from salt._logging import LOG_LEVELS
from salt.exceptions import (
    CommandExecutionError,
    SaltInvocationError,
    TimedProcTimeoutError,
)

# Only available on POSIX systems, nonfatal on windows
try:
    import grp
    import pwd
except ImportError:
    pass

if salt.utils.platform.is_windows():
    from salt.utils.win_functions import escape_argument as _cmd_quote
    from salt.utils.win_runas import runas as win_runas

    HAS_WIN_RUNAS = True
else:
    import shlex

    _cmd_quote = shlex.quote

    HAS_WIN_RUNAS = False

__proxyenabled__ = ["*"]
# Define the module's virtual name
__virtualname__ = "cmd"

log = logging.getLogger(__name__)

DEFAULT_SHELL = salt.grains.extra.shell()["shell"]


# Overwriting the cmd python module makes debugging modules with pdb a bit
# harder so lets do it this way instead.
def __virtual__():
    return __virtualname__


def _log_cmd(cmd):
    if isinstance(cmd, (tuple, list)):
        return cmd[0].strip()
    else:
        return str(cmd).split()[0].strip()


def _check_cb(cb_):
    """
    If the callback is None or is not callable, return a lambda that returns
    the value passed.
    """
    if cb_ is not None:
        if hasattr(cb_, "__call__"):
            return cb_
        else:
            log.error("log_callback is not callable, ignoring")
    return lambda x: x


def _python_shell_default(python_shell, __pub_jid):
    """
    Set python_shell default based on remote execution and __opts__['cmd_safe']
    """
    try:
        # Default to python_shell=True when run directly from remote execution
        # system. Cross-module calls won't have a jid.
        if __pub_jid and python_shell is None:
            return True
        elif __opts__.get("cmd_safe", True) is False and python_shell is None:
            # Override-switch for python_shell
            return True
    except NameError:
        pass
    return python_shell


def _chroot_pids(chroot):
    pids = []
    for root in glob.glob("/proc/[0-9]*/root"):
        try:
            link = os.path.realpath(root)
            if link.startswith(chroot):
                pids.append(int(os.path.basename(os.path.dirname(root))))
        except OSError:
            pass
    return pids


def _render_cmd(cmd, cwd, template, saltenv=None, pillarenv=None, pillar_override=None):
    """
    If template is a valid template engine, process the cmd and cwd through
    that engine.
    """
    if saltenv is None:
        try:
            saltenv = __opts__.get("saltenv", "base")
        except NameError:
            saltenv = "base"

    if not template:
        return (cmd, cwd)

    # render the path as a template using path_template_engine as the engine
    if template not in salt.utils.templates.TEMPLATE_REGISTRY:
        raise CommandExecutionError(
            f"Attempted to render file paths with unavailable engine {template}"
        )

    kwargs = {}
    kwargs["salt"] = __salt__
    if pillarenv is not None or pillar_override is not None:
        pillarenv = pillarenv or __opts__["pillarenv"]
        kwargs["pillar"] = _gather_pillar(pillarenv, pillar_override)
    else:
        kwargs["pillar"] = __pillar__
    kwargs["grains"] = __grains__
    kwargs["opts"] = __opts__
    kwargs["saltenv"] = saltenv

    def _render(contents):
        # write out path to temp file
        tmp_path_fn = salt.utils.files.mkstemp()
        with salt.utils.files.fopen(tmp_path_fn, "w+") as fp_:
            fp_.write(salt.utils.stringutils.to_str(contents))
        data = salt.utils.templates.TEMPLATE_REGISTRY[template](
            tmp_path_fn, to_str=True, **kwargs
        )
        salt.utils.files.safe_rm(tmp_path_fn)
        if not data["result"]:
            # Failed to render the template
            raise CommandExecutionError(
                "Failed to execute cmd with error: {}".format(data["data"])
            )
        else:
            return data["data"]

    cmd = _render(cmd)
    cwd = _render(cwd)
    return (cmd, cwd)


def _check_loglevel(level="info"):
    """
    Retrieve the level code for use in logging.Logger.log().
    """
    try:
        level = level.lower()
        if level == "quiet":
            return None
        else:
            return LOG_LEVELS[level]
    except (AttributeError, KeyError):
        log.error(
            "Invalid output_loglevel '%s'. Valid levels are: %s. Falling "
            "back to 'info'.",
            level,
            ", ".join(sorted(LOG_LEVELS, reverse=True)),
        )
        return LOG_LEVELS["info"]


def _parse_env(env):
    if not env:
        env = {}
    if isinstance(env, list):
        env = salt.utils.data.repack_dictlist(env)
    if not isinstance(env, dict):
        env = {}
    return env


def _gather_pillar(pillarenv, pillar_override):
    """
    Whenever a state run starts, gather the pillar data fresh
    """
    pillar = salt.pillar.get_pillar(
        __opts__,
        __grains__.value(),
        __opts__["id"],
        __opts__["saltenv"],
        pillar_override=pillar_override,
        pillarenv=pillarenv,
    )
    ret = pillar.compile_pillar()
    if pillar_override and isinstance(pillar_override, dict):
        ret.update(pillar_override)
    return ret


def _check_avail(cmd):
    """
    Check to see if the given command can be run
    """
    if isinstance(cmd, list):
        cmd = " ".join([str(x) if not isinstance(x, str) else x for x in cmd])
    bret = True
    wret = False
    if __salt__["config.get"]("cmd_blacklist_glob"):
        blist = __salt__["config.get"]("cmd_blacklist_glob", [])
        for comp in blist:
            if fnmatch.fnmatch(cmd, comp):
                # BAD! you are blacklisted
                bret = False
    if __salt__["config.get"]("cmd_whitelist_glob", []):
        blist = __salt__["config.get"]("cmd_whitelist_glob", [])
        for comp in blist:
            if fnmatch.fnmatch(cmd, comp):
                # GOOD! You are whitelisted
                wret = True
                break
    else:
        # If no whitelist set then alls good!
        wret = True
    return bret and wret


def _prep_powershell_cmd(shell, cmd, stack, encoded_cmd):
    """
    Prep cmd when shell is powershell
    """

    # If this is running on Windows wrap
    # the shell in quotes in case there are
    # spaces in the paths.
    if salt.utils.platform.is_windows():
        shell = f'"{shell}"'

    # extract_stack() returns a list of tuples.
    # The last item in the list [-1] is the current method.
    # The third item[2] in each tuple is the name of that method.
    if stack[-2][2] == "script":
        cmd = (
            "{} -NonInteractive -NoProfile -ExecutionPolicy Bypass -Command {}".format(
                shell, cmd
            )
        )
    elif encoded_cmd:
        cmd = f"{shell} -NonInteractive -NoProfile -EncodedCommand {cmd}"
    else:
        cmd = f'{shell} -NonInteractive -NoProfile -Command "{cmd}"'

    return cmd


def _run(
    cmd,
    cwd=None,
    stdin=None,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    output_encoding=None,
    output_loglevel="debug",
    log_callback=None,
    runas=None,
    group=None,
    shell=DEFAULT_SHELL,
    python_shell=False,
    env=None,
    clean_env=False,
    prepend_path=None,
    rstrip=True,
    template=None,
    umask=None,
    timeout=None,
    with_communicate=True,
    reset_system_locale=True,
    ignore_retcode=False,
    saltenv=None,
    pillarenv=None,
    pillar_override=None,
    use_vt=False,
    password=None,
    bg=False,
    encoded_cmd=False,
    success_retcodes=None,
    success_stdout=None,
    success_stderr=None,
    windows_codepage=65001,
    **kwargs,
):
    """
    Do the DRY thing and only call subprocess.Popen() once
    """
    if "pillar" in kwargs and not pillar_override:
        pillar_override = kwargs["pillar"]
    if output_loglevel != "quiet" and _is_valid_shell(shell) is False:
        log.warning(
            "Attempt to run a shell command with what may be an invalid shell! "
            "Check to ensure that the shell <%s> is valid for this user.",
            shell,
        )

    output_loglevel = _check_loglevel(output_loglevel)
    log_callback = _check_cb(log_callback)
    use_sudo = False

    if runas is None and "__context__" in globals():
        runas = __context__.get("runas")

    if password is None and "__context__" in globals():
        password = __context__.get("runas_password")

    # Set the default working directory to the home directory of the user
    # salt-minion is running as. Defaults to home directory of user under which
    # the minion is running.
    if not cwd:
        cwd = os.path.expanduser("~{}".format("" if not runas else runas))

        # make sure we can access the cwd
        # when run from sudo or another environment where the euid is
        # changed ~ will expand to the home of the original uid and
        # the euid might not have access to it. See issue #1844
        if not os.access(cwd, os.R_OK):
            cwd = "/"
            if salt.utils.platform.is_windows():
                cwd = os.path.abspath(os.sep)
    else:
        # Handle edge cases where numeric/other input is entered, and would be
        # yaml-ified into non-string types
        cwd = str(cwd)

    if bg:
        ignore_retcode = True
        use_vt = False

    change_windows_codepage = False
    if not salt.utils.platform.is_windows():
        if not os.path.isfile(shell) or not os.access(shell, os.X_OK):
            msg = f"The shell {shell} is not available"
            raise CommandExecutionError(msg)
    elif use_vt:  # Memozation so not much overhead
        raise CommandExecutionError("VT not available on windows")
    else:
        if windows_codepage:
            if not isinstance(windows_codepage, int):
                windows_codepage = int(windows_codepage)
            previous_windows_codepage = salt.utils.win_chcp.get_codepage_id()
            if windows_codepage != previous_windows_codepage:
                change_windows_codepage = True

    # The powershell binary is "powershell"
    # The powershell core binary is "pwsh"
    # you can also pass a path here as long as the binary name is one of the two
    if any(word in shell.lower().strip() for word in ["powershell", "pwsh"]):
        # Strip whitespace
        if isinstance(cmd, str):
            cmd = cmd.strip()
        elif isinstance(cmd, list):
            cmd = " ".join(cmd).strip()
        cmd = cmd.replace('"', '\\"')

        # If we were called by script(), then fakeout the Windows
        # shell to run a Powershell script.
        # Else just run a Powershell command.
        stack = traceback.extract_stack(limit=2)

        cmd = _prep_powershell_cmd(shell, cmd, stack, encoded_cmd)

    # munge the cmd and cwd through the template
    (cmd, cwd) = _render_cmd(cmd, cwd, template, saltenv, pillarenv, pillar_override)
    ret = {}

    # If the pub jid is here then this is a remote ex or salt call command and needs to be
    # checked if blacklisted
    if "__pub_jid" in kwargs:
        if not _check_avail(cmd):
            raise CommandExecutionError(f'The shell command "{cmd}" is not permitted')

    env = _parse_env(env)

    for bad_env_key in (x for x, y in env.items() if y is None):
        log.error(
            "Environment variable '%s' passed without a value. "
            "Setting value to an empty string",
            bad_env_key,
        )
        env[bad_env_key] = ""

    if output_loglevel is not None:
        # Always log the shell commands at INFO unless quiet logging is
        # requested. The command output is what will be controlled by the
        # 'loglevel' parameter.
        msg = "Executing command {}{}{} {}{}in directory '{}'{}".format(
            "'" if not isinstance(cmd, list) else "",
            _log_cmd(cmd),
            "'" if not isinstance(cmd, list) else "",
            f"as user '{runas}' " if runas else "",
            f"in group '{group}' " if group else "",
            cwd,
            (
                ". Executing command in the background, no output will be logged."
                if bg
                else ""
            ),
        )
        log.info(log_callback(msg))

    if runas and salt.utils.platform.is_windows():
        if not HAS_WIN_RUNAS:
            msg = "missing salt/utils/win_runas.py"
            raise CommandExecutionError(msg)

        if isinstance(cmd, (list, tuple)):
            cmd = " ".join(cmd)

        return win_runas(cmd, runas, password, cwd)

    if runas and salt.utils.platform.is_darwin():
        # We need to insert the user simulation into the command itself and not
        # just run it from the environment on macOS as that method doesn't work
        # properly when run as root for certain commands.
        if isinstance(cmd, (list, tuple)):
            cmd = " ".join(map(_cmd_quote, cmd))

        # Ensure directory is correct before running command
        cmd = f"cd -- {_cmd_quote(cwd)} && {{ {cmd}\n }}"

        # Ensure environment is correct for a newly logged-in user by running
        # the command under bash as a login shell
        try:
            # Do not rely on populated __salt__ dict (ie avoid __salt__['user.info'])
            user_shell = [x for x in pwd.getpwall() if x.pw_name == runas][0].pw_shell
            if re.search("bash$", user_shell):
                cmd = "{shell} -l -c {cmd}".format(
                    shell=user_shell, cmd=_cmd_quote(cmd)
                )
        except (AttributeError, IndexError):
            pass

        # Ensure the login is simulated correctly (note: su runs sh, not bash,
        # which causes the environment to be initialised incorrectly, which is
        # fixed by the previous line of code)
        cmd = f"su -l {_cmd_quote(runas)} -c {_cmd_quote(cmd)}"

        # Set runas to None, because if you try to run `su -l` after changing
        # user, su will prompt for the password of the user and cause salt to
        # hang.
        runas = None

    if runas:
        # Save the original command before munging it
        try:
            pwd.getpwnam(runas)
        except KeyError:
            raise CommandExecutionError(f"User '{runas}' is not available")

    if group:
        if salt.utils.platform.is_windows():
            msg = "group is not currently available on Windows"
            raise SaltInvocationError(msg)
        if not which_bin(["sudo"]):
            msg = "group argument requires sudo but not found"
            raise CommandExecutionError(msg)
        try:
            grp.getgrnam(group)
        except KeyError:
            raise CommandExecutionError(f"Group '{runas}' is not available")
        else:
            use_sudo = True

    if runas or group:
        try:
            # Getting the environment for the runas user
            # Use markers to thwart any stdout noise
            # There must be a better way to do this.
            import uuid

            marker = "<<<" + str(uuid.uuid4()) + ">>>"
            marker_b = marker.encode(__salt_system_encoding__)
            py_code = (
                "import sys, os, itertools; sys.stdout.write('{0}'); "
                "sys.stdout.write('\\0'.join(itertools.chain(*os.environ.items()))); "
                "sys.stdout.write('{0}');".format(marker)
            )

            if use_sudo:
                env_cmd = ["sudo"]
                # runas is optional if use_sudo is set.
                if runas:
                    env_cmd.extend(["-u", runas])
                if group:
                    env_cmd.extend(["-g", group])
                if shell != DEFAULT_SHELL:
                    env_cmd.extend(["-s", "--", shell, "-c"])
                else:
                    env_cmd.extend(["-i", "--"])
            elif __grains__["os"] in ["FreeBSD"]:
                env_cmd = [
                    "su",
                    "-",
                    runas,
                    "-c",
                ]
            elif __grains__["os_family"] in ["Solaris"]:
                env_cmd = ["su", "-", runas, "-c"]
            elif __grains__["os_family"] in ["AIX"]:
                env_cmd = ["su", "-", runas, "-c"]
            else:
                env_cmd = ["su", "-s", shell, "-", runas, "-c"]

            if not salt.utils.pkg.check_bundled():
                if __grains__["os"] in ["FreeBSD"]:
                    env_cmd.extend([f"{shell} -c {sys.executable}"])
                else:
                    env_cmd.extend([sys.executable])
            else:
                with tempfile.NamedTemporaryFile("w", delete=False) as fp:
                    if __grains__["os"] in ["FreeBSD"]:
                        env_cmd.extend(
                            [
                                "{} -c {} python {}".format(
                                    shell, sys.executable, fp.name
                                )
                            ]
                        )
                    else:
                        env_cmd.extend([f"{sys.executable} python {fp.name}"])
                    fp.write(py_code)
                    shutil.chown(fp.name, runas)

            msg = f"env command: {env_cmd}"
            log.debug(log_callback(msg))
            env_bytes, env_encoded_err = subprocess.Popen(
                env_cmd,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stdin=subprocess.PIPE,
            ).communicate(salt.utils.stringutils.to_bytes(py_code))
            if salt.utils.pkg.check_bundled():
                os.remove(fp.name)
            marker_count = env_bytes.count(marker_b)
            if marker_count == 0:
                # Possibly PAM prevented the login
                log.error(
                    "Environment could not be retrieved for user '%s': "
                    "stderr=%r stdout=%r",
                    runas,
                    env_encoded_err,
                    env_bytes,
                )
                # Ensure that we get an empty env_runas dict below since we
                # were not able to get the environment.
                env_bytes = b""
            elif marker_count != 2:
                raise CommandExecutionError(
                    "Environment could not be retrieved for user '{}'",
                    info={"stderr": repr(env_encoded_err), "stdout": repr(env_bytes)},
                )
            else:
                # Strip the marker
                env_bytes = env_bytes.split(marker_b)[1]

            env_runas = dict(list(zip(*[iter(env_bytes.split(b"\0"))] * 2)))

            env_runas = {
                salt.utils.stringutils.to_str(k): salt.utils.stringutils.to_str(v)
                for k, v in env_runas.items()
            }
            env_runas.update(env)

            # Fix platforms like Solaris that don't set a USER env var in the
            # user's default environment as obtained above.
            if env_runas.get("USER") != runas:
                env_runas["USER"] = runas

            # Fix some corner cases where shelling out to get the user's
            # environment returns the wrong home directory.
            runas_home = os.path.expanduser(f"~{runas}")
            if env_runas.get("HOME") != runas_home:
                env_runas["HOME"] = runas_home

            env = env_runas
        except ValueError as exc:
            log.exception("Error raised retrieving environment for user %s", runas)
            raise CommandExecutionError(
                "Environment could not be retrieved for user '{}': {}".format(
                    runas, exc
                )
            )

    if reset_system_locale is True:
        if not salt.utils.platform.is_windows():
            # Default to C!
            # Salt only knows how to parse English words
            # Don't override if the user has passed LC_ALL
            env.setdefault("LC_CTYPE", "C")
            env.setdefault("LC_NUMERIC", "C")
            env.setdefault("LC_TIME", "C")
            env.setdefault("LC_COLLATE", "C")
            env.setdefault("LC_MONETARY", "C")
            env.setdefault("LC_MESSAGES", "C")
            env.setdefault("LC_PAPER", "C")
            env.setdefault("LC_NAME", "C")
            env.setdefault("LC_ADDRESS", "C")
            env.setdefault("LC_TELEPHONE", "C")
            env.setdefault("LC_MEASUREMENT", "C")
            env.setdefault("LC_IDENTIFICATION", "C")
            env.setdefault("LANGUAGE", "C")

    if clean_env:
        run_env = env

    else:
        if salt.utils.platform.is_windows():
            import nt

            run_env = nt.environ.copy()
        else:
            run_env = os.environ.copy()
        run_env.update(env)

    if prepend_path:
        run_env["PATH"] = ":".join((prepend_path, run_env["PATH"]))

    if "NOTIFY_SOCKET" not in env:
        run_env.pop("NOTIFY_SOCKET", None)

    if python_shell is None:
        python_shell = False

    new_kwargs = {
        "cwd": cwd,
        "shell": python_shell,
        "env": run_env,
        "stdin": str(stdin) if stdin is not None else stdin,
        "stdout": stdout,
        "stderr": stderr,
        "with_communicate": with_communicate,
        "timeout": timeout,
        "bg": bg,
    }

    if "stdin_raw_newlines" in kwargs:
        new_kwargs["stdin_raw_newlines"] = kwargs["stdin_raw_newlines"]

    if umask is not None:
        _umask = str(umask).lstrip("0")

        if _umask == "":
            msg = "Zero umask is not allowed."
            raise CommandExecutionError(msg)

        try:
            _umask = int(_umask, 8)
        except ValueError:
            raise CommandExecutionError(f"Invalid umask: '{umask}'")
    else:
        _umask = None

    if runas or group or umask:
        new_kwargs["preexec_fn"] = functools.partial(
            salt.utils.user.chugid_and_umask, runas, _umask, group
        )

    if not salt.utils.platform.is_windows():
        # close_fds is not supported on Windows platforms if you redirect
        # stdin/stdout/stderr
        if new_kwargs["shell"] is True:
            new_kwargs["executable"] = shell
        if salt.utils.platform.is_freebsd() and sys.version_info < (3, 9):
            # https://bugs.python.org/issue38061
            new_kwargs["close_fds"] = False
        else:
            new_kwargs["close_fds"] = True

    if not os.path.isabs(cwd) or not os.path.isdir(cwd):
        raise CommandExecutionError(
            f"Specified cwd '{cwd}' either not absolute or does not exist"
        )

    if (
        python_shell is not True
        and not salt.utils.platform.is_windows()
        and not isinstance(cmd, list)
    ):
        cmd = salt.utils.args.shlex_split(cmd)

    if success_retcodes is None:
        success_retcodes = [0]
    else:
        try:
            success_retcodes = [
                int(i) for i in salt.utils.args.split_input(success_retcodes)
            ]
        except ValueError:
            raise SaltInvocationError("success_retcodes must be a list of integers")

    if success_stdout is None:
        success_stdout = []
    else:
        success_stdout = salt.utils.args.split_input(success_stdout)

    if success_stderr is None:
        success_stderr = []
    else:
        success_stderr = salt.utils.args.split_input(success_stderr)

    if not use_vt:
        # This is where the magic happens
        try:
            if change_windows_codepage:
                salt.utils.win_chcp.set_codepage_id(windows_codepage)
            try:
                proc = salt.utils.timed_subprocess.TimedProc(cmd, **new_kwargs)
            except OSError as exc:
                msg = "Unable to run command '{}' with the context '{}', reason: {}".format(
                    cmd if output_loglevel is not None else "REDACTED",
                    new_kwargs,
                    exc,
                )
                raise CommandExecutionError(msg)

            try:
                proc.run()
            except TimedProcTimeoutError as exc:
                ret["stdout"] = str(exc)
                ret["stderr"] = ""
                ret["retcode"] = None
                ret["pid"] = proc.process.pid
                # ok return code for timeouts?
                ret["retcode"] = 1
                return ret
        finally:
            if change_windows_codepage:
                salt.utils.win_chcp.set_codepage_id(previous_windows_codepage)

        if output_loglevel != "quiet" and output_encoding is not None:
            log.debug(
                "Decoding output from command %s using %s encoding",
                cmd,
                output_encoding,
            )

        try:
            out = salt.utils.stringutils.to_unicode(
                proc.stdout, encoding=output_encoding
            )
        except TypeError:
            # stdout is None
            out = ""
        except UnicodeDecodeError:
            out = salt.utils.stringutils.to_unicode(
                proc.stdout, encoding=output_encoding, errors="replace"
            )
            if output_loglevel != "quiet":
                log.error(
                    "Failed to decode stdout from command %s, non-decodable "
                    "characters have been replaced",
                    _log_cmd(cmd),
                )

        try:
            err = salt.utils.stringutils.to_unicode(
                proc.stderr, encoding=output_encoding
            )
        except TypeError:
            # stderr is None
            err = ""
        except UnicodeDecodeError:
            err = salt.utils.stringutils.to_unicode(
                proc.stderr, encoding=output_encoding, errors="replace"
            )
            if output_loglevel != "quiet":
                log.error(
                    "Failed to decode stderr from command %s, non-decodable "
                    "characters have been replaced",
                    _log_cmd(cmd),
                )

        if rstrip:
            if out is not None:
                out = out.rstrip()
            if err is not None:
                err = err.rstrip()
        ret["pid"] = proc.process.pid
        ret["retcode"] = proc.process.returncode
        if ret["retcode"] in success_retcodes:
            ret["retcode"] = 0
        ret["stdout"] = out
        ret["stderr"] = err
        if any(
            [stdo in ret["stdout"] for stdo in success_stdout]
            + [stde in ret["stderr"] for stde in success_stderr]
        ):
            ret["retcode"] = 0
    else:
        formatted_timeout = ""
        if timeout:
            formatted_timeout = f" (timeout: {timeout}s)"
        if output_loglevel is not None:
            msg = f"Running {cmd} in VT{formatted_timeout}"
            log.debug(log_callback(msg))
        stdout, stderr = "", ""
        now = time.time()
        if timeout:
            will_timeout = now + timeout
        else:
            will_timeout = -1
        try:
            proc = salt.utils.vt.Terminal(
                cmd,
                shell=True,
                log_stdout=True,
                log_stderr=True,
                cwd=cwd,
                preexec_fn=new_kwargs.get("preexec_fn", None),
                env=run_env,
                log_stdin_level=output_loglevel,
                log_stdout_level=output_loglevel,
                log_stderr_level=output_loglevel,
                stream_stdout=True,
                stream_stderr=True,
            )
            ret["pid"] = proc.pid
            stdout = ""
            stderr = ""
            while proc.has_unread_data:
                try:
                    try:
                        time.sleep(0.5)
                        try:
                            cstdout, cstderr = proc.recv()
                        except OSError:
                            cstdout, cstderr = "", ""
                        if cstdout:
                            stdout += cstdout
                        if cstderr:
                            stderr += cstderr
                        if timeout and (time.time() > will_timeout):
                            ret["stderr"] = "SALT: Timeout after {}s\n{}".format(
                                timeout, stderr
                            )
                            ret["retcode"] = None
                            break
                    except KeyboardInterrupt:
                        ret["stderr"] = f"SALT: User break\n{stderr}"
                        ret["retcode"] = 1
                        break
                except salt.utils.vt.TerminalException as exc:
                    log.error("VT: %s", exc, exc_info_on_loglevel=logging.DEBUG)
                    ret = {"retcode": 1, "pid": "2"}
                    break
                # only set stdout on success as we already mangled in other
                # cases
                ret["stdout"] = stdout
                if not proc.isalive():
                    # Process terminated, i.e., not canceled by the user or by
                    # the timeout
                    ret["stderr"] = stderr
                    ret["retcode"] = proc.exitstatus
                    if ret["retcode"] in success_retcodes:
                        ret["retcode"] = 0
                    if any(
                        [stdo in ret["stdout"] for stdo in success_stdout]
                        + [stde in ret["stderr"] for stde in success_stderr]
                    ):
                        ret["retcode"] = 0
                ret["pid"] = proc.pid
        finally:
            proc.close(terminate=True, kill=True)
    try:
        if ignore_retcode:
            __context__["retcode"] = 0
        else:
            __context__["retcode"] = ret["retcode"]
    except NameError:
        # Ignore the context error during grain generation
        pass

    # Log the output
    if output_loglevel is not None:
        if not ignore_retcode and ret["retcode"] != 0:
            if output_loglevel < LOG_LEVELS["error"]:
                output_loglevel = LOG_LEVELS["error"]
            msg = "Command '{}' failed with return code: {}".format(
                _log_cmd(cmd), ret["retcode"]
            )
            log.error(log_callback(msg))
        if ret["stdout"]:
            log.log(output_loglevel, "stdout: %s", log_callback(ret["stdout"]))
        if ret["stderr"]:
            log.log(output_loglevel, "stderr: %s", log_callback(ret["stderr"]))
        if ret["retcode"]:
            log.log(output_loglevel, "retcode: %s", ret["retcode"])

    return ret


def _run_quiet(
    cmd,
    cwd=None,
    stdin=None,
    output_encoding=None,
    runas=None,
    shell=DEFAULT_SHELL,
    python_shell=False,
    env=None,
    template=None,
    umask=None,
    timeout=None,
    reset_system_locale=True,
    saltenv=None,
    pillarenv=None,
    pillar_override=None,
    success_retcodes=None,
    success_stdout=None,
    success_stderr=None,
    ignore_retcode=None,
):
    """
    Helper for running commands quietly for minion startup
    """
    return _run(
        cmd,
        runas=runas,
        cwd=cwd,
        stdin=stdin,
        stderr=subprocess.STDOUT,
        output_encoding=output_encoding,
        output_loglevel="quiet",
        log_callback=None,
        shell=shell,
        python_shell=python_shell,
        env=env,
        template=template,
        umask=umask,
        timeout=timeout,
        reset_system_locale=reset_system_locale,
        saltenv=saltenv,
        pillarenv=pillarenv,
        pillar_override=pillar_override,
        success_retcodes=success_retcodes,
        success_stdout=success_stdout,
        success_stderr=success_stderr,
        ignore_retcode=ignore_retcode,
    )["stdout"]


def _run_all_quiet(
    cmd,
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
    saltenv=None,
    pillarenv=None,
    pillar_override=None,
    output_encoding=None,
    success_retcodes=None,
    success_stdout=None,
    success_stderr=None,
    ignore_retcode=None,
):
    """
    Helper for running commands quietly for minion startup.
    Returns a dict of return data.

    output_loglevel argument is ignored. This is here for when we alias
    cmd.run_all directly to _run_all_quiet in certain chicken-and-egg
    situations where modules need to work both before and after
    the __salt__ dictionary is populated (cf dracr.py)
    """
    return _run(
        cmd,
        runas=runas,
        cwd=cwd,
        stdin=stdin,
        shell=shell,
        python_shell=python_shell,
        env=env,
        output_encoding=output_encoding,
        output_loglevel="quiet",
        log_callback=None,
        template=template,
        umask=umask,
        timeout=timeout,
        reset_system_locale=reset_system_locale,
        saltenv=saltenv,
        pillarenv=pillarenv,
        pillar_override=pillar_override,
        success_retcodes=success_retcodes,
        success_stdout=success_stdout,
        success_stderr=success_stderr,
        ignore_retcode=ignore_retcode,
    )


def run(
    cmd,
    cwd=None,
    stdin=None,
    runas=None,
    group=None,
    shell=DEFAULT_SHELL,
    python_shell=None,
    env=None,
    clean_env=False,
    template=None,
    rstrip=True,
    umask=None,
    output_encoding=None,
    output_loglevel="debug",
    log_callback=None,
    hide_output=False,
    timeout=None,
    reset_system_locale=True,
    ignore_retcode=False,
    saltenv=None,
    use_vt=False,
    bg=False,
    password=None,
    encoded_cmd=False,
    raise_err=False,
    prepend_path=None,
    success_retcodes=None,
    success_stdout=None,
    success_stderr=None,
    **kwargs,
):
    r"""
    Execute the passed command and return the output as a string

    :param str cmd: The command to run. ex: ``ls -lart /home``

    :param str cwd: The directory from which to execute the command. Defaults
        to the home directory of the user specified by ``runas`` (or the user
        under which Salt is running if ``runas`` is not specified).

    :param str stdin: A string of standard input can be specified for the
        command to be run using the ``stdin`` parameter. This can be useful in
        cases where sensitive information must be read from standard input.

    :param str runas: Specify an alternate user to run the command. The default
        behavior is to run as the user under which Salt is running.

        .. warning::

            For versions 2018.3.3 and above on macosx while using runas,
            on linux while using run, to pass special characters to the
            command you need to escape the characters on the shell.

            Example:

            .. code-block:: bash

                cmd.run 'echo '\''h=\"baz\"'\''' runas=macuser

    :param str group: Group to run command as. Not currently supported
        on Windows.

    :param str password: Windows only. Required when specifying ``runas``. This
        parameter will be ignored on non-Windows platforms.

        .. versionadded:: 2016.3.0

    :param str shell: Specify an alternate shell. Defaults to the system's
        default shell.

    :param bool python_shell: If ``False``, let python handle the positional
        arguments. Set to ``True`` to use shell features, such as pipes or
        redirection.

    :param bool bg: If ``True``, run command in background and do not await or
        deliver its results

        .. versionadded:: 2016.3.0

    :param dict env: Environment variables to be set prior to execution.

        .. note::
            When passing environment variables on the CLI, they should be
            passed as the string representation of a dictionary.

            .. code-block:: bash

                salt myminion cmd.run 'some command' env='{"FOO": "bar"}'

        .. note::
            When using environment variables on Window's, case-sensitivity
            matters, i.e. Window's uses `Path` as opposed to `PATH` for other
            systems.

    :param bool clean_env: Attempt to clean out all other shell environment
        variables and set only those provided in the 'env' argument to this
        function.

    :param str prepend_path: $PATH segment to prepend (trailing ':' not
        necessary) to $PATH

        .. versionadded:: 2018.3.0

    :param str template: If this setting is applied then the named templating
        engine will be used to render the downloaded file. Currently jinja,
        mako, and wempy are supported.

    :param bool rstrip: Strip all whitespace off the end of output before it is
        returned.

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

    :param int timeout: A timeout in seconds for the executed process to return.

    :param bool use_vt: Use VT utils (saltstack) to stream the command output
        more interactively to the console and the logs. This is experimental.

    :param bool encoded_cmd: Specify if the supplied command is encoded.
        Only applies to shell 'powershell' and 'pwsh'.

        .. versionadded:: 2018.3.0

        Older versions of powershell seem to return raw xml data in the return.
        To avoid raw xml data in the return, prepend your command with the
        following before encoding:

        `$ProgressPreference='SilentlyContinue'; <your command>`

        The following powershell code block will encode the `Write-Output`
        command so that it will not have the raw xml data in the return:

        .. code-block:: powershell

            # target string
            $Command = '$ProgressPreference="SilentlyContinue"; Write-Output "hello"'

            # Convert to Base64 encoded string
            $Encoded = [convert]::ToBase64String([System.Text.encoding]::Unicode.GetBytes($command))

            Write-Output $Encoded

    :param bool raise_err: If ``True`` and the command has a nonzero exit code,
        a CommandExecutionError exception will be raised.

    .. warning::
        This function does not process commands through a shell
        unless the python_shell flag is set to True. This means that any
        shell-specific functionality such as 'echo' or the use of pipes,
        redirection or &&, should either be migrated to cmd.shell or
        have the python_shell=True flag set here.

        The use of python_shell=True means that the shell will accept _any_ input
        including potentially malicious commands such as 'good_command;rm -rf /'.
        Be absolutely certain that you have sanitized your input prior to using
        python_shell=True

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

    :param int windows_codepage: 65001
        Only applies to Windows: the minion uses `C:\Windows\System32\chcp.com` to
        verify or set the code page before the command `cmd` is executed.
        Code page 65001 corresponds with UTF-8 and allows international localization of Windows.

      .. versionadded:: 3002

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
    information must be read from standard input.

    .. code-block:: bash

        salt '*' cmd.run "grep f" stdin='one\\ntwo\\nthree\\nfour\\nfive\\n'

    If an equal sign (``=``) appears in an argument to a Salt command it is
    interpreted as a keyword argument in the format ``key=val``. That
    processing can be bypassed in order to pass an equal sign through to the
    remote shell command by manually specifying the kwarg:

    .. code-block:: bash

        salt '*' cmd.run cmd='sed -e s/=/:/g'
    """
    python_shell = _python_shell_default(python_shell, kwargs.get("__pub_jid", ""))
    ret = _run(
        cmd,
        runas=runas,
        group=group,
        shell=shell,
        python_shell=python_shell,
        cwd=cwd,
        stdin=stdin,
        stderr=subprocess.STDOUT,
        env=env,
        clean_env=clean_env,
        prepend_path=prepend_path,
        template=template,
        rstrip=rstrip,
        umask=umask,
        output_encoding=output_encoding,
        output_loglevel=output_loglevel,
        log_callback=log_callback,
        timeout=timeout,
        reset_system_locale=reset_system_locale,
        ignore_retcode=ignore_retcode,
        saltenv=saltenv,
        use_vt=use_vt,
        bg=bg,
        password=password,
        encoded_cmd=encoded_cmd,
        success_retcodes=success_retcodes,
        success_stdout=success_stdout,
        success_stderr=success_stderr,
        **kwargs,
    )

    log_callback = _check_cb(log_callback)

    lvl = _check_loglevel(output_loglevel)
    if lvl is not None:
        if not ignore_retcode and ret["retcode"] != 0:
            if lvl < LOG_LEVELS["error"]:
                lvl = LOG_LEVELS["error"]
            msg = "Command '{}' failed with return code: {}".format(
                _log_cmd(cmd), ret["retcode"]
            )
            log.error(log_callback(msg))
            if raise_err:
                raise CommandExecutionError(
                    log_callback(ret["stdout"] if not hide_output else "")
                )
        log.log(lvl, "output: %s", log_callback(ret["stdout"]))
    return ret["stdout"] if not hide_output else ""


def shell(
    cmd,
    cwd=None,
    stdin=None,
    runas=None,
    group=None,
    shell=DEFAULT_SHELL,
    env=None,
    clean_env=False,
    template=None,
    rstrip=True,
    umask=None,
    output_encoding=None,
    output_loglevel="debug",
    log_callback=None,
    hide_output=False,
    timeout=None,
    reset_system_locale=True,
    ignore_retcode=False,
    saltenv=None,
    use_vt=False,
    bg=False,
    password=None,
    prepend_path=None,
    success_retcodes=None,
    success_stdout=None,
    success_stderr=None,
    **kwargs,
):
    """
    Execute the passed command and return the output as a string.

    .. versionadded:: 2015.5.0

    :param str cmd: The command to run. ex: ``ls -lart /home``

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

        .. warning::

            For versions 2018.3.3 and above on macosx while using runas,
            to pass special characters to the command you need to escape
            the characters on the shell.

            Example:

            .. code-block:: bash

                cmd.shell 'echo '\\''h=\\"baz\\"'\\''' runas=macuser

    :param str group: Group to run command as. Not currently supported
      on Windows.

    :param str password: Windows only. Required when specifying ``runas``. This
        parameter will be ignored on non-Windows platforms.

        .. versionadded:: 2016.3.0

    :param int shell: Shell to execute under. Defaults to the system default
        shell.

    :param bool bg: If True, run command in background and do not await or
        deliver its results

    :param dict env: Environment variables to be set prior to execution.

        .. note::
            When passing environment variables on the CLI, they should be
            passed as the string representation of a dictionary.

            .. code-block:: bash

                salt myminion cmd.shell 'some command' env='{"FOO": "bar"}'

        .. note::
            When using environment variables on Window's, case-sensitivity
            matters, i.e. Window's uses `Path` as opposed to `PATH` for other
            systems.

    :param bool clean_env: Attempt to clean out all other shell environment
        variables and set only those provided in the 'env' argument to this
        function.

    :param str prepend_path: $PATH segment to prepend (trailing ':' not necessary)
        to $PATH

        .. versionadded:: 2018.3.0

    :param str template: If this setting is applied then the named templating
        engine will be used to render the downloaded file. Currently jinja,
        mako, and wempy are supported.

    :param bool rstrip: Strip all whitespace off the end of output before it is
        returned.

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

    :param int timeout: A timeout in seconds for the executed process to
        return.

    :param bool use_vt: Use VT utils (saltstack) to stream the command output
        more interactively to the console and the logs. This is experimental.

    .. warning::

        This passes the cmd argument directly to the shell without any further
        processing! Be absolutely sure that you have properly sanitized the
        command passed to this function and do not use untrusted inputs.

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
    information must be read from standard input.

    .. code-block:: bash

        salt '*' cmd.shell "grep f" stdin='one\\ntwo\\nthree\\nfour\\nfive\\n'

    If an equal sign (``=``) appears in an argument to a Salt command it is
    interpreted as a keyword argument in the format ``key=val``. That
    processing can be bypassed in order to pass an equal sign through to the
    remote shell command by manually specifying the kwarg:

    .. code-block:: bash

        salt '*' cmd.shell cmd='sed -e s/=/:/g'
    """
    if "python_shell" in kwargs:
        python_shell = kwargs.pop("python_shell")
    else:
        python_shell = True
    return run(
        cmd,
        cwd=cwd,
        stdin=stdin,
        runas=runas,
        group=group,
        shell=shell,
        env=env,
        clean_env=clean_env,
        prepend_path=prepend_path,
        template=template,
        rstrip=rstrip,
        umask=umask,
        output_encoding=output_encoding,
        output_loglevel=output_loglevel,
        log_callback=log_callback,
        hide_output=hide_output,
        timeout=timeout,
        reset_system_locale=reset_system_locale,
        ignore_retcode=ignore_retcode,
        saltenv=saltenv,
        use_vt=use_vt,
        python_shell=python_shell,
        bg=bg,
        password=password,
        success_retcodes=success_retcodes,
        success_stdout=success_stdout,
        success_stderr=success_stderr,
        **kwargs,
    )


def run_stdout(
    cmd,
    cwd=None,
    stdin=None,
    runas=None,
    group=None,
    shell=DEFAULT_SHELL,
    python_shell=None,
    env=None,
    clean_env=False,
    template=None,
    rstrip=True,
    umask=None,
    output_encoding=None,
    output_loglevel="debug",
    log_callback=None,
    hide_output=False,
    timeout=None,
    reset_system_locale=True,
    ignore_retcode=False,
    saltenv=None,
    use_vt=False,
    password=None,
    prepend_path=None,
    success_retcodes=None,
    success_stdout=None,
    success_stderr=None,
    **kwargs,
):
    """
    Execute a command, and only return the standard out

    :param str cmd: The command to run. ex: ``ls -lart /home``

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

        .. warning::

            For versions 2018.3.3 and above on macosx while using runas,
            to pass special characters to the command you need to escape
            the characters on the shell.

            Example:

            .. code-block:: bash

                cmd.run_stdout 'echo '\\''h=\\"baz\\"'\\''' runas=macuser

    :param str password: Windows only. Required when specifying ``runas``. This
        parameter will be ignored on non-Windows platforms.

        .. versionadded:: 2016.3.0

    :param str group: Group to run command as. Not currently supported
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

                salt myminion cmd.run_stdout 'some command' env='{"FOO": "bar"}'

        .. note::
            When using environment variables on Window's, case-sensitivity
            matters, i.e. Window's uses `Path` as opposed to `PATH` for other
            systems.

    :param bool clean_env: Attempt to clean out all other shell environment
        variables and set only those provided in the 'env' argument to this
        function.

    :param str prepend_path: $PATH segment to prepend (trailing ':' not necessary)
        to $PATH

        .. versionadded:: 2018.3.0

    :param str template: If this setting is applied then the named templating
        engine will be used to render the downloaded file. Currently jinja,
        mako, and wempy are supported.

    :param bool rstrip: Strip all whitespace off the end of output before it is
        returned.

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

    :param int timeout: A timeout in seconds for the executed process to
        return.

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

        salt '*' cmd.run_stdout "ls -l | awk '/foo/{print \\$2}'"

    The template arg can be set to 'jinja' or another supported template
    engine to render the command arguments before execution.
    For example:

    .. code-block:: bash

        salt '*' cmd.run_stdout template=jinja "ls -l /tmp/{{grains.id}} | awk '/foo/{print \\$2}'"

    A string of standard input can be specified for the command to be run using
    the ``stdin`` parameter. This can be useful in cases where sensitive
    information must be read from standard input.

    .. code-block:: bash

        salt '*' cmd.run_stdout "grep f" stdin='one\\ntwo\\nthree\\nfour\\nfive\\n'
    """
    python_shell = _python_shell_default(python_shell, kwargs.get("__pub_jid", ""))
    ret = _run(
        cmd,
        runas=runas,
        group=group,
        cwd=cwd,
        stdin=stdin,
        shell=shell,
        python_shell=python_shell,
        env=env,
        clean_env=clean_env,
        prepend_path=prepend_path,
        template=template,
        rstrip=rstrip,
        umask=umask,
        output_encoding=output_encoding,
        output_loglevel=output_loglevel,
        log_callback=log_callback,
        timeout=timeout,
        reset_system_locale=reset_system_locale,
        ignore_retcode=ignore_retcode,
        saltenv=saltenv,
        use_vt=use_vt,
        password=password,
        success_retcodes=success_retcodes,
        success_stdout=success_stdout,
        success_stderr=success_stderr,
        **kwargs,
    )

    return ret["stdout"] if not hide_output else ""


def run_stderr(
    cmd,
    cwd=None,
    stdin=None,
    runas=None,
    group=None,
    shell=DEFAULT_SHELL,
    python_shell=None,
    env=None,
    clean_env=False,
    template=None,
    rstrip=True,
    umask=None,
    output_encoding=None,
    output_loglevel="debug",
    log_callback=None,
    hide_output=False,
    timeout=None,
    reset_system_locale=True,
    ignore_retcode=False,
    saltenv=None,
    use_vt=False,
    password=None,
    prepend_path=None,
    success_retcodes=None,
    success_stdout=None,
    success_stderr=None,
    **kwargs,
):
    """
    Execute a command and only return the standard error

    :param str cmd: The command to run. ex: ``ls -lart /home``

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

        .. warning::

            For versions 2018.3.3 and above on macosx while using runas,
            to pass special characters to the command you need to escape
            the characters on the shell.

            Example:

            .. code-block:: bash

                cmd.run_stderr 'echo '\\''h=\\"baz\\"'\\''' runas=macuser

    :param str password: Windows only. Required when specifying ``runas``. This
        parameter will be ignored on non-Windows platforms.

        .. versionadded:: 2016.3.0

    :param str group: Group to run command as. Not currently supported
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

                salt myminion cmd.run_stderr 'some command' env='{"FOO": "bar"}'

        .. note::
            When using environment variables on Window's, case-sensitivity
            matters, i.e. Window's uses `Path` as opposed to `PATH` for other
            systems.

    :param bool clean_env: Attempt to clean out all other shell environment
        variables and set only those provided in the 'env' argument to this
        function.

    :param str prepend_path: $PATH segment to prepend (trailing ':' not
        necessary) to $PATH

        .. versionadded:: 2018.3.0

    :param str template: If this setting is applied then the named templating
        engine will be used to render the downloaded file. Currently jinja,
        mako, and wempy are supported.

    :param bool rstrip: Strip all whitespace off the end of output before it is
        returned.

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

    :param int timeout: A timeout in seconds for the executed process to
        return.

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

        salt '*' cmd.run_stderr "ls -l | awk '/foo/{print \\$2}'"

    The template arg can be set to 'jinja' or another supported template
    engine to render the command arguments before execution.
    For example:

    .. code-block:: bash

        salt '*' cmd.run_stderr template=jinja "ls -l /tmp/{{grains.id}} | awk '/foo/{print \\$2}'"

    A string of standard input can be specified for the command to be run using
    the ``stdin`` parameter. This can be useful in cases where sensitive
    information must be read from standard input.

    .. code-block:: bash

        salt '*' cmd.run_stderr "grep f" stdin='one\\ntwo\\nthree\\nfour\\nfive\\n'
    """
    python_shell = _python_shell_default(python_shell, kwargs.get("__pub_jid", ""))
    ret = _run(
        cmd,
        runas=runas,
        group=group,
        cwd=cwd,
        stdin=stdin,
        shell=shell,
        python_shell=python_shell,
        env=env,
        clean_env=clean_env,
        prepend_path=prepend_path,
        template=template,
        rstrip=rstrip,
        umask=umask,
        output_encoding=output_encoding,
        output_loglevel=output_loglevel,
        log_callback=log_callback,
        timeout=timeout,
        reset_system_locale=reset_system_locale,
        ignore_retcode=ignore_retcode,
        use_vt=use_vt,
        saltenv=saltenv,
        password=password,
        success_retcodes=success_retcodes,
        success_stdout=success_stdout,
        success_stderr=success_stderr,
        **kwargs,
    )

    return ret["stderr"] if not hide_output else ""


def run_all(
    cmd,
    cwd=None,
    stdin=None,
    runas=None,
    group=None,
    shell=DEFAULT_SHELL,
    python_shell=None,
    env=None,
    clean_env=False,
    template=None,
    rstrip=True,
    umask=None,
    output_encoding=None,
    output_loglevel="debug",
    log_callback=None,
    hide_output=False,
    timeout=None,
    reset_system_locale=True,
    ignore_retcode=False,
    saltenv=None,
    use_vt=False,
    redirect_stderr=False,
    password=None,
    encoded_cmd=False,
    prepend_path=None,
    success_retcodes=None,
    success_stdout=None,
    success_stderr=None,
    **kwargs,
):
    """
    Execute the passed command and return a dict of return data

    :param str cmd: The command to run. ex: ``ls -lart /home``

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

        .. warning::

            For versions 2018.3.3 and above on macosx while using runas,
            to pass special characters to the command you need to escape
            the characters on the shell.

            Example:

            .. code-block:: bash

                cmd.run_all 'echo '\\''h=\\"baz\\"'\\''' runas=macuser

    :param str password: Windows only. Required when specifying ``runas``. This
        parameter will be ignored on non-Windows platforms.

        .. versionadded:: 2016.3.0

    :param str group: Group to run command as. Not currently supported
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

                salt myminion cmd.run_all 'some command' env='{"FOO": "bar"}'

        .. note::
            When using environment variables on Window's, case-sensitivity
            matters, i.e. Window's uses `Path` as opposed to `PATH` for other
            systems.

    :param bool clean_env: Attempt to clean out all other shell environment
        variables and set only those provided in the 'env' argument to this
        function.

    :param str prepend_path: $PATH segment to prepend (trailing ':' not
        necessary) to $PATH

        .. versionadded:: 2018.3.0

    :param str template: If this setting is applied then the named templating
        engine will be used to render the downloaded file. Currently jinja,
        mako, and wempy are supported.

    :param bool rstrip: Strip all whitespace off the end of output before it is
        returned.

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

    :param int timeout: A timeout in seconds for the executed process to
        return.

    :param bool use_vt: Use VT utils (saltstack) to stream the command output
        more interactively to the console and the logs. This is experimental.

    :param bool encoded_cmd: Specify if the supplied command is encoded.
        Only applies to shell 'powershell' and 'pwsh'.

        .. versionadded:: 2018.3.0

        Older versions of powershell seem to return raw xml data in the return.
        To avoid raw xml data in the return, prepend your command with the
        following before encoding:

        `$ProgressPreference='SilentlyContinue'; <your command>`

        The following powershell code block will encode the `Write-Output`
        command so that it will not have the raw xml data in the return:

        .. code-block:: powershell

            # target string
            $Command = '$ProgressPreference="SilentlyContinue"; Write-Output "hello"'

            # Convert to Base64 encoded string
            $Encoded = [convert]::ToBase64String([System.Text.encoding]::Unicode.GetBytes($command))

            Write-Output $Encoded

    :param bool redirect_stderr: If set to ``True``, then stderr will be
        redirected to stdout. This is helpful for cases where obtaining both
        the retcode and output is desired, but it is not desired to have the
        output separated into both stdout and stderr.

        .. versionadded:: 2015.8.2

    :param str password: Windows only. Required when specifying ``runas``. This
        parameter will be ignored on non-Windows platforms.

          .. versionadded:: 2016.3.0

    :param bool bg: If ``True``, run command in background and do not await or
        deliver its results

        .. versionadded:: 2016.3.6

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

        salt '*' cmd.run_all "ls -l | awk '/foo/{print \\$2}'"

    The template arg can be set to 'jinja' or another supported template
    engine to render the command arguments before execution.
    For example:

    .. code-block:: bash

        salt '*' cmd.run_all template=jinja "ls -l /tmp/{{grains.id}} | awk '/foo/{print \\$2}'"

    A string of standard input can be specified for the command to be run using
    the ``stdin`` parameter. This can be useful in cases where sensitive
    information must be read from standard input.

    .. code-block:: bash

        salt '*' cmd.run_all "grep f" stdin='one\\ntwo\\nthree\\nfour\\nfive\\n'
    """
    python_shell = _python_shell_default(python_shell, kwargs.get("__pub_jid", ""))
    stderr = subprocess.STDOUT if redirect_stderr else subprocess.PIPE
    ret = _run(
        cmd,
        runas=runas,
        group=group,
        cwd=cwd,
        stdin=stdin,
        stderr=stderr,
        shell=shell,
        python_shell=python_shell,
        env=env,
        clean_env=clean_env,
        prepend_path=prepend_path,
        template=template,
        rstrip=rstrip,
        umask=umask,
        output_encoding=output_encoding,
        output_loglevel=output_loglevel,
        log_callback=log_callback,
        timeout=timeout,
        reset_system_locale=reset_system_locale,
        ignore_retcode=ignore_retcode,
        saltenv=saltenv,
        use_vt=use_vt,
        password=password,
        encoded_cmd=encoded_cmd,
        success_retcodes=success_retcodes,
        success_stdout=success_stdout,
        success_stderr=success_stderr,
        **kwargs,
    )

    if hide_output:
        ret["stdout"] = ret["stderr"] = ""
    return ret


def retcode(
    cmd,
    cwd=None,
    stdin=None,
    runas=None,
    group=None,
    shell=DEFAULT_SHELL,
    python_shell=None,
    env=None,
    clean_env=False,
    template=None,
    umask=None,
    output_encoding=None,
    output_loglevel="debug",
    log_callback=None,
    timeout=None,
    reset_system_locale=True,
    ignore_retcode=False,
    saltenv=None,
    use_vt=False,
    password=None,
    success_retcodes=None,
    success_stdout=None,
    success_stderr=None,
    **kwargs,
):
    """
    Execute a shell command and return the command's return code.

    :param str cmd: The command to run. ex: ``ls -lart /home``

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

        .. warning::

            For versions 2018.3.3 and above on macosx while using runas,
            to pass special characters to the command you need to escape
            the characters on the shell.

            Example:

            .. code-block:: bash

                cmd.retcode 'echo '\\''h=\\"baz\\"'\\''' runas=macuser

    :param str password: Windows only. Required when specifying ``runas``. This
        parameter will be ignored on non-Windows platforms.

        .. versionadded:: 2016.3.0

    :param str group: Group to run command as. Not currently supported
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

                salt myminion cmd.retcode 'some command' env='{"FOO": "bar"}'

        .. note::
            When using environment variables on Window's, case-sensitivity
            matters, i.e. Window's uses `Path` as opposed to `PATH` for other
            systems.

    :param bool clean_env: Attempt to clean out all other shell environment
        variables and set only those provided in the 'env' argument to this
        function.

    :param str template: If this setting is applied then the named templating
        engine will be used to render the downloaded file. Currently jinja,
        mako, and wempy are supported.

    :param bool rstrip: Strip all whitespace off the end of output before it is
        returned.

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

    :param int timeout: A timeout in seconds for the executed process to return.

    :param bool use_vt: Use VT utils (saltstack) to stream the command output
      more interactively to the console and the logs. This is experimental.

    :rtype: int
    :rtype: None
    :returns: Return Code as an int or None if there was an exception.

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

        salt '*' cmd.retcode "file /bin/bash"

    The template arg can be set to 'jinja' or another supported template
    engine to render the command arguments before execution.
    For example:

    .. code-block:: bash

        salt '*' cmd.retcode template=jinja "file {{grains.pythonpath[0]}}/python"

    A string of standard input can be specified for the command to be run using
    the ``stdin`` parameter. This can be useful in cases where sensitive
    information must be read from standard input.

    .. code-block:: bash

        salt '*' cmd.retcode "grep f" stdin='one\\ntwo\\nthree\\nfour\\nfive\\n'
    """
    python_shell = _python_shell_default(python_shell, kwargs.get("__pub_jid", ""))

    ret = _run(
        cmd,
        runas=runas,
        group=group,
        cwd=cwd,
        stdin=stdin,
        stderr=subprocess.STDOUT,
        shell=shell,
        python_shell=python_shell,
        env=env,
        clean_env=clean_env,
        template=template,
        umask=umask,
        output_encoding=output_encoding,
        output_loglevel=output_loglevel,
        log_callback=log_callback,
        timeout=timeout,
        reset_system_locale=reset_system_locale,
        ignore_retcode=ignore_retcode,
        saltenv=saltenv,
        use_vt=use_vt,
        password=password,
        success_retcodes=success_retcodes,
        success_stdout=success_stdout,
        success_stderr=success_stderr,
        **kwargs,
    )
    return ret["retcode"]


def _retcode_quiet(
    cmd,
    cwd=None,
    stdin=None,
    runas=None,
    group=None,
    shell=DEFAULT_SHELL,
    python_shell=False,
    env=None,
    clean_env=False,
    template=None,
    umask=None,
    output_encoding=None,
    log_callback=None,
    timeout=None,
    reset_system_locale=True,
    ignore_retcode=False,
    saltenv=None,
    use_vt=False,
    password=None,
    success_retcodes=None,
    success_stdout=None,
    success_stderr=None,
    **kwargs,
):
    """
    Helper for running commands quietly for minion startup. Returns same as
    the retcode() function.
    """
    return retcode(
        cmd,
        cwd=cwd,
        stdin=stdin,
        runas=runas,
        group=group,
        shell=shell,
        python_shell=python_shell,
        env=env,
        clean_env=clean_env,
        template=template,
        umask=umask,
        output_encoding=output_encoding,
        output_loglevel="quiet",
        log_callback=log_callback,
        timeout=timeout,
        reset_system_locale=reset_system_locale,
        ignore_retcode=ignore_retcode,
        saltenv=saltenv,
        use_vt=use_vt,
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
    shell=DEFAULT_SHELL,
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

        salt '*' cmd.script salt://scripts/runme.sh
        salt '*' cmd.script salt://scripts/runme.sh 'arg1 arg2 "arg 3"'
        salt '*' cmd.script salt://scripts/windows_task.ps1 args=' -Input c:\\tmp\\infile.txt' shell='powershell'


    .. code-block:: bash

        salt '*' cmd.script salt://scripts/runme.sh stdin='one\\ntwo\\nthree\\nfour\\nfive\\n'
    """
    if saltenv is None:
        try:
            saltenv = __opts__.get("saltenv", "base")
        except NameError:
            saltenv = "base"
    python_shell = _python_shell_default(python_shell, kwargs.get("__pub_jid", ""))

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

    if "__env__" in kwargs:
        # "env" is not supported; Use "saltenv".
        kwargs.pop("__env__")

    win_cwd = False
    if salt.utils.platform.is_windows() and runas and cwd is None:
        # Create a temp working directory
        cwd = tempfile.mkdtemp(dir=__opts__["cachedir"])
        win_cwd = True
        salt.utils.win_dacl.set_permissions(
            obj_name=cwd, principal=runas, permissions="full_control"
        )

    path = salt.utils.files.mkstemp(
        dir=cwd, suffix=os.path.splitext(salt.utils.url.split_env(source)[0])[1]
    )

    if template:
        if "pillarenv" in kwargs or "pillar" in kwargs:
            pillarenv = kwargs.get("pillarenv", __opts__.get("pillarenv"))
            kwargs["pillar"] = _gather_pillar(pillarenv, kwargs.get("pillar"))
        fn_ = __salt__["cp.get_template"](source, path, template, saltenv, **kwargs)
        if not fn_:
            _cleanup_tempfile(path)
            # If a temp working directory was created (Windows), let's remove that
            if win_cwd:
                _cleanup_tempfile(cwd)
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
            # If a temp working directory was created (Windows), let's remove that
            if win_cwd:
                _cleanup_tempfile(cwd)
            return {
                "pid": 0,
                "retcode": 1,
                "stdout": "",
                "stderr": "",
                "cache_error": True,
            }
        shutil.copyfile(fn_, path)
    if not salt.utils.platform.is_windows():
        os.chmod(path, 320)
        os.chown(path, __salt__["file.user_to_uid"](runas), -1)

    if salt.utils.platform.is_windows() and shell.lower() != "powershell":
        cmd_path = _cmd_quote(path, escape=False)
    else:
        cmd_path = _cmd_quote(path)

    ret = _run(
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
        use_vt=use_vt,
        bg=bg,
        password=password,
        success_retcodes=success_retcodes,
        success_stdout=success_stdout,
        success_stderr=success_stderr,
        **kwargs,
    )
    _cleanup_tempfile(path)
    # If a temp working directory was created (Windows), let's remove that
    if win_cwd:
        _cleanup_tempfile(cwd)

    if hide_output:
        ret["stdout"] = ret["stderr"] = ""
    return ret


def script_retcode(
    source,
    args=None,
    cwd=None,
    stdin=None,
    runas=None,
    group=None,
    shell=DEFAULT_SHELL,
    python_shell=None,
    env=None,
    template="jinja",
    umask=None,
    timeout=None,
    reset_system_locale=True,
    saltenv=None,
    output_encoding=None,
    output_loglevel="debug",
    log_callback=None,
    use_vt=False,
    password=None,
    success_retcodes=None,
    success_stdout=None,
    success_stderr=None,
    **kwargs,
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
        **kwargs,
    )["retcode"]


def which(cmd):
    """
    Returns the path of an executable available on the minion, None otherwise

    CLI Example:

    .. code-block:: bash

        salt '*' cmd.which cat
    """
    return salt.utils.path.which(cmd)


def which_bin(cmds):
    """
    Returns the first command found in a list of commands

    CLI Example:

    .. code-block:: bash

        salt '*' cmd.which_bin '[pip2, pip, pip-python]'
    """
    return salt.utils.path.which_bin(cmds)


def has_exec(cmd):
    """
    Returns true if the executable is available on the minion, false otherwise

    CLI Example:

    .. code-block:: bash

        salt '*' cmd.has_exec cat
    """
    return which(cmd) is not None


def exec_code(lang, code, cwd=None, args=None, **kwargs):
    """
    Pass in two strings, the first naming the executable language, aka -
    python2, python3, ruby, perl, lua, etc. the second string containing
    the code you wish to execute. The stdout will be returned.

    All parameters from :mod:`cmd.run_all <salt.modules.cmdmod.run_all>` except python_shell can be used.

    CLI Example:

    .. code-block:: bash

        salt '*' cmd.exec_code ruby 'puts "cheese"'
        salt '*' cmd.exec_code ruby 'puts "cheese"' args='["arg1", "arg2"]' env='{"FOO": "bar"}'
    """
    return exec_code_all(lang, code, cwd, args, **kwargs)["stdout"]


def exec_code_all(lang, code, cwd=None, args=None, **kwargs):
    """
    Pass in two strings, the first naming the executable language, aka -
    python2, python3, ruby, perl, lua, etc. the second string containing
    the code you wish to execute. All cmd artifacts (stdout, stderr, retcode, pid)
    will be returned.

    All parameters from :mod:`cmd.run_all <salt.modules.cmdmod.run_all>` except python_shell can be used.

    CLI Example:

    .. code-block:: bash

        salt '*' cmd.exec_code_all ruby 'puts "cheese"'
        salt '*' cmd.exec_code_all ruby 'puts "cheese"' args='["arg1", "arg2"]' env='{"FOO": "bar"}'
    """
    powershell = lang.lower().startswith("powershell")

    if powershell:
        codefile = salt.utils.files.mkstemp(suffix=".ps1")
    else:
        codefile = salt.utils.files.mkstemp()

    with salt.utils.files.fopen(codefile, "w+t", binary=False) as fp_:
        fp_.write(salt.utils.stringutils.to_str(code))

    if powershell:
        cmd = [lang, "-File", codefile]
    else:
        cmd = [lang, codefile]

    if isinstance(args, str):
        cmd.append(args)
    elif isinstance(args, list):
        cmd += args

    def _cleanup_tempfile(path):
        try:
            __salt__["file.remove"](path)
        except (SaltInvocationError, CommandExecutionError) as exc:
            log.error(
                "cmd.exec_code_all: Unable to clean tempfile '%s': %s",
                path,
                exc,
                exc_info_on_loglevel=logging.DEBUG,
            )

    runas = kwargs.get("runas")
    if runas is not None:
        if not salt.utils.platform.is_windows():
            os.chown(codefile, __salt__["file.user_to_uid"](runas), -1)

    ret = run_all(cmd, cwd=cwd, python_shell=False, **kwargs)
    _cleanup_tempfile(codefile)
    return ret


def tty(device, echo=""):
    """
    Echo a string to a specific tty

    CLI Example:

    .. code-block:: bash

        salt '*' cmd.tty tty0 'This is a test'
        salt '*' cmd.tty pts3 'This is a test'
    """
    if device.startswith("tty"):
        teletype = f"/dev/{device}"
    elif device.startswith("pts"):
        teletype = "/dev/{}".format(device.replace("pts", "pts/"))
    else:
        return {"Error": "The specified device is not a valid TTY"}
    try:
        with salt.utils.files.fopen(teletype, "wb") as tty_device:
            tty_device.write(salt.utils.stringutils.to_bytes(echo))
        return {"Success": f"Message was successfully echoed to {teletype}"}
    except OSError:
        return {"Error": f"Echoing to {teletype} returned error"}


def run_chroot(
    root,
    cmd,
    cwd=None,
    stdin=None,
    runas=None,
    group=None,
    shell=DEFAULT_SHELL,
    python_shell=True,
    binds=None,
    env=None,
    clean_env=False,
    template=None,
    rstrip=True,
    umask=None,
    output_encoding=None,
    output_loglevel="quiet",
    log_callback=None,
    hide_output=False,
    timeout=None,
    reset_system_locale=True,
    ignore_retcode=False,
    saltenv=None,
    use_vt=False,
    bg=False,
    success_retcodes=None,
    success_stdout=None,
    success_stderr=None,
    **kwargs,
):
    """
    .. versionadded:: 2014.7.0

    This function runs :mod:`cmd.run_all <salt.modules.cmdmod.run_all>` wrapped
    within a chroot, with dev and proc mounted in the chroot

    :param str root: Path to the root of the jail to use.

    :param str stdin: A string of standard input can be specified for
        the command to be run using the ``stdin`` parameter. This can
        be useful in cases where sensitive information must be read
        from standard input.:

    :param str runas: User to run script as.

    :param str group: Group to run script as.

    :param str shell: Shell to execute under. Defaults to the system
        default shell.

    :param str cmd: The command to run. ex: ``ls -lart /home``

    :param str cwd: The directory from which to execute the command. Defaults
        to the home directory of the user specified by ``runas`` (or the user
        under which Salt is running if ``runas`` is not specified).

    :parar str stdin: A string of standard input can be specified for the
        command to be run using the ``stdin`` parameter. This can be useful in
        cases where sensitive information must be read from standard input.

    :param str runas: Specify an alternate user to run the command. The default
        behavior is to run as the user under which Salt is running. If running
        on a Windows minion you must also use the ``password`` argument, and
        the target user account must be in the Administrators group.

    :param str shell: Specify an alternate shell. Defaults to the system's
        default shell.

    :param bool python_shell: If False, let python handle the positional
        arguments. Set to True to use shell features, such as pipes or
        redirection.

    :param list binds: List of directories that will be exported inside
        the chroot with the bind option.

        .. versionadded:: 3000

    :param dict env: Environment variables to be set prior to execution.

        .. note::
            When passing environment variables on the CLI, they should be
            passed as the string representation of a dictionary.

            .. code-block:: bash

                salt myminion cmd.run_chroot 'some command' env='{"FOO": "bar"}'

        .. note::
            When using environment variables on Window's, case-sensitivity
            matters, i.e. Window's uses `Path` as opposed to `PATH` for other
            systems.

    :param dict clean_env: Attempt to clean out all other shell environment
        variables and set only those provided in the 'env' argument to this
        function.

    :param str template: If this setting is applied then the named templating
        engine will be used to render the downloaded file. Currently jinja,
        mako, and wempy are supported.

    :param bool rstrip: Strip all whitespace off the end of output
        before it is returned.

    :param str umask: The umask (in octal) to use when running the
         command.

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

    :param int timeout:
        A timeout in seconds for the executed process to return.

    :param bool use_vt:
        Use VT utils (saltstack) to stream the command output more
        interactively to the console and the logs. This is experimental.

    :param success_retcodes: This parameter will allow a list of
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

    CLI Example:

    .. code-block:: bash

        salt '*' cmd.run_chroot /var/lib/lxc/container_name/rootfs 'sh /tmp/bootstrap.sh'
    """
    __salt__["mount.mount"](os.path.join(root, "dev"), "devtmpfs", fstype="devtmpfs")
    __salt__["mount.mount"](os.path.join(root, "proc"), "proc", fstype="proc")
    __salt__["mount.mount"](os.path.join(root, "sys"), "sysfs", fstype="sysfs")

    binds = binds if binds else []
    for bind_exported in binds:
        bind_exported_to = os.path.relpath(bind_exported, os.path.sep)
        bind_exported_to = os.path.join(root, bind_exported_to)
        __salt__["mount.mount"](bind_exported_to, bind_exported, opts="default,bind")

    # Execute chroot routine
    sh_ = "/bin/sh"
    if os.path.isfile(os.path.join(root, "bin/bash")):
        sh_ = "/bin/bash"

    if isinstance(cmd, (list, tuple)):
        cmd = " ".join([str(i) for i in cmd])

    # If runas and group are provided, we expect that the user lives
    # inside the chroot, not outside.
    if runas:
        userspec = "--userspec {}:{}".format(runas, group if group else "")
    else:
        userspec = ""

    cmd = f"chroot {userspec} {root} {sh_} -c {_cmd_quote(cmd)}"

    run_func = __context__.pop("cmd.run_chroot.func", run_all)

    ret = run_func(
        cmd,
        cwd=cwd,
        stdin=stdin,
        shell=shell,
        python_shell=python_shell,
        env=env,
        clean_env=clean_env,
        template=template,
        rstrip=rstrip,
        umask=umask,
        output_encoding=output_encoding,
        output_loglevel=output_loglevel,
        log_callback=log_callback,
        timeout=timeout,
        reset_system_locale=reset_system_locale,
        ignore_retcode=ignore_retcode,
        saltenv=saltenv,
        pillarenv=kwargs.get("pillarenv"),
        pillar=kwargs.get("pillar"),
        use_vt=use_vt,
        success_retcodes=success_retcodes,
        success_stdout=success_stdout,
        success_stderr=success_stderr,
        bg=bg,
    )

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
        log.error(
            "Processes running in chroot could not be killed, "
            "filesystem will remain mounted"
        )

    for bind_exported in binds:
        bind_exported_to = os.path.relpath(bind_exported, os.path.sep)
        bind_exported_to = os.path.join(root, bind_exported_to)
        __salt__["mount.umount"](bind_exported_to)

    __salt__["mount.umount"](os.path.join(root, "sys"))
    __salt__["mount.umount"](os.path.join(root, "proc"))
    __salt__["mount.umount"](os.path.join(root, "dev"))
    if hide_output:
        ret["stdout"] = ret["stderr"] = ""
    return ret


def _is_valid_shell(shell):
    """
    Attempts to search for valid shells on a system and
    see if a given shell is in the list
    """
    if salt.utils.platform.is_windows():
        return True  # Don't even try this for Windows
    shells = "/etc/shells"
    available_shells = []
    if os.path.exists(shells):
        try:
            with salt.utils.files.fopen(shells, "r") as shell_fp:
                lines = [
                    salt.utils.stringutils.to_unicode(x)
                    for x in shell_fp.read().splitlines()
                ]
            for line in lines:
                if line.startswith("#"):
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
    """
    Lists the valid shells on this system via the /etc/shells file

    .. versionadded:: 2015.5.0

    CLI Example:

    .. code-block:: bash

        salt '*' cmd.shells
    """
    shells_fn = "/etc/shells"
    ret = []
    if os.path.exists(shells_fn):
        try:
            with salt.utils.files.fopen(shells_fn, "r") as shell_fp:
                lines = [
                    salt.utils.stringutils.to_unicode(x)
                    for x in shell_fp.read().splitlines()
                ]
            for line in lines:
                line = line.strip()
                if line.startswith("#"):
                    continue
                elif not line:
                    continue
                else:
                    ret.append(line)
        except OSError:
            log.error("File '%s' was not found", shells_fn)
    return ret


def shell_info(shell, list_modules=False):
    """
    .. versionadded:: 2016.11.0

    Provides information about a shell or script languages which often use
    ``#!``. The values returned are dependent on the shell or scripting
    languages all return the ``installed``, ``path``, ``version``,
    ``version_raw``

    Args:
        shell (str): Name of the shell. Support shells/script languages include
        bash, cmd, perl, php, powershell, python, ruby and zsh

        list_modules (bool): True to list modules available to the shell.
        Currently only lists powershell modules.

    Returns:
        dict: A dictionary of information about the shell

    .. code-block:: python

        {'version': '<2 or 3 numeric components dot-separated>',
         'version_raw': '<full version string>',
         'path': '<full path to binary>',
         'installed': <True, False or None>,
         '<attribute>': '<attribute value>'}

    .. note::
        - ``installed`` is always returned, if ``None`` or ``False`` also
          returns error and may also return ``stdout`` for diagnostics.
        - ``version`` is for use in determine if a shell/script language has a
          particular feature set, not for package management.
        - The shell must be within the executable search path.

    CLI Example:

    .. code-block:: bash

        salt '*' cmd.shell_info bash
        salt '*' cmd.shell_info powershell

    :codeauthor: Damon Atkins <https://github.com/damon-atkins>
    """
    regex_shells = {
        "bash": [r"version (\d\S*)", "bash", "--version"],
        "bash-test-error": [
            r"versioZ ([-\w.]+)",
            "bash",
            "--version",
        ],  # used to test an error result
        "bash-test-env": [
            r"(HOME=.*)",
            "bash",
            "-c",
            "declare",
        ],  # used to test an error result
        "zsh": [r"^zsh (\d\S*)", "zsh", "--version"],
        "tcsh": [r"^tcsh (\d\S*)", "tcsh", "--version"],
        "cmd": [r"Version ([\d.]+)", "cmd.exe", "/C", "ver"],
        "powershell": [
            r"PSVersion\s+(\d\S*)",
            "powershell",
            "-NonInteractive",
            "$PSVersionTable",
        ],
        "perl": [r"^(\d\S*)", "perl", "-e", 'printf "%vd\n", $^V;'],
        "python": [r"^Python (\d\S*)", "python", "-V"],
        "ruby": [r"^ruby (\d\S*)", "ruby", "-v"],
        "php": [r"^PHP (\d\S*)", "php", "-v"],
    }
    # Ensure ret['installed'] always as a value of True, False or None (not sure)
    ret = {"installed": False}
    if salt.utils.platform.is_windows() and shell == "powershell":
        pw_keys = salt.utils.win_reg.list_keys(
            hive="HKEY_LOCAL_MACHINE", key="Software\\Microsoft\\PowerShell"
        )
        pw_keys.sort(key=int)
        if not pw_keys:
            return {
                "error": (
                    "Unable to locate 'powershell' Reason: Cannot be found in registry."
                ),
                "installed": False,
            }
        for reg_ver in pw_keys:
            install_data = salt.utils.win_reg.read_value(
                hive="HKEY_LOCAL_MACHINE",
                key=f"Software\\Microsoft\\PowerShell\\{reg_ver}",
                vname="Install",
            )
            if (
                install_data.get("vtype") == "REG_DWORD"
                and install_data.get("vdata") == 1
            ):
                details = salt.utils.win_reg.list_values(
                    hive="HKEY_LOCAL_MACHINE",
                    key="Software\\Microsoft\\PowerShell\\{}\\PowerShellEngine".format(
                        reg_ver
                    ),
                )

                # reset data, want the newest version details only as powershell
                # is backwards compatible
                ret = {}

                # if all goes well this will become True
                ret["installed"] = None
                ret["path"] = which("powershell.exe")
                for attribute in details:
                    if attribute["vname"].lower() == "(default)":
                        continue
                    elif attribute["vname"].lower() == "powershellversion":
                        ret["psversion"] = attribute["vdata"]
                        ret["version_raw"] = attribute["vdata"]
                    elif attribute["vname"].lower() == "runtimeversion":
                        ret["crlversion"] = attribute["vdata"]
                        if ret["crlversion"][0].lower() == "v":
                            ret["crlversion"] = ret["crlversion"][1::]
                    elif attribute["vname"].lower() == "pscompatibleversion":
                        # reg attribute does not end in s, the powershell
                        # attribute does
                        ret["pscompatibleversions"] = (
                            attribute["vdata"].replace(" ", "").split(",")
                        )
                    else:
                        # keys are lower case as python is case sensitive the
                        # registry is not
                        ret[attribute["vname"].lower()] = attribute["vdata"]
    else:
        if shell not in regex_shells:
            return {
                "error": (
                    "Salt does not know how to get the version number for {}".format(
                        shell
                    )
                ),
                "installed": None,
            }
        shell_data = regex_shells[shell]
        pattern = shell_data.pop(0)
        # We need to make sure HOME set, so shells work correctly
        # salt-call will general have home set, the salt-minion service may not
        # We need to assume ports of unix shells to windows will look after
        # themselves in setting HOME as they do it in many different ways
        if salt.utils.platform.is_windows():
            import nt

            newenv = nt.environ
        else:
            newenv = os.environ

        if ("HOME" not in newenv) and (not salt.utils.platform.is_windows()):
            newenv["HOME"] = os.path.expanduser("~")
            log.debug("HOME environment set to %s", newenv["HOME"])
        try:
            proc = salt.utils.timed_subprocess.TimedProc(
                shell_data,
                stdin=None,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=10,
                env=newenv,
            )
        except OSError as exc:
            return {
                "error": "Unable to run command '{}' Reason: {}".format(
                    " ".join(shell_data), exc
                ),
                "installed": False,
            }
        try:
            proc.run()
        except TimedProcTimeoutError as exc:
            return {
                "error": "Unable to run command '{}' Reason: Timed out.".format(
                    " ".join(shell_data)
                ),
                "installed": False,
            }

        ret["path"] = which(shell_data[0])
        pattern_result = re.search(pattern, proc.stdout, flags=re.IGNORECASE)
        # only set version if we find it, so code later on can deal with it
        if pattern_result:
            ret["version_raw"] = pattern_result.group(1)

    if "version_raw" in ret:
        version_results = re.match(r"(\d[\d.]*)", ret["version_raw"])
        if version_results:
            ret["installed"] = True
            ver_list = version_results.group(1).split(".")[:3]
            if len(ver_list) == 1:
                ver_list.append("0")
            ret["version"] = ".".join(ver_list[:3])
    else:
        ret["installed"] = None  # Have an unexpected result

    # Get a list of the PowerShell modules which are potentially available
    # to be imported
    if shell == "powershell" and ret["installed"] and list_modules:
        ret["modules"] = salt.utils.powershell.get_modules()

    if "version" not in ret:
        ret["error"] = (
            "The version regex pattern for shell {}, could not "
            "find the version string".format(shell)
        )
        ret["stdout"] = proc.stdout  # include stdout so they can see the issue
        log.error(ret["error"])

    return ret


def powershell(
    cmd,
    cwd=None,
    stdin=None,
    runas=None,
    shell="powershell",
    env=None,
    clean_env=False,
    template=None,
    rstrip=True,
    umask=None,
    output_encoding=None,
    output_loglevel="debug",
    hide_output=False,
    timeout=None,
    reset_system_locale=True,
    ignore_retcode=False,
    saltenv=None,
    use_vt=False,
    password=None,
    depth=None,
    encode_cmd=False,
    success_retcodes=None,
    success_stdout=None,
    success_stderr=None,
    **kwargs,
):
    """
    Execute the passed PowerShell command and return the output as a dictionary.

    Other ``cmd.*`` functions (besides ``cmd.powershell_all``)
    return the raw text output of the command. This
    function appends ``| ConvertTo-JSON`` to the command and then parses the
    JSON into a Python dictionary. If you want the raw textual result of your
    PowerShell command you should use ``cmd.run`` with the ``shell=powershell``
    option.

    For example:

    .. code-block:: bash

        salt '*' cmd.run '$PSVersionTable.CLRVersion' shell=powershell
        salt '*' cmd.run 'Get-NetTCPConnection' shell=powershell

    .. versionadded:: 2016.3.0

    .. warning::

        This passes the cmd argument directly to PowerShell
        without any further processing! Be absolutely sure that you
        have properly sanitized the command passed to this function
        and do not use untrusted inputs.

    In addition to the normal ``cmd.run`` parameters, this command offers the
    ``depth`` parameter to change the Windows default depth for the
    ``ConvertTo-JSON`` powershell command. The Windows default is 2. If you need
    more depth, set that here.

    .. note::
        For some commands, setting the depth to a value greater than 4 greatly
        increases the time it takes for the command to return and in many cases
        returns useless data.

    :param str cmd: The powershell command to run.

    :param str cwd: The directory from which to execute the command. Defaults
        to the home directory of the user specified by ``runas`` (or the user
        under which Salt is running if ``runas`` is not specified).

    :param str stdin: A string of standard input can be specified for the
      command to be run using the ``stdin`` parameter. This can be useful in cases
      where sensitive information must be read from standard input.

    :param str runas: Specify an alternate user to run the command. The default
        behavior is to run as the user under which Salt is running. If running
        on a Windows minion you must also use the ``password`` argument, and
        the target user account must be in the Administrators group.

    :param str password: Windows only. Required when specifying ``runas``. This
      parameter will be ignored on non-Windows platforms.

      .. versionadded:: 2016.3.0

    :param str shell: Specify an alternate shell. Defaults to "powershell". Can
        also use "pwsh" for powershell core if present on the system

    :param bool python_shell: If False, let python handle the positional
      arguments. Set to True to use shell features, such as pipes or
      redirection.

    :param dict env: Environment variables to be set prior to execution.

        .. note::
            When passing environment variables on the CLI, they should be
            passed as the string representation of a dictionary.

            .. code-block:: bash

                salt myminion cmd.powershell 'some command' env='{"FOO": "bar"}'

        .. note::
            When using environment variables on Window's, case-sensitivity
            matters, i.e. Window's uses `Path` as opposed to `PATH` for other
            systems.

    :param bool clean_env: Attempt to clean out all other shell environment
        variables and set only those provided in the 'env' argument to this
        function.

    :param str template: If this setting is applied then the named templating
        engine will be used to render the downloaded file. Currently jinja,
        mako, and wempy are supported.

    :param bool rstrip: Strip all whitespace off the end of output before it is
        returned.

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

    :param int timeout: A timeout in seconds for the executed process to return.

    :param bool use_vt: Use VT utils (saltstack) to stream the command output
        more interactively to the console and the logs. This is experimental.

    :param bool reset_system_locale: Resets the system locale

    :param str saltenv: The salt environment to use. Default is 'base'

    :param int depth: The number of levels of contained objects to be included.
        Default is 2. Values greater than 4 seem to greatly increase the time
        it takes for the command to complete for some commands. eg: ``dir``

        .. versionadded:: 2016.3.4

    :param bool encode_cmd: Encode the command before executing. Use in cases
        where characters may be dropped or incorrectly converted when executed.
        Default is False.

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

    :returns:
        :dict: A dictionary of data returned by the powershell command.

    CLI Example:

    .. code-block:: powershell

        salt '*' cmd.powershell "$PSVersionTable.CLRVersion"
    """
    if shell not in ["powershell", "pwsh"]:
        raise CommandExecutionError(
            "Must specify a valid powershell binary. Must be 'powershell' or 'pwsh'"
        )

    if "python_shell" in kwargs:
        python_shell = kwargs.pop("python_shell")
    else:
        python_shell = True

    # Append PowerShell Object formatting
    # ConvertTo-JSON is only available on PowerShell 3.0 and later
    psversion = shell_info("powershell")["psversion"]
    if salt.utils.versions.version_cmp(psversion, "2.0") == 1:
        cmd += " | ConvertTo-JSON"
        if depth is not None:
            cmd += f" -Depth {depth}"

    # Put the whole command inside a try / catch block
    # Some errors in PowerShell are not "Terminating Errors" and will not be
    # caught in a try/catch block. For example, the `Get-WmiObject` command will
    # often return a "Non Terminating Error". To fix this, make sure
    # `-ErrorAction Stop` is set in the powershell command
    cmd = "try {" + cmd + '} catch { "{}" }'

    if encode_cmd:
        # Convert the cmd to UTF-16LE without a BOM and base64 encode.
        # Just base64 encoding UTF-8 or including a BOM is not valid.
        log.debug("Encoding PowerShell command '%s'", cmd)
        cmd = f"$ProgressPreference='SilentlyContinue'; {cmd}"
        cmd_utf16 = cmd.encode("utf-16-le")
        cmd = base64.standard_b64encode(cmd_utf16)
        cmd = salt.utils.stringutils.to_str(cmd)
        encoded_cmd = True
    else:
        encoded_cmd = False

    # Retrieve the response, while overriding shell with 'powershell'
    response = run(
        cmd,
        cwd=cwd,
        stdin=stdin,
        runas=runas,
        shell=shell,
        env=env,
        clean_env=clean_env,
        template=template,
        rstrip=rstrip,
        umask=umask,
        output_encoding=output_encoding,
        output_loglevel=output_loglevel,
        hide_output=hide_output,
        timeout=timeout,
        reset_system_locale=reset_system_locale,
        ignore_retcode=ignore_retcode,
        saltenv=saltenv,
        use_vt=use_vt,
        python_shell=python_shell,
        password=password,
        encoded_cmd=encoded_cmd,
        success_retcodes=success_retcodes,
        success_stdout=success_stdout,
        success_stderr=success_stderr,
        **kwargs,
    )

    # Sometimes Powershell returns an empty string, which isn't valid JSON
    if response == "":
        response = "{}"
    try:
        return salt.utils.json.loads(response)
    except Exception:  # pylint: disable=broad-except
        log.error("Error converting PowerShell JSON return", exc_info=True)
        return {}


def powershell_all(
    cmd,
    cwd=None,
    stdin=None,
    runas=None,
    shell="powershell",
    env=None,
    clean_env=False,
    template=None,
    rstrip=True,
    umask=None,
    output_encoding=None,
    output_loglevel="debug",
    quiet=False,
    timeout=None,
    reset_system_locale=True,
    ignore_retcode=False,
    saltenv=None,
    use_vt=False,
    password=None,
    depth=None,
    encode_cmd=False,
    force_list=False,
    success_retcodes=None,
    success_stdout=None,
    success_stderr=None,
    **kwargs,
):
    """
    Execute the passed PowerShell command and return a dictionary with a result
    field representing the output of the command, as well as other fields
    showing us what the PowerShell invocation wrote to ``stderr``, the process
    id, and the exit code of the invocation.

    This function appends ``| ConvertTo-JSON`` to the command before actually
    invoking powershell.

    An unquoted empty string is not valid JSON, but it's very normal for the
    Powershell output to be exactly that. Therefore, we do not attempt to parse
    empty Powershell output (which would result in an exception). Instead we
    treat this as a special case and one of two things will happen:

    - If the value of the ``force_list`` parameter is ``True``, then the
      ``result`` field of the return dictionary will be an empty list.

    - If the value of the ``force_list`` parameter is ``False``, then the
      return dictionary **will not have a result key added to it**. We aren't
      setting ``result`` to ``None`` in this case, because ``None`` is the
      Python representation of "null" in JSON. (We likewise can't use ``False``
      for the equivalent reason.)

    If Powershell's output is not an empty string and Python cannot parse its
    content, then a ``CommandExecutionError`` exception will be raised.

    If Powershell's output is not an empty string, Python is able to parse its
    content, and the type of the resulting Python object is other than ``list``
    then one of two things will happen:

    - If the value of the ``force_list`` parameter is ``True``, then the
      ``result`` field will be a singleton list with the Python object as its
      sole member.

    - If the value of the ``force_list`` parameter is ``False``, then the value
      of ``result`` will be the unmodified Python object.

    If Powershell's output is not an empty string, Python is able to parse its
    content, and the type of the resulting Python object is ``list``, then the
    value of ``result`` will be the unmodified Python object. The
    ``force_list`` parameter has no effect in this case.

    .. note::
         An example of why the ``force_list`` parameter is useful is as
         follows: The Powershell command ``dir x | Convert-ToJson`` results in

         - no output when x is an empty directory.
         - a dictionary object when x contains just one item.
         - a list of dictionary objects when x contains multiple items.

         By setting ``force_list`` to ``True`` we will always end up with a
         list of dictionary items, representing files, no matter how many files
         x contains.  Conversely, if ``force_list`` is ``False``, we will end
         up with no ``result`` key in our return dictionary when x is an empty
         directory, and a dictionary object when x contains just one file.

    If you want a similar function but with a raw textual result instead of a
    Python dictionary, you should use ``cmd.run_all`` in combination with
    ``shell=powershell``.

    The remaining fields in the return dictionary are described in more detail
    in the ``Returns`` section.

    Example:

    .. code-block:: bash

        salt '*' cmd.run_all '$PSVersionTable.CLRVersion' shell=powershell
        salt '*' cmd.run_all 'Get-NetTCPConnection' shell=powershell

    .. versionadded:: 2018.3.0

    .. warning::

        This passes the cmd argument directly to PowerShell without any further
        processing! Be absolutely sure that you have properly sanitized the
        command passed to this function and do not use untrusted inputs.

    In addition to the normal ``cmd.run`` parameters, this command offers the
    ``depth`` parameter to change the Windows default depth for the
    ``ConvertTo-JSON`` powershell command. The Windows default is 2. If you need
    more depth, set that here.

    .. note::
        For some commands, setting the depth to a value greater than 4 greatly
        increases the time it takes for the command to return and in many cases
        returns useless data.

    :param str cmd: The powershell command to run.

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

    :param str shell: Specify an alternate shell. Defaults to "powershell". Can
        also use "pwsh" for powershell core if present on the system

    :param bool python_shell: If False, let python handle the positional
        arguments. Set to True to use shell features, such as pipes or
        redirection.

    :param dict env: Environment variables to be set prior to execution.

        .. note::
            When passing environment variables on the CLI, they should be
            passed as the string representation of a dictionary.

            .. code-block:: bash

                salt myminion cmd.powershell_all 'some command' env='{"FOO": "bar"}'

        .. note::
            When using environment variables on Window's, case-sensitivity
            matters, i.e. Window's uses `Path` as opposed to `PATH` for other
            systems.

    :param bool clean_env: Attempt to clean out all other shell environment
        variables and set only those provided in the 'env' argument to this
        function.

    :param str template: If this setting is applied then the named templating
        engine will be used to render the downloaded file. Currently jinja,
        mako, and wempy are supported.

    :param bool rstrip: Strip all whitespace off the end of output before it is
        returned.

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

    :param int timeout: A timeout in seconds for the executed process to
        return.

    :param bool use_vt: Use VT utils (saltstack) to stream the command output
        more interactively to the console and the logs. This is experimental.

    :param bool reset_system_locale: Resets the system locale

    :param bool ignore_retcode: If the exit code of the command is nonzero,
        this is treated as an error condition, and the output from the command
        will be logged to the minion log. However, there are some cases where
        programs use the return code for signaling and a nonzero exit code
        doesn't necessarily mean failure. Pass this argument as ``True`` to
        skip logging the output if the command has a nonzero exit code.

    :param str saltenv: The salt environment to use. Default is 'base'

    :param int depth: The number of levels of contained objects to be included.
        Default is 2. Values greater than 4 seem to greatly increase the time
        it takes for the command to complete for some commands. eg: ``dir``

    :param bool encode_cmd: Encode the command before executing. Use in cases
        where characters may be dropped or incorrectly converted when executed.
        Default is False.

    :param bool force_list: The purpose of this parameter is described in the
        preamble of this function's documentation. Default value is False.

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

    :return: A dictionary with the following entries:

        result
            For a complete description of this field, please refer to this
            function's preamble. **This key will not be added to the dictionary
            when force_list is False and Powershell's output is the empty
            string.**
        stderr
            What the PowerShell invocation wrote to ``stderr``.
        pid
            The process id of the PowerShell invocation
        retcode
            This is the exit code of the invocation of PowerShell.
            If the final execution status (in PowerShell) of our command
            (with ``| ConvertTo-JSON`` appended) is ``False`` this should be non-0.
            Likewise if PowerShell exited with ``$LASTEXITCODE`` set to some
            non-0 value, then ``retcode`` will end up with this value.

    :rtype: dict

    CLI Example:

    .. code-block:: bash

        salt '*' cmd.powershell_all "$PSVersionTable.CLRVersion"

    CLI Example:

    .. code-block:: bash

        salt '*' cmd.powershell_all "dir mydirectory" force_list=True
    """
    if shell not in ["powershell", "pwsh"]:
        raise CommandExecutionError(
            "Must specify a valid powershell binary. Must be 'powershell' or 'pwsh'"
        )

    if "python_shell" in kwargs:
        python_shell = kwargs.pop("python_shell")
    else:
        python_shell = True

    # Append PowerShell Object formatting
    cmd += " | ConvertTo-JSON"
    if depth is not None:
        cmd += f" -Depth {depth}"

    if encode_cmd:
        # Convert the cmd to UTF-16LE without a BOM and base64 encode.
        # Just base64 encoding UTF-8 or including a BOM is not valid.
        log.debug("Encoding PowerShell command '%s'", cmd)
        cmd = f"$ProgressPreference='SilentlyContinue'; {cmd}"
        cmd_utf16 = cmd.encode("utf-16-le")
        cmd = base64.standard_b64encode(cmd_utf16)
        cmd = salt.utils.stringutils.to_str(cmd)
        encoded_cmd = True
    else:
        encoded_cmd = False

    # Retrieve the response, while overriding shell with 'powershell'
    response = run_all(
        cmd,
        cwd=cwd,
        stdin=stdin,
        runas=runas,
        shell=shell,
        env=env,
        clean_env=clean_env,
        template=template,
        rstrip=rstrip,
        umask=umask,
        output_encoding=output_encoding,
        output_loglevel=output_loglevel,
        quiet=quiet,
        timeout=timeout,
        reset_system_locale=reset_system_locale,
        ignore_retcode=ignore_retcode,
        saltenv=saltenv,
        use_vt=use_vt,
        python_shell=python_shell,
        password=password,
        encoded_cmd=encoded_cmd,
        success_retcodes=success_retcodes,
        success_stdout=success_stdout,
        success_stderr=success_stderr,
        **kwargs,
    )
    stdoutput = response["stdout"]

    # if stdoutput is the empty string and force_list is True we return an empty list
    # Otherwise we return response with no result key
    if not stdoutput:
        response.pop("stdout")
        if force_list:
            response["result"] = []
        return response

    # If we fail to parse stdoutput we will raise an exception
    try:
        result = salt.utils.json.loads(stdoutput)
    except Exception:  # pylint: disable=broad-except
        err_msg = "cmd.powershell_all " + "cannot parse the Powershell output."
        response["cmd"] = cmd
        raise CommandExecutionError(message=err_msg, info=response)

    response.pop("stdout")

    if type(result) is not list:
        if force_list:
            response["result"] = [result]
        else:
            response["result"] = result
    else:
        # result type is list so the force_list param has no effect
        response["result"] = result
    return response


def run_bg(
    cmd,
    cwd=None,
    runas=None,
    group=None,
    shell=DEFAULT_SHELL,
    python_shell=None,
    env=None,
    clean_env=False,
    template=None,
    umask=None,
    timeout=None,
    output_encoding=None,
    output_loglevel="debug",
    log_callback=None,
    reset_system_locale=True,
    ignore_retcode=False,
    saltenv=None,
    password=None,
    prepend_path=None,
    success_retcodes=None,
    success_stdout=None,
    success_stderr=None,
    **kwargs,
):
    r"""
    .. versionadded:: 2016.3.0

    Execute the passed command in the background and return its PID

    .. note::

        If the init system is systemd and the backgrounded task should run even
        if the salt-minion process is restarted, prepend ``systemd-run
        --scope`` to the command. This will reparent the process in its own
        scope separate from salt-minion, and will not be affected by restarting
        the minion service.

    :param str cmd: The command to run. ex: ``ls -lart /home``

    :param str cwd: The directory from which to execute the command. Defaults
        to the home directory of the user specified by ``runas`` (or the user
        under which Salt is running if ``runas`` is not specified).

    :param str group: Group to run command as. Not currently supported
      on Windows.

    :param str shell: Shell to execute under. Defaults to the system default
      shell.

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

    :param str runas: Specify an alternate user to run the command. The default
        behavior is to run as the user under which Salt is running. If running
        on a Windows minion you must also use the ``password`` argument, and
        the target user account must be in the Administrators group.

        .. warning::

            For versions 2018.3.3 and above on macosx while using runas,
            to pass special characters to the command you need to escape
            the characters on the shell.

            Example:

            .. code-block:: bash

                cmd.run_bg 'echo '\''h=\"baz\"'\''' runas=macuser

    :param str password: Windows only. Required when specifying ``runas``. This
        parameter will be ignored on non-Windows platforms.

        .. versionadded:: 2016.3.0

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

                salt myminion cmd.run_bg 'some command' env='{"FOO": "bar"}'

        .. note::
            When using environment variables on Window's, case-sensitivity
            matters, i.e. Window's uses `Path` as opposed to `PATH` for other
            systems.

    :param bool clean_env: Attempt to clean out all other shell environment
        variables and set only those provided in the 'env' argument to this
        function.

    :param str prepend_path: $PATH segment to prepend (trailing ':' not
        necessary) to $PATH

        .. versionadded:: 2018.3.0

    :param str template: If this setting is applied then the named templating
        engine will be used to render the downloaded file. Currently jinja,
        mako, and wempy are supported.

    :param str umask: The umask (in octal) to use when running the command.

    :param int timeout: A timeout in seconds for the executed process to return.

    .. warning::

        This function does not process commands through a shell unless the
        ``python_shell`` argument is set to ``True``. This means that any
        shell-specific functionality such as 'echo' or the use of pipes,
        redirection or &&, should either be migrated to cmd.shell or have the
        python_shell=True flag set here.

        The use of ``python_shell=True`` means that the shell will accept _any_
        input including potentially malicious commands such as 'good_command;rm
        -rf /'.  Be absolutely certain that you have sanitized your input prior
        to using ``python_shell=True``.

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

        salt '*' cmd.run_bg "fstrim-all"

    The template arg can be set to 'jinja' or another supported template
    engine to render the command arguments before execution.
    For example:

    .. code-block:: bash

        salt '*' cmd.run_bg template=jinja "ls -l /tmp/{{grains.id}} | awk '/foo/{print \\$2}'"

    Specify an alternate shell with the shell parameter:

    .. code-block:: bash

        salt '*' cmd.run_bg "Get-ChildItem C:\\ " shell='powershell'

    If an equal sign (``=``) appears in an argument to a Salt command it is
    interpreted as a keyword argument in the format ``key=val``. That
    processing can be bypassed in order to pass an equal sign through to the
    remote shell command by manually specifying the kwarg:

    .. code-block:: bash

        salt '*' cmd.run_bg cmd='ls -lR / | sed -e s/=/:/g > /tmp/dontwait'
    """

    python_shell = _python_shell_default(python_shell, kwargs.get("__pub_jid", ""))
    res = _run(
        cmd,
        stdin=None,
        stderr=None,
        stdout=None,
        output_encoding=output_encoding,
        output_loglevel=output_loglevel,
        use_vt=None,
        bg=True,
        with_communicate=False,
        rstrip=False,
        runas=runas,
        group=group,
        shell=shell,
        python_shell=python_shell,
        cwd=cwd,
        env=env,
        clean_env=clean_env,
        prepend_path=prepend_path,
        template=template,
        umask=umask,
        log_callback=log_callback,
        timeout=timeout,
        reset_system_locale=reset_system_locale,
        saltenv=saltenv,
        password=password,
        success_retcodes=success_retcodes,
        success_stdout=success_stdout,
        success_stderr=success_stderr,
        **kwargs,
    )

    return {"pid": res["pid"]}
