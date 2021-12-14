"""
unit tests for the cache runner
"""

import os

import pytest
import salt.runners.queue as queue_mod
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase


class QueueTest(TestCase, LoaderModuleMockMixin):
    """
    Validate the queue runner
    """

    def setup_loader_modules(self):
        return {
            queue_mod: {
                "__opts__": {
                    "sock_dir": os.path.join(RUNTIME_VARS.TMP, "queue-runner-sock-dir"),
                    "transport": "zeromq",
                }
            }
        }

    def test_insert_runner(self):
        queue_insert = MagicMock(return_value=True)
        with patch.object(queue_mod, "insert", queue_insert):
            queue_mod.insert_runner("test.stdout_print", queue="salt")
        expected_call = {
            "queue": "salt",
            "items": {"fun": "test.stdout_print", "args": [], "kwargs": {}},
            "backend": "pgjsonb",
        }
        queue_insert.assert_called_once_with(**expected_call)

    @pytest.mark.slow_test
    def test_process_runner(self):
        ret = [{"fun": "test.stdout_print", "args": [], "kwargs": {}}]

        queue_pop = MagicMock(return_value=ret)
        test_stdout_print = MagicMock(return_value=True)
        with patch.dict(queue_mod.__salt__, {"test.stdout_print": test_stdout_print}):
            with patch.object(queue_mod, "pop", queue_pop):
                queue_mod.process_runner(queue="salt")
            queue_pop.assert_called_once_with(
                is_runner=True, queue="salt", quantity=1, backend="pgjsonb"
            )
            test_stdout_print.assert_called_once_with()
            queue_pop.assert_called_once_with(
                is_runner=True, queue="salt", quantity=1, backend="pgjsonb"
            )
