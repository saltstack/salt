"""
For running command line executables with a timeout
"""

import shlex
import subprocess
import threading

import salt.exceptions
import salt.utils.data
import salt.utils.stringutils


class TimedProc:
    """
    Create a TimedProc object, calls subprocess.Popen with passed args and **kwargs
    """

    def __init__(self, args, **kwargs):

        self.wait = not kwargs.pop("bg", False)
        self.stdin = kwargs.pop("stdin", None)
        self.with_communicate = kwargs.pop("with_communicate", self.wait)
        self.timeout = kwargs.pop("timeout", None)
        self.stdin_raw_newlines = kwargs.pop("stdin_raw_newlines", False)

        # If you're not willing to wait for the process
        # you can't define any stdin, stdout or stderr
        if not self.wait:
            self.stdin = kwargs["stdin"] = None
            self.with_communicate = False
        elif self.stdin is not None:
            if not self.stdin_raw_newlines:
                # Translate a newline submitted as '\n' on the CLI to an actual
                # newline character.
                self.stdin = self.stdin.replace("\\n", "\n")
            self.stdin = salt.utils.stringutils.to_bytes(self.stdin)
            kwargs["stdin"] = subprocess.PIPE

        if not self.with_communicate:
            self.stdout = kwargs["stdout"] = None
            self.stderr = kwargs["stderr"] = None

        if self.timeout and not isinstance(self.timeout, (int, float)):
            raise salt.exceptions.TimedProcTimeoutError(
                f"Error: timeout {self.timeout} must be a number"
            )
        if kwargs.get("shell", False):
            args = salt.utils.data.decode(args, to_str=True)

        try:
            self.process = subprocess.Popen(args, **kwargs)
        except (AttributeError, TypeError):
            if not kwargs.get("shell", False):
                if not isinstance(args, (list, tuple)):
                    try:
                        args = shlex.split(args)
                    except AttributeError:
                        args = shlex.split(str(args))
                str_args = []
                for arg in args:
                    if not isinstance(arg, str):
                        str_args.append(str(arg))
                    else:
                        str_args.append(arg)
                args = str_args
            else:
                if not isinstance(args, (list, tuple, str)):
                    # Handle corner case where someone does a 'cmd.run 3'
                    args = str(args)
            # Ensure that environment variables are strings
            for key, val in kwargs.get("env", {}).items():
                if not isinstance(val, str):
                    kwargs["env"][key] = str(val)
                if not isinstance(key, str):
                    kwargs["env"][str(key)] = kwargs["env"].pop(key)
            args = salt.utils.data.decode(args)
            self.process = subprocess.Popen(args, **kwargs)
        self.command = args

    def run(self):
        """
        wait for subprocess to terminate and return subprocess' return code.
        If timeout is reached, throw TimedProcTimeoutError
        """

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
            if rt.is_alive():
                # Subprocess cleanup (best effort)
                self.process.kill()

                def terminate():
                    if rt.is_alive():
                        self.process.terminate()

                threading.Timer(10, terminate).start()
                raise salt.exceptions.TimedProcTimeoutError(
                    "{} : Timed out after {} seconds".format(
                        self.command,
                        str(self.timeout),
                    )
                )
        return self.process.returncode
