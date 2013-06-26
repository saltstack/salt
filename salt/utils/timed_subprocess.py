"""For running command line executables with a timeout"""

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
        self.process = subprocess.Popen(args, stdin=subprocess.PIPE, **kwargs)

    def wait(self, timeout=None):
        '''
        wait for subprocess to terminate and return subprocess' return code.
        If timeout is reached, throw TimedProcTimeoutError
        '''
        def receive():
            (self.stdout, self.stderr) = \
                self.process.communicate(input=self.stdin)

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
                raise salt.exceptions.TimedProcTimeoutError('%s : Timed out after %s seconds' % (
                    self.command,
                    str(timeout),
                ))
        else:
            receive()
        return self.process.returncode
