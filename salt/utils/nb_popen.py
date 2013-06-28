# -*- coding: utf-8 -*-
'''
    salt.utils.nb_popen
    ~~~~~~~~~~~~~~~~~~~

    Non blocking subprocess Popen.

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.
'''

# Import python libs
import os
import sys
import fcntl
import logging
import tempfile
import subprocess

log = logging.getLogger(__name__)


class NonBlockingPopen(subprocess.Popen):

    _stdout_logger_name_ = 'salt.utils.nb_popen.STDOUT.PID-{pid}'
    _stderr_logger_name_ = 'salt.utils.nb_popen.STDERR.PID-{pid}'

    def __init__(self, *args, **kwargs):
        self.stream_stds = kwargs.pop('stream_stds', False)

        # Half a megabyte in memory is more than enough to start writing to
        # a temporary file.
        self.max_size_in_mem = kwargs.pop('max_size_in_mem', 512000)

        # Let's configure the std{out,err} logging handler names
        self._stdout_logger_name_ = kwargs.pop(
            'stdout_logger_name', self._stdout_logger_name_
        )
        self._stderr_logger_name_ = kwargs.pop(
            'stderr_logger_name', self._stderr_logger_name_
        )

        super(NonBlockingPopen, self).__init__(*args, **kwargs)

        if self.stdout is not None:
            fod = self.stdout.fileno()
            fol = fcntl.fcntl(fod, fcntl.F_GETFL)
            fcntl.fcntl(fod, fcntl.F_SETFL, fol | os.O_NONBLOCK)
        self.obuff = tempfile.SpooledTemporaryFile(self.max_size_in_mem)
        self._stdout_logger = logging.getLogger(
            self._stdout_logger_name_.format(pid=self.pid)
        )

        if self.stderr is not None:
            fed = self.stderr.fileno()
            fel = fcntl.fcntl(fed, fcntl.F_GETFL)
            fcntl.fcntl(fed, fcntl.F_SETFL, fel | os.O_NONBLOCK)
        self.ebuff = tempfile.SpooledTemporaryFile(self.max_size_in_mem)
        self._stderr_logger = logging.getLogger(
            self._stderr_logger_name_.format(pid=self.pid)
        )

        log.info(
            'Running command under pid {0}: {1!r}'.format(self.pid, *args)
        )

    def poll(self):
        poll = super(NonBlockingPopen, self).poll()

        if self.stdout is not None:
            try:
                obuff = self.stdout.read()
                if obuff:
                    self.obuff.write(obuff)
                    self._stdout_logger.debug(obuff.rstrip())
                    if self.stream_stds:
                        sys.stdout.write(obuff)
            except IOError, err:
                if err.errno not in (11, 35):
                    # We only handle Resource not ready properly, any other
                    # raise the exception
                    raise

        if self.stderr is not None:
            try:
                ebuff = self.stderr.read()
                if ebuff:
                    self.ebuff.write(ebuff)
                    self._stderr_logger.debug(ebuff.rstrip())
                    if self.stream_stds:
                        sys.stderr.write(ebuff)
            except IOError, err:
                if err.errno not in (11, 35):
                    # We only handle Resource not ready properly, any other
                    # raise the exception
                    raise

        return poll

    def __del__(self):
        if self.stdout is not None:
            try:
                fod = self.stdout.fileno()
                fol = fcntl.fcntl(fod, fcntl.F_GETFL)
                fcntl.fcntl(fod, fcntl.F_SETFL, fol & ~os.O_NONBLOCK)
            except ValueError:
                # Closed FD
                pass

        if self.stderr is not None:
            try:
                fed = self.stderr.fileno()
                fel = fcntl.fcntl(fed, fcntl.F_GETFL)
                fcntl.fcntl(fed, fcntl.F_SETFL, fel & ~os.O_NONBLOCK)
            except ValueError:
                # Closed FD
                pass

        super(NonBlockingPopen, self).__del__()
