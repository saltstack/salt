# -*- coding: utf-8 -*-
'''
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    salt.utils.vt
    ~~~~~~~~~~~~~

    Virtual Terminal

    This code has been heavily inspired by Python's subprocess code, the `non
    blocking version of it`__, some minor online snippets about TTY handling
    with python including `Python's own ``pty`` source code`__ and `Pexpect`__
    which has already surpassed some of the pitfalls that some systems would
    get us into.

    .. __: http://code.activestate.com/recipes/440554/
    .. __: https://github.com/python-mirror/python/blob/3.3/Lib/pty.py
    .. __: https://github.com/pexpect/pexpect

'''
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import os
import sys
import time
import errno
import signal
import select
import logging

# Import salt libs
from salt.ext import six

mswindows = (sys.platform == "win32")

try:
    # pylint: disable=F0401,W0611
    from win32file import ReadFile, WriteFile
    from win32pipe import PeekNamedPipe
    import msvcrt
    import win32api
    import win32con
    import win32process
    # pylint: enable=F0401,W0611
except ImportError:
    import pty
    import fcntl
    import struct
    import termios
    import resource

# Import salt libs
import salt.utils.crypt
import salt.utils.data
import salt.utils.stringutils
from salt.ext.six import string_types
from salt.log.setup import LOG_LEVELS

log = logging.getLogger(__name__)


class TerminalException(Exception):
    '''
    Terminal specific exception
    '''


# ----- Cleanup Running Instances ------------------------------------------->
# This lists holds Terminal instances for which the underlying process had
# not exited at the time its __del__ method got called: those processes are
# wait()ed for synchronously from _cleanup() when a new Terminal object is
# created, to avoid zombie processes.
_ACTIVE = []


