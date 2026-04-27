"""
Run child processes as another Windows user.

The main entry points are :func:`runas` (starts the child with
``CreateProcessWithTokenW`` when the minion can obtain a privileged context) and
:func:`runas_unpriv` (uses ``CreateProcessWithLogonW`` as a fallback). Both are
used from :mod:`salt.modules.cmdmod` when ``runas`` is set on Windows.
"""

# Import Python Libraries
import ctypes
import logging
import os
import subprocess
import threading
import time

from salt.exceptions import CommandExecutionError

try:
    import msvcrt

    import pywintypes
    import win32api
    import win32con
    import win32event
    import win32pipe
    import win32process
    import win32profile
    import win32security

    import salt.platform.win

    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


log = logging.getLogger(__name__)


def _preview_cmd(cmd, max_len=500):
    """
    Shorten a command line for safe logging (full line is never executed from
    this helper).

    Args:
        cmd: Command string; non-strings are formatted with ``repr()``.
        max_len: Maximum length before truncation; an ellipsis is appended.

    Returns:
        Truncated string suitable for debug log lines.
    """
    s = cmd if isinstance(cmd, str) else repr(cmd)
    if len(s) > max_len:
        return s[:max_len] + "…"
    return s


# Although utils are often directly imported, it is also possible to use the
# loader.
def __virtual__():
    """
    Load this module only when PyWin32 (and related imports) succeeded.

    Returns:
        The string ``win_runas`` on success, or ``(False, reason)`` when
        required imports failed so the loader should skip the module.
    """
    if not HAS_WIN32:
        return False, "This utility requires pywin32"

    return "win_runas"


def split_username(username):
    """
    Parse domain-style account names into a plain user name and domain.

    Accepts UPN (``user@domain``), down-level (``DOMAIN\\user``), or a bare
    name (domain becomes ``.`` for local accounts).

    Args:
        username: Account string; non-strings are coerced with ``str()`` at the
            start of this function.

    Returns:
        A ``(user_name, domain)`` pair suitable for ``LogonUser`` and family.
    """
    domain = "."
    user_name = str(username)
    # Domain users with User Principal Name (UPN): user@DOMAIN
    if "@" in user_name:
        user_name, domain = user_name.split("@", maxsplit=1)
        domain = domain.removesuffix(".local")
    # Domain users with Down-Level Logon Name: DOMAIN\user
    if "\\" in user_name:
        domain, user_name = user_name.split("\\", maxsplit=1)
    return str(user_name), str(domain)


def create_env(user_token, inherit=False, timeout=1):
    """
    Build a user environment block for ``CreateProcess*`` using
    ``CreateEnvironmentBlock``.

    Retries for up to ``timeout`` seconds if the call fails (e.g. logon/logoff
    races). Does not use ``LoadUserProfile`` / ``UnloadUserProfile``: that can
    block for a long time and is not required when the caller already holds a
    user token from ``LogonUser`` or similar.

    Args:
        user_token: Windows access token (handle) for the target user, as used
            by ``win32profile.CreateEnvironmentBlock`` / ``CreateProcess*``.
        inherit: Passed through to ``CreateEnvironmentBlock`` (whether to
            inherit the environment of the process associated with
            ``user_token``; typically ``False`` for an isolated child env).
        timeout: If ``CreateEnvironmentBlock`` raises, retry until this many
            seconds have elapsed since the first attempt, then give up.

    Returns:
        Environment data for the ``environment`` parameter to ``CreateProcess*``,
        or ``None`` if no block was produced and there was no exception to
        re-raise. On repeated failure, the last ``pywintypes.error`` may be
        raised.
    """
    t0 = time.monotonic()
    log.debug("win_runas.create_env: begin inherit=%s timeout=%ss", inherit, timeout)
    start = time.time()
    env = None
    exc = None
    attempt = 0
    while True:
        attempt += 1
        try:
            env = win32profile.CreateEnvironmentBlock(user_token, inherit)
        except pywintypes.error as exc:
            log.debug(
                "win_runas.create_env: CreateEnvironmentBlock attempt %s failed: %s",
                attempt,
                exc,
            )
        else:
            break
        if time.time() - start > timeout:
            log.debug(
                "win_runas.create_env: giving up after %s attempts in %.2fs",
                attempt,
                time.time() - start,
            )
            break
    elapsed = time.monotonic() - t0
    if env is not None:
        log.debug("win_runas.create_env: success in %.3fs", elapsed)
        return env
    log.debug("win_runas.create_env: no environment block after %.3fs", elapsed)
    if exc is not None:
        log.debug("win_runas.create_env: re-raising last CreateEnvironmentBlock error")
        raise exc


