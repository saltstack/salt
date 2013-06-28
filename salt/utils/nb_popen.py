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
import io
import os
import sys
import fcntl
import logging
import tempfile
import subprocess

log = logging.getLogger(__name__)


class NonBlockingPopen(subprocess.Popen):

    def __init__(self, *args, **kwargs):
        self.stream_stds = kwargs.pop('stream_stds', False)
        super(NonBlockingPopen, self).__init__(*args, **kwargs)

        if self.stdout is not None:
            fod = self.stdout.fileno()
            fol = fcntl.fcntl(fod, fcntl.F_GETFL)
            fcntl.fcntl(fod, fcntl.F_SETFL, fol | os.O_NONBLOCK)
        self.obuff = SubprocessBuffer()

        if self.stderr is not None:
            fed = self.stderr.fileno()
            fel = fcntl.fcntl(fed, fcntl.F_GETFL)
            fcntl.fcntl(fed, fcntl.F_SETFL, fel | os.O_NONBLOCK)
        self.ebuff = SubprocessBuffer()

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
                    logging.getLogger(
                        'salt.utils.nb_popen.STDOUT.PID-{0}'.format(self.pid)
                    ).debug(obuff.rstrip())
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
                    logging.getLogger(
                        'salt.utils.nb_popen.STDERR.PID-{0}'.format(self.pid)
                    ).debug(ebuff.rstrip())
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


class SubprocessBuffer(object):
    '''
    Simple buffer which holds data in memory up to a specific size. If more
    than the allowed needs to be written, the internal buffer is switched for
    a temporary file used for the remaining of the write operations.
    '''

    # Half a megabyte in memory is more than enough to start writing to
    # a temporary file.
    max_size_in_mem = 512000

    def __init__(self, initial_contents=''):
        self.__buffer = io.BytesIO(initial_contents)
        if initial_contents:
            self.__buffer.write(initial_contents)

    def write(self, bytes):
        if isinstance(self.__buffer, io.BytesIO) and \
                self.__buffer.tell() + len(bytes) >= self.max_size_in_mem:
            filebuffer = tempfile.TemporaryFile('wb+')
            self.__buffer.seek(0)
            filebuffer.write(self.__buffer.read())
            self.__buffer.close()
            self.__buffer = filebuffer
        self.__buffer.write(bytes)

    def read(self):
        self.__buffer.seek(0)
        return self.__buffer.read()
