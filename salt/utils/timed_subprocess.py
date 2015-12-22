# -*- coding: utf-8 -*-
'''For running command line executables with a timeout'''
from __future__ import absolute_import

import subprocess
import threading
import salt.exceptions
from salt.ext import six


class TimedProc(object):
    '''
    Create a TimedProc object, calls subprocess.Popen with passed args and **kwargs
    '''
    def __init__(self, args, **kwargs):

        self.wait = kwargs.pop('wait', True)

        # If you're not willing to wait for the process
        # you can't define any stdin, stdout or stderr
        if not self.wait:
            self.stdin = kwargs['stdin'] = None
        else:
            self.stdin = kwargs.pop('stdin', None)
            if self.stdin is not None:
                # Translate a newline submitted as '\n' on the CLI to an actual
                # newline character.
                self.stdin = self.stdin.replace('\\n', '\n')
                kwargs['stdin'] = subprocess.PIPE

        self.with_communicate = kwargs.pop('with_communicate', self.wait)
        if not self.with_communicate:
            self.stdout = kwargs['stdout'] = None
            self.stderr = kwargs['stderr'] = None

        if not self.wait or 'timeout' not in kwargs:
            self.timeout = None
        else:
            self.timeout = kwargs.pop('timeout')
            if self.timeout is not None and not isinstance(self.timeout, (int, float)):
                raise salt.exceptions.TimedProcTimeoutError('Error: timeout {0} must be a number'.format(timeout))

        try:
            self.process = subprocess.Popen(args, **kwargs)
        except TypeError:
            str_args = []
            for arg in args:
                if not isinstance(arg, six.string_types):
                    str_args.append(str(arg))
                else:
                    str_args.append(arg)
            args = str_args
            self.process = subprocess.Popen(args, **kwargs)
        self.command = args

    def run(self):
        '''
        wait for subprocess to terminate and return subprocess' return code.
        If timeout is reached, throw TimedProcTimeoutError
        '''
        def receive():
            if self.with_communicate:
                self.stdout, self.stderr = self.process.communicate(input=self.stdin)
            elif self.wait:
                self.process.wait()

        if not self.wait or not self.timeout:
            receive()
        else:
            rt = threading.Thread(target=receive)
            rt.start()
            rt.join(self.timeout)
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
                        str(self.timeout),
                    )
                )
        return self.process.returncode
