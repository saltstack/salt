# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    tests.unit.utils.vt_test
    ~~~~~~~~~~~~~~~~~~~~~~~~

    VirtualTerminal tests
'''

# Import python libs
import os
import sys
import random
import subprocess
import time

# Import Salt Testing libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
from salt.utils import fopen, is_darwin, vt


class VTTestCase(TestCase):

    @skipIf(True, 'Disabled until we can figure out why this fails when whole test suite runs.')
    def test_vt_size(self):
        '''Confirm that the terminal size is being set'''
        if not sys.stdin.isatty():
            self.skipTest('Not attached to a TTY. The test would fail.')
        cols = random.choice(range(80, 250))
        terminal = vt.Terminal(
            'echo "Foo!"',
            shell=True,
            cols=cols,
            rows=24,
            stream_stdout=False,
            stream_stderr=False
        )
        # First the assertion
        self.assertEqual(
            terminal.getwinsize(), (24, cols)
        )
        # Then wait for the terminal child to exit
        terminal.wait()
        terminal.close()

    @skipIf(True, 'Disabled until we can find out why this kills the tests suite with an exit code of 134')
    def test_issue_10404_ptys_not_released(self):
        n_executions = 15

        def current_pty_count():
            # Get current number of PTY's
            try:
                if os.path.exists('/proc/sys/kernel/pty/nr'):
                    with fopen('/proc/sys/kernel/pty/nr') as fh_:
                        return int(fh_.read().strip())

                proc = subprocess.Popen(
                    'sysctl -a 2> /dev/null | grep pty.nr | awk \'{print $3}\'',
                    shell=True,
                    stdout=subprocess.PIPE
                )
                stdout, _ = proc.communicate()
                return int(stdout.strip())
            except (ValueError, OSError, IOError):
                if is_darwin():
                    # We're unable to findout how many PTY's are open
                    self.skipTest(
                        'Unable to find out how many PTY\'s are open on Darwin - '
                        'Skipping for now'
                    )
                self.fail('Unable to find out how many PTY\'s are open')

        nr_ptys = current_pty_count()

        # Using context manager's
        for idx in range(0, nr_ptys + n_executions):
            try:
                with vt.Terminal('echo "Run {0}"'.format(idx),
                                shell=True,
                                stream_stdout=False,
                                stream_stderr=False) as terminal:
                    terminal.wait()
                try:
                    if current_pty_count() > (nr_ptys + (n_executions/2)):
                        self.fail('VT is not cleaning up PTY\'s')
                except (ValueError, OSError, IOError):
                    self.fail('Unable to find out how many PTY\'s are open')
            except Exception as exc:
                if 'out of pty devices' in exc:
                    # We're not cleaning up
                    raise
                # We're pushing the system resources, let's keep going
                continue

        # Not using context manager's
        for idx in range(0, nr_ptys + n_executions):
            try:
                terminal = vt.Terminal('echo "Run {0}"'.format(idx),
                                       shell=True,
                                       stream_stdout=False,
                                       stream_stderr=False)
                terminal.wait()
                try:
                    if current_pty_count() > (nr_ptys + (n_executions/2)):
                        self.fail('VT is not cleaning up PTY\'s')
                except (ValueError, OSError, IOError):
                    self.fail('Unable to find out how many PTY\'s are open')
            except Exception as exc:
                if 'out of pty devices' in exc:
                    # We're not cleaning up
                    raise
                # We're pushing the system resources, let's keep going
                continue

    def test_isalive_while_theres_data_to_read(self):
        expected_data = 'Alive!\n'
        term = vt.Terminal('echo "Alive!"', shell=True, stream_stdout=False, stream_stderr=False)
        buffer_o = buffer_e = ''
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

        expected_data = 'Alive!\n'
        term = vt.Terminal('echo "Alive!" 1>&2', shell=True, stream_stdout=False, stream_stderr=False)
        buffer_o = buffer_e = ''
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

        expected_data = 'Alive!\nAlive!\n'
        term = vt.Terminal('echo "Alive!"; sleep 1; echo "Alive!"', shell=True, stream_stdout=False, stream_stderr=False)
        buffer_o = buffer_e = ''
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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(VTTestCase, needs_daemon=False)
