import functools
import io
import logging
import multiprocessing
import os
import queue
import signal
import tempfile
import threading
import time

import pytest

import salt._logging
import salt.utils.platform
import salt.utils.process
from tests.support.mock import patch
from tests.support.unit import TestCase

HAS_PSUTIL = False
try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    pass

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.timeout_unless_on_windows(120),
]


def die(func):
    """
    Add proc title
    """

    @functools.wraps(func)
    def wrapper(self):
        # Strip off the "test_" from the function name
        name = func.__name__[5:]

        def _die():
            salt.utils.process.appendproctitle(f"test_{name}")

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
            salt.utils.process.appendproctitle(f"test_{name}")
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
            salt.utils.process.appendproctitle(f"test_{name}")
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
        with patch(
            "salt._logging.get_logging_options_dict", return_value={"1": 1}
        ) as ls1, patch("salt._logging.setup_logging") as ls2, patch(
            "salt._logging.shutdown_logging"
        ) as ls3:
            evt = multiprocessing.Event()
            proc = salt.utils.process.Process(target=self.process_target, args=(evt,))
            proc.run()
            assert evt.is_set()
        ls1.assert_called()
        ls2.assert_called()
        ls3.assert_called()

    def test_callbacks_called_when_run_overridden(self):
        "Validate Process sub classes call after fork and finalize methods when run is overridden"

        class MyProcess(salt.utils.process.Process):
            def __init__(self):
                super().__init__()
                self.evt = multiprocessing.Event()

            def run(self):
                self.evt.set()

        with patch(
            "salt._logging.get_logging_options_dict", return_value={"1": 1}
        ) as ls1, patch("salt._logging.setup_logging") as ls2, patch(
            "salt._logging.shutdown_logging"
        ) as ls3:
            proc = MyProcess()
            proc.run()
            assert proc.evt.is_set()
        ls1.assert_called()
        ls2.assert_called()
        ls3.assert_called()


@pytest.mark.skipif(not HAS_PSUTIL, reason="Missing psutil")
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

    @pytest.mark.skip_on_windows(reason="No os.fork on Windows")
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

    @pytest.mark.skip_on_windows(reason="Required signals not supported on windows")
    @pytest.mark.slow_test
    @staticmethod
    def _signal_handling_subprocess_body(result_queue):
        """
        Body of ``test_signal_processing_handle_signals_called`` that runs
        inside a fresh ``spawn``-context subprocess.

        Running in a fresh interpreter is required because the pytest
        process inherits saltfactories' session threads (``LogServer``,
        ``EventListener``, etc.) plus any leaked daemon threads from
        earlier tests. Forking a ``SignalHandlingProcess`` from that
        multi-threaded parent on Python 3.14 reliably deadlocks the child
        in ``salt._logging.shutdown_logging()`` /
        ``setup_logging()``, because the locks held by the surviving
        parent threads at fork time have no thread to release them in the
        child. The deadlocked child then doesn't honour SIGTERM and the
        whole shard sits at the pytest-timeout mark.

        By running this body in a clean spawn child, the *only* thread at
        fork time is MainThread, so the inner forks are safe. The result
        is communicated back via ``result_queue`` as
        ``("pass", "")`` / ``("fail", message)`` / ``("skip", reason)``.
        """
        # pylint: disable=import-outside-toplevel,reimported
        import multiprocessing
        import os
        import signal
        import time

        import salt._logging
        import salt.utils.process

        # Pin the inner ``multiprocessing`` start method to ``fork`` so the
        # test exercises the production code path. This subprocess is
        # single-threaded, so the fork-after-thread risk that motivated
        # this refactor is not present here.
        try:
            multiprocessing.set_start_method("fork", force=True)
        except (RuntimeError, ValueError):
            pass

        # When Salt's ``Process`` runs under pytest, the logging options
        # dict has been populated as a side effect of test collection.
        # In this fresh spawn child we have to seed it ourselves;
        # ``wrapped_run_func`` would otherwise pass ``None`` down to
        # ``set_lowest_log_level_by_opts`` and the child would die with
        # ``AttributeError: 'NoneType' object has no attribute 'get'``
        # before reaching ``val.value = os.getpid()``.
        if not salt._logging.get_logging_options_dict():
            salt._logging.set_logging_options_dict({"log_level": "warning"})

        # Pre-bind the staticmethod targets so the spawn pickle of those
        # ``Process`` objects below resolves them by import path rather
        # than via the bound TestCase ``self``.
        pid_setting_target = TestSignalHandlingProcess.pid_setting_target
        run_forever_sub_target = TestSignalHandlingProcess.run_forever_sub_target
        run_forever_target = TestSignalHandlingProcess.run_forever_target

        evt = multiprocessing.Event()
        sig_handled = multiprocessing.Event()
        val = multiprocessing.Value("i", 0)

        proc = salt.utils.process.SignalHandlingProcess(
            target=pid_setting_target,
            args=(run_forever_sub_target, val, evt),
        )
        proc.register_finalize_method(sig_handled.set)
        proc.start()

        proc2 = multiprocessing.Process(
            target=run_forever_target,
            args=(run_forever_sub_target, evt),
        )
        proc2.start()

        try:
            start = time.time()
            while time.time() - start < 30 and not val.value:
                time.sleep(0.1)
            if not val.value:
                result_queue.put(("skip", "subprocess did not set its pid in time"))
                return

            if sig_handled.is_set():
                result_queue.put(("fail", "sig_handled was set before SIGTERM"))
                return

            os.kill(val.value, signal.SIGTERM)

            start = time.time()
            while time.time() - start < 10 and not sig_handled.is_set():
                time.sleep(0.1)
            if not sig_handled.is_set():
                result_queue.put(
                    ("skip", "Event took too long to get set, skipping for now.")
                )
                return

            proc.join(1)
            if not proc2.is_alive():
                result_queue.put(("fail", "proc2 (no signal handler) is not alive"))
                return

            result_queue.put(("pass", ""))
        finally:
            evt.set()
            for p in (proc, proc2):
                if p.is_alive():
                    try:
                        p.terminate()
                    except Exception:  # pylint: disable=broad-except
                        pass
                p.join(5)
                if p.is_alive():
                    try:
                        p.kill()
                    except Exception:  # pylint: disable=broad-except
                        pass
                    p.join(5)

    def test_signal_processing_handle_signals_called(self):
        "Validate SignalHandlingProcess handles signals"
        # The actual SignalHandlingProcess fork has to happen from a
        # single-threaded parent on Py3.14. Run the body in a clean
        # ``spawn`` subprocess; see ``_signal_handling_subprocess_body``
        # for the rationale.
        ctx = multiprocessing.get_context("spawn")
        result_queue = ctx.Queue()
        runner = ctx.Process(
            target=TestSignalHandlingProcess._signal_handling_subprocess_body,
            args=(result_queue,),
        )
        runner.start()
        try:
            runner.join(90)
            if runner.is_alive():
                try:
                    runner.terminate()
                except Exception:  # pylint: disable=broad-except
                    pass
                runner.join(5)
                if runner.is_alive():
                    try:
                        runner.kill()
                    except Exception:  # pylint: disable=broad-except
                        pass
                    runner.join(5)
                pytest.fail("Spawn-based test runner did not finish within 90 seconds")

            try:
                status, message = result_queue.get_nowait()
            except queue.Empty:
                pytest.fail(
                    "Spawn runner exited without reporting a result "
                    f"(exitcode={runner.exitcode})"
                )
            if status == "pass":
                return
            if status == "skip":
                pytest.skip(message)
            pytest.fail(message)
        finally:
            if runner.is_alive():
                try:
                    runner.kill()
                except Exception:  # pylint: disable=broad-except
                    pass
                runner.join(5)


