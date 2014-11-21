# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import os
import time
import signal
import multiprocessing

# Import Salt Testing libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import salt.utils.process

# Import 3rd-party libs
import salt.ext.six as six
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin


class TestProcessManager(TestCase):

    def test_basic(self):
        '''
        Make sure that the process is alive 2s later
        '''
        def spin():
            while True:
                time.sleep(1)

        process_manager = salt.utils.process.ProcessManager()
        process_manager.add_process(spin)
        initial_pid = next(six.iterkeys(process_manager._process_map))
        time.sleep(2)
        process_manager.check_children()
        assert initial_pid == next(six.iterkeys(process_manager._process_map))
        process_manager.kill_children()

    def test_kill(self):
        def spin():
            while True:
                time.sleep(1)

        process_manager = salt.utils.process.ProcessManager()
        process_manager.add_process(spin)
        initial_pid = next(six.iterkeys(process_manager._process_map))
        # kill the child
        os.kill(initial_pid, signal.SIGTERM)
        # give the OS time to give the signal...
        time.sleep(0.1)
        process_manager.check_children()
        assert initial_pid != next(six.iterkeys(process_manager._process_map))
        process_manager.kill_children()

    def test_restarting(self):
        '''
        Make sure that the process is alive 2s later
        '''
        def die():
            time.sleep(1)

        process_manager = salt.utils.process.ProcessManager()
        process_manager.add_process(die)
        initial_pid = next(six.iterkeys(process_manager._process_map))
        time.sleep(2)
        process_manager.check_children()
        assert initial_pid != next(six.iterkeys(process_manager._process_map))
        process_manager.kill_children()

    def test_counter(self):
        def incr(counter, num):
            for _ in range(0, num):
                counter.value += 1
        counter = multiprocessing.Value('i', 0)
        process_manager = salt.utils.process.ProcessManager()
        process_manager.add_process(incr, args=(counter, 2))
        time.sleep(1)
        process_manager.check_children()
        time.sleep(1)
        # we should have had 2 processes go at it
        assert counter.value == 4
        process_manager.kill_children()


if __name__ == '__main__':
    from integration import run_tests
    run_tests(
        [TestProcessManager],
        needs_daemon=False
    )
