# -*- coding: utf-8 -*-
'''
    saltcloud.utils.nb_popen
    ~~~~~~~~~~~~~~~~~~~~~~~~

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
import subprocess

log = logging.getLogger(__name__)


class CloudNonBlockingPopen(subprocess.Popen):

    def __init__(self, *args, **kwargs):
        self.stream_stds = kwargs.pop('stream_stds', False)
        super(NonBlockingPopen, self).__init__(*args, **kwargs)

        if self.stdout is not None:
            fod = self.stdout.fileno()
            fol = fcntl.fcntl(fod, fcntl.F_GETFL)
            fcntl.fcntl(fod, fcntl.F_SETFL, fol | os.O_NONBLOCK)
        self.obuff = ''

        if self.stderr is not None:
            fed = self.stderr.fileno()
            fel = fcntl.fcntl(fed, fcntl.F_GETFL)
            fcntl.fcntl(fed, fcntl.F_SETFL, fel | os.O_NONBLOCK)
        self.ebuff = ''

        log.info('Running command {0!r}'.format(*args))

    def poll(self):
        poll = super(NonBlockingPopen, self).poll()

        if self.stdout is not None:
            try:
                obuff = self.stdout.read()
                self.obuff += obuff
                if obuff:
                    logging.getLogger(
                        'saltcloud.Popen.STDOUT.PID-{0}'.format(self.pid)
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
                self.ebuff += ebuff
                if ebuff:
                    logging.getLogger(
                        'saltcloud.Popen.STDERR.PID-{0}'.format(self.pid)
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


try:
    from salt.utils.nb_popen import NonBlockingPopen as SaltNonBlockingPopen

    class NonBlockingPopen(SaltNonBlockingPopen):
        _stdout_logger_name_ = 'saltcloud.utils.nb_popen.STDOUT.PID-{pid}'
        _stderr_logger_name_ = 'saltcloud.utils.nb_popen.STDERR.PID-{pid}'

except ImportError:
    NonBlockingPopen = CloudNonBlockingPopen
