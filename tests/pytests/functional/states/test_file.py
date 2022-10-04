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


class RequestHandler(http.server.SimpleHTTPRequestHandler):
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
                os.path.join(self.directory, self.path[1:])
            ) as reqfp:
                return_text = reqfp.read().encode("utf-8")
                # We're using this checksum as the etag to show file changes
                checksum = hashlib.md5(return_text).hexdigest()
                if none_match == checksum:
                    # Status code 304 Not Modified is returned if the file is unchanged
                    status_code = 304
        except:  # pylint: disable=bare-except
            # Something went wrong. We didn't find the requested file
            status_code = 404
            return_text = None
            checksum = None

        self.send_response(status_code)

        # Return the Etag header if we have the checksum
        if checksum:
            # IMPORTANT: This introduces randomness into the tests. The Etag header key
            # will be converted to lowercase in the code... but if someone breaks that,
            # it'll rear it's head here as random failures that are hard to reproduce.
            # Any alternatives seem overly complex. So... don't break the case insensitivity
            # in the code.
            possible_etags = ["Etag", "ETag"]
            self.send_header(random.choice(possible_etags), checksum)
            self.end_headers()

        # Return file content
        if return_text:
            self.wfile.write(return_text)


def serve(port=8000, directory=None):
    """
    Function to serve a directory via http.server
    """
    handler = functools.partial(RequestHandler, directory=directory)
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


def test_file_managed_web_source_etag_operation(
    states, free_port, web_root, minion_opts
):
    """
    This functional test checks the operation of the use_etag parameter to the
    file.managed state. There are four (4) invocations of file.managed with a
    web source, but only three (3) will trigger a call to the web server as
    shown below and in comments within.

        127.0.0.1 - - [08/Jan/2022 00:53:11] "GET /foo.txt HTTP/1.1" 200 -
        127.0.0.1 - - [08/Jan/2022 00:53:11] "GET /foo.txt HTTP/1.1" 304 -
        127.0.0.1 - - [08/Jan/2022 00:53:12] "GET /foo.txt HTTP/1.1" 200 -

    Checks are documented in the comments.
    """
    # Create file in the web root directory to serve
    states.file.managed(
        name=os.path.join(web_root, "foo.txt"), contents="this is my file"
    )

    # File should not be cached yet
    cached_file = os.path.join(
        minion_opts["cachedir"],
        "extrn_files",
        "base",
        "localhost:{free_port}".format(free_port=free_port),
        "foo.txt",
    )
    cached_etag = cached_file + ".etag"
    assert not os.path.exists(cached_file)
    assert not os.path.exists(cached_etag)

    # Pull the file from the web server
    #     Web server returns 200 status code with content:
    #     127.0.0.1 - - [08/Jan/2022 00:53:11] "GET /foo.txt HTTP/1.1" 200 -
    states.file.managed(
        name=os.path.join(web_root, "bar.txt"),
        source="http://localhost:{free_port}/foo.txt".format(free_port=free_port),
        use_etag=True,
    )

    # Now the file is cached
    assert os.path.exists(cached_file)
    assert os.path.exists(cached_etag)

    # Store the original modified time of the cached file
    cached_file_mtime = os.path.getmtime(cached_file)

    # Pull the file again. Etag hasn't changed. No download occurs.
    #     Web server returns 304 status code and no content:
    #     127.0.0.1 - - [08/Jan/2022 00:53:11] "GET /foo.txt HTTP/1.1" 304 -
    states.file.managed(
        name=os.path.join(web_root, "bar.txt"),
        source="http://localhost:{free_port}/foo.txt".format(free_port=free_port),
        use_etag=True,
    )

    # Check that the modified time of the cached file hasn't changed
    assert cached_file_mtime == os.path.getmtime(cached_file)

    # Change file in the web root directory
    states.file.managed(
        name=os.path.join(web_root, "foo.txt"), contents="this is my changed file"
    )

    # Don't use Etag. Cached file is there, Salt won't try to download.
    #     No call to the web server will be made.
    states.file.managed(
        name=os.path.join(web_root, "bar.txt"),
        source="http://localhost:{free_port}/foo.txt".format(free_port=free_port),
        use_etag=False,
    )

    # Check that the modified time of the cached file hasn't changed
    assert cached_file_mtime == os.path.getmtime(cached_file)

    # Now use Etag again. Cached file changes
    #     Web server returns 200 status code with content
    #     127.0.0.1 - - [08/Jan/2022 00:53:12] "GET /foo.txt HTTP/1.1" 200 -
    states.file.managed(
        name=os.path.join(web_root, "bar.txt"),
        source="http://localhost:{free_port}/foo.txt".format(free_port=free_port),
        use_etag=True,
    )

    # The modified time of the cached file now changes
    assert cached_file_mtime != os.path.getmtime(cached_file)
