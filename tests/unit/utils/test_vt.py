import functools
import io
import os
import random
import subprocess
import sys
import time

import pytest

import salt.utils
import salt.utils.files
import salt.utils.platform
import salt.utils.stringutils
import salt.utils.vt
from tests.support.paths import CODE_DIR
from tests.support.unit import TestCase


def stdout_fileno_available():
    """
    Tests if sys.stdout.fileno is available in this testing environment
    """
    try:
        sys.stdout.fileno()
        return True
    except io.UnsupportedOperation:
        return False


def fixStdOutErrFileNoIfNeeded(func):
    """
    Decorator that sets stdout and stderr to their original objects if
    sys.stdout.fileno() doesn't work and restores them after running the
    decorated function. This doesn't check if the original objects actually
    work. If they don't then the test environment is too broken to test
    the VT.
    """

    @functools.wraps(func)
    def wrapper_fixStdOutErrFileNoIfNeeded(*args, **kwargs):
        original_stdout = os.sys.stdout
        original_stderr = os.sys.stderr
        if not stdout_fileno_available():
            os.sys.stdout = os.sys.__stdout__
            os.sys.stderr = os.sys.__stderr__
        try:
            return func(*args, **kwargs)
        finally:
            os.sys.stdout = original_stdout
            os.sys.stderr = original_stderr

    return wrapper_fixStdOutErrFileNoIfNeeded


