# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import os
import sys
import time
import signal
import multiprocessing

# Import Salt Testing libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import salt libs
import salt.utils.process

# Import 3rd-party libs
from salt.ext import six
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin


class TestProcessManager(TestCase):

    def test_basic(self):
        '''
        Make sure that the process is alive 2s later
        '''
        def spin():
            salt.utils.process.appendproctitle('test_basic')
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
                process_manager.send_signal_to_processes(signal.SIGKILL)
                process_manager.stop_restarting()
                process_manager.kill_children()

    def test_kill(self):
        def spin():
            salt.utils.process.appendproctitle('test_kill')
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
                process_manager.send_signal_to_processes(signal.SIGKILL)
                process_manager.stop_restarting()
                process_manager.kill_children()

    def test_restarting(self):
        '''
        Make sure that the process is alive 2s later
        '''
        def die():
            salt.utils.process.appendproctitle('test_restarting')

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
                process_manager.send_signal_to_processes(signal.SIGKILL)
                process_manager.stop_restarting()
                process_manager.kill_children()

    @skipIf(sys.version_info < (2, 7), 'Needs > Py 2.7 due to bug in stdlib')
    def test_counter(self):
        def incr(counter, num):
            salt.utils.process.appendproctitle('test_counter')
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
                process_manager.send_signal_to_processes(signal.SIGKILL)
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


class TestProcess(TestCase):

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_daemonize_if(self):
        # pylint: disable=assignment-from-none
        with patch('sys.argv', ['salt-call']):
            ret = salt.utils.process.daemonize_if({})
            self.assertEqual(None, ret)

        ret = salt.utils.process.daemonize_if({'multiprocessing': False})
        self.assertEqual(None, ret)

        with patch('sys.platform', 'win'):
            ret = salt.utils.process.daemonize_if({})
            self.assertEqual(None, ret)

        with patch('salt.utils.process.daemonize'):
            salt.utils.process.daemonize_if({})
            self.assertTrue(salt.utils.process.daemonize.called)
        # pylint: enable=assignment-from-none
