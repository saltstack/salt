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
import subprocess


class NonBlockingPopen(subprocess.Popen):

    def __init__(self, *args, **kwargs):
        self.stream_stds = kwargs.pop('stream_stds', False)
        super(NonBlockingPopen, self).__init__(*args, **kwargs)
        if self.stdout is not None and self.stream_stds:
            fod = self.stdout.fileno()
            fol = fcntl.fcntl(fod, fcntl.F_GETFL)
            fcntl.fcntl(fod, fcntl.F_SETFL, fol | os.O_NONBLOCK)
            self.obuff = ''

        if self.stderr is not None and self.stream_stds:
            fed = self.stderr.fileno()
            fel = fcntl.fcntl(fed, fcntl.F_GETFL)
            fcntl.fcntl(fed, fcntl.F_SETFL, fel | os.O_NONBLOCK)
            self.ebuff = ''

    def poll(self):
        poll = super(NonBlockingPopen, self).poll()

        if self.stdout is not None and self.stream_stds:
            try:
                obuff = self.stdout.read()
                self.obuff += obuff
                sys.stdout.write(obuff)
            except IOError, err:
                if err.errno not in (11, 35):
                    # We only handle Resource not ready properly, any other
                    # raise the exception
                    raise
        if self.stderr is not None and self.stream_stds:
            try:
                ebuff = self.stderr.read()
                self.ebuff += ebuff
                sys.stderr.write(ebuff)
            except IOError, err:
                if err.errno not in (11, 35):
                    # We only handle Resource not ready properly, any other
                    # raise the exception
                    raise

        if poll is None:
            # Not done yet
            return poll

        if not self.stream_stds:
            # Allow the same attribute access even though not streaming to stds
            try:
                self.obuff = self.stdout.read()
            except IOError, err:
                if err.errno not in (11, 35):
                    # We only handle Resource not ready properly, any other
                    # raise the exception
                    raise
            try:
                self.ebuff = self.stderr.read()
            except IOError, err:
                if err.errno not in (11, 35):
                    # We only handle Resource not ready properly, any other
                    # raise the exception
                    raise
        return poll