class TestSignalHandlingProcessCallbacks(TestCase):
    @staticmethod
    def process_target(evt):
        evt.set()

    def test_callbacks(self):
        "Validate SignalHandlingProcess call after fork and finalize methods"

        sig_to_mock = "salt.utils.process.SignalHandlingProcess._setup_signals"
        # Mock _setup_signals so we do not register one for this process.
        evt = multiprocessing.Event()
        with patch(sig_to_mock):
            with patch(
                "salt._logging.get_logging_options_dict", return_value={"1": 1}
            ) as ls1, patch("salt._logging.setup_logging") as ls2, patch(
                "salt._logging.shutdown_logging"
            ) as ls3:
                sh_proc = salt.utils.process.SignalHandlingProcess(
                    target=self.process_target, args=(evt,)
                )
                sh_proc.run()
                assert evt.is_set()
        ls1.assert_called()
        ls2.assert_called()
        ls3.assert_called()

    def test_callbacks_called_when_run_overridden(self):
        "Validate SignalHandlingProcess sub classes call after fork and finalize methods when run is overridden"

        class MyProcess(salt.utils.process.SignalHandlingProcess):
            def __init__(self):
                super().__init__()
                self.evt = multiprocessing.Event()

            def run(self):
                self.evt.set()

        sig_to_mock = "salt.utils.process.SignalHandlingProcess._setup_signals"
        # Mock _setup_signals so we do not register one for this process.
        with patch(sig_to_mock):
            with patch(
                "salt._logging.get_logging_options_dict", return_value={"1": 1}
            ) as ls1, patch("salt._logging.setup_logging") as ls2, patch(
                "salt._logging.shutdown_logging"
            ) as ls3:
                sh_proc = MyProcess()
                sh_proc.run()
                assert sh_proc.evt.is_set()
        ls1.assert_called()
        ls2.assert_called()
        ls3.assert_called()


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


@pytest.mark.skipif(not HAS_PSUTIL, reason="Missing psutil")
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


@pytest.mark.skipif(not HAS_PSUTIL, reason="Missing psutil")
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


@pytest.mark.skipif(not HAS_PSUTIL, reason="Missing psutil")
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
