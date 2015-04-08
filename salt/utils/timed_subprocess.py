# -*- coding: utf-8 -*-
'''For running command line executables with a timeout'''
from __future__ import absolute_import

import subprocess
import threading
import salt.exceptions


class TimedProc(object):
    '''
    Create a TimedProc object, calls subprocess.Popen with passed args and **kwargs
    '''
    def __init__(self, args, **kwargs):

        self.command = args
        self.stdin = kwargs.pop('stdin', None)
        if self.stdin is not None:
            # Translate a newline submitted as '\n' on the CLI to an actual
            # newline character.
            self.stdin = self.stdin.replace('\\n', '\n')
            kwargs['stdin'] = subprocess.PIPE
        self.with_communicate = kwargs.pop('with_communicate', True)

        self.process = subprocess.Popen(args, **kwargs)

    def wait(self, timeout=None):
        '''
        wait for subprocess to terminate and return subprocess' return code.
        If timeout is reached, throw TimedProcTimeoutError
        '''
        def receive():
            if self.with_communicate:
                (self.stdout, self.stderr) = self.process.communicate(input=self.stdin)
            else:
                self.process.wait()
                (self.stdout, self.stderr) = (None, None)

        if timeout:
            if not isinstance(timeout, (int, float)):
                raise salt.exceptions.TimedProcTimeoutError('Error: timeout must be a number')
            rt = threading.Thread(target=receive)
            rt.start()
            rt.join(timeout)
            if rt.isAlive():
                # Subprocess cleanup (best effort)
                self.process.kill()

                def terminate():
                    if rt.isAlive():
                        self.process.terminate()
                threading.Timer(10, terminate).start()
                raise salt.exceptions.TimedProcTimeoutError(
                    '{0} : Timed out after {1} seconds'.format(
                        self.command,
                        str(timeout),
                    )
                )
        else:
            receive()
        return self.process.returncode
