# -*- coding: utf-8 -*-
'''
For running command line executables with a timeout
'''
from __future__ import absolute_import, print_function, unicode_literals

import shlex
import subprocess
import threading
import salt.exceptions
import salt.utils.data
from salt.ext import six


class TimedProc(object):
    '''
    Create a TimedProc object, calls subprocess.Popen with passed args and **kwargs
    '''
    def __init__(self, args, **kwargs):

        self.wait = not kwargs.pop('bg', False)
        self.stdin = kwargs.pop('stdin', None)
        self.with_communicate = kwargs.pop('with_communicate', self.wait)
        self.timeout = kwargs.pop('timeout', None)

        # If you're not willing to wait for the process
        # you can't define any stdin, stdout or stderr
        if not self.wait:
            self.stdin = kwargs['stdin'] = None
            self.with_communicate = False
        elif self.stdin is not None:
            # Translate a newline submitted as '\n' on the CLI to an actual
            # newline character.
            self.stdin = self.stdin.replace('\\n', '\n').encode(__salt_system_encoding__)
            kwargs['stdin'] = subprocess.PIPE

        if not self.with_communicate:
            self.stdout = kwargs['stdout'] = None
            self.stderr = kwargs['stderr'] = None

        if self.timeout and not isinstance(self.timeout, (int, float)):
            raise salt.exceptions.TimedProcTimeoutError('Error: timeout {0} must be a number'.format(self.timeout))

        try:
            self.process = subprocess.Popen(args, **kwargs)
        except (AttributeError, TypeError):
            if not kwargs.get('shell', False):
                if not isinstance(args, (list, tuple)):
                    try:
                        args = shlex.split(args)
                    except AttributeError:
                        args = shlex.split(six.text_type(args))
                str_args = []
                for arg in args:
                    if not isinstance(arg, six.string_types):
                        str_args.append(six.text_type(arg))
                    else:
                        str_args.append(arg)
                args = str_args
            else:
                if not isinstance(args, (list, tuple, six.string_types)):
                    # Handle corner case where someone does a 'cmd.run 3'
                    args = six.text_type(args)
            # Ensure that environment variables are strings
            for key, val in six.iteritems(kwargs.get('env', {})):
                if not isinstance(val, six.string_types):
                    kwargs['env'][key] = six.text_type(val)
                if not isinstance(key, six.string_types):
                    kwargs['env'][six.text_type(key)] = kwargs['env'].pop(key)
            if six.PY2 and 'env' in kwargs:
                # Ensure no unicode in custom env dict, as it can cause
                # problems with subprocess.
                kwargs['env'] = salt.utils.data.encode_dict(kwargs['env'])
            args = salt.utils.data.decode(args)
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

        if not self.timeout:
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
                        six.text_type(self.timeout),
                    )
                )
        return self.process.returncode
