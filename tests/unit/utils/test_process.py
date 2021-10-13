import datetime
import functools
import io
import multiprocessing
import os
import signal
import sys
import tempfile
import threading
import time
import warnings

import pytest
import salt.utils.platform
import salt.utils.process
from salt.utils.versions import warn_until_date
from tests.support.mock import patch
from tests.support.unit import TestCase, skipIf

HAS_PSUTIL = False
try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    pass


def die(func):
    """
    Add proc title
    """

    @functools.wraps(func)
    def wrapper(self):
        # Strip off the "test_" from the function name
        name = func.__name__[5:]

        def _die():
            salt.utils.process.appendproctitle("test_{}".format(name))

        attrname = "die_" + name
        setattr(self, attrname, _die)
        self.addCleanup(delattr, self, attrname)

    return wrapper


def incr(func):
    """
    Increment counter
    """

    @functools.wraps(func)
    def wrapper(self):
        # Strip off the "test_" from the function name
        name = func.__name__[5:]

        def _incr(counter, num):
            salt.utils.process.appendproctitle("test_{}".format(name))
            for _ in range(0, num):
                counter.value += 1

        attrname = "incr_" + name
        setattr(self, attrname, _incr)
        self.addCleanup(delattr, self, attrname)

    return wrapper


def spin(func):
    """
    Spin indefinitely
    """

    @functools.wraps(func)
    def wrapper(self):
        # Strip off the "test_" from the function name
        name = func.__name__[5:]

        def _spin():
            salt.utils.process.appendproctitle("test_{}".format(name))
            while True:
                time.sleep(1)

        attrname = "spin_" + name
        setattr(self, attrname, _spin)
        self.addCleanup(delattr, self, attrname)

    return wrapper


class TestProcessManager(TestCase):
    @spin
    @pytest.mark.slow_test
    def test_basic(self):
        """
        Make sure that the process is alive 2s later
        """
        process_manager = salt.utils.process.ProcessManager()
        self.addCleanup(process_manager.terminate)
        process_manager.add_process(self.spin_basic)
        initial_pid = next(iter(process_manager._process_map.keys()))
        time.sleep(2)
        process_manager.check_children()
        assert initial_pid == next(iter(process_manager._process_map.keys()))

    @spin
    def test_kill(self):
        process_manager = salt.utils.process.ProcessManager()
        self.addCleanup(process_manager.terminate)
        process_manager.add_process(self.spin_kill)
        initial_pid = next(iter(process_manager._process_map.keys()))
        # kill the child
        if salt.utils.platform.is_windows():
            os.kill(initial_pid, signal.SIGTERM)
        else:
            os.kill(initial_pid, signal.SIGKILL)
        # give the OS time to give the signal...
        time.sleep(0.1)
        process_manager.check_children()
        assert initial_pid != next(iter(process_manager._process_map.keys()))

    @die
    def test_restarting(self):
        """
        Make sure that the process is alive 2s later
        """
        process_manager = salt.utils.process.ProcessManager()
        self.addCleanup(process_manager.terminate)
        process_manager.add_process(self.die_restarting)
        initial_pid = next(iter(process_manager._process_map.keys()))
        time.sleep(2)
        process_manager.check_children()
        assert initial_pid != next(iter(process_manager._process_map.keys()))

    @incr
    def test_counter(self):
        counter = multiprocessing.Value("i", 0)
        process_manager = salt.utils.process.ProcessManager()
        self.addCleanup(process_manager.terminate)
        process_manager.add_process(self.incr_counter, args=(counter, 2))
        time.sleep(1)
        process_manager.check_children()
        time.sleep(1)
        # we should have had 2 processes go at it
        assert counter.value == 4


