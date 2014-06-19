# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    tests.unit.utils.vt_test
    ~~~~~~~~~~~~~~~~~~~~~~~~

    VirtualTerminal tests
'''

# Import python libs
import sys
import random

# Import Salt Testing libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
from salt.utils import vt


class VTTestCase(TestCase):

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

    def test_issue_10404_ptys_not_released(self):
        n_executions = 15
        # Get current number of PTY's
        try:
            nr_ptys = int(open('/proc/sys/kernel/pty/nr').read().strip())
        except (ValueError, OSError, IOError):
            self.fail('Unable to find out how many PTY\'s are open')

        # Using context manager's
        for idx in range(0, nr_ptys + n_executions):
            try:
                with vt.Terminal('echo "Run {0}"'.format(idx),
                                shell=True,
                                stream_stdout=False,
                                stream_stderr=False) as terminal:
                    terminal.wait()
                try:
                    if int(open('/proc/sys/kernel/pty/nr').read().strip()) > (nr_ptys + (n_executions/2)):
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
                    if int(open('/proc/sys/kernel/pty/nr').read().strip()) > (nr_ptys + (n_executions/2)):
                        self.fail('VT is not cleaning up PTY\'s')
                except (ValueError, OSError, IOError):
                    self.fail('Unable to find out how many PTY\'s are open')
            except Exception as exc:
                if 'out of pty devices' in exc:
                    # We're not cleaning up
                    raise
                # We're pushing the system resources, let's keep going
                continue


if __name__ == '__main__':
    from integration import run_tests
    run_tests(VTTestCase, needs_daemon=False)
