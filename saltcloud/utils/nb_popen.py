# -*- coding: utf-8 -*-
'''
    saltcloud.utils.nb_popen
    ~~~~~~~~~~~~~~~~~~~~~~~~

    Non blocking subprocess Popen.

    This functionality has been adapted to work on windows following the recipe
    found on:

        http://code.activestate.com/recipes/440554/

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.
'''

# Import python libs
import os
import sys
import time
import errno
import select
import logging
import tempfile
import subprocess

if subprocess.mswindows:
    from win32file import ReadFile, WriteFile
    from win32pipe import PeekNamedPipe
    import msvcrt
else:
    import fcntl

log = logging.getLogger(__name__)


class CloudNonBlockingPopen(subprocess.Popen):

    _stdout_logger_name_ = 'saltcloud.utils.nb_popen.STDOUT.PID-{pid}'
    _stderr_logger_name_ = 'saltcloud.utils.nb_popen.STDERR.PID-{pid}'

    def __init__(self, *args, **kwargs):
        self.stream_stds = kwargs.pop('stream_stds', False)

        # Half a megabyte in memory is more than enough to start writing to
        # a temporary file.
        self.max_size_in_mem = kwargs.pop('max_size_in_mem', 512000)

        # Let's configure the std{in, out,err} logging handler names
        #self._stdin_logger_name_ = kwargs.pop(
        #    'stdin_logger_name', self._stdin_logger_name_
        #)
        self._stdout_logger_name_ = kwargs.pop(
            'stdout_logger_name', self._stdout_logger_name_
        )
        self._stderr_logger_name_ = kwargs.pop(
            'stderr_logger_name', self._stderr_logger_name_
        )

        super(CloudNonBlockingPopen, self).__init__(*args, **kwargs)

        #self._stdin_logger = logging.getLogger(
        #    self._stdin_logger_name_.format(pid=self.pid)
        #)

        self.stdout_buff = tempfile.SpooledTemporaryFile(self.max_size_in_mem)
        self._stdout_logger = logging.getLogger(
            self._stdout_logger_name_.format(pid=self.pid)
        )

        self.stderr_buff = tempfile.SpooledTemporaryFile(self.max_size_in_mem)
        self._stderr_logger = logging.getLogger(
            self._stderr_logger_name_.format(pid=self.pid)
        )
        log.info(
            'Running command under pid {0}: {1!r}'.format(self.pid, *args)
        )

    def recv(self, maxsize=None):
        return self._recv('stdout', maxsize)

    def recv_err(self, maxsize=None):
        return self._recv('stderr', maxsize)

    def send_recv(self, input='', maxsize=None):
        return self.send(input), self.recv(maxsize), self.recv_err(maxsize)

    def get_conn_maxsize(self, which, maxsize):
        if maxsize is None:
            maxsize = 1024
        elif maxsize < 1:
            maxsize = 1
        return getattr(self, which), maxsize

    def _close(self, which):
        getattr(self, which).close()
        setattr(self, which, None)

    if subprocess.mswindows:
        def send(self, input):
            if not self.stdin:
                return None

            try:
                x = msvcrt.get_osfhandle(self.stdin.fileno())
                (errCode, written) = WriteFile(x, input)
                #self._stdin_logger.debug(input.rstrip())
            except ValueError:
                return self._close('stdin')
            except (subprocess.pywintypes.error, Exception), why:
                if why[0] in (109, errno.ESHUTDOWN):
                    return self._close('stdin')
                raise

            return written

        def _recv(self, which, maxsize):
            conn, maxsize = self.get_conn_maxsize(which, maxsize)
            if conn is None:
                return None

            try:
                x = msvcrt.get_osfhandle(conn.fileno())
                (read, nAvail, nMessage) = PeekNamedPipe(x, 0)
                if maxsize < nAvail:
                    nAvail = maxsize
                if nAvail > 0:
                    (errCode, read) = ReadFile(x, nAvail, None)
            except ValueError:
                return self._close(which)
            except (subprocess.pywintypes.error, Exception), why:
                if why[0] in (109, errno.ESHUTDOWN):
                    return self._close(which)
                raise

            getattr(self, '{0}_buff'.format(which)).write(read)
            getattr(self, '_{0}_logger'.format(which)).debug(read.rstrip())
            if self.stream_stds:
                getattr(sys, which).write(read)

            if self.universal_newlines:
                read = self._translate_newlines(read)
            return read

    else:

        def send(self, input):
            if not self.stdin:
                return None

            if not select.select([], [self.stdin], [], 0)[1]:
                return 0

            try:
                written = os.write(self.stdin.fileno(), input)
                #self._stdin_logger.debug(input.rstrip())
            except OSError, why:
                if why[0] == errno.EPIPE:  # broken pipe
                    return self._close('stdin')
                raise

            return written

        def _recv(self, which, maxsize):
            conn, maxsize = self.get_conn_maxsize(which, maxsize)
            if conn is None:
                return None

            flags = fcntl.fcntl(conn, fcntl.F_GETFL)
            if not conn.closed:
                fcntl.fcntl(conn, fcntl.F_SETFL, flags | os.O_NONBLOCK)

            try:
                if not select.select([conn], [], [], 0)[0]:
                    return ''

                buff = conn.read(maxsize)
                if not buff:
                    return self._close(which)

                if self.universal_newlines:
                    buff = self._translate_newlines(buff)

                getattr(self, '{0}_buff'.format(which)).write(buff)
                getattr(self, '_{0}_logger'.format(which)).debug(buff.rstrip())
                if self.stream_stds:
                    getattr(sys, which).write(buff)

                return buff
            finally:
                if not conn.closed:
                    fcntl.fcntl(conn, fcntl.F_SETFL, flags)

    def poll_and_read_until_finish(self):
        while self.poll() is None:
            if self.stdout is not None:
                self.recv()

            if self.stderr is not None:
                self.recv_err()

            time.sleep(0.01)


try:
    from salt.utils.nb_popen import NonBlockingPopen as SaltNonBlockingPopen

    class NonBlockingPopen(SaltNonBlockingPopen):
        _stdout_logger_name_ = 'saltcloud.utils.nb_popen.STDOUT.PID-{pid}'
        _stderr_logger_name_ = 'saltcloud.utils.nb_popen.STDERR.PID-{pid}'

except ImportError:
    NonBlockingPopen = CloudNonBlockingPopen