class TestThreadPool(TestCase):
    @pytest.mark.slow_test
    def test_basic(self):
        """
        Make sure the threadpool can do things
        """

        def incr_counter(counter):
            counter.value += 1

        counter = multiprocessing.Value("i", 0)

        pool = salt.utils.process.ThreadPool()
        sent = pool.fire_async(incr_counter, args=(counter,))
        self.assertTrue(sent)
        time.sleep(1)  # Sleep to let the threads do things
        self.assertEqual(counter.value, 1)
        self.assertEqual(pool._job_queue.qsize(), 0)

    @pytest.mark.slow_test
    def test_full_queue(self):
        """
        Make sure that a full threadpool acts as we expect
        """

        def incr_counter(counter):
            counter.value += 1

        counter = multiprocessing.Value("i", 0)

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
    def test_daemonize_if(self):
        # pylint: disable=assignment-from-none
        with patch("sys.argv", ["salt-call"]):
            ret = salt.utils.process.daemonize_if({})
            self.assertEqual(None, ret)

        ret = salt.utils.process.daemonize_if({"multiprocessing": False})
        self.assertEqual(None, ret)

        with patch("sys.platform", "win"):
            ret = salt.utils.process.daemonize_if({})
            self.assertEqual(None, ret)

        with patch("salt.utils.process.daemonize"), patch("sys.platform", "linux2"):
            salt.utils.process.daemonize_if({})
            self.assertTrue(salt.utils.process.daemonize.called)
        # pylint: enable=assignment-from-none


class TestProcessCallbacks(TestCase):
    @staticmethod
    def process_target(evt):
        evt.set()

    def test_callbacks(self):
        "Validate Process call after fork and finalize methods"
        teardown_to_mock = "salt.log.setup.shutdown_multiprocessing_logging"
        log_to_mock = "salt.log.setup.setup_multiprocessing_logging"
        with patch(teardown_to_mock) as ma, patch(log_to_mock) as mb:
            evt = multiprocessing.Event()
            proc = salt.utils.process.Process(target=self.process_target, args=(evt,))
            proc.run()
            assert evt.is_set()
        mb.assert_called()
        ma.assert_called()

    def test_callbacks_called_when_run_overridden(self):
        "Validate Process sub classes call after fork and finalize methods when run is overridden"

        class MyProcess(salt.utils.process.Process):
            def __init__(self):
                super().__init__()
                self.evt = multiprocessing.Event()

            def run(self):
                self.evt.set()

        teardown_to_mock = "salt.log.setup.shutdown_multiprocessing_logging"
        log_to_mock = "salt.log.setup.setup_multiprocessing_logging"
        with patch(teardown_to_mock) as ma, patch(log_to_mock) as mb:
            proc = MyProcess()
            proc.run()
            assert proc.evt.is_set()
        ma.assert_called()
        mb.assert_called()


