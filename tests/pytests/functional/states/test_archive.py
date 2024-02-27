import functools
import hashlib
import http.server
import multiprocessing
import os
import random
import shutil
import socket
import sys
from contextlib import closing

import pytest

import salt.utils.files


class TestRequestHandler(http.server.SimpleHTTPRequestHandler):
    """
    Modified request handler class
    """

    def __init__(self, *args, directory=None, **kwargs):
        if directory is None:
            directory = os.getcwd()
        self.directory = directory
        if sys.version_info.minor < 7:
            super().__init__(*args, **kwargs)
        else:
            super().__init__(*args, directory=directory, **kwargs)

    def do_GET(self):
        """
        GET request handling
        """
        none_match = self.headers.get("If-None-Match")
        status_code = 200
        try:
            # Retrieve the local file from the web root to serve to clients
            with salt.utils.files.fopen(
                os.path.join(self.directory, self.path[1:]), "rb"
            ) as reqfp:
                return_data = reqfp.read()
                # We're using this checksum as the etag to show file changes
                checksum = hashlib.sha256(return_data).hexdigest()
                if none_match == checksum:
                    # Status code 304 Not Modified is returned if the file is unchanged
                    status_code = 304
        except:  # pylint: disable=bare-except
            # Something went wrong. We didn't find the requested file
            status_code = 404
            return_data = None
            checksum = None

        self.send_response(status_code)

        # Return the Etag header if we have the checksum
        if checksum:
            # IMPORTANT: This introduces randomness into the tests. The Etag header key
            # will be converted to lowercase in the code... but if someone breaks that,
            # it'll rear it's head here as random failures that are hard to reproduce.
            # Any alternatives seem overly complex. So... don't break the case insensitivity
            # in the code.
            possible_etags = ["Etag", "ETag", "etag", "ETAG"]
            self.send_header(random.choice(possible_etags), checksum)
            self.end_headers()

        # Return file content
        if return_data:
            self.wfile.write(return_data)


def serve(port=8000, directory=None):
    """
    Function to serve a directory via http.server
    """
    handler = functools.partial(TestRequestHandler, directory=directory)
    s = http.server.HTTPServer(("127.0.0.1", port), handler)
    s.serve_forever()


@pytest.fixture(scope="module")
def free_port():
    """
    Utility fixture to grab a free port for the web server
    """
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


@pytest.fixture(autouse=True, scope="module")
def server(free_port, web_root):
    """
    Web server fixture
    """
    p = multiprocessing.Process(target=serve, args=(free_port, web_root))
    p.start()
    yield
    p.terminate()
    p.join()


@pytest.fixture(scope="module")
def web_root(tmp_path_factory):
    """
    Temporary directory fixture for the web server root
    """
    _web_root = tmp_path_factory.mktemp("web_root")
    try:
        yield str(_web_root)
    finally:
        shutil.rmtree(str(_web_root), ignore_errors=True)


@pytest.mark.slow_test
def test_archive_extracted_web_source_etag_operation(
    modules, states, free_port, web_root, minion_opts
):
    """
    This functional test checks the operation of the use_etag parameter to the
    archive.extracted state. There are four (4) invocations of archive.extracted
    with a web source, but only three (3) will trigger a call to the web server
    as shown below and in comments within.

        127.0.0.1 - - [08/Mar/2022 13:07:10] "GET /foo.tar.gz HTTP/1.1" 200 -
        127.0.0.1 - - [08/Mar/2022 13:07:10] "GET /foo.tar.gz HTTP/1.1" 304 -
        127.0.0.1 - - [08/Mar/2022 13:07:10] "GET /foo.tar.gz HTTP/1.1" 200 -

    Checks are documented in the comments.
    """
    # Create file in the web root directory to serve
    states.file.managed(
        name=os.path.join(web_root, "foo", "bar.txt"),
        contents="this is my file",
        makedirs=True,
    )
    modules.archive.tar(
        options="czf",
        tarfile=os.path.join(web_root, "foo.tar.gz"),
        sources=[os.path.join(web_root, "foo")],
        cwd=web_root,
    )

    # File should not be cached yet
    cached_file = os.path.join(
        minion_opts["cachedir"],
        "extrn_files",
        "base",
        f"localhost{free_port}",
        "foo.tar.gz",
    )
    cached_etag = cached_file + ".etag"
    assert not os.path.exists(cached_file)
    assert not os.path.exists(cached_etag)

    # Pull the file from the web server
    #     Web server returns 200 status code with content:
    #     127.0.0.1 - - [08/Mar/2022 13:07:10] "GET /foo.tar.gz HTTP/1.1" 200 -
    states.archive.extracted(
        name=web_root,
        source=f"http://localhost:{free_port}/foo.tar.gz",
        archive_format="tar",
        options="z",
        use_etag=True,
    )

    # Now the file is cached
    assert os.path.exists(cached_file)
    assert os.path.exists(cached_etag)

    # Store the original modified time of the cached file
    cached_file_mtime = os.path.getmtime(cached_file)

    # Pull the file again. Etag hasn't changed. No download occurs.
    #     Web server returns 304 status code and no content:
    #     127.0.0.1 - - [08/Mar/2022 13:07:10] "GET /foo.tar.gz HTTP/1.1" 304 -
    states.archive.extracted(
        name=web_root,
        source=f"http://localhost:{free_port}/foo.tar.gz",
        archive_format="tar",
        options="z",
        use_etag=True,
    )

    # Check that the modified time of the cached file hasn't changed
    assert cached_file_mtime == os.path.getmtime(cached_file)

    # Change file in the web root directory
    states.file.managed(
        name=os.path.join(web_root, "foo", "bar.txt"),
        contents="this is my changed file",
    )
    modules.archive.tar(
        options="czf",
        tarfile=os.path.join(web_root, "foo.tar.gz"),
        sources=[os.path.join(web_root, "foo")],
        cwd=web_root,
    )

    # Don't use Etag. Cached file is there, Salt won't try to download.
    #     No call to the web server will be made.
    states.archive.extracted(
        name=web_root,
        source=f"http://localhost:{free_port}/foo.tar.gz",
        archive_format="tar",
        options="z",
        use_etag=False,
    )

    # Check that the modified time of the cached file hasn't changed
    assert cached_file_mtime == os.path.getmtime(cached_file)

    # Now use Etag again. Cached file changes
    #     Web server returns 200 status code with content
    #     127.0.0.1 - - [08/Mar/2022 13:07:10] "GET /foo.tar.gz HTTP/1.1" 200 -
    states.archive.extracted(
        name=web_root,
        source=f"http://localhost:{free_port}/foo.tar.gz",
        archive_format="tar",
        options="z",
        use_etag=True,
    )

    # The modified time of the cached file now changes
    assert cached_file_mtime != os.path.getmtime(cached_file)