def runas(cmd, username, password=None, cwd=None):
    """
    Run ``cmd`` as ``username`` using a logon token and
    ``CreateProcessWithTokenW``.

    The minion must be able to impersonate ``SYSTEM`` (e.g. admin with
    ``SeImpersonatePrivilege``) for the primary path. If that fails, this
    delegates to :func:`runas_unpriv` (logon + ``CreateProcessWithLogonW``) so a
    password is required for non-service accounts in that case.

    The process is created suspended, the primary thread is resumed with
    ``ResumeThread``, and stdout/stderr are read on helper threads while waiting
    so large child output cannot fill the pipe and deadlock the parent.

    Args:
        cmd: Full process command line (string) or argv sequence; lists are
            passed through ``subprocess.list2cmdline`` to build
            ``lpCommandLine``.
        username: Target account; UPN, ``DOMAIN\\user``, or local name. May be
            non-string (e.g. numeric local user name) and is coerced to ``str``.
        password: Password for ``LogonUser`` when required; may be omitted for
            some service accounts and when S4U logon is used.
        cwd: Optional working directory for the child (``lpCurrentDirectory``);
            ``None`` uses the default for the new process.

    Returns:
        Dict with keys: ``pid``, ``retcode`` (if wait succeeded), ``stdout``,
        ``stderr`` (empty strings on read failure).

    Raises:
        salt.exceptions.CommandExecutionError: If the account name cannot be
            resolved (e.g. ``LookupAccountName`` failure).
    """
    # Sometimes this comes in as an int. LookupAccountName can't handle an int
    # Let's make it a string if it's anything other than a string
    if not isinstance(username, str):
        username = str(username)
    # Validate the domain and sid exist for the username
    try:
        _, domain, _ = win32security.LookupAccountName(None, username)
        username, _ = split_username(username)
    except pywintypes.error as exc:
        message = win32api.FormatMessage(exc.winerror).rstrip("\n")
        raise CommandExecutionError(message)

    # Elevate the token from the current process
    access = win32security.TOKEN_QUERY | win32security.TOKEN_ADJUST_PRIVILEGES
    th = win32security.OpenProcessToken(win32api.GetCurrentProcess(), access)
    import salt.platform.win

    salt.platform.win.elevate_token(th)

    # Try to impersonate the SYSTEM user. This process needs to be running as a
    # user who has been granted the SeImpersonatePrivilege, Administrator
    # accounts have this permission by default.
    try:
        impersonation_token = salt.platform.win.impersonate_sid(
            salt.platform.win.SYSTEM_SID,
            session_id=0,
            privs=["SeTcbPrivilege"],
        )
    except OSError:
        log.debug("Unable to impersonate SYSTEM user")
        impersonation_token = None
        win32api.CloseHandle(th)

    if isinstance(cmd, (list, tuple)):
        # CreateProcess parameter lpCommandLine must be a string.
        # Since it is called directly and not via the subprocess module,
        # the arguments must be processed manually.
        cmd = subprocess.list2cmdline(cmd)

    log.debug(
        "win_runas.runas: user=%r domain=%r cwd=%r cmdline=%s",
        username,
        domain,
        cwd,
        _preview_cmd(cmd),
    )

    # Impersonation of the SYSTEM user failed. Fallback to an un-privileged
    # runas.
    if not impersonation_token:
        log.debug("No impersonation token, using unprivileged runas")
        return runas_unpriv(cmd, username, password, cwd)

    if domain == "NT AUTHORITY":
        # Logon as a system level account, SYSTEM, LOCAL SERVICE, or NETWORK
        # SERVICE.
        user_token = win32security.LogonUser(
            username,
            domain,
            "",
            win32con.LOGON32_LOGON_SERVICE,
            win32con.LOGON32_PROVIDER_DEFAULT,
        )
    elif password:
        # Login with a password.
        user_token = win32security.LogonUser(
            username,
            domain,
            password,
            win32con.LOGON32_LOGON_INTERACTIVE,
            win32con.LOGON32_PROVIDER_DEFAULT,
        )
    else:
        # Login without a password. This always returns an elevated token.
        user_token = salt.platform.win.logon_msv1_s4u(username).Token

    # Get a linked user token to elevate if needed
    elevation_type = win32security.GetTokenInformation(
        user_token, win32security.TokenElevationType
    )
    if elevation_type > 1:
        user_token = win32security.GetTokenInformation(
            user_token, win32security.TokenLinkedToken
        )

    # Elevate the user token
    salt.platform.win.elevate_token(user_token)

    # Make sure the user's token has access to a windows station and desktop
    salt.platform.win.grant_winsta_and_desktop(user_token)

    # Create pipes for standard in, out and error streams
    security_attributes = win32security.SECURITY_ATTRIBUTES()
    security_attributes.bInheritHandle = 1

    stdin_read, stdin_write = win32pipe.CreatePipe(security_attributes, 0)
    stdin_read = salt.platform.win.make_inheritable(stdin_read)

    stdout_read, stdout_write = win32pipe.CreatePipe(security_attributes, 0)
    stdout_write = salt.platform.win.make_inheritable(stdout_write)

    stderr_read, stderr_write = win32pipe.CreatePipe(security_attributes, 0)
    stderr_write = salt.platform.win.make_inheritable(stderr_write)

    # Run the process without showing a window.
    creationflags = (
        win32process.CREATE_NO_WINDOW
        | win32process.CREATE_NEW_CONSOLE
        | win32process.CREATE_SUSPENDED
    )

    flags = win32con.STARTF_USESTDHANDLES
    flags |= win32con.STARTF_USESHOWWINDOW
    startup_info = salt.platform.win.STARTUPINFO(
        dwFlags=flags,
        hStdInput=stdin_read.handle,
        hStdOutput=stdout_write.handle,
        hStdError=stderr_write.handle,
    )

    # Create the environment for the user
    log.debug("win_runas.runas: building environment block for user token")
    env = create_env(user_token, inherit=False)

    hProcess = None
    try:
        # Start the process in a suspended state.
        log.debug("win_runas.runas: calling CreateProcessWithTokenW (suspended)")
        t0 = time.monotonic()
        process_info = salt.platform.win.CreateProcessWithTokenW(
            int(user_token),
            logonflags=1,
            applicationname=None,
            commandline=cmd,
            currentdirectory=cwd,
            creationflags=creationflags,
            startupinfo=startup_info,
            environment=env,
        )
        log.debug(
            "win_runas.runas: CreateProcessWithTokenW returned in %.3fs",
            time.monotonic() - t0,
        )

        hProcess = process_info.hProcess
        hThread = process_info.hThread
        dwProcessId = process_info.dwProcessId
        dwThreadId = process_info.dwThreadId
        log.debug(
            "win_runas.runas: new process pid=%s main_thread_id=%s",
            dwProcessId,
            dwThreadId,
        )

        # We don't use these, so let's close the handle
        salt.platform.win.kernel32.CloseHandle(stdin_write.handle)
        salt.platform.win.kernel32.CloseHandle(stdout_write.handle)
        salt.platform.win.kernel32.CloseHandle(stderr_write.handle)

        ret = {"pid": dwProcessId}
        # CREATE_SUSPENDED: the primary thread must be resumed. psutil's
        # process resume is not as reliable as ResumeThread on the handle
        # returned in PROCESS_INFORMATION.
        if hThread:
            resume_count = win32process.ResumeThread(hThread)
            log.debug(
                "win_runas.runas: ResumeThread returned %s (previously-suspended count)",
                resume_count,
            )
            if resume_count in (-1, 0xFFFFFFFF):
                log.error(
                    "win_runas.runas: ResumeThread failed; process may never run; "
                    "if the next line logs an infinite wait, the child is likely still suspended"
                )
            win32api.CloseHandle(hThread)

        # Read stdout/stderr in background threads *before* waiting on the
        # process. If we WaitForSingleObject first then read, the child can
        # fill the 64k pipe and block in WriteFile (e.g. huge ``dir`` output
        # when ``cd`` failed) while the parent is stuck in Wait -- deadlock.
        stdout_buf = []
        stderr_buf = []

        def _pump_pipecopy(handle, bucket, name):
            """Read one inherited pipe end into *bucket* (list with one string)."""
            try:
                fd = msvcrt.open_osfhandle(int(handle), os.O_RDONLY | os.O_TEXT)
                with os.fdopen(fd, "r") as fh:
                    bucket.append(fh.read())
            except OSError as exc:
                log.debug("win_runas.runas: reading %s pipe: %s", name, exc)
                bucket.append("")

        t_out = threading.Thread(
            target=_pump_pipecopy,
            args=(stdout_read.handle, stdout_buf, "stdout"),
        )
        t_err = threading.Thread(
            target=_pump_pipecopy,
            args=(stderr_read.handle, stderr_buf, "stderr"),
        )
        t_out.start()
        t_err.start()
        log.debug("win_runas.runas: started pipe-drain threads for pid=%s", dwProcessId)

        # Wait for the process to exit and get its return code.
        log.debug(
            "win_runas.runas: waiting for pid=%s to exit (infinite wait)",
            dwProcessId,
        )
        t_wait = time.monotonic()
        if (
            win32event.WaitForSingleObject(hProcess, win32event.INFINITE)
            == win32con.WAIT_OBJECT_0
        ):
            log.debug(
                "win_runas.runas: WaitForSingleObject signalled after %.3fs for pid=%s",
                time.monotonic() - t_wait,
                dwProcessId,
            )
            exitcode = win32process.GetExitCodeProcess(hProcess)
            log.debug("win_runas.runas: pid=%s exit code=%s", dwProcessId, exitcode)
            ret["retcode"] = exitcode
        else:
            log.error(
                "win_runas.runas: unexpected WaitForSingleObject result for pid=%s",
                dwProcessId,
            )

        t_out.join()
        t_err.join()
        log.debug("win_runas.runas: pipe-drain threads joined for pid=%s", dwProcessId)
        ret["stdout"] = (stdout_buf[0] if stdout_buf else "").strip()
        ret["stderr"] = stderr_buf[0] if stderr_buf else ""
    finally:
        if hProcess is not None:
            salt.platform.win.kernel32.CloseHandle(hProcess)
        win32api.CloseHandle(th)
        win32api.CloseHandle(user_token)
        if impersonation_token:
            win32security.RevertToSelf()
            win32api.CloseHandle(impersonation_token)

    return ret


