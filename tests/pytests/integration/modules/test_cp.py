"""
Integration tests for the cp execution module.
"""

import hashlib
import os
import socketserver
import threading
from http.server import BaseHTTPRequestHandler

import pytest

import salt.utils.files
import salt.utils.stringutils


@pytest.fixture
def issue_68572_template_tree(base_env_state_tree_root_dir):
    main = base_env_state_tree_root_dir / "issue-68572-main.j2"
    mapfile = base_env_state_tree_root_dir / "issue-68572-map.jinja"
    main.write_text(
        "{%- from 'issue-68572-map.jinja' import defaults with context -%}\n"
        "{{ defaults['foo'] }}\n"
    )
    mapfile.write_text("{% set defaults = {'foo': 'bar'} %}\n")
    try:
        yield "salt://issue-68572-main.j2"
    finally:
        main.unlink(missing_ok=True)
        mapfile.unlink(missing_ok=True)


def test_get_template_with_imported_context(
    salt_call_cli, issue_68572_template_tree, tmp_path
):
    """
    Regression test for #68572.

    ``cp.get_template`` against a Jinja template that contains a
    ``{% from '...' import ... with context %}`` statement must render
    successfully. Prior to the fix the loader-backed dunders passed to the
    template rendering machinery were left wrapped in
    ``NamedLoaderContext``; the file client and channel constructed by
    ``SaltCacheLoader`` for the imported template then ran on the tornado
    IO loop where the loader context is not set, causing
    ``NamedLoaderContext.value()`` to return ``None`` and the channel's
    ``self.opts.get(...)`` call to raise
    ``AttributeError: 'NoneType' object has no attribute 'get'``.
    """
    dest = tmp_path / "issue-68572.out"
    ret = salt_call_cli.run("cp.get_template", issue_68572_template_tree, str(dest))
    assert ret.returncode == 0, ret
    assert ret.data, ret
    with salt.utils.files.fopen(str(dest), "r") as fp_:
        rendered = salt.utils.stringutils.to_unicode(fp_.read())
    assert "bar" in rendered


# Comfortably larger than Tornado's 100MiB (104857600 byte) default
# max_buffer_size, so a truncated download would be reliably detected.
_LARGE_DOWNLOAD_SIZE = 101 * 1024 * 1024
# Deterministic, cheap-to-regenerate payload so the expected hash can be
# computed independently of the server that streams it.
_LARGE_DOWNLOAD_PATTERN = bytes(range(256))


def _expected_large_download_sha256():
    digest = hashlib.sha256()
    remaining = _LARGE_DOWNLOAD_SIZE
    while remaining:
        chunk = _LARGE_DOWNLOAD_PATTERN[: min(len(_LARGE_DOWNLOAD_PATTERN), remaining)]
        digest.update(chunk)
        remaining -= len(chunk)
    return digest.hexdigest()


class _NoContentLengthHandler(BaseHTTPRequestHandler):
    """
    Serves ``_LARGE_DOWNLOAD_SIZE`` bytes of a deterministic pattern with no
    ``Content-Length`` header, forcing the client to read until the
    connection is closed, same as e.g. a winrepo installer served without
    that header.
    """

    def do_GET(self):  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.end_headers()
        remaining = _LARGE_DOWNLOAD_SIZE
        while remaining:
            chunk = _LARGE_DOWNLOAD_PATTERN[
                : min(len(_LARGE_DOWNLOAD_PATTERN), remaining)
            ]
            try:
                self.wfile.write(chunk)
            except OSError:
                return
            remaining -= len(chunk)

    def log_message(self, *args):  # pylint: disable=arguments-differ
        pass


@pytest.fixture
def no_content_length_webserver():
    httpd = socketserver.TCPServer(("127.0.0.1", 0), _NoContentLengthHandler)
    port = httpd.server_address[1]
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()
    try:
        yield f"http://127.0.0.1:{port}/large-file"
    finally:
        httpd.shutdown()
        server_thread.join(timeout=5)


@pytest.mark.slow_test
@pytest.mark.windows_whitelisted
def test_cache_file_large_http_download_without_content_length_not_truncated(
    salt_call_cli, no_content_length_webserver
):
    """
    Regression test for https://github.com/saltstack/salt/issues/69916

    ``cp.cache_file`` (used by ``win_pkg`` to download winrepo installers,
    among others) must not silently truncate downloads at Tornado's 100MiB
    default ``max_buffer_size`` when the server doesn't send a
    ``Content-Length`` header.
    """
    ret = salt_call_cli.run("cp.cache_file", no_content_length_webserver, _timeout=120)
    assert ret.returncode == 0, ret
    cached_path = ret.data
    assert cached_path, ret

    assert os.path.getsize(cached_path) == _LARGE_DOWNLOAD_SIZE, (
        f"Expected {_LARGE_DOWNLOAD_SIZE} bytes but got "
        f"{os.path.getsize(cached_path)}; the download was truncated "
        "(see #69916)"
    )

    digest = hashlib.sha256()
    with salt.utils.files.fopen(cached_path, "rb") as fp_:
        for chunk in iter(lambda: fp_.read(1024 * 1024), b""):
            digest.update(chunk)
    assert digest.hexdigest() == _expected_large_download_sha256()
