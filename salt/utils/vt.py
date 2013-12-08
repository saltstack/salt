# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.


    salt.utils.vt
    ~~~~~~~~~~~~~

    Virtual Terminal
'''

# Import python libs
import os
import sys
import time
import errno
import signal
import select
import logging
import resource
import subprocess

if subprocess.mswindows:
    from win32file import ReadFile, WriteFile
    from win32pipe import PeekNamedPipe
    import msvcrt
else:
    import pty
    import fcntl

# Import salt libs
from salt._compat import string_types

log = logging.getLogger(__name__)


class TerminalException(Exception):
    '''
    Terminal specific exception
    '''


class TimeoutExpired(TerminalException):
    '''
    This exception is raised when the timeout expires while waiting for a
    child process.
    '''

    def __init__(self, cmd, timeout, output=None):
        self.cmd = cmd
        self.timeout = timeout
        self.output = output

    def __str__(self):
        return 'Command {0!r} timed out after {1} seconds'.format(
            self.cmd, self.timeout
        )


# ----- Cleanup Running Instances ------------------------------------------->
# This lists holds Terminal instances for which the underlying process had
# not exited at the time its __del__ method got called: those processes are
# wait()ed for synchronously from _cleanup() when a new Terminal object is
# created, to avoid zombie processes.
_ACTIVE = []


def _cleanup():
    for inst in _ACTIVE[:]:
        res = inst._internal_poll(_deadstate=sys.maxsize)
        if res is not None:
            try:
                _ACTIVE.remove(inst)
            except ValueError:
                # This can happen if two threads create a new Terminal instance
                # It's harmless that it was already removed, so ignore.
                pass
# <---- Cleanup Running Instances --------------------------------------------


class Terminal(object):
    '''
    I'm a virtual terminal
    '''
    def __init__(self,
                 args,
                 executable=None,
                 shell=False,
                 cwd=None,
                 env=None,

                 # Logging options
                 log_stdin=None,
                 log_stdout=None,
                 log_stderr=None,

                 # sys.stdXYZ streaming options
                 stream_stdout=None,
                 stream_stderr=None,
                 ):

        # Let's avoid Zombies!!!
        _cleanup()

        self.args = args
        self.executable = executable
        self.shell = shell
        self.cwd = cwd
        self.env = env

        # ----- Internally Set Attributes ----------------------------------->
        self.pid = None
        self.stdin = None
        self.stdout = None
        self.stderr = None
        self.closed = False
        self.returncode = None
        self.child_fd = None
        self.child_fde = None
        self.terminated = False
        # <---- Internally Set Attributes ------------------------------------

        # ----- Direct Streaming Setup -------------------------------------->
        if stream_stdout is True:
            self.stream_stdout = sys.stdout
        elif stream_stdout is not None:
            if not hasattr(stream_stdout, 'write') or \
                    not hasattr(stream_stdout, 'flush') or \
                    not hasattr(stream_stdout, 'close'):
                raise RuntimeError(
                    '\'stream_stdout\' needs to have at least 3 methods, '
                    '\'write()\', \'flush()\' and \'close()\'.'
                )
            self.stream_stdout = stream_stdout
        else:
            self.stream_stdout = None

        if stream_stderr is True:
            self.stream_stderr = sys.stderr
        elif stream_stderr is not None:
            if not hasattr(stream_stderr, 'write') or \
                    not hasattr(stream_stderr, 'flush') or \
                    not hasattr(stream_stderr, 'close'):
                raise RuntimeError(
                    '\'stream_stderr\' needs to have at least 3 methods, '
                    '\'write()\', \'flush()\' and \'close()\'.'
                )
            self.stream_stderr = stream_stderr
        else:
            self.stream_stderr = None
        # <---- Direct Streaming Setup ---------------------------------------

        # ----- Spawn our terminal ------------------------------------------>
        self._spawn()
        log.debug(
            'Child Forked! PID: {0}  STDOUT_FD: {1}  STDERR_FD: '
            '{2}'.format(self.pid, self.child_fd, self.child_fde)
        )
        log.debug('Terminal Command: {0}'.format(' '.join(self.args)))
        # <---- Spawn our terminal -------------------------------------------

        # ----- Setup Logging ----------------------------------------------->
        # Setup logging after spawned in order to have a pid value
        if log_stdin is True:
            self.stdin_logger = logging.getLogger(
                '{0}.{1}.PID-{2}.STDIN'.format(
                    __name__, self.__class__.__name__, self.pid
                )
            )
        elif log_stdin is not None:
            if not hasattr(log_stdin, 'debug'):
                raise RuntimeError(
                    '\'log_stdin\' needs to have at least the \'debug()\' '
                    'method.'
                )
            self.stdin_logger = log_stdin
        else:
            self.stdin_logger = None

        if log_stdout is True:
            self.stdout_logger = logging.getLogger(
                '{0}.{1}.PID-{2}.STDOUT'.format(
                    __name__, self.__class__.__name__, self.pid
                )
            )
        elif log_stdout is not None:
            if not hasattr(log_stdout, 'debug'):
                raise RuntimeError(
                    '\'log_stdout\' needs to have at least the \'debug()\' '
                    'method.'
                )
            self.stdout_logger = log_stdout
        else:
            self.stdout_logger = None

        if log_stderr is True:
            self.stderr_logger = logging.getLogger(
                '{0}.{1}.PID-{2}.STDERR'.format(
                    __name__, self.__class__.__name__, self.pid
                )
            )
        elif log_stderr is not None:
            if not hasattr(log_stderr, 'debug'):
                raise RuntimeError(
                    '\'log_stderr\' needs to have at least the \'debug()\' '
                    'method.'
                )
            self.stderr_logger = log_stderr
        else:
            self.stderr_logger = None
        # <---- Setup Logging ------------------------------------------------

    # ----- Common Public API ----------------------------------------------->
    def poll(self):
        return self._internal_poll()

    def send(self, data):
        return self._send(data)

    def sendline(self, data, linesep=os.linesep):
        return self.send('{0}{1}'.format(data, linesep))

    def recv(self, maxsize=None):
        if maxsize is None:
            maxsize = 1024
        elif maxsize < 1:
            maxsize = 1
        return self._recv(maxsize)
    # <---- Common Public API ------------------------------------------------

    # ----- Common Internal API --------------------------------------------->
    def _remaining_time(self, endtime):
        '''
        Convenience method when computing timeouts.
        '''
        if endtime is None:
            return None
        else:
            return endtime - time.time()
    # <---- Common Internal API ----------------------------------------------

    # ----- Context Manager Methods ----------------------------------------->
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.stdout:
            self.stdout.close()
        if self.stderr:
            self.stderr.close()
        if self.stdin:
            self.stdin.close()
        # Wait for the process to terminate, to avoid zombies.
        self.wait()
    # <---- Context Manager Methods ------------------------------------------

# ----- Platform Specific Methods ------------------------------------------->
    if subprocess.mswindows:
    # ----- Windows Methods ------------------------------------------------->
        def _execute(self):
            raise NotImplementedError

        def _spawn(self):
            raise NotImplementedError

        def _recv(self, maxsize):
            raise NotImplementedError

        def _send(self, data):
            raise NotImplementedError

        def send_signal(self, sig):
            '''
            Send a signal to the process
            '''
            if sig == signal.SIGTERM:
                self.terminate()
            elif sig == signal.CTRL_C_EVENT:
                os.kill(self.pid, signal.CTRL_C_EVENT)
            elif sig == signal.CTRL_BREAK_EVENT:
                os.kill(self.pid, signal.CTRL_BREAK_EVENT)
            else:
                raise ValueError('Unsupported signal: {0}'.format(sig))

        def terminate(self):
            '''
            Terminates the process
            '''
            try:
                _winapi.TerminateProcess(self._handle, 1)
            except PermissionError:
                # ERROR_ACCESS_DENIED (winerror 5) is received when the
                # process already died.
                rc = _winapi.GetExitCodeProcess(self._handle)
                if rc == _winapi.STILL_ACTIVE:
                    raise
                self.returncode = rc

        kill = terminate
    # <---- Windows Methods --------------------------------------------------
    else:
    # ----- Linux Methods --------------------------------------------------->
        # ----- Internal API ------------------------------------------------>
        def _spawn(self):
            self.pid, self.child_fd, self.child_fde = self.__fork_ptys()

            if isinstance(self.args, string_types):
                args = [self.args]
            else:
                args = list(self.args)

            if self.shell:
                self.args = ['/bin/sh', '-c'] + args

            if self.executable:
                self.args[0] = self.executable

            if self.executable is None:
                self.executable = self.args[0]

            if self.pid == 0:
                # Child
                self.stdin = sys.stdin.fileno()
                self.stdout = sys.stdout.fileno()
                self.stderr = sys.stderr.fileno()

                # Do not allow child to inherit open file descriptors from
                # parent
                max_fd = resource.getrlimit(resource.RLIMIT_NOFILE)
                try:
                    os.closerange(pty.STDERR_FILENO + 1, max_fd[0])
                except OSError:
                    pass

                if self.cwd is not None:
                    os.chdir(self.cwd)

                if self.env is None:
                    os.execv(self.executable, self.args)
                else:
                    os.execvpe(self.executable, self.args, self.env)

            # Parent
            self.closed = False

        def __fork_ptys(self):
            '''
            Fork the PTY

            The major difference from the python source is that we separate the
            stdout from stderr output.
            '''
            stdout_parent_fd, stdout_child_fd = pty.openpty()
            if stdout_parent_fd < 0 or stdout_child_fd < 0:
                raise TerminalException('Failed to open a TTY for stdout')

            stderr_parent_fd, stderr_child_fd = pty.openpty()
            if stderr_parent_fd < 0 or stderr_child_fd < 0:
                raise TerminalException('Failed to open a TTY for stderr')

            pid = os.fork()
            if pid < pty.CHILD:
                raise TerminalException('Failed to fork')
            elif pid == pty.CHILD:
                # Child.
                # Close parent FDs
                os.close(stdout_parent_fd)
                os.close(stderr_parent_fd)

                # ----- Make STDOUT the controlling PTY --------------------->
                child_name = os.ttyname(stdout_child_fd)
                # Disconnect from controlling tty. Harmless if not already
                # connected
                try:
                    tty_fd = os.open('/dev/tty', os.O_RDWR | os.O_NOCTTY)
                    if tty_fd >= 0:
                        os.close(tty_fd)
                # which exception, shouldn't we catch explicitly .. ?
                except:
                    # Already disconnected. This happens if running inside cron
                    pass

                os.setsid()

                # Verify we are disconnected from controlling tty
                # by attempting to open it again.
                try:
                    tty_fd = os.open('/dev/tty', os.O_RDWR | os.O_NOCTTY)
                    if tty_fd >= 0:
                        os.close(tty_fd)
                        raise TerminalException(
                            'Failed to disconnect from controlling tty. It is '
                            'still possible to open /dev/tty.'
                        )
                # which exception, shouldn't we catch explicitly .. ?
                except:
                    # Good! We are disconnected from a controlling tty.
                    pass

                # Verify we can open child pty.
                tty_fd = os.open(child_name, os.O_RDWR)
                if tty_fd < 0:
                    raise TerminalException(
                        'Could not open child pty, {0}'.format(child_name)
                    )
                else:
                    os.close(tty_fd)

                # Verify we now have a controlling tty.
                tty_fd = os.open('/dev/tty', os.O_WRONLY)
                if tty_fd < 0:
                    raise TerminalException(
                        'Could not open controlling tty, /dev/tty'
                    )
                else:
                    os.close(tty_fd)
                # <---- Make STDOUT the controlling PTY ----------------------

                # ----- Duplicate Descriptors ------------------------------->
                os.dup2(stdout_child_fd, pty.STDIN_FILENO)
                os.dup2(stdout_child_fd, pty.STDOUT_FILENO)
                os.dup2(stderr_child_fd, pty.STDERR_FILENO)
                # <---- Duplicate Descriptors --------------------------------
            else:
                # Parent. Close Child PTY's
                os.close(stdout_child_fd)
                os.close(stderr_child_fd)

            return pid, stdout_parent_fd, stderr_parent_fd

        def _send(self, data):
            if self.child_fd is None:
                return None

            if not select.select([], [self.child_fd], [], 0)[1]:
                return 0

            try:
                if self.stdin_logger:
                    self.stdin_logger.debug(data)
                written = os.write(self.child_fd, data)
            except OSError as why:
                if why.errno == errno.EPIPE:  # broken pipe
                    os.close(self.child_fd)
                    self.child_fd = None
                    return
                raise
            return written

        def _recv(self, maxsize):
            if self.closed or (self.child_fd is None and self.child_fde is None):
                return None, None

            stderr = ''
            stdout = ''

            # ----- Store FD Flags ------------------------------------------>
            fd_flags = fcntl.fcntl(self.child_fd, fcntl.F_GETFL)
            fde_flags = fcntl.fcntl(self.child_fde, fcntl.F_GETFL)
            # <---- Store FD Flags -------------------------------------------

            # ----- Non blocking Reads -------------------------------------->
            fcntl.fcntl(self.child_fd, fcntl.F_SETFL, fd_flags | os.O_NONBLOCK)
            fcntl.fcntl(self.child_fde, fcntl.F_SETFL, fde_flags | os.O_NONBLOCK)
            # <---- Non blocking Reads ---------------------------------------

            # ----- Check for any incoming data ----------------------------->
            rlist, wlist, xlist = select.select(
                [self.child_fd, self.child_fde], [], [], 0
            )
            # <---- Check for any incoming data ------------------------------

            # ----- Process STDERR ------------------------------------------>
            if self.child_fde in rlist:
                try:
                    stderr = os.read(self.child_fde, maxsize)

                    if not stderr:
                        os.close(self.child_fde)
                        self.child_fde = None
                        stderr = None
                    else:
                        if self.stream_stderr:
                            self.stream_stderr.write(stderr)
                            self.stream_stderr.flush()

                        if self.stderr_logger:
                            stripped = stderr.rstrip()
                            if stripped.startswith('\r\n'):
                                stripped = stripped[2:]
                            if stripped:
                                self.stderr_logger.debug(stripped)
                except OSError:
                    os.close(self.child_fde)
                    self.child_fde = None
                    stderr = None
                finally:
                    if not self.closed and self.child_fde is not None:
                        fcntl.fcntl(self.child_fde, fcntl.F_SETFL, fde_flags)
            # <---- Process STDERR -------------------------------------------

            # ----- Process STDOUT ------------------------------------------>
            if self.child_fd in rlist:
                try:
                    stdout = os.read(self.child_fd, maxsize)

                    if not stdout:
                        os.close(self.child_fd)
                        self.child_fd = None
                        stdout = None
                    else:
                        if self.stream_stdout:
                            self.stream_stdout.write(stdout)
                            self.stream_stdout.flush()

                        if self.stdout_logger:
                            stripped = stdout.rstrip()
                            if stripped.startswith('\r\n'):
                                stripped = stripped[2:]
                            if stripped:
                                self.stdout_logger.debug(stripped)
                except OSError:
                    os.close(self.child_fd)
                    self.child_fd = None
                    stdout = None
                finally:
                    if not self.closed and self.child_fd is not None:
                        fcntl.fcntl(self.child_fd, fcntl.F_SETFL, fd_flags)
            # <---- Process STDOUT -------------------------------------------
            return stdout, stderr

        def _internal_poll(self,
                           _deadstate=None,
                           _waitpid=os.waitpid,
                           _WNOHANG=os.WNOHANG,
                           _os_error=os.error,
                           _ECHILD=errno.ECHILD):
            '''
            Check if child process has terminated. Returns returncode attribute

            This method is called by __del__, so it cannot reference anything
            outside of the local scope (nor can any methods it calls).
            '''
            if self.returncode is None:
                try:
                    pid, sts = _waitpid(self.pid, _WNOHANG)
                    if pid == self.pid:
                        self._handle_exitstatus(sts)
                except _os_error as exc:
                    if _deadstate is not None:
                        self.returncode = _deadstate
                    elif exc.errno == _ECHILD:
                        # This happens if SIGCLD is set to be ignored or
                        # waiting for child processes has otherwise been
                        # disabled for our process. This child is dead, we
                        # can't get the status.
                        # http://bugs.python.org/issue15756
                        self.returncode = 0
            return self.returncode

        def _try_wait(self, wait_flags):
            try:
                (pid, sts) = subprocess._eintr_retry_call(os.waitpid,
                                                          self.pid,
                                                          wait_flags)
            except OSError as exc:
                if exc.errno != errno.ECHILD:
                    raise
                # This happens if SIGCLD is set to be ignored or waiting
                # for child processes has otherwise been disabled for our
                # process. This child is dead, we can't get the status.
                pid = self.pid
                sts = 0
            return (pid, sts)

        def _handle_exitstatus(self,
                               sts,
                               _WIFSIGNALED=os.WIFSIGNALED,
                               _WTERMSIG=os.WTERMSIG,
                               _WIFEXITED=os.WIFEXITED,
                               _WEXITSTATUS=os.WEXITSTATUS):
            # This method is called (indirectly) by __del__, so it cannot
            # refer to anything outside of its local scope
            if _WIFSIGNALED(sts):
                self.returncode = -_WTERMSIG(sts)
            elif _WIFEXITED(sts):
                self.returncode = _WEXITSTATUS(sts)
            else:
                # Should never happen
                raise RuntimeError('Unknown child exit status!')

        # <---- Internal API -------------------------------------------------

        # ----- Public API -------------------------------------------------->
        def wait(self, timeout=None, endtime=None):
            '''
            Wait for child process to terminate. Returns returncode attribute.
            '''

            if self.returncode is not None:
                return self.returncode

            # endtime is preferred to timeout. timeout is only used for
            # printing.
            if endtime is not None or timeout is not None:
                if endtime is None:
                    endtime = time.time() + timeout
                elif timeout is None:
                    timeout = self._remaining_time(endtime)

            if endtime is not None:
                # Enter a busy loop if we have a timeout. This busy loop was
                # cribbed from Lib/threading.py in Thread.wait() at r71065.
                delay = 0.0005  # 500 us -> initial delay of 1 ms
                while True:
                    (pid, sts) = self._try_wait(os.WNOHANG)
                    assert pid == self.pid or pid == 0
                    if pid == self.pid:
                        self._handle_exitstatus(sts)
                        break
                    remaining = self._remaining_time(endtime)
                    if remaining <= 0:
                        raise TimeoutExpired(self.args, timeout)
                    delay = min(delay * 2, remaining, .05)
                    time.sleep(delay)
            else:
                while self.returncode is None:
                    (pid, sts) = self._try_wait(0)
                    # Check the pid and loop as waitpid has been known to return
                    # 0 even without WNOHANG in odd situations. issue14396.
                    if pid == self.pid:
                        self._handle_exitstatus(sts)
            return self.returncode

        def send_signal(self, sig):
            '''
            Send a signal to the process
            '''
            os.kill(self.pid, sig)

        def terminate(self):
            '''
            Terminate the process with SIGTERM
            '''
            self.send_signal(signal.SIGTERM)

        def kill(self):
            '''
            Kill the process with SIGKILL
            '''
            self.send_signal(signal.SIGKILL)
        # <---- Public API ---------------------------------------------------
    # <---- Linux Methods ----------------------------------------------------

    # ----- Cleanup!!! ------------------------------------------------------>
    def __del__(self, _maxsize=sys.maxsize, _active=_ACTIVE):
        if self.pid is None:
            # We didn't get to successfully create a child process.
            return

        # In case the child hasn't been waited on, check if it's done.
        self._internal_poll(_deadstate=_maxsize)
        if self.returncode is None and _ACTIVE is not None:
            # Child is still running, keep us alive until we can wait on it.
            _ACTIVE.append(self)
    # <---- Cleanup!!! -------------------------------------------------------
# <---- Platform Specific Methods --------------------------------------------
