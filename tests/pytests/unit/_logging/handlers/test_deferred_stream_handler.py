import logging
import multiprocessing
import signal
import subprocess
import sys
import time

import pytest
from pytestshellutils.utils.processes import terminate_process

from salt._logging.handlers import DeferredStreamHandler
from salt.utils.nb_popen import NonBlockingPopen
from tests.support.helpers import CaptureOutput, dedent
from tests.support.runtests import RUNTIME_VARS

log = logging.getLogger(__name__)


def _sync_with_handlers_proc_target():

    with CaptureOutput() as stds:
        handler = DeferredStreamHandler(sys.stderr)
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)
        logging.root.addHandler(handler)
        logger = logging.getLogger(__name__)
        logger.info("Foo")
        logger.info("Bar")
        logging.root.removeHandler(handler)

        assert not stds.stdout
        assert not stds.stderr

        stream_handler = logging.StreamHandler(sys.stderr)

        # Sync with the other handlers
        handler.sync_with_handlers([stream_handler])

        assert not stds.stdout
        assert stds.stderr == "Foo\nBar\n"


def _deferred_write_on_flush_proc_target():

    with CaptureOutput() as stds:
        handler = DeferredStreamHandler(sys.stderr)
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)
        logging.root.addHandler(handler)
        logger = logging.getLogger(__name__)
        logger.info("Foo")
        logger.info("Bar")
        logging.root.removeHandler(handler)

        assert not stds.stdout
        assert not stds.stderr

        # Flush the handler
        handler.flush()
        assert not stds.stdout
        assert stds.stderr == "Foo\nBar\n"


def test_sync_with_handlers():
    proc = multiprocessing.Process(target=_sync_with_handlers_proc_target)
    proc.start()
    proc.join()
    assert proc.exitcode == 0


def test_deferred_write_on_flush():
    proc = multiprocessing.Process(target=_deferred_write_on_flush_proc_target)
    proc.start()
    proc.join()
    assert proc.exitcode == 0


def test_deferred_write_on_atexit(tmp_path):
    # Python will .flush() and .close() all logging handlers at interpreter shutdown.
    # This should be enough to flush our deferred messages.
    pyscript = dedent(
        r"""
        import sys
        import time
        import logging

        CODE_DIR = {!r}
        if CODE_DIR in sys.path:
            sys.path.remove(CODE_DIR)
        sys.path.insert(0, CODE_DIR)

        from salt._logging.handlers import DeferredStreamHandler
        # Reset any logging handlers we might have already
        logging.root.handlers[:] = []

        handler = DeferredStreamHandler(sys.stderr)
        handler.setLevel(logging.DEBUG)
        logging.root.addHandler(handler)

        log = logging.getLogger(__name__)
        sys.stdout.write('STARTED\n')
        sys.stdout.flush()
        log.debug('Foo')
        sys.exit(0)
    """.format(
            RUNTIME_VARS.CODE_DIR
        )
    )
    script_path = tmp_path / "atexit_deferred_logging_test.py"
    script_path.write_text(pyscript, encoding="utf-8")

    proc = NonBlockingPopen(
        [sys.executable, str(script_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    out = b""
    err = b""

    # This test should never take more than 5 seconds
    execution_time = 5
    max_time = time.time() + execution_time
    try:
        # Just loop consuming output
        while True:
            if time.time() > max_time:
                pytest.fail("Script didn't exit after {} second".format(execution_time))

            time.sleep(0.125)
            _out = proc.recv()
            _err = proc.recv_err()
            if _out:
                out += _out
            if _err:
                err += _err

            if _out is None and _err is None:
                # The script exited
                break

            if proc.poll() is not None:
                # The script exited
                break
    finally:
        terminate_process(proc.pid, kill_children=True)
    if b"Foo" not in err:
        pytest.fail("'Foo' should be in stderr and it's not: {}".format(err))


@pytest.mark.skip_on_windows(reason="Windows does not support SIGINT")
def test_deferred_write_on_sigint(tmp_path):
    pyscript = dedent(
        r"""
        import sys
        import time
        import signal
        import logging

        CODE_DIR = {!r}
        if CODE_DIR in sys.path:
            sys.path.remove(CODE_DIR)
        sys.path.insert(0, CODE_DIR)

        from salt._logging.handlers import DeferredStreamHandler
        # Reset any logging handlers we might have already
        logging.root.handlers[:] = []

        handler = DeferredStreamHandler(sys.stderr)
        handler.setLevel(logging.DEBUG)
        logging.root.addHandler(handler)

        if signal.getsignal(signal.SIGINT) != signal.default_int_handler:
            # Looking at you Debian based distros :/
            signal.signal(signal.SIGINT, signal.default_int_handler)

        log = logging.getLogger(__name__)

        start_printed = False
        while True:
            try:
                log.debug('Foo')
                if start_printed is False:
                    sys.stdout.write('STARTED\n')
                    sys.stdout.write('SIGINT HANDLER: {{!r}}\n'.format(signal.getsignal(signal.SIGINT)))
                    sys.stdout.flush()
                    start_printed = True
                time.sleep(0.125)
            except (KeyboardInterrupt, SystemExit):
                log.info('KeyboardInterrupt caught')
                sys.stdout.write('KeyboardInterrupt caught\n')
                sys.stdout.flush()
                break
        log.info('EXITING')
        sys.stdout.write('EXITING\n')
        sys.stdout.flush()
        sys.exit(0)
        """.format(
            RUNTIME_VARS.CODE_DIR
        )
    )
    script_path = tmp_path / "sigint_deferred_logging_test.py"
    script_path.write_text(pyscript, encoding="utf-8")

    proc = NonBlockingPopen(
        [sys.executable, str(script_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    out = b""
    err = b""

    # Test should take less than 20 seconds, way less
    execution_time = 10
    start = time.time()
    max_time = time.time() + execution_time
    try:
        signalled = False
        log.info("Starting Loop")
        while True:

            time.sleep(0.125)
            _out = proc.recv()
            _err = proc.recv_err()
            if _out:
                out += _out
            if _err:
                err += _err

            if b"STARTED" in out and not signalled:
                # Enough time has passed
                proc.send_signal(signal.SIGINT)
                signalled = True
                log.debug("Sent SIGINT after: %s", time.time() - start)

            if signalled is False:
                if out:
                    pytest.fail(
                        "We have stdout output when there should be none: {}".format(
                            out
                        )
                    )
                if err:
                    pytest.fail(
                        "We have stderr output when there should be none: {}".format(
                            err
                        )
                    )

            if _out is None and _err is None:
                log.info("_out and _err are None")
                if b"Foo" not in err:
                    pytest.fail(
                        "No more output and 'Foo' should be in stderr and it's not: {}".format(
                            err
                        )
                    )
                break

            if proc.poll() is not None:
                log.debug("poll() is not None")
                if b"Foo" not in err:
                    pytest.fail(
                        "Process terminated and 'Foo' should be in stderr and it's not: {}".format(
                            err
                        )
                    )
                break

            if time.time() > max_time:
                log.debug("Reached max time")
                if b"Foo" not in err:
                    pytest.fail(
                        "'Foo' should be in stderr and it's not:\n{0}\nSTDERR:\n{0}\n{1}\n{0}\nSTDOUT:\n{0}\n{2}\n{0}".format(
                            "-" * 80, err, out
                        )
                    )
    finally:
        terminate_process(proc.pid, kill_children=True)
    log.debug("Test took %s seconds", time.time() - start)
