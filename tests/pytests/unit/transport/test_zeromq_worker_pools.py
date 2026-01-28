"""
Unit tests for ZeroMQ worker pool functionality
"""

import inspect

import pytest

import salt.transport.zeromq

pytestmark = [
    pytest.mark.core_test,
]


class TestWorkerPoolCodeStructure:
    """
    Tests to verify the code structure of worker pool methods to catch
    common Python scoping issues that only manifest at runtime.
    """

    def test_zmq_device_pooled_imports_before_usage(self):
        """
        Test that zmq_device_pooled has imports in the correct order.

        This test verifies that the 'import salt.master' statement appears
        BEFORE any usage of salt.utils.files.fopen(). This prevents the
        UnboundLocalError bug where:
        - Line X uses salt.utils.files.fopen()
        - Line Y has 'import salt.master' (Y > X)
        - Python sees the import and treats 'salt' as a local variable
        - Results in: UnboundLocalError: cannot access local variable 'salt'
        """
        # Get the source code of zmq_device_pooled
        source = inspect.getsource(
            salt.transport.zeromq.RequestServer.zmq_device_pooled
        )

        # Find the line numbers
        import_salt_master_line = None
        fopen_usage_line = None

        for line_num, line in enumerate(source.split("\n"), 1):
            if "import salt.master" in line:
                import_salt_master_line = line_num
            if "salt.utils.files.fopen" in line:
                fopen_usage_line = line_num

        # Verify both exist
        assert (
            import_salt_master_line is not None
        ), "Expected 'import salt.master' in zmq_device_pooled"
        assert (
            fopen_usage_line is not None
        ), "Expected 'salt.utils.files.fopen' usage in zmq_device_pooled"

        # The import must come before the usage
        assert import_salt_master_line < fopen_usage_line, (
            f"'import salt.master' at line {import_salt_master_line} must appear "
            f"BEFORE 'salt.utils.files.fopen' at line {fopen_usage_line}. "
            f"Otherwise Python will treat 'salt' as a local variable and "
            f"raise UnboundLocalError."
        )

    def test_zmq_device_pooled_has_worker_pools_param(self):
        """
        Test that zmq_device_pooled accepts worker_pools parameter.
        """
        sig = inspect.signature(salt.transport.zeromq.RequestServer.zmq_device_pooled)
        assert (
            "worker_pools" in sig.parameters
        ), "zmq_device_pooled should have worker_pools parameter"

    def test_zmq_device_pooled_creates_marker_file(self):
        """
        Test that zmq_device_pooled includes code to create workers.ipc marker file.

        This marker file is required for netapi's _is_master_running() check.
        """
        source = inspect.getsource(
            salt.transport.zeromq.RequestServer.zmq_device_pooled
        )

        # Check for marker file creation
        assert (
            "workers.ipc" in source
        ), "zmq_device_pooled should create workers.ipc marker file"
        assert (
            "salt.utils.files.fopen" in source or "open(" in source
        ), "zmq_device_pooled should use fopen or open to create marker file"
        assert (
            "os.chmod" in source
        ), "zmq_device_pooled should set permissions on marker file"

    def test_zmq_device_pooled_uses_router(self):
        """
        Test that zmq_device_pooled creates and uses RequestRouter for routing.
        """
        source = inspect.getsource(
            salt.transport.zeromq.RequestServer.zmq_device_pooled
        )

        assert (
            "RequestRouter" in source
        ), "zmq_device_pooled should create RequestRouter instance"
        assert (
            "route_request" in source
        ), "zmq_device_pooled should call route_request method"


class TestRequestServerIntegration:
    """
    Tests for RequestServer that verify worker pool setup without
    actually running multiprocessing code.
    """

    def test_pre_fork_with_worker_pools(self):
        """
        Test that pre_fork method exists and accepts worker_pools parameter.
        """
        sig = inspect.signature(salt.transport.zeromq.RequestServer.pre_fork)
        assert (
            "process_manager" in sig.parameters
        ), "pre_fork should have process_manager parameter"
        assert (
            "worker_pools" in sig.parameters
        ), "pre_fork should have worker_pools parameter"

    def test_request_server_has_zmq_device_pooled_method(self):
        """
        Test that RequestServer has the zmq_device_pooled method.
        """
        assert hasattr(
            salt.transport.zeromq.RequestServer, "zmq_device_pooled"
        ), "RequestServer should have zmq_device_pooled method"

        # Verify it's a callable method
        assert callable(
            salt.transport.zeromq.RequestServer.zmq_device_pooled
        ), "zmq_device_pooled should be callable"