@skipIf(not HAS_PSUTIL, "Missing psutil")
class TestSignalHandlingProcess(TestCase):
    @classmethod
    def Process(cls, pid):
        raise psutil.NoSuchProcess(pid)

    @classmethod
    def target(cls):
        os.kill(os.getpid(), signal.SIGTERM)

    @classmethod
    def children(cls, *args, **kwargs):
        raise psutil.NoSuchProcess(1)

    def test_process_does_not_exist(self):
        try:
            with patch("psutil.Process", self.Process):
                proc = salt.utils.process.SignalHandlingProcess(target=self.target)
                proc.start()
        except psutil.NoSuchProcess:
            assert False, "psutil.NoSuchProcess raised"

    def test_process_children_do_not_exist(self):
        try:
            with patch("psutil.Process.children", self.children):
                proc = salt.utils.process.SignalHandlingProcess(target=self.target)
                proc.start()
        except psutil.NoSuchProcess:
            assert False, "psutil.NoSuchProcess raised"

    @staticmethod
    def run_forever_sub_target(evt):
        "Used by run_forever_target to create a sub-process"
        while not evt.is_set():
            time.sleep(1)

    @staticmethod
    def run_forever_target(sub_target, evt):
        "A target that will run forever or until an event is set"
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
        time.sleep(0.1)
        try:
            os.kill(os.getpid(), signal.SIGINT)
        except KeyboardInterrupt:
            pass

    @skipIf(sys.platform.startswith("win"), "No os.fork on Windows")
    @pytest.mark.slow_test
    def test_signal_processing_regression_test(self):
        evt = multiprocessing.Event()
        sh_proc = salt.utils.process.SignalHandlingProcess(
            target=self.run_forever_target, args=(self.run_forever_sub_target, evt)
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

    @staticmethod
    def pid_setting_target(sub_target, val, evt):
        val.value = os.getpid()
        p = multiprocessing.Process(target=sub_target, args=(evt,))
        p.start()
        p.join()

    @skipIf(sys.platform.startswith("win"), "Required signals not supported on windows")
    @pytest.mark.slow_test
    def test_signal_processing_handle_signals_called(self):
        "Validate SignalHandlingProcess handles signals"
        # Gloobal event to stop all processes we're creating
        evt = multiprocessing.Event()

        # Create a process to test signal handler
        val = multiprocessing.Value("i", 0)
        proc = salt.utils.process.SignalHandlingProcess(
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

        # Wait for the sub process to set its pid
        while not val.value:
            time.sleep(0.3)

        assert not proc.signal_handled()

        # Send a signal that should get handled by the subprocess
        os.kill(val.value, signal.SIGTERM)

        # wait up to 10 seconds for signal handler:
        start = time.time()
        while time.time() - start < 10:
            if proc.signal_handled():
                break
            time.sleep(0.3)

        try:
            # Allow some time for the signal handler to do its thing
            assert proc.signal_handled()
            # Reap the signaled process
            proc.join(1)
            assert proc2.is_alive()
        finally:
            evt.set()
            proc2.join(30)
            proc.join(30)


class TestSignalHandlingProcessCallbacks(TestCase):
    @staticmethod
    def process_target(evt):
        evt.set()

    def test_callbacks(self):
        "Validate SignalHandlingProcess call after fork and finalize methods"

        teardown_to_mock = "salt.log.setup.shutdown_multiprocessing_logging"
        log_to_mock = "salt.log.setup.setup_multiprocessing_logging"
        sig_to_mock = "salt.utils.process.SignalHandlingProcess._setup_signals"
        # Mock _setup_signals so we do not register one for this process.
        evt = multiprocessing.Event()
        with patch(sig_to_mock):
            with patch(teardown_to_mock) as ma, patch(log_to_mock) as mb:
                sh_proc = salt.utils.process.SignalHandlingProcess(
                    target=self.process_target, args=(evt,)
                )
                sh_proc.run()
                assert evt.is_set()
        ma.assert_called()
        mb.assert_called()

    def test_callbacks_called_when_run_overridden(self):
        "Validate SignalHandlingProcess sub classes call after fork and finalize methods when run is overridden"

        class MyProcess(salt.utils.process.SignalHandlingProcess):
            def __init__(self):
                super().__init__()
                self.evt = multiprocessing.Event()

            def run(self):
                self.evt.set()

        teardown_to_mock = "salt.log.setup.shutdown_multiprocessing_logging"
        log_to_mock = "salt.log.setup.setup_multiprocessing_logging"
        sig_to_mock = "salt.utils.process.SignalHandlingProcess._setup_signals"
        # Mock _setup_signals so we do not register one for this process.
        with patch(sig_to_mock):
            with patch(teardown_to_mock) as ma, patch(log_to_mock) as mb:
                sh_proc = MyProcess()
                sh_proc.run()
                assert sh_proc.evt.is_set()
        ma.assert_called()
        mb.assert_called()


class TestDup2(TestCase):
    def test_dup2_no_fileno(self):
        "The dup2 method does not fail on streams without fileno support"
        f1 = io.StringIO("some initial text data")
        f2 = io.StringIO("some initial other text data")
        with self.assertRaises(io.UnsupportedOperation):
            f1.fileno()
        with patch("os.dup2") as dup_mock:
            try:
                salt.utils.process.dup2(f1, f2)
            except io.UnsupportedOperation:
                assert False, "io.UnsupportedOperation was raised"
        assert not dup_mock.called


def null_target():
    pass


def event_target(event):
    while True:
        if event.wait(5):
            break


class TestProcessList(TestCase):
    @staticmethod
    def wait_for_proc(proc, timeout=10):
        start = time.time()
        while proc.is_alive():
            if time.time() - start > timeout:
                raise Exception("Process did not finishe before timeout")
            time.sleep(0.3)

    @pytest.mark.slow_test
    def test_process_list_process(self):
        plist = salt.utils.process.SubprocessList()
        proc = multiprocessing.Process(target=null_target)
        proc.start()
        plist.add(proc)
        assert proc in plist.processes
        self.wait_for_proc(proc)
        assert not proc.is_alive()
        plist.cleanup()
        assert proc not in plist.processes

    def test_process_list_thread(self):
        plist = salt.utils.process.SubprocessList()
        thread = threading.Thread(target=null_target)
        thread.start()
        plist.add(thread)
        assert thread in plist.processes
        self.wait_for_proc(thread)
        assert not thread.is_alive()
        plist.cleanup()
        assert thread not in plist.processes

    @pytest.mark.slow_test
    def test_process_list_cleanup(self):
        plist = salt.utils.process.SubprocessList()
        event = multiprocessing.Event()
        proc = multiprocessing.Process(target=event_target, args=[event])
        proc.start()
        plist.add(proc)
        assert proc in plist.processes
        plist.cleanup()
        event.set()
        assert proc in plist.processes
        self.wait_for_proc(proc)
        assert not proc.is_alive()
        plist.cleanup()
        assert proc not in plist.processes


class TestDeprecatedClassNames(TestCase):
    @staticmethod
    def process_target():
        pass

    @staticmethod
    def patched_warn_until_date(current_date):
        def _patched_warn_until_date(
            date,
            message,
            category=DeprecationWarning,
            stacklevel=None,
            _current_date=current_date,
            _dont_call_warnings=False,
        ):
            # Because we add another function in between, the stacklevel
            # set in salt.utils.process, 3, needs to now be 4
            stacklevel = 4
            return warn_until_date(
                date,
                message,
                category=category,
                stacklevel=stacklevel,
                _current_date=_current_date,
                _dont_call_warnings=_dont_call_warnings,
            )

        return _patched_warn_until_date

    def test_multiprocessing_process_warning(self):
        # We *always* want *all* warnings thrown on this module
        warnings.filterwarnings("always", "", DeprecationWarning, __name__)

        fake_utcnow = datetime.date(2021, 1, 1)

        proc = None

        try:
            with patch(
                "salt.utils.versions.warn_until_date",
                self.patched_warn_until_date(fake_utcnow),
            ):
                # Test warning
                with warnings.catch_warnings(record=True) as recorded_warnings:
                    proc = salt.utils.process.MultiprocessingProcess(
                        target=self.process_target
                    )
                    self.assertEqual(
                        "Please stop using 'salt.utils.process.MultiprocessingProcess' "
                        "and instead use 'salt.utils.process.Process'. "
                        "'salt.utils.process.MultiprocessingProcess' will go away "
                        "after 2022-01-01.",
                        str(recorded_warnings[0].message),
                    )
        finally:
            if proc is not None:
                del proc

    def test_multiprocessing_process_runtime_error(self):
        fake_utcnow = datetime.date(2022, 1, 1)

        proc = None

        try:
            with patch(
                "salt.utils.versions.warn_until_date",
                self.patched_warn_until_date(fake_utcnow),
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    r"Please stop using 'salt.utils.process.MultiprocessingProcess' "
                    r"and instead use 'salt.utils.process.Process'. "
                    r"'salt.utils.process.MultiprocessingProcess' will go away "
                    r"after 2022-01-01. "
                    r"This warning\(now exception\) triggered on "
                    r"filename '(.*)test_process.py', line number ([\d]+), is "
                    r"supposed to be shown until ([\d-]+). Today is ([\d-]+). "
                    r"Please remove the warning.",
                ):
                    proc = salt.utils.process.MultiprocessingProcess(
                        target=self.process_target
                    )
        finally:
            if proc is not None:
                del proc

    def test_signal_handling_multiprocessing_process_warning(self):
        # We *always* want *all* warnings thrown on this module
        warnings.filterwarnings("always", "", DeprecationWarning, __name__)

        fake_utcnow = datetime.date(2021, 1, 1)

        proc = None

        try:
            with patch(
                "salt.utils.versions.warn_until_date",
                self.patched_warn_until_date(fake_utcnow),
            ):
                # Test warning
                with warnings.catch_warnings(record=True) as recorded_warnings:
                    proc = salt.utils.process.SignalHandlingMultiprocessingProcess(
                        target=self.process_target
                    )
                    self.assertEqual(
                        "Please stop using"
                        " 'salt.utils.process.SignalHandlingMultiprocessingProcess' and"
                        " instead use 'salt.utils.process.SignalHandlingProcess'."
                        " 'salt.utils.process.SignalHandlingMultiprocessingProcess'"
                        " will go away after 2022-01-01.",
                        str(recorded_warnings[0].message),
                    )
        finally:
            if proc is not None:
                del proc

    def test_signal_handling_multiprocessing_process_runtime_error(self):
        fake_utcnow = datetime.date(2022, 1, 1)

        proc = None

        try:
            with patch(
                "salt.utils.versions.warn_until_date",
                self.patched_warn_until_date(fake_utcnow),
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    r"Please stop using"
                    r" 'salt.utils.process.SignalHandlingMultiprocessingProcess' "
                    r"and instead use 'salt.utils.process.SignalHandlingProcess'. "
                    r"'salt.utils.process.SignalHandlingMultiprocessingProcess' will go"
                    r" away "
                    r"after 2022-01-01. "
                    r"This warning\(now exception\) triggered on "
                    r"filename '(.*)test_process.py', line number ([\d]+), is "
                    r"supposed to be shown until ([\d-]+). Today is ([\d-]+). "
                    r"Please remove the warning.",
                ):
                    proc = salt.utils.process.SignalHandlingMultiprocessingProcess(
                        target=self.process_target
                    )
        finally:
            if proc is not None:
                del proc


class CMORProcessHelper:
    def __init__(self, file_name):
        self._lock = threading.Lock()
        self._running = True
        self._queue = multiprocessing.Queue()
        self._ret_queue = multiprocessing.Queue()
        self._process = multiprocessing.Process(
            target=self.test_process,
            args=(file_name, self._queue, self._ret_queue),
            daemon=True,
        )
        self._process.start()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def claim(self):
        try:
            self._lock.acquire()
            if self._running:
                self._queue.put("claim")
                return self._ret_queue.get(timeout=10)
        finally:
            self._lock.release()

    def stop(self):
        try:
            self._lock.acquire()
            if self._running:
                self._running = False

                self._queue.put("stop")
                self._process.join(timeout=10)

                self._queue.close()
                self._ret_queue.close()
        finally:
            self._lock.release()

    @property
    def pid(self):
        return self._process.pid

    @staticmethod
    def test_process(file_name, queue, ret_queue):
        while True:
            action = queue.get()
            if action == "claim":
                ret_queue.put(
                    salt.utils.process.claim_mantle_of_responsibility(file_name)
                )
            elif action == "stop":
                return


@skipIf(not HAS_PSUTIL, "Missing psutil")
class TestGetProcessInfo(TestCase):
    def setUp(self):
        handle, self.cmor_test_file_path = tempfile.mkstemp()
        os.close(handle)
        self.addCleanup(os.unlink, self.cmor_test_file_path)

    def test_this_process(self):
        this_process_info = salt.utils.process.get_process_info()

        self.assertEqual(
            this_process_info, salt.utils.process.get_process_info(os.getpid())
        )
        self.assertIsNotNone(this_process_info)

        for key in ("pid", "name", "start_time"):
            self.assertIn(key, this_process_info)

        raw_process_info = psutil.Process(os.getpid())
        self.assertEqual(this_process_info["pid"], os.getpid())
        self.assertEqual(this_process_info["name"], raw_process_info.name())
        self.assertEqual(
            this_process_info["start_time"], raw_process_info.create_time()
        )

    def test_random_processes(self):
        for _ in range(3):
            with CMORProcessHelper(self.cmor_test_file_path) as p1:
                pid = p1.pid
                self.assertIsInstance(salt.utils.process.get_process_info(pid), dict)
            self.assertIsNone(salt.utils.process.get_process_info(pid))


@skipIf(not HAS_PSUTIL, "Missing psutil")
class TestClaimMantleOfResponsibility(TestCase):
    def setUp(self):
        handle, self.cmor_test_file_path = tempfile.mkstemp()
        os.close(handle)
        self.addCleanup(os.unlink, self.cmor_test_file_path)

    def test_simple_claim_no_psutil(self):
        salt.utils.process.claim_mantle_of_responsibility(self.cmor_test_file_path)

    def test_simple_claim(self):
        for _ in range(5):
            self.assertTrue(
                salt.utils.process.claim_mantle_of_responsibility(
                    self.cmor_test_file_path
                )
            )

    def test_multiple_processes(self):
        with CMORProcessHelper(self.cmor_test_file_path) as p1:
            self.assertTrue(p1.claim())
            self.assertFalse(
                salt.utils.process.claim_mantle_of_responsibility(
                    self.cmor_test_file_path
                )
            )
            with CMORProcessHelper(self.cmor_test_file_path) as p2:
                for _ in range(3):
                    self.assertFalse(p2.claim())
            self.assertTrue(p1.claim())

        with CMORProcessHelper(self.cmor_test_file_path) as p1:
            self.assertTrue(p1.claim())
            self.assertFalse(
                salt.utils.process.claim_mantle_of_responsibility(
                    self.cmor_test_file_path
                )
            )

        self.assertTrue(
            salt.utils.process.claim_mantle_of_responsibility(self.cmor_test_file_path)
        )


@skipIf(not HAS_PSUTIL, "Missing psutil")
class TestCheckMantleOfResponsibility(TestCase):
    def setUp(self):
        handle, self.cmor_test_file_path = tempfile.mkstemp()
        os.close(handle)
        self.addCleanup(os.unlink, self.cmor_test_file_path)

    def test_simple_claim_no_psutil(self):
        self.assertIsNone(
            salt.utils.process.check_mantle_of_responsibility(self.cmor_test_file_path)
        )

    def test_simple_claim(self):
        self.assertIsNone(
            salt.utils.process.check_mantle_of_responsibility(self.cmor_test_file_path)
        )
        salt.utils.process.claim_mantle_of_responsibility(self.cmor_test_file_path)
        pid = salt.utils.process.get_process_info()["pid"]
        self.assertEqual(
            pid,
            salt.utils.process.check_mantle_of_responsibility(self.cmor_test_file_path),
        )

    def test_multiple_processes(self):
        self.assertIsNone(
            salt.utils.process.check_mantle_of_responsibility(self.cmor_test_file_path)
        )

        with CMORProcessHelper(self.cmor_test_file_path) as p1:
            self.assertTrue(p1.claim())
            random_pid = salt.utils.process.check_mantle_of_responsibility(
                self.cmor_test_file_path
            )

            self.assertIsInstance(random_pid, int)

            with CMORProcessHelper(self.cmor_test_file_path) as p2:
                for _ in range(3):
                    self.assertFalse(p2.claim())
                self.assertEqual(
                    random_pid,
                    salt.utils.process.check_mantle_of_responsibility(
                        self.cmor_test_file_path
                    ),
                )

        self.assertIsNone(
            salt.utils.process.check_mantle_of_responsibility(self.cmor_test_file_path)
        )
        salt.utils.process.claim_mantle_of_responsibility(self.cmor_test_file_path)
        pid = salt.utils.process.get_process_info()["pid"]
        self.assertEqual(
            pid,
            salt.utils.process.check_mantle_of_responsibility(self.cmor_test_file_path),
        )
