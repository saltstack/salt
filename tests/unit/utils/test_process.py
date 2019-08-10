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
import psutil


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


class TestSignalHandlingMultiprocessingProcess(TestCase):

    @classmethod
    def Process(cls, pid):
        raise psutil.NoSuchProcess(pid)

    @classmethod
    def target(cls):
        os.kill(os.getpid(), signal.SIGTERM)

    @classmethod
    def children(cls, *args, **kwargs):
        raise psutil.NoSuchProcess(1)

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_process_does_not_exist(self):
        try:
            with patch('psutil.Process', self.Process):
                proc = salt.utils.process.SignalHandlingMultiprocessingProcess(target=self.target)
                proc.start()
        except psutil.NoSuchProcess:
            assert False, "psutil.NoSuchProcess raised"

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_process_children_do_not_exist(self):
        try:
            with patch('psutil.Process.children', self.children):
                proc = salt.utils.process.SignalHandlingMultiprocessingProcess(target=self.target)
                proc.start()
        except psutil.NoSuchProcess:
            assert False, "psutil.NoSuchProcess raised"

    @staticmethod
    def run_forever_sub_target(evt):
        'Used by run_forever_target to create a sub-process'
        while not evt.is_set():
            time.sleep(1)

    @staticmethod
    def run_forever_target(sub_target, evt):
        'A target that will run forever or until an event is set'
        p = multiprocessing.Process(target=sub_target, args=(evt,))
        p.start()
        p.join()

    @staticmethod
    def kill_target_sub_proc():
        pid = os.fork()
        if pid == 0:
            return
        pid = os.fork()
        if pid == 0:
            return
        time.sleep(.1)
        try:
            os.kill(os.getpid(), signal.SIGINT)
        except KeyboardInterrupt:
            pass

    @skipIf(sys.platform.startswith('win'), 'No os.fork on Windows')
    def test_signal_processing_regression_test(self):
        evt = multiprocessing.Event()
        sh_proc = salt.utils.process.SignalHandlingMultiprocessingProcess(
            target=self.run_forever_target,
            args=(self.run_forever_sub_target, evt)
        )
        sh_proc.start()
        proc = multiprocessing.Process(target=self.kill_target_sub_proc)
        proc.start()
        proc.join()
        # When the bug exists, the kill_target_sub_proc signal will kill both
        # processes. sh_proc will be alive if the bug is fixed
        try:
            assert sh_proc.is_alive()
        finally:
            evt.set()
            sh_proc.join()

    @staticmethod
    def no_op_target():
        pass

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_signal_processing_test_after_fork_called(self):
        'Validate MultiprocessingProcess and sub classes call after fork methods'
        evt = multiprocessing.Event()
        sig_to_mock = 'salt.utils.process.SignalHandlingMultiprocessingProcess._setup_signals'
        log_to_mock = 'salt.utils.process.MultiprocessingProcess._setup_process_logging'
        with patch(sig_to_mock) as ma, patch(log_to_mock) as mb:
            self.sh_proc = salt.utils.process.SignalHandlingMultiprocessingProcess(target=self.no_op_target)
            self.sh_proc._run()
        ma.assert_called()
        mb.assert_called()

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_signal_processing_test_final_methods_called(self):
        'Validate MultiprocessingProcess and sub classes call finalize methods'
        evt = multiprocessing.Event()
        teardown_to_mock = 'salt.log.setup.shutdown_multiprocessing_logging'
        log_to_mock = 'salt.utils.process.MultiprocessingProcess._setup_process_logging'
        with patch(teardown_to_mock) as ma, patch(log_to_mock) as mb:
            self.sh_proc = salt.utils.process.SignalHandlingMultiprocessingProcess(target=self.no_op_target)
            self.sh_proc._run()
        ma.assert_called()
        mb.assert_called()

    @staticmethod
    def pid_setting_target(sub_target, val, evt):
        val.value = os.getpid()
        p = multiprocessing.Process(target=sub_target, args=(evt,))
        p.start()
        p.join()

    @skipIf(sys.platform.startswith('win'), 'Required signals not supported on windows')
    def test_signal_processing_handle_signals_called(self):
        'Validate SignalHandlingMultiprocessingProcess handles signals'
        # Gloobal event to stop all processes we're creating
        evt = multiprocessing.Event()

        # Create a process to test signal handler
        val = multiprocessing.Value('i', 0)
        proc = salt.utils.process.SignalHandlingMultiprocessingProcess(
            target=self.pid_setting_target,
            args=(self.run_forever_sub_target, val, evt),
        )
        proc.start()

        # Create a second process that should not respond to SIGINT or SIGTERM
        proc2 = multiprocessing.Process(
            target=self.run_forever_target,
            args=(self.run_forever_sub_target, evt),
        )
        proc2.start()

        # Wait for the sub process to set it's pid
        while not val.value:
            time.sleep(.3)

        assert not proc.signal_handled()

        # Send a signal that should get handled by the subprocess
        os.kill(val.value, signal.SIGTERM)

        # wait up to 10 seconds for signal handler:
        start = time.time()
        while time.time() - start < 10:
            if proc.signal_handled():
                break
            time.sleep(.3)

        assert not proc.is_alive()
        assert proc.signal_handled()
        # Reap the signaled process
        proc.join(1)
        try:
            assert proc2.is_alive()
        finally:
            evt.set()
            proc2.join()
