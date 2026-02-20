import os

import pytest

import salt.config
import salt.ext.tornado.gen
import salt.ext.tornado.ioloop
import salt.payload
import salt.utils.files
import salt.utils.state
from tests.support.mock import MagicMock, patch


class MockProcess:
    def __init__(self, pid, alive=True):
        self.pid = pid
        self._alive = alive

    def is_alive(self):
        return self._alive


@pytest.fixture
def minion_opts(tmp_path):
    # Use real minion config defaults
    opts = salt.config.minion_config(None)
    opts.update(
        {
            "cachedir": str(tmp_path),
            "process_count_max": 2,
            "multiprocessing": True,
            "minion_jid_queue_hwm": 100,
            "conf_file": None,
            "sock_dir": str(tmp_path),
            "pki_dir": str(tmp_path),
        }
    )
    os.makedirs(os.path.join(str(tmp_path), "proc"), exist_ok=True)
    os.makedirs(os.path.join(str(tmp_path), "state_queue"), exist_ok=True)
    os.makedirs(os.path.join(str(tmp_path), "job_queue"), exist_ok=True)
    return opts


def test_state_queue_placeholder_creation(minion_opts):
    """
    Verify that _process_state_queue_async_impl writes a placeholder proc file
    before releasing the lock.
    """
    from salt.minion import Minion

    io_loop = salt.ext.tornado.ioloop.IOLoop.current()

    async def run_test():
        with patch(
            "salt.minion.Minion._load_modules", return_value=(None, None, None, None)
        ), patch("salt.crypt.AsyncAuth.get_keys", return_value=None), patch(
            "salt.loader.grains", return_value={}
        ):
            minion = Minion(minion_opts)
            minion.subprocess_list = MagicMock()
            minion.subprocess_list.processes = []

            # Create a queued state job
            jid = "20260212000000000001"
            queue_dir = os.path.join(minion_opts["cachedir"], "state_queue")
            payload = {"jid": jid, "fun": "state.apply", "arg": [], "kwarg": {}}
            path = os.path.join(queue_dir, f"queued_0_{jid}.p")
            with salt.utils.files.fopen(path, "w+b") as fp:
                salt.payload.dump(payload, fp)

            # Mock check_prior_running_states to return empty (no conflicts)
            with patch(
                "salt.utils.state.check_prior_running_states", return_value=[]
            ), patch("salt.utils.state.get_active_states", return_value=[]), patch(
                "salt.minion.Minion._handle_decoded_payload"
            ) as mock_handle:

                # Run the queue processor
                await minion._process_state_queue_async_impl()

                # Verify placeholder exists
                proc_fn = os.path.join(minion_opts["cachedir"], "proc", jid)
                assert os.path.exists(proc_fn), "Placeholder proc file should exist"

                with salt.utils.files.fopen(proc_fn, "rb") as fp:
                    data = salt.payload.load(fp)
                    assert data["jid"] == jid
                    assert data["pid"] == os.getpid()

    io_loop.run_sync(run_test)


def test_headroom_check_inside_lock(minion_opts):
    """
    Verify that headroom is re-checked inside the job_queue lock.
    """
    from salt.minion import Minion

    io_loop = salt.ext.tornado.ioloop.IOLoop.current()

    async def run_test():
        with patch(
            "salt.minion.Minion._load_modules", return_value=(None, None, None, None)
        ), patch("salt.crypt.AsyncAuth.get_keys", return_value=None), patch(
            "salt.loader.grains", return_value={}
        ):
            minion = Minion(minion_opts)
            minion.subprocess_list = MagicMock()
            minion.subprocess_list.processes = []

            data = {"jid": "123", "fun": "test.ping"}

            # Mock headroom to pass initially but fail inside lock
            minion._has_fd_headroom = MagicMock(
                side_effect=[True, False]
            )  # Pass then Fail
            minion._queue_job = MagicMock()
            minion._invoke_execution = MagicMock()

            # Run _handle_decoded_payload_impl
            await minion._handle_decoded_payload_impl(data)

            # Verify it was queued despite passing the initial check
            minion._queue_job.assert_called_once()
            minion._invoke_execution.assert_not_called()
            # It should be called twice (outside then inside lock)
            assert minion._has_fd_headroom.call_count == 2

    io_loop.run_sync(run_test)
