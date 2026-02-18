"""
Test salt.utils.zeromq
"""

import pytest
import zmq

import salt.utils.zeromq
from salt.exceptions import SaltSystemExit
from tests.support.mock import patch
from tests.support.unit import TestCase


class UtilsTestCase(TestCase):
    @pytest.mark.skipif(
        not hasattr(zmq, "IPC_PATH_MAX_LEN"),
        reason="ZMQ does not have max length support.",
    )
    def test_check_ipc_length(self):
        """
        Ensure we throw an exception if we have a too-long IPC URI
        """
        with patch("zmq.IPC_PATH_MAX_LEN", 1):
            self.assertRaises(
                SaltSystemExit, salt.utils.zeromq.check_ipc_path_max_len, "1" * 1024
            )


def test_is_retryable_connection_error_tornado_callbacks_race():
    exc = TypeError("'NoneType' object is not iterable")
    assert salt.utils.zeromq.is_retryable_connection_error(exc)


def test_is_retryable_connection_error_walks_exception_chain():
    try:
        try:
            raise TypeError("'NoneType' object is not iterable")
        except TypeError as exc:
            raise RuntimeError("wrapper") from exc
    except RuntimeError as exc:
        assert salt.utils.zeromq.is_retryable_connection_error(exc)


def test_is_retryable_connection_error_non_retryable():
    assert not salt.utils.zeromq.is_retryable_connection_error(ValueError("fatal"))