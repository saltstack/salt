# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import sys
import time
import signal
import multiprocessing
import functools

# Import Salt Testing libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import salt libs
import salt.utils.platform
import salt.utils.process

# Import 3rd-party libs
from salt.ext import six
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin


def die(func):
    '''
    Add proc title
    '''
    @functools.wraps(func)
    def wrapper(self):
        # Strip off the "test_" from the function name
        name = func.__name__[5:]

        def _die():
            salt.utils.process.appendproctitle('test_{0}'.format(name))
        setattr(self, 'die_' + name, _die)

    return wrapper


def incr(func):
    '''
    Increment counter
    '''
    @functools.wraps(func)
    def wrapper(self):
        # Strip off the "test_" from the function name
        name = func.__name__[5:]

        def _incr(counter, num):
            salt.utils.process.appendproctitle('test_{0}'.format(name))
            for _ in range(0, num):
                counter.value += 1
        setattr(self, 'incr_' + name, _incr)

    return wrapper


def spin(func):
    '''
    Spin indefinitely
    '''
    @functools.wraps(func)
    def wrapper(self):
        # Strip off the "test_" from the function name
        name = func.__name__[5:]

        def _spin():
            salt.utils.process.appendproctitle('test_{0}'.format(name))
            while True:
                time.sleep(1)
        setattr(self, 'spin_' + name, _spin)

    return wrapper


class TestProcessManager(TestCase):

    @spin
    def test_basic(self):
        '''
        Make sure that the process is alive 2s later
        '''
        process_manager = salt.utils.process.ProcessManager()
        process_manager.add_process(self.spin_basic)
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

    @spin
    def test_kill(self):
        process_manager = salt.utils.process.ProcessManager()
        process_manager.add_process(self.spin_kill)
        initial_pid = next(six.iterkeys(process_manager._process_map))
        # kill the child
        if salt.utils.platform.is_windows():
            os.kill(initial_pid, signal.SIGTERM)
        else:
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

    @die
    def test_restarting(self):
        '''
        Make sure that the process is alive 2s later
        '''
        process_manager = salt.utils.process.ProcessManager()
        process_manager.add_process(self.die_restarting)
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
    @incr
    def test_counter(self):
        counter = multiprocessing.Value('i', 0)
        process_manager = salt.utils.process.ProcessManager()
        process_manager.add_process(self.incr_counter, args=(counter, 2))
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

        with patch('salt.utils.process.daemonize'), \
                patch('sys.platform', 'linux2'):
            salt.utils.process.daemonize_if({})
            self.assertTrue(salt.utils.process.daemonize.called)
        # pylint: enable=assignment-from-none