def _cleanup():
    '''
    Make sure that any terminal processes still running when __del__ was called
    to the waited and cleaned up.
    '''
    for inst in _ACTIVE[:]:
        res = inst.isalive()
        if res is not True:
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
                 args=None,
                 executable=None,
                 shell=False,
                 cwd=None,
                 env=None,
                 preexec_fn=None,

                 # Terminal Size
                 rows=None,
                 cols=None,

                 # Logging options
                 log_stdin=None,
                 log_stdin_level='debug',
                 log_stdout=None,
                 log_stdout_level='debug',
                 log_stderr=None,
                 log_stderr_level='debug',

                 # sys.stdXYZ streaming options
                 stream_stdout=None,
                 stream_stderr=None,
                 ):

        # Let's avoid Zombies!!!
        _cleanup()

        if not args and not executable:
            raise TerminalException(
                'You need to pass at least one of "args", "executable" '
            )

        self.args = args
        self.executable = executable
        self.shell = shell
        self.cwd = cwd
        self.env = env
        self.preexec_fn = preexec_fn

        # ----- Set the desired terminal size ------------------------------->
        if rows is None and cols is None:
            rows, cols = self.__detect_parent_terminal_size()
        elif rows is not None and cols is None:
            _, cols = self.__detect_parent_terminal_size()
        elif rows is None and cols is not None:
            rows, _ = self.__detect_parent_terminal_size()
        self.rows = rows
        self.cols = cols
        # <---- Set the desired terminal size --------------------------------

        # ----- Internally Set Attributes ----------------------------------->
        self.pid = None
        self.stdin = None
        self.stdout = None
        self.stderr = None

        self.child_fd = None
        self.child_fde = None

        self.closed = True
        self.flag_eof_stdout = False
        self.flag_eof_stderr = False
        self.terminated = True
        self.exitstatus = None
        self.signalstatus = None
        # status returned by os.waitpid
        self.status = None
        self.__irix_hack = 'irix' in sys.platform.lower()
        # <---- Internally Set Attributes ------------------------------------

        # ----- Direct Streaming Setup -------------------------------------->
        if stream_stdout is True:
            self.stream_stdout = sys.stdout
        elif stream_stdout is False:
            self.stream_stdout = None
        elif stream_stdout is not None:
            if not hasattr(stream_stdout, 'write') or \
                    not hasattr(stream_stdout, 'flush') or \
                    not hasattr(stream_stdout, 'close'):
                raise TerminalException(
                    '\'stream_stdout\' needs to have at least 3 methods, '
                    '\'write()\', \'flush()\' and \'close()\'.'
                )
            self.stream_stdout = stream_stdout
        else:
            raise TerminalException(
                'Don\'t know how to handle \'{0}\' as the VT\'s '
                '\'stream_stdout\' parameter.'.format(stream_stdout)
            )

        if stream_stderr is True:
            self.stream_stderr = sys.stderr
        elif stream_stderr is False:
            self.stream_stderr = None
        elif stream_stderr is not None:
            if not hasattr(stream_stderr, 'write') or \
                    not hasattr(stream_stderr, 'flush') or \
                    not hasattr(stream_stderr, 'close'):
                raise TerminalException(
                    '\'stream_stderr\' needs to have at least 3 methods, '
                    '\'write()\', \'flush()\' and \'close()\'.'
                )
            self.stream_stderr = stream_stderr
        else:
            raise TerminalException(
                'Don\'t know how to handle \'{0}\' as the VT\'s '
                '\'stream_stderr\' parameter.'.format(stream_stderr)
            )
        # <---- Direct Streaming Setup ---------------------------------------

        # ----- Spawn our terminal ------------------------------------------>
        try:
            self._spawn()
        except Exception as err:  # pylint: disable=W0703
            # A lot can go wrong, so that's why we're catching the most general
            # exception type
            log.warning(
                'Failed to spawn the VT: %s', err,
                 exc_info_on_loglevel=logging.DEBUG
            )
            raise TerminalException(
                'Failed to spawn the VT. Error: {0}'.format(err)
            )

        log.debug(
            'Child Forked! PID: %s  STDOUT_FD: %s  STDERR_FD: %s',
            self.pid, self.child_fd, self.child_fde
        )
        terminal_command = ' '.join(self.args)
        if 'decode("base64")' in terminal_command or 'base64.b64decode(' in terminal_command:
            log.debug('VT: Salt-SSH SHIM Terminal Command executed. Logged to TRACE')
            log.trace('Terminal Command: %s', terminal_command)
        else:
            log.debug('Terminal Command: %s', terminal_command)
        # <---- Spawn our terminal -------------------------------------------

        # ----- Setup Logging ----------------------------------------------->
        # Setup logging after spawned in order to have a pid value
        self.stdin_logger_level = LOG_LEVELS.get(log_stdin_level, log_stdin_level)
        if log_stdin is True:
            self.stdin_logger = logging.getLogger(
                '{0}.{1}.PID-{2}.STDIN'.format(
                    __name__, self.__class__.__name__, self.pid
                )
            )
        elif log_stdin is not None:
            if not isinstance(log_stdin, logging.Logger):
                raise RuntimeError(
                    '\'log_stdin\' needs to subclass `logging.Logger`'
                )
            self.stdin_logger = log_stdin
        else:
            self.stdin_logger = None

        self.stdout_logger_level = LOG_LEVELS.get(log_stdout_level, log_stdout_level)
        if log_stdout is True:
            self.stdout_logger = logging.getLogger(
                '{0}.{1}.PID-{2}.STDOUT'.format(
                    __name__, self.__class__.__name__, self.pid
                )
            )
        elif log_stdout is not None:
            if not isinstance(log_stdout, logging.Logger):
                raise RuntimeError(
                    '\'log_stdout\' needs to subclass `logging.Logger`'
                )
            self.stdout_logger = log_stdout
        else:
            self.stdout_logger = None

        self.stderr_logger_level = LOG_LEVELS.get(log_stderr_level, log_stderr_level)
        if log_stderr is True:
            self.stderr_logger = logging.getLogger(
                '{0}.{1}.PID-{2}.STDERR'.format(
                    __name__, self.__class__.__name__, self.pid
                )
            )
        elif log_stderr is not None:
            if not isinstance(log_stderr, logging.Logger):
                raise RuntimeError(
                    '\'log_stderr\' needs to subclass `logging.Logger`'
                )
            self.stderr_logger = log_stderr
        else:
            self.stderr_logger = None
        # <---- Setup Logging ------------------------------------------------

    # ----- Common Public API ----------------------------------------------->
    def send(self, data):
        '''
        Send data to the terminal. You are responsible to send any required
        line feeds.
        '''
        return self._send(data)

    def sendline(self, data, linesep=os.linesep):
        '''
        Send the provided data to the terminal appending a line feed.
        '''
        return self.send('{0}{1}'.format(data, linesep))

    def recv(self, maxsize=None):
        '''
        Receive data from the terminal as a (``stdout``, ``stderr``) tuple. If
        any of those is ``None`` we can no longer communicate with the
        terminal's child process.
        '''
        if maxsize is None:
            maxsize = 1024
        elif maxsize < 1:
            maxsize = 1
        return self._recv(maxsize)

    def close(self, terminate=True, kill=False):
        '''
        Close the communication with the terminal's child.
        If ``terminate`` is ``True`` then additionally try to terminate the
        terminal, and if ``kill`` is also ``True``, kill the terminal if
        terminating it was not enough.
        '''
        if not self.closed:
            if self.child_fd is not None:
                os.close(self.child_fd)
                self.child_fd = None
            if self.child_fde is not None:
                os.close(self.child_fde)
                self.child_fde = None
            time.sleep(0.1)
            if terminate:
                if not self.terminate(kill):
                    raise TerminalException('Failed to terminate child process.')
            self.closed = True

    @property
    def has_unread_data(self):
        return self.flag_eof_stderr is False or self.flag_eof_stdout is False

    # <---- Common Public API ------------------------------------------------

    # ----- Common Internal API --------------------------------------------->
    def _translate_newlines(self, data):
        if data is None or not data:
            return
        # PTY's always return \r\n as the line feeds
        return data.replace('\r\n', os.linesep)
    # <---- Common Internal API ----------------------------------------------

    # ----- Context Manager Methods ----------------------------------------->
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close(terminate=True, kill=True)
        # Wait for the process to terminate, to avoid zombies.
        if self.isalive():
            self.wait()
    # <---- Context Manager Methods ------------------------------------------

