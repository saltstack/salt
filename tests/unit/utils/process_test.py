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
import salt.utils
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
            salt.utils.appendproctitle('test_basic')
            while True:
                time.sleep(1)

        process_manager = salt.utils.process.ProcessManager()
        process_manager.add_process(spin)
        initial_pid = next(six.iterkeys(process_manager._process_map))
        time.sleep(2)
        process_manager.check_children()
        try:
            assert initial_pid == next(six.iterkeys(process_manager._process_map))
        finally:
            process_manager.stop_restarting()
            process_manager.kill_children()
            time.sleep(0.5)
            # Are there child processes still running?
            if process_manager._process_map.keys():
                process_manager.send_signal_to_processes(signal.SIGILL)
                process_manager.stop_restarting()
                process_manager.kill_children()

    def test_kill(self):
        def spin():
            salt.utils.appendproctitle('test_kill')
            while True:
                time.sleep(1)

        process_manager = salt.utils.process.ProcessManager()
        process_manager.add_process(spin)
        initial_pid = next(six.iterkeys(process_manager._process_map))
        # kill the child
        os.kill(initial_pid, signal.SIGKILL)
        # give the OS time to give the signal...
        time.sleep(0.1)
        process_manager.check_children()
        try:
            assert initial_pid != next(six.iterkeys(process_manager._process_map))
        finally:
            process_manager.stop_restarting()
            process_manager.kill_children()
            time.sleep(0.5)
            # Are there child processes still running?
            if process_manager._process_map.keys():
                process_manager.send_signal_to_processes(signal.SIGILL)
                process_manager.stop_restarting()
                process_manager.kill_children()

    def test_restarting(self):
        '''
        Make sure that the process is alive 2s later
        '''
        def die():
            salt.utils.appendproctitle('test_restarting')
            time.sleep(1)

        process_manager = salt.utils.process.ProcessManager()
        process_manager.add_process(die)
        initial_pid = next(six.iterkeys(process_manager._process_map))
        time.sleep(2)
        process_manager.check_children()
        try:
            assert initial_pid != next(six.iterkeys(process_manager._process_map))
        finally:
            process_manager.stop_restarting()
            process_manager.kill_children()
            time.sleep(0.5)
            # Are there child processes still running?
            if process_manager._process_map.keys():
                process_manager.send_signal_to_processes(signal.SIGILL)
                process_manager.stop_restarting()
                process_manager.kill_children()

    def test_counter(self):
        def incr(counter, num):
            salt.utils.appendproctitle('test_counter')
            for _ in range(0, num):
                counter.value += 1
        counter = multiprocessing.Value('i', 0)
        process_manager = salt.utils.process.ProcessManager()
        process_manager.add_process(incr, args=(counter, 2))
        time.sleep(1)
        process_manager.check_children()
        time.sleep(1)
        # we should have had 2 processes go at it
        try:
            assert counter.value == 4
        finally:
            process_manager.stop_restarting()
            process_manager.kill_children()
            time.sleep(0.5)
            # Are there child processes still running?
            if process_manager._process_map.keys():
                process_manager.send_signal_to_processes(signal.SIGILL)
                process_manager.stop_restarting()
                process_manager.kill_children()


class TestThreadPool(TestCase):

    def test_basic(self):
        '''
        Make sure the threadpool can do things
        '''
        def incr_counter(counter):
            counter.value += 1
        counter = multiprocessing.Value('i', 0)

        pool = salt.utils.process.ThreadPool()
        sent = pool.fire_async(incr_counter, args=(counter,))
        self.assertTrue(sent)
        time.sleep(1)  # Sleep to let the threads do things
        self.assertEqual(counter.value, 1)
        self.assertEqual(pool._job_queue.qsize(), 0)

    def test_full_queue(self):
        '''
        Make sure that a full threadpool acts as we expect
        '''
        def incr_counter(counter):
            counter.value += 1
        counter = multiprocessing.Value('i', 0)

        # Create a pool with no workers and 1 queue size
        pool = salt.utils.process.ThreadPool(0, 1)
        # make sure we can put the one item in
        sent = pool.fire_async(incr_counter, args=(counter,))
        self.assertTrue(sent)
        # make sure we can't put more in
        sent = pool.fire_async(incr_counter, args=(counter,))
        self.assertFalse(sent)
        time.sleep(1)  # Sleep to let the threads do things
        # make sure no one updated the counter
        self.assertEqual(counter.value, 0)
        # make sure the queue is still full
        self.assertEqual(pool._job_queue.qsize(), 1)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(
        [TestProcessManager, TestThreadPool],
        needs_daemon=False
    )
