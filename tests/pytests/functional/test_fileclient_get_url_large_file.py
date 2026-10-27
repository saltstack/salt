"""
Integration-style regression tests for
https://github.com/saltstack/salt/issues/69916.

Unlike the unit tests in ``tests/pytests/unit/utils/test_http.py`` and
``tests/pytests/unit/fileclient/test_fileclient.py`` (which exercise
``salt.utils.http.query`` and ``salt.fileclient.Client.get_url`` in
isolation, mocking the other), these tests drive
``salt.fileclient.Client.get_url`` end-to-end against a real HTTP
server with nothing mocked, to confirm the whole download pipeline
(fileclient -> salt.utils.http.query -> a real socket -> the minion's
file cache on disk) actually delivers large files intact for both the
``tornado`` and ``requests`` backends.
"""

import hashlib
import os
import socketserver
import threading
from http.server import BaseHTTPRequestHandler

import pytest

import salt.fileclient as fileclient
import salt.utils.files
from salt.exceptions import MinionError

# This bug (#69916) is specifically about winrepo_ng downloads on
# Windows, so make sure these tests actually run there too.
pytestmark = [pytest.mark.windows_whitelisted]


class _CloseWithoutContentLengthHandler(BaseHTTPRequestHandler):
    """
    Serves ``body`` with no ``Content-Length`` header, forcing the
    client to read until the connection is closed. This is the framing
    that triggered Tornado's silent truncation at its default
    ``max_buffer_size`` (100MiB) prior to the fix for #69916.
    """

    body = b""

    def do_GET(self):  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.end_headers()
        try:
            self.wfile.write(self.body)
        except OSError:
            # Client gave up; nothing left to do.
            pass

    def log_message(self, *args):  # pylint: disable=arguments-differ
        pass


class _TruncatedContentLengthHandler(BaseHTTPRequestHandler):
    """
    Advertises the full size of ``body`` via ``Content-Length``, but
    only sends half of it before dropping the connection, simulating a
    server-side failure partway through a download.
    """

    body = b""

    def do_GET(self):  # noqa: N802
        truncated_at = len(self.body) // 2
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(self.body)))
        self.end_headers()
        try:
            self.wfile.write(self.body[:truncated_at])
        except OSError:
            pass
        self.connection.close()

    def log_message(self, *args):  # pylint: disable=arguments-differ
        pass


@pytest.fixture(scope="module")
def large_body():
    # Comfortably larger than Tornado's 100MiB default max_buffer_size
    # so a truncation would be reliably detected. Built from a
    # repeating, non-constant pattern (rather than all-zero/all-'x'
    # bytes) so that a regression which corrupts data without changing
    # its length wouldn't slip past a naive size-only check.
    pattern = bytes(range(256))
    size = 101 * 1024 * 1024
    reps, remainder = divmod(size, len(pattern))
    return pattern * reps + pattern[:remainder]


def _start_server(handler_cls, body):
    handler = type("Handler", (handler_cls,), {"body": body})
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()
    return httpd, server_thread, f"http://127.0.0.1:{port}/largefile.bin"


@pytest.mark.slow_test
@pytest.mark.parametrize("backend", ["tornado", "requests"])
def test_get_url_large_file_no_content_length_not_truncated(
    tmp_path, large_body, backend
):
    """
    A minion downloading a large (>100MiB) file from a server that
    doesn't send a Content-Length header (as can happen with
    winrepo_ng HTTP servers) must receive and cache the entire file
    instead of having it silently truncated.
    """
    httpd, server_thread, url = _start_server(
        _CloseWithoutContentLengthHandler, large_body
    )
    try:
        dest = str(tmp_path / "downloaded.bin")
        client = fileclient.Client(
            {"cachedir": str(tmp_path / "cache"), "backend": backend}
        )

        result = client.get_url(url, dest)

        assert result == dest
        assert os.path.getsize(dest) == len(large_body)
        with salt.utils.files.fopen(dest, "rb") as fp_:
            downloaded = fp_.read()
        assert (
            hashlib.sha256(downloaded).digest() == hashlib.sha256(large_body).digest()
        )
    finally:
        httpd.shutdown()
        server_thread.join(timeout=5)


@pytest.mark.slow_test
@pytest.mark.parametrize("backend", ["tornado", "requests"])
def test_get_url_truncated_content_length_raises_cleanly(tmp_path, large_body, backend):
    """
    If a server advertises a Content-Length but the connection drops
    before delivering that many bytes, both backends detect the broken
    connection themselves (before get_url's own Content-Length check
    ever runs) and get_url must surface that as a clean MinionError
    instead of the underlying tornado/requests exception propagating
    unhandled -- notably for the ``requests`` backend, which used to
    crash here with an unhandled ``ChunkedEncodingError``/
    ``IncompleteRead`` prior to the fix for #69916. Either way, the
    partial download must not be promoted to ``dest``.
    """
    httpd, server_thread, url = _start_server(
        _TruncatedContentLengthHandler, large_body
    )
    try:
        dest = str(tmp_path / "downloaded.bin")
        client = fileclient.Client(
            {"cachedir": str(tmp_path / "cache"), "backend": backend}
        )

        with pytest.raises(MinionError):
            client.get_url(url, dest)

        assert not os.path.exists(dest)
    finally:
        httpd.shutdown()
        server_thread.join(timeout=5)