# ----- Platform Specific Methods ------------------------------------------->
    if mswindows:
        # ----- Windows Methods --------------------------------------------->
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
            # pylint: disable=E1101
            if sig == signal.SIGTERM:
                self.terminate()
            elif sig == signal.CTRL_C_EVENT:
                os.kill(self.pid, signal.CTRL_C_EVENT)
            elif sig == signal.CTRL_BREAK_EVENT:
                os.kill(self.pid, signal.CTRL_BREAK_EVENT)
            else:
                raise ValueError('Unsupported signal: {0}'.format(sig))
            # pylint: enable=E1101

        def terminate(self):
            '''
            Terminates the process
            '''
            try:
                win32api.TerminateProcess(self._handle, 1)
            except OSError:
                # ERROR_ACCESS_DENIED (winerror 5) is received when the
                # process already died.
                ecode = win32process.GetExitCodeProcess(self._handle)
                if ecode == win32con.STILL_ACTIVE:
                    raise
                self.exitstatus = ecode

        kill = terminate
    # <---- Windows Methods --------------------------------------------------
    else:
        # ----- Linux Methods ----------------------------------------------->
        # ----- Internal API ------------------------------------------------>
        def _spawn(self):
            self.pid, self.child_fd, self.child_fde = self.__fork_ptys()

            if isinstance(self.args, string_types):
                args = [self.args]
            elif self.args:
                args = list(self.args)
            else:
                args = []

            if self.shell and self.args:
                self.args = ['/bin/sh', '-c', ' '.join(args)]
            elif self.shell:
                self.args = ['/bin/sh']
            else:
                self.args = args

            if self.executable:
                self.args[0] = self.executable

            if self.executable is None:
                self.executable = self.args[0]

            if self.pid == 0:
                # Child
                self.stdin = sys.stdin.fileno()
                self.stdout = sys.stdout.fileno()
                self.stderr = sys.stderr.fileno()

                # Set the terminal size
                self.child_fd = self.stdin

                if os.isatty(self.child_fd):
                    # Only try to set the window size if the parent IS a tty
                    try:
                        self.setwinsize(self.rows, self.cols)
                    except IOError as err:
                        log.warning(
                            'Failed to set the VT terminal size: %s',
                            err, exc_info_on_loglevel=logging.DEBUG
                        )

                # Do not allow child to inherit open file descriptors from
                # parent
                max_fd = resource.getrlimit(resource.RLIMIT_NOFILE)
                try:
                    os.closerange(pty.STDERR_FILENO + 1, max_fd[0])
                except OSError:
                    pass

                if self.cwd is not None:
                    os.chdir(self.cwd)

                if self.preexec_fn:
                    self.preexec_fn()

                if self.env is None:
                    os.execvp(self.executable, self.args)
                else:
                    os.execvpe(self.executable, self.args, self.env)

            # Parent
            self.closed = False
            self.terminated = False

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
                salt.utils.crypt.reinit_crypto()

                # ----- Make STDOUT the controlling PTY --------------------->
                child_name = os.ttyname(stdout_child_fd)
                # Disconnect from controlling tty. Harmless if not already
                # connected
                try:
                    tty_fd = os.open('/dev/tty', os.O_RDWR | os.O_NOCTTY)
                    if tty_fd >= 0:
                        os.close(tty_fd)
                # which exception, shouldn't we catch explicitly .. ?
                except Exception:
                    # Already disconnected. This happens if running inside cron
                    pass

                # New session!
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
                except Exception:
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
                if os.name != 'posix':
                    # Only do this check in not BSD-like operating systems. BSD-like operating systems breaks at this point
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
                salt.utils.crypt.reinit_crypto()
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
                    self.stdin_logger.log(self.stdin_logger_level, data)
                if six.PY3:
                    written = os.write(self.child_fd, data.encode(__salt_system_encoding__))
                else:
                    written = os.write(self.child_fd, data)
            except OSError as why:
                if why.errno == errno.EPIPE:  # broken pipe
                    os.close(self.child_fd)
                    self.child_fd = None
                    return
                raise
            return written

        def _recv(self, maxsize):
            rfds = []
            if self.child_fd:
                rfds.append(self.child_fd)
            if self.child_fde:
                rfds.append(self.child_fde)

            if not self.isalive():
                if not rfds:
                    return None, None
                rlist, _, _ = select.select(rfds, [], [], 0)
                if not rlist:
                    self.flag_eof_stdout = self.flag_eof_stderr = True
                    log.debug('End of file(EOL). Brain-dead platform.')
                    return None, None
            elif self.__irix_hack:
                # Irix takes a long time before it realizes a child was
                # terminated.
                # FIXME So does this mean Irix systems are forced to always
                # have a 2 second delay when calling read_nonblocking?
                # That sucks.
                rlist, _, _ = select.select(rfds, [], [], 2)
                if not rlist:
                    self.flag_eof_stdout = self.flag_eof_stderr = True
                    log.debug('End of file(EOL). Slow platform.')
                    return None, None

            stderr = ''
            stdout = ''

            # ----- Store FD Flags ------------------------------------------>
            if self.child_fd:
                fd_flags = fcntl.fcntl(self.child_fd, fcntl.F_GETFL)
            if self.child_fde:
                fde_flags = fcntl.fcntl(self.child_fde, fcntl.F_GETFL)
            # <---- Store FD Flags -------------------------------------------

            # ----- Non blocking Reads -------------------------------------->
            if self.child_fd:
                fcntl.fcntl(self.child_fd,
                            fcntl.F_SETFL, fd_flags | os.O_NONBLOCK)
            if self.child_fde:
                fcntl.fcntl(self.child_fde,
                            fcntl.F_SETFL, fde_flags | os.O_NONBLOCK)
            # <---- Non blocking Reads ---------------------------------------

            # ----- Check for any incoming data ----------------------------->
            rlist, _, _ = select.select(rfds, [], [], 0)
            # <---- Check for any incoming data ------------------------------

            # ----- Nothing to Process!? ------------------------------------>
            if not rlist:
                if not self.isalive():
                    self.flag_eof_stdout = self.flag_eof_stderr = True
                    log.debug('End of file(EOL). Very slow platform.')
                    return None, None
            # <---- Nothing to Process!? -------------------------------------

            # ----- Process STDERR ------------------------------------------>
            if self.child_fde in rlist:
                try:
                    stderr = self._translate_newlines(
                        salt.utils.stringutils.to_unicode(
                            os.read(self.child_fde, maxsize)
                        )
                    )

                    if not stderr:
                        self.flag_eof_stderr = True
                        stderr = None
                    else:
                        if self.stream_stderr:
                            self.stream_stderr.write(stderr)
                            self.stream_stderr.flush()

                        if self.stderr_logger:
                            stripped = stderr.rstrip()
                            if stripped.startswith(os.linesep):
                                stripped = stripped[len(os.linesep):]
                            if stripped:
                                self.stderr_logger.log(self.stderr_logger_level, stripped)
                except OSError:
                    os.close(self.child_fde)
                    self.child_fde = None
                    self.flag_eof_stderr = True
                    stderr = None
                finally:
                    if self.child_fde is not None:
                        fcntl.fcntl(self.child_fde, fcntl.F_SETFL, fde_flags)
            # <---- Process STDERR -------------------------------------------

            # ----- Process STDOUT ------------------------------------------>
            if self.child_fd in rlist:
                try:
                    stdout = self._translate_newlines(
                        salt.utils.stringutils.to_unicode(
                            os.read(self.child_fd, maxsize)
                        )
                    )

                    if not stdout:
                        self.flag_eof_stdout = True
                        stdout = None
                    else:
                        if self.stream_stdout:
                            self.stream_stdout.write(salt.utils.stringutils.to_str(stdout))
                            self.stream_stdout.flush()

                        if self.stdout_logger:
                            stripped = stdout.rstrip()
                            if stripped.startswith(os.linesep):
                                stripped = stripped[len(os.linesep):]
                            if stripped:
                                self.stdout_logger.log(self.stdout_logger_level, stripped)
                except OSError:
                    os.close(self.child_fd)
                    self.child_fd = None
                    self.flag_eof_stdout = True
                    stdout = None
                finally:
                    if self.child_fd is not None:
                        fcntl.fcntl(self.child_fd, fcntl.F_SETFL, fd_flags)
            # <---- Process STDOUT -------------------------------------------
            return stdout, stderr

        def __detect_parent_terminal_size(self):
            try:
                TIOCGWINSZ = getattr(termios, 'TIOCGWINSZ', 1074295912)
                packed = struct.pack(b'HHHH', 0, 0, 0, 0)
                ioctl = fcntl.ioctl(sys.stdin.fileno(), TIOCGWINSZ, packed)
                return struct.unpack(b'HHHH', ioctl)[0:2]
            except IOError:
                # Return a default value of 24x80
                return 24, 80
        # <---- Internal API -------------------------------------------------

        # ----- Public API -------------------------------------------------->
        def getwinsize(self):
            '''
            This returns the terminal window size of the child tty. The return
            value is a tuple of (rows, cols).

            Thank you for the shortcut PEXPECT
            '''
            if self.child_fd is None:
                raise TerminalException(
                    'Can\'t check the size of the terminal since we\'re not '
                    'connected to the child process.'
                )

            TIOCGWINSZ = getattr(termios, 'TIOCGWINSZ', 1074295912)
            packed = struct.pack(b'HHHH', 0, 0, 0, 0)
            ioctl = fcntl.ioctl(self.child_fd, TIOCGWINSZ, packed)
            return struct.unpack(b'HHHH', ioctl)[0:2]

        def setwinsize(self, rows, cols):
            '''
            This sets the terminal window size of the child tty. This will
            cause a SIGWINCH signal to be sent to the child. This does not
            change the physical window size. It changes the size reported to
            TTY-aware applications like vi or curses -- applications that
            respond to the SIGWINCH signal.

            Thank you for the shortcut PEXPECT
            '''
            # Check for buggy platforms. Some Python versions on some platforms
            # (notably OSF1 Alpha and RedHat 7.1) truncate the value for
            # termios.TIOCSWINSZ. It is not clear why this happens.
            # These platforms don't seem to handle the signed int very well;
            # yet other platforms like OpenBSD have a large negative value for
            # TIOCSWINSZ and they don't have a truncate problem.
            # Newer versions of Linux have totally different values for
            # TIOCSWINSZ.
            # Note that this fix is a hack.
            TIOCSWINSZ = getattr(termios, 'TIOCSWINSZ', -2146929561)
            if TIOCSWINSZ == 2148037735:
                # Same bits, but with sign.
                TIOCSWINSZ = -2146929561
            # Note, assume ws_xpixel and ws_ypixel are zero.
            packed = struct.pack(b'HHHH', rows, cols, 0, 0)
            fcntl.ioctl(self.child_fd, TIOCSWINSZ, packed)

        def isalive(self,
                    _waitpid=os.waitpid,
                    _wnohang=os.WNOHANG,
                    _wifexited=os.WIFEXITED,
                    _wexitstatus=os.WEXITSTATUS,
                    _wifsignaled=os.WIFSIGNALED,
                    _wifstopped=os.WIFSTOPPED,
                    _wtermsig=os.WTERMSIG,
                    _os_error=os.error,
                    _errno_echild=errno.ECHILD,
                    _terminal_exception=TerminalException):
            '''
            This tests if the child process is running or not. This is
            non-blocking. If the child was terminated then this will read the
            exitstatus or signalstatus of the child. This returns True if the
            child process appears to be running or False if not. It can take
            literally SECONDS for Solaris to return the right status.
            '''
            if self.terminated:
                return False

            if self.has_unread_data is False:
                # This is for Linux, which requires the blocking form
                # of waitpid to get status of a defunct process.
                # This is super-lame. The flag_eof_* would have been set
                # in recv(), so this should be safe.
                waitpid_options = 0
            else:
                waitpid_options = _wnohang

            try:
                pid, status = _waitpid(self.pid, waitpid_options)
            except _os_error:
                err = sys.exc_info()[1]
                # No child processes
                if err.errno == _errno_echild:
                    raise _terminal_exception(
                        'isalive() encountered condition where "terminated" '
                        'is 0, but there was no child process. Did someone '
                        'else call waitpid() on our process?'
                    )
                else:
                    six.reraise(*sys.exc_info())

            # I have to do this twice for Solaris.
            # I can't even believe that I figured this out...
            # If waitpid() returns 0 it means that no child process
            # wishes to report, and the value of status is undefined.
            if pid == 0:
                try:
                    ### os.WNOHANG # Solaris!
                    pid, status = _waitpid(self.pid, waitpid_options)
                except _os_error as exc:
                    # This should never happen...
                    if exc.errno == _errno_echild:
                        raise _terminal_exception(
                            'isalive() encountered condition that should '
                            'never happen. There was no child process. Did '
                            'someone else call waitpid() on our process?'
                        )
                    else:
                        six.reraise(*sys.exc_info())

                # If pid is still 0 after two calls to waitpid() then the
                # process really is alive. This seems to work on all platforms,
                # except for Irix which seems to require a blocking call on
                # waitpid or select, so I let recv take care of this situation
                # (unfortunately, this requires waiting through the timeout).
                if pid == 0:
                    return True

            if pid == 0:
                return True

            if _wifexited(status):
                self.status = status
                self.exitstatus = _wexitstatus(status)
                self.signalstatus = None
                self.terminated = True
            elif _wifsignaled(status):
                self.status = status
                self.exitstatus = None
                self.signalstatus = _wtermsig(status)
                self.terminated = True
            elif _wifstopped(status):
                raise _terminal_exception(
                    'isalive() encountered condition where child process is '
                    'stopped. This is not supported. Is some other process '
                    'attempting job control with our child pid?'
                )
            return False

        def terminate(self, force=False):
            '''
            This forces a child process to terminate. It starts nicely with
            SIGHUP and SIGINT. If "force" is True then moves onto SIGKILL. This
            returns True if the child was terminated. This returns False if the
            child could not be terminated.
            '''
            if not self.closed:
                self.close(terminate=False)

            if not self.isalive():
                return True
            try:
                self.send_signal(signal.SIGHUP)
                time.sleep(0.1)
                if not self.isalive():
                    return True
                self.send_signal(signal.SIGCONT)
                time.sleep(0.1)
                if not self.isalive():
                    return True
                self.send_signal(signal.SIGINT)
                time.sleep(0.1)
                if not self.isalive():
                    return True
                if force:
                    self.send_signal(signal.SIGKILL)
                    time.sleep(0.1)
                    if not self.isalive():
                        return True
                    else:
                        return False
                return False
            except OSError:
                # I think there are kernel timing issues that sometimes cause
                # this to happen. I think isalive() reports True, but the
                # process is dead to the kernel.
                # Make one last attempt to see if the kernel is up to date.
                time.sleep(0.1)
                if not self.isalive():
                    return True
                else:
                    return False

        def wait(self):
            '''
            This waits until the child exits internally consuming any remaining
            output from the child, thus, no blocking forever because the child
            has unread data.
            '''
            if self.isalive():
                while self.isalive():
                    stdout, stderr = self.recv()
                    if stdout is None:
                        break
                    if stderr is None:
                        break
            else:
                raise TerminalException('Cannot wait for dead child process.')
            return self.exitstatus

        def send_signal(self, sig):
            '''
            Send a signal to the process
            '''
            os.kill(self.pid, sig)

        def kill(self):
            '''
            Kill the process with SIGKILL
            '''
            self.send_signal(signal.SIGKILL)
        # <---- Public API ---------------------------------------------------
    # <---- Linux Methods ----------------------------------------------------

    # ----- Cleanup!!! ------------------------------------------------------>
    # pylint: disable=W1701
    def __del__(self, _maxsize=sys.maxsize, _active=_ACTIVE):  # pylint: disable=W0102
        # I've disabled W0102 above which is regarding a dangerous default
        # value of [] for _ACTIVE, though, this is how Python itself handles
        # their subprocess clean up code.
        # XXX: Revisit this cleanup code to make it less dangerous.

        if self.pid is None:
            # We didn't get to successfully create a child process.
            return

        # In case the child hasn't been waited on, check if it's done.
        if self.isalive() and _ACTIVE is not None:
            # Child is still running, keep us alive until we can wait on it.
            _ACTIVE.append(self)
    # pylint: enable=W1701
    # <---- Cleanup!!! -------------------------------------------------------
# <---- Platform Specific Methods --------------------------------------------