class VTTestCase(TestCase):
    @pytest.mark.skip_on_windows(
        reason="Skip on Windows because this feature is not supported",
    )
    def test_vt_size(self):
        """Confirm that the terminal size is being set"""
        cols = random.choice(range(80, 250))
        terminal = salt.utils.vt.Terminal(
            "stty size",
            shell=True,
            cols=cols,
            rows=24,
            stream_stdout=False,
            stream_stderr=False,
        )
        self.assertEqual(terminal.getwinsize(), (24, cols))
        buffer_o = buffer_e = ""
        while terminal.has_unread_data:
            stdout, stderr = terminal.recv()
            if stdout:
                buffer_o += stdout
            if stderr:
                buffer_e += stderr
        assert buffer_o.strip() == "24 {}".format(cols)
        try:
            # Then wait for the terminal child to exit, this will raise an
            # exception if the process has already exited.
            terminal.wait()
        except salt.utils.vt.TerminalException:
            pass
        terminal.close()

    @pytest.mark.skip(
        reason="Disabled until we can find out why this kills the tests suite with an exit code of 134",
    )
    def test_issue_10404_ptys_not_released(self):
        n_executions = 15

        def current_pty_count():
            # Get current number of PTY's
            try:
                if os.path.exists("/proc/sys/kernel/pty/nr"):
                    with salt.utils.files.fopen("/proc/sys/kernel/pty/nr") as fh_:
                        return int(fh_.read().strip())

                proc = subprocess.Popen(
                    "sysctl -a 2> /dev/null | grep pty.nr | awk '{print $3}'",
                    shell=True,
                    stdout=subprocess.PIPE,
                )
                stdout, _ = proc.communicate()
                return int(stdout.strip())
            except (ValueError, OSError):
                if salt.utils.platform.is_darwin():
                    # We're unable to findout how many PTY's are open
                    self.skipTest(
                        "Unable to find out how many PTY's are open on Darwin - "
                        "Skipping for now"
                    )
                self.fail("Unable to find out how many PTY's are open")

        nr_ptys = current_pty_count()

        # Using context manager's
        for idx in range(0, nr_ptys + n_executions):
            try:
                with salt.utils.vt.Terminal(
                    'echo "Run {}"'.format(idx),
                    shell=True,
                    stream_stdout=False,
                    stream_stderr=False,
                ) as terminal:
                    terminal.wait()
                try:
                    if current_pty_count() > (nr_ptys + (n_executions / 2)):
                        self.fail("VT is not cleaning up PTY's")
                except (ValueError, OSError):
                    self.fail("Unable to find out how many PTY's are open")
            except Exception as exc:  # pylint: disable=broad-except
                if "out of pty devices" in str(exc):
                    # We're not cleaning up
                    raise
                # We're pushing the system resources, let's keep going
                continue

        # Not using context manager's
        for idx in range(0, nr_ptys + n_executions):
            try:
                terminal = salt.utils.vt.Terminal(
                    'echo "Run {}"'.format(idx),
                    shell=True,
                    stream_stdout=False,
                    stream_stderr=False,
                )
                terminal.wait()
                try:
                    if current_pty_count() > (nr_ptys + (n_executions / 2)):
                        self.fail("VT is not cleaning up PTY's")
                except (ValueError, OSError):
                    self.fail("Unable to find out how many PTY's are open")
            except Exception as exc:  # pylint: disable=broad-except
                if "out of pty devices" in str(exc):
                    # We're not cleaning up
                    raise
                # We're pushing the system resources, let's keep going
                continue

    @pytest.mark.skip(
        reason="Disabled until we can figure out how to make this more reliable."
    )
    def test_isalive_while_theres_data_to_read(self):
        expected_data = "Alive!\n"
        term = salt.utils.vt.Terminal(
            'echo "Alive!"', shell=True, stream_stdout=False, stream_stderr=False
        )
        buffer_o = buffer_e = ""
        try:
            while term.has_unread_data:
                stdout, stderr = term.recv()
                if stdout:
                    buffer_o += stdout
                if stderr:
                    buffer_e += stderr
                # While there's data to be read, the process is alive
                if stdout is None and stderr is None:
                    self.assertFalse(term.isalive())

            # term should be dead now
            self.assertEqual(buffer_o, expected_data)
            self.assertFalse(term.isalive())

            stdout, stderr = term.recv()
            self.assertFalse(term.isalive())
            self.assertIsNone(stderr)
            self.assertIsNone(stdout)
        finally:
            term.close(terminate=True, kill=True)

        expected_data = "Alive!\n"
        term = salt.utils.vt.Terminal(
            'echo "Alive!" 1>&2', shell=True, stream_stdout=False, stream_stderr=False
        )
        buffer_o = buffer_e = ""
        try:
            while term.has_unread_data:
                stdout, stderr = term.recv()
                if stdout:
                    buffer_o += stdout
                if stderr:
                    buffer_e += stderr
                # While there's data to be read, the process is alive
                if stdout is None and stderr is None:
                    self.assertFalse(term.isalive())

            # term should be dead now
            self.assertEqual(buffer_e, expected_data)
            self.assertFalse(term.isalive())

            stdout, stderr = term.recv()
            self.assertFalse(term.isalive())
            self.assertIsNone(stderr)
            self.assertIsNone(stdout)
        finally:
            term.close(terminate=True, kill=True)

        expected_data = "Alive!\nAlive!\n"
        term = salt.utils.vt.Terminal(
            'echo "Alive!"; sleep 5; echo "Alive!"',
            shell=True,
            stream_stdout=False,
            stream_stderr=False,
        )
        buffer_o = buffer_e = ""
        try:
            while term.has_unread_data:
                stdout, stderr = term.recv()
                if stdout:
                    buffer_o += stdout
                if stderr:
                    buffer_e += stderr
                # While there's data to be read, the process is alive
                if stdout is None and stderr is None:
                    self.assertFalse(term.isalive())

                if buffer_o != expected_data:
                    self.assertTrue(term.isalive())
                # Don't spin
                time.sleep(0.1)

            # term should be dead now
            self.assertEqual(buffer_o, expected_data)
            self.assertFalse(term.isalive())

            stdout, stderr = term.recv()
            self.assertFalse(term.isalive())
            self.assertIsNone(stderr)
            self.assertIsNone(stdout)
        finally:
            term.close(terminate=True, kill=True)

    @staticmethod
    def generate_multibyte_stdout_unicode(block_size):
        return b"\xE2\x80\xA6" * 4 * block_size

    @staticmethod
    def generate_multibyte_stderr_unicode(block_size):
        return b"\x2E" + VTTestCase.generate_multibyte_stdout_unicode(block_size)

    @pytest.mark.skip_initial_onedir_failure
    @pytest.mark.skip_on_windows(reason="Skip VT tests on windows, due to issue 54290")
    @fixStdOutErrFileNoIfNeeded
    def test_split_multibyte_characters_unicode(self):
        """
        Tests that the vt correctly handles multibyte characters that are
        split between blocks of transmitted data.
        """
        block_size = 1024
        encoding = "utf-8"
        stdout_content = VTTestCase.generate_multibyte_stdout_unicode(block_size)
        # stderr is offset by one byte to guarentee a split character in
        # one of the output streams
        stderr_content = VTTestCase.generate_multibyte_stderr_unicode(block_size)

        expected_stdout = salt.utils.stringutils.to_unicode(stdout_content, encoding)
        expected_stderr = salt.utils.stringutils.to_unicode(stderr_content, encoding)
        python_command = "\n".join(
            (
                "import sys",
                "import os",
                "import warnings",
                "warnings.simplefilter('ignore')",
                "import tests.unit.utils.test_vt as test_vt",
                (
                    "os.write(sys.stdout.fileno(), "
                    "test_vt.VTTestCase.generate_multibyte_stdout_unicode("
                    + str(block_size)
                    + "))"
                ),
                (
                    "os.write(sys.stderr.fileno(), "
                    "test_vt.VTTestCase.generate_multibyte_stderr_unicode("
                    + str(block_size)
                    + "))"
                ),
            )
        )
        env = os.environ.copy()
        env["PYTHONWARNINGS"] = "ignore"
        term = salt.utils.vt.Terminal(
            args=[sys.executable, "-c", '"' + python_command + '"'],
            shell=True,
            cwd=CODE_DIR,
            env=env,
            stream_stdout=False,
            stream_stderr=False,
            force_receive_encoding=encoding,
        )
        buffer_o = buffer_e = salt.utils.stringutils.to_unicode("")
        try:
            while term.has_unread_data:
                stdout, stderr = term.recv(block_size)
                if stdout:
                    buffer_o += stdout
                if stderr:
                    buffer_e += stderr

            self.assertEqual(buffer_o, expected_stdout)
            self.assertEqual(buffer_e, expected_stderr)
        finally:
            term.close(terminate=True, kill=True)

    @staticmethod
    def generate_multibyte_stdout_shiftjis(block_size):
        return b"\x8B\x80" * 4 * block_size

    @staticmethod
    def generate_multibyte_stderr_shiftjis(block_size):
        return b"\x2E" + VTTestCase.generate_multibyte_stdout_shiftjis(block_size)

    @pytest.mark.skip_initial_onedir_failure
    @pytest.mark.skip_on_windows(reason="Skip VT tests on windows, due to issue 54290")
    @fixStdOutErrFileNoIfNeeded
    def test_split_multibyte_characters_shiftjis(self):
        """
        Tests that the vt correctly handles multibyte characters that are
        split between blocks of transmitted data.
        Uses shift-jis encoding to make sure code doesn't assume unicode.
        """
        block_size = 1024
        encoding = "shift-jis"
        stdout_content = VTTestCase.generate_multibyte_stdout_shiftjis(block_size)
        stderr_content = VTTestCase.generate_multibyte_stderr_shiftjis(block_size)

        expected_stdout = salt.utils.stringutils.to_unicode(stdout_content, encoding)
        expected_stderr = salt.utils.stringutils.to_unicode(stderr_content, encoding)
        python_command = "\n".join(
            (
                "import sys",
                "import os",
                "import warnings",
                "warnings.simplefilter('ignore')",
                "import tests.unit.utils.test_vt as test_vt",
                (
                    "os.write(sys.stdout.fileno(), "
                    "test_vt.VTTestCase.generate_multibyte_stdout_shiftjis("
                    + str(block_size)
                    + "))"
                ),
                (
                    "os.write(sys.stderr.fileno(), "
                    "test_vt.VTTestCase.generate_multibyte_stderr_shiftjis("
                    + str(block_size)
                    + "))"
                ),
            )
        )
        env = os.environ.copy()
        env["PYTHONWARNINGS"] = "ignore"
        term = salt.utils.vt.Terminal(
            args=[sys.executable, "-c", '"' + python_command + '"'],
            shell=True,
            cwd=CODE_DIR,
            env=env,
            stream_stdout=False,
            stream_stderr=False,
            force_receive_encoding=encoding,
        )
        buffer_o = buffer_e = salt.utils.stringutils.to_unicode("")
        try:
            while term.has_unread_data:
                stdout, stderr = term.recv(block_size)
                if stdout:
                    buffer_o += stdout
                if stderr:
                    buffer_e += stderr

            self.assertEqual(buffer_o, expected_stdout)
            self.assertEqual(buffer_e, expected_stderr)
        finally:
            term.close(terminate=True, kill=True)