def runas_unpriv(cmd, username, password, cwd=None):
    """
    Run ``cmd`` as ``username`` using ``CreateProcessWithLogonW`` (with profile).

    Used when :func:`runas` cannot use ``CreateProcessWithTokenW`` (e.g. no
    SYSTEM impersonation). Requires ``password`` for the target account. Stdin
    is inherited from the minion; stdout/stderr are collected from anonymous
    pipes. Output is read after the process exit wait (acceptable for typical
    output sizes; the privileged :func:`runas` path uses concurrent draining to
    avoid pipe deadlocks on very large streams).

    Args:
        cmd: Command line string, or a list/tuple passed to
            ``subprocess.list2cmdline``.
        username: Target account; coerced to ``str`` if needed.
        password: Password for ``CreateProcessWithLogonW`` (required).
        cwd: Optional working directory for the child; ``None`` for default.

    Returns:
        Dict with ``pid``, ``retcode`` (if the process handle wait succeeded),
        ``stdout``, and ``stderr`` strings.

    Raises:
        salt.exceptions.CommandExecutionError: If the account name cannot be
            resolved.
    """
    # Sometimes this comes in as an int. LookupAccountName can't handle an int
    # Let's make it a string if it's anything other than a string
    if not isinstance(username, str):
        username = str(username)
    # Validate the domain and sid exist for the username
    try:
        _, domain, _ = win32security.LookupAccountName(None, username)
        username, _ = split_username(username)
    except pywintypes.error as exc:
        message = win32api.FormatMessage(exc.winerror).rstrip("\n")
        raise CommandExecutionError(message)

    if isinstance(cmd, (list, tuple)):
        cmd = subprocess.list2cmdline(cmd)
    log.debug(
        "win_runas.runas_unpriv: user=%r domain=%r cwd=%r cmdline=%s",
        username,
        domain,
        cwd,
        _preview_cmd(cmd),
    )

    # Create a pipe to set as stdout in the child. The write handle needs to be
    # inheritable.
    c2pread, c2pwrite = salt.platform.win.CreatePipe(
        inherit_read=False,
        inherit_write=True,
    )
    errread, errwrite = salt.platform.win.CreatePipe(
        inherit_read=False,
        inherit_write=True,
    )

    # Create inheritable copy of the stdin
    stdin = salt.platform.win.kernel32.GetStdHandle(
        salt.platform.win.STD_INPUT_HANDLE,
    )
    dupin = salt.platform.win.DuplicateHandle(srchandle=stdin, inherit=True)

    # Get startup info structure
    flags = win32con.STARTF_USESTDHANDLES
    flags |= win32con.STARTF_USESHOWWINDOW
    startup_info = salt.platform.win.STARTUPINFO(
        dwFlags=flags,
        hStdInput=dupin,
        hStdOutput=c2pwrite,
        hStdError=errwrite,
    )

    try:
        # Run command and return process info structure
        log.debug("win_runas.runas_unpriv: CreateProcessWithLogonW")
        t0 = time.monotonic()
        process_info = salt.platform.win.CreateProcessWithLogonW(
            username=username,
            domain=domain,
            password=password,
            logonflags=salt.platform.win.LOGON_WITH_PROFILE,
            commandline=cmd,
            startupinfo=startup_info,
            currentdirectory=cwd,
        )
        log.debug(
            "win_runas.runas_unpriv: process started pid=%s in %.3fs",
            process_info.dwProcessId,
            time.monotonic() - t0,
        )
        salt.platform.win.kernel32.CloseHandle(process_info.hThread)
    finally:
        salt.platform.win.kernel32.CloseHandle(dupin)
        salt.platform.win.kernel32.CloseHandle(c2pwrite)
        salt.platform.win.kernel32.CloseHandle(errwrite)

    # Initialize ret and set first element
    ret = {"pid": process_info.dwProcessId}

    # Get Standard Out
    fd_out = msvcrt.open_osfhandle(c2pread, os.O_RDONLY | os.O_TEXT)
    with os.fdopen(fd_out, "r") as f_out:
        ret["stdout"] = f_out.read()

    # Get Standard Error
    fd_err = msvcrt.open_osfhandle(errread, os.O_RDONLY | os.O_TEXT)
    with os.fdopen(fd_err, "r") as f_err:
        ret["stderr"] = f_err.read()

    # Get Return Code
    log.debug(
        "win_runas.runas_unpriv: waiting for pid=%s to exit (infinite wait)",
        process_info.dwProcessId,
    )
    t_wait = time.monotonic()
    if (
        salt.platform.win.kernel32.WaitForSingleObject(
            process_info.hProcess, win32event.INFINITE
        )
        == win32con.WAIT_OBJECT_0
    ):
        log.debug(
            "win_runas.runas_unpriv: WaitForSingleObject done after %.3fs for pid=%s",
            time.monotonic() - t_wait,
            process_info.dwProcessId,
        )
        exitcode = salt.platform.win.wintypes.DWORD()
        salt.platform.win.kernel32.GetExitCodeProcess(
            process_info.hProcess, ctypes.byref(exitcode)
        )
        log.debug(
            "win_runas.runas_unpriv: pid=%s exit code=%s",
            process_info.dwProcessId,
            exitcode.value,
        )
        ret["retcode"] = exitcode.value

    # Close handle to process
    salt.platform.win.kernel32.CloseHandle(process_info.hProcess)

    return ret
