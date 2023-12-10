import logging

import salt.utils.minion
from tests.support.mock import MagicMock, mock_open, patch
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


class FakeThreadingClass:
    name = "thread-name"


class MinionUtilTestCase(TestCase):
    """
    TestCase for salt.utils.minion
    """

    def test__read_proc_file_multiprocessing_false(self):
        """
        test get_minion_pillar when
        target exists
        """

        opts = {"multiprocessing": False}
        proc_data = {
            "tgt_type": "glob",
            "jid": "20200310230030623022",
            "tgt": "minion",
            "pid": 12345,
            "ret": "",
            "user": "root",
            "arg": [10],
            "fun": "test.sleep",
        }

        fake_thread = FakeThreadingClass()
        fake_thread.name = "20200310230030623022-Job-20200310230030623022"

        with patch("os.getpid", MagicMock(return_value=12345)):
            with patch("salt.utils.files.fopen", mock_open(read_data=b"msgpack")):
                with patch("salt.payload.loads", MagicMock(return_value=proc_data)):
                    with patch(
                        "salt.utils.process.os_is_running", MagicMock(return_value=True)
                    ):
                        with patch(
                            "threading.enumerate", MagicMock(return_value=[fake_thread])
                        ):
                            with patch(
                                "salt.utils.minion._check_cmdline",
                                MagicMock(return_value=True),
                            ):
                                data = salt.utils.minion._read_proc_file(
                                    "/var/cache/salt/minion/proc/20200310230030623022",
                                    opts,
                                )
                                self.assertEqual(data, proc_data)

        opts = {"multiprocessing": False}
        proc_data = {
            "tgt_type": "glob",
            "jid": "20200310230030623022",
            "tgt": "minion",
            "pid": 12345,
            "ret": "",
            "user": "root",
            "arg": [10],
            "fun": "test.sleep",
        }

        fake_thread = FakeThreadingClass()
        fake_thread.name = "20200310230030623022"

        with patch("os.getpid", MagicMock(return_value=12345)):
            with patch("salt.utils.files.fopen", mock_open(read_data=b"msgpack")):
                with patch("salt.payload.loads", MagicMock(return_value=proc_data)):
                    with patch(
                        "salt.utils.process.os_is_running", MagicMock(return_value=True)
                    ):
                        with patch(
                            "threading.enumerate", MagicMock(return_value=[fake_thread])
                        ):
                            with patch(
                                "salt.utils.minion._check_cmdline",
                                MagicMock(return_value=True),
                            ):
                                data = salt.utils.minion._read_proc_file(
                                    "/var/cache/salt/minion/proc/20200310230030623022",
                                    opts,
                                )
                                self.assertEqual(data, proc_data)

        opts = {"multiprocessing": False}
        proc_data = {
            "tgt_type": "glob",
            "jid": "20200310230030623022",
            "tgt": "minion",
            "pid": 12345,
            "ret": "",
            "user": "root",
            "arg": [10],
            "fun": "test.sleep",
        }

        fake_thread = FakeThreadingClass()
        fake_thread.name = "20200310230030623022"

        with patch("os.getpid", MagicMock(return_value=12345)):
            with patch("salt.utils.files.fopen", mock_open(read_data=b"msgpack")):
                with patch("salt.payload.loads", MagicMock(return_value=proc_data)):
                    with patch(
                        "salt.utils.process.os_is_running", MagicMock(return_value=True)
                    ):
                        with patch(
                            "threading.enumerate", MagicMock(return_value=[fake_thread])
                        ):
                            with patch(
                                "salt.utils.minion._check_cmdline",
                                MagicMock(return_value=False),
                            ):
                                with patch("os.remove", MagicMock(return_value=True)):
                                    data = salt.utils.minion._read_proc_file(
                                        "/var/cache/salt/minion/proc/20200310230030623022",
                                        opts,
                                    )
                                    self.assertEqual(data, None)

    def test__read_proc_file_multiprocessing_true(self):
        """
        test get_minion_pillar when
        target exists
        """

        opts = {"multiprocessing": True}
        proc_data = {
            "tgt_type": "glob",
            "jid": "20200310230030623022",
            "tgt": "minion",
            "pid": 12345,
            "ret": "",
            "user": "root",
            "arg": [10],
            "fun": "test.sleep",
        }

        with patch("os.getpid", MagicMock(return_value=12345)):
            with patch("salt.utils.files.fopen", mock_open(read_data=b"msgpack")):
                with patch("salt.payload.loads", MagicMock(return_value=proc_data)):
                    with patch(
                        "salt.utils.process.os_is_running", MagicMock(return_value=True)
                    ):
                        with patch(
                            "salt.utils.minion._check_cmdline",
                            MagicMock(return_value=True),
                        ):
                            data = salt.utils.minion._read_proc_file(
                                "/var/cache/salt/minion/proc/20200310230030623022", opts
                            )
                            self.assertEqual(data, None)
