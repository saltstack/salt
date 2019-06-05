# -*- coding: utf-8 -*-
'''
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    tests.unit.utils.vt_test
    ~~~~~~~~~~~~~~~~~~~~~~~~

    VirtualTerminal tests
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import sys
import random
import subprocess
import time
import tempfile
import shutil

# Import Salt Testing libs
from tests.support.unit import TestCase, skipIf

# Import Salt libs
import salt.utils
import salt.utils.files
import salt.utils.platform
import salt.utils.vt
import salt.utils.stringutils

# Import 3rd-party libs
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin

def stdout_fileno_available():
    '''
        Tests if sys.stdout.fileno is available in this testing enviroment
    '''
    try:
        sys.stdout.fileno()
        return True
    except:
        return False

class VTTestCase(TestCase):

    def run_test_in_subprocess(self, test_name):
        '''
            Runs a named test in a new instance of python to avoid broken
            sys.stdout.fileno method
        '''
        test_root = os.path.abspath(
            os.path.join(
                os.path.join(
                    os.path.join(
                        os.path.dirname(os.path.realpath(__file__)), os.pardir
                    ),
                    os.pardir,
                ),
                os.pardir,
            )
        )
        # Test the test isn't a fork bomb before starting a new process
        self.assertFalse('TEST_VT_CHILD' in os.environ)
        self.assertEqual(
            0,
            subprocess.call(
                args=(
                    sys.executable,
                    os.path.join(test_root, 'tests/runtests.py'),
                    '--name=unit.utils.test_vt.VTTestCase.' + test_name,
                    '--verbose',
                ),
                cwd=test_root,
                env=dict(os.environ, TEST_VT_CHILD='1'),
            ),
        )

    @skipIf(True, 'Disabled until we can figure out why this fails when whole test suite runs.')
    def test_vt_size(self):
        '''Confirm that the terminal size is being set'''
        if not sys.stdin.isatty():
            self.skipTest('Not attached to a TTY. The test would fail.')
        cols = random.choice(range(80, 250))
        terminal = salt.utils.vt.Terminal(
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
                    with salt.utils.files.fopen('/proc/sys/kernel/pty/nr') as fh_:
                        return int(fh_.read().strip())

                proc = subprocess.Popen(
                    'sysctl -a 2> /dev/null | grep pty.nr | awk \'{print $3}\'',
                    shell=True,
                    stdout=subprocess.PIPE
                )
                stdout, _ = proc.communicate()
                return int(stdout.strip())
            except (ValueError, OSError, IOError):
                if salt.utils.platform.is_darwin():
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
                with salt.utils.vt.Terminal('echo "Run {0}"'.format(idx),
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
                terminal = salt.utils.vt.Terminal('echo "Run {0}"'.format(idx),
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

    @skipIf(True, 'Disabled until we can figure out how to make this more reliable.')
    def test_isalive_while_theres_data_to_read(self):
        expected_data = 'Alive!\n'
        term = salt.utils.vt.Terminal('echo "Alive!"',
                                      shell=True,
                                      stream_stdout=False,
                                      stream_stderr=False)
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
        term = salt.utils.vt.Terminal('echo "Alive!" 1>&2',
                                      shell=True,
                                      stream_stdout=False,
                                      stream_stderr=False)
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
        term = salt.utils.vt.Terminal('echo "Alive!"; sleep 5; echo "Alive!"',
                                      shell=True,
                                      stream_stdout=False,
                                      stream_stderr=False)
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

    def test_split_multibyte_characters_unicode(self):
        '''
            Tests that the vt correctly handles multibyte characters that are
            split between blocks of transmitted data.
        '''
        if not stdout_fileno_available() and 'TEST_VT_CHILD' not in os.environ:
            self.run_test_in_subprocess(
                'test_split_multibyte_characters_unicode'
            )
            return
        block_size = 1024
        encoding = 'utf-8'
        try:
            tempdir = tempfile.mkdtemp(suffix='test_vt_unicode')
            file_path_stdout = os.path.join(tempdir, "vt_unicode_stdout.txt")
            file_path_stderr = os.path.join(tempdir, "vt_unicode_stderr.txt")
            stdout_content = b'\xE2\x80\xA6' * 4 * block_size
            # stderr is offset by one byte to guarentee a split character in
            # one of the output streams
            stderr_content = b'\x2E' + stdout_content
            with salt.utils.fopen(file_path_stdout, "wb") as fout:
                fout.write(stdout_content)
            with salt.utils.fopen(file_path_stderr, "wb") as ferr:
                ferr.write(stderr_content)

            expected_stdout = salt.utils.stringutils.to_unicode(stdout_content,
                                                                encoding)
            expected_stderr = salt.utils.stringutils.to_unicode(stderr_content,
                                                                encoding)
            python_command = '\n'.join((
                'import sys',
                'with open(\'' + file_path_stdout + '\', \'rb\') as fout:',
                '    sys.stdout.buffer.write(fout.read())',
                'with open(\'' + file_path_stderr + '\', \'rb\') as ferr:',
                '    sys.stderr.buffer.write(ferr.read())',))
            term = salt.utils.vt.Terminal(
                args=[sys.executable,
                      '-c',
                      '"' + python_command + '"'],
                shell=True,
                stream_stdout=False,
                stream_stderr=False,
                force_receive_encoding=encoding)
            buffer_o = buffer_e = salt.utils.stringutils.to_unicode('')
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
        finally:
            # Ignore errors because on some platforms the tempdir doesn't exist
            # which would seem be indicative of deeper problems
            shutil.rmtree(tempdir, ignore_errors=True)

    def test_split_multibyte_characters_shiftjis(self):
        '''
            Tests that the vt correctly handles multibyte characters that are
            split between blocks of transmitted data.
            Uses shift-jis encoding to make sure code doesn't assume unicode.
        '''
        if not stdout_fileno_available() and 'TEST_VT_CHILD' not in os.environ:
            self.run_test_in_subprocess(
                'test_split_multibyte_characters_shiftjis'
            )
            return
        block_size = 1024
        encoding = 'shift-jis'
        try:
            tempdir = tempfile.mkdtemp(suffix='test_vt_shiftjis')
            file_path_stdout = os.path.join(tempdir, "vt_shiftjis_stdout.txt")
            file_path_stderr = os.path.join(tempdir, "vt_shiftjis_stderr.txt")
            stdout_content = b'\x8B\x80' * 4 * block_size
            # stderr is offset by one byte to guarentee a split character in
            # one of the output streams
            stderr_content = b'\x2E' + stdout_content
            with salt.utils.fopen(file_path_stdout, "wb") as fout:
                fout.write(stdout_content)
            with salt.utils.fopen(file_path_stderr, "wb") as ferr:
                ferr.write(stderr_content)

            expected_stdout = salt.utils.stringutils.to_unicode(stdout_content,
                                                                encoding)
            expected_stderr = salt.utils.stringutils.to_unicode(stderr_content,
                                                                encoding)
            python_command = '\n'.join((
                'import sys',
                'with open(\'' + file_path_stdout + '\', \'rb\') as fout:',
                '    sys.stdout.buffer.write(fout.read())',
                'with open(\'' + file_path_stderr + '\', \'rb\') as ferr:',
                '    sys.stderr.buffer.write(ferr.read())',))
            term = salt.utils.vt.Terminal(
                args=[sys.executable,
                      '-c',
                      '"' + python_command + '"'],
                shell=True,
                stream_stdout=False,
                stream_stderr=False,
                force_receive_encoding=encoding)
            buffer_o = buffer_e = salt.utils.stringutils.to_unicode('')
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
        finally:
            # Ignore errors because on some platforms the tempdir doesn't exist
            # which would seem be indicative of deeper problems
            shutil.rmtree(tempdir, ignore_errors=True)
