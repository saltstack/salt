import functools
import hashlib
import http.server
import multiprocessing
import os
import random
import shutil
import socket
import subprocess
import sys
from contextlib import closing
from pathlib import Path

import psutil
import pytest

import salt.utils.files
from tests.support.runtests import RUNTIME_VARS

try:
    import gnupg as gnupglib

    HAS_GNUPG = True
except ImportError:
    HAS_GNUPG = False


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


@pytest.fixture
def gpghome(tmp_path):
    root = tmp_path / "gpghome"
    root.mkdir(mode=0o0700)
    try:
        yield root
    finally:
        # Make sure we don't leave any gpg-agents running behind
        gpg_connect_agent = shutil.which("gpg-connect-agent")
        if gpg_connect_agent:
            gnupghome = root / ".gnupg"
            if not gnupghome.is_dir():
                gnupghome = root
            try:
                subprocess.run(
                    [gpg_connect_agent, "killagent", "/bye"],
                    env={"GNUPGHOME": str(gnupghome)},
                    shell=False,
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except subprocess.CalledProcessError:
                # This is likely CentOS 7 or Amazon Linux 2
                pass

        # If the above errored or was not enough, as a last resort, let's check
        # the running processes.
        for proc in psutil.process_iter():
            try:
                if "gpg-agent" in proc.name():
                    for arg in proc.cmdline():
                        if str(root) in arg:
                            proc.terminate()
            except Exception:  # pylint: disable=broad-except
                pass


@pytest.fixture
def gnupg(gpghome):
    return gnupglib.GPG(gnupghome=str(gpghome))


@pytest.fixture
def a_pubkey():
    return """\
-----BEGIN PGP PUBLIC KEY BLOCK-----

mI0EY9pxawEEAPpBbXxRYFUm6np5h746Nch7+OrbLdtBxP8x7VDOockr/x7drssb
llVFuK4HmiJg+Nkyakn3XmVYBHY2yBIkN/MP+R1zRxiFmniKOTD15UuHSQaWZTqh
qac6XrLZ20BiWl1fKweCz1wGUcMZaOBs0WVB0sIupqfS90Ub93VC/+oxABEBAAG0
JlNhbHRTdGFjayBBIFRlc3QgPGF0ZXN0QHNhbHRzdGFjay5jb20+iNEEEwEIADsW
IQT4zMjLXh2IaNqlhZqx+apXxJfnHAUCY9pxawIbAwULCQgHAgIiAgYVCgkICwIE
FgIDAQIeBwIXgAAKCRCx+apXxJfnHFDhA/47t5yYdCcjxXu/1Kn9sQwI+aq/S3x9
/ZKE+RodlryqA43BUT7N6JLQ5zJO6p+kRhMwCcVfBeDNJANqVi63HEDp8q3633BF
q1Cbi3BG0ugBdCADIETYBwl/ytMSgYwRO8b4TkYCyhWuWAgliVF3ceX0AVsng8pF
o6Vh4A3SqosQgA==
=eHpb
-----END PGP PUBLIC KEY BLOCK-----"""


@pytest.fixture
def a_fp():
    return "F8CCC8CB5E1D8868DAA5859AB1F9AA57C497E71C"


@pytest.fixture
def b_pubkey():
    return """\
-----BEGIN PGP PUBLIC KEY BLOCK-----

mI0EY9pxigEEANbHCh566IEbp9Ez1WE3oEi+XXyf7H3GDgrVc8v9COMexpAFkJa1
gG+yCm4bOZ5vHAXbP2rGvlOEcao3y3evj2TWahg0+05CDugRjL0pO4JcMUBV1mBZ
ynUGoQ5T+WtKilJ5k/JrSRpJW3y//46q0g5c470qVNn9ZX0YZW/b7DFXABEBAAG0
JlNhbHRTdGFjayBCIFRlc3QgPGJ0ZXN0QHNhbHRzdGFjay5jb20+iNEEEwEIADsW
IQSN8J3lSrZ/YDHXHW8h5Z/XBbOHgQUCY9pxigIbAwULCQgHAgIiAgYVCgkICwIE
FgIDAQIeBwIXgAAKCRAh5Z/XBbOHgTCuA/9mYXAehM9avvq0Jm2dVbPidqxLstki
tgo3gCWmO1b5dXEBrhOZ8pZAktQ3WWoRrbwpNA7NAEIDF5l6uwMLLbGPQ5jreOdP
uzHpHONR1WWAzw2dj3v+5IcLDQ4sLi9VRgJqtMasTd8TpqMCVNcMArDBiy5hRF/e
XWEkf19Nb8qrdg==
=OEiT
-----END PGP PUBLIC KEY BLOCK-----"""


@pytest.fixture
def b_fp():
    return "8DF09DE54AB67F6031D71D6F21E59FD705B38781"


@pytest.fixture
def pub_ec():
    return """\
-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEACXBqu2ndMLUS/Z0X/fKUGAgRUfe
nYBie3erw/QNOYfQpgDIjNu+6xVxMLRRvSYGrQ2JREwUVXR0SR5pERAnoQ==
-----END PUBLIC KEY-----"""


@pytest.fixture
def pub_ec2():
    return """\
-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAErtBZ3qL5m97SzlSwOoxFzzG/1v5a
sLzOIrXykh4yO8tDn4h6JMOe+P0HuoUbENxk4+f/1D9hTEI88rj70bi7Ig==
-----END PUBLIC KEY-----"""


@pytest.fixture
def gpg_keys_present(gnupg, a_pubkey, b_pubkey, a_fp, b_fp):
    pubkeys = [a_pubkey, b_pubkey]
    fingerprints = [a_fp, b_fp]
    gnupg.import_keys("\n".join(pubkeys))
    present_keys = gnupg.list_keys()
    for fp in fingerprints:
        assert any(x["fingerprint"] == fp for x in present_keys)
    yield
    # cleanup is taken care of by gpghome and tmp_path


@pytest.fixture(scope="module", autouse=True)
def sig_files_present(web_root, modules):
    base = Path(RUNTIME_VARS.BASE_FILES)
    for file in [
        "custom.tar.gz",
        "custom.tar.gz.asc",
        "custom.tar.gz.sig",
        "custom.tar.gz.SHA256",
        "custom.tar.gz.SHA256.clearsign.asc",
        "custom.tar.gz.SHA256.asc",
        "custom.tar.gz.SHA256.sig",
    ]:
        modules.file.copy(base / file, Path(web_root) / file)


@pytest.mark.skipif(HAS_GNUPG is False, reason="Needs python-gnupg library")
@pytest.mark.usefixtures("gpg_keys_present")
def test_archive_extracted_signature(tmp_path, gpghome, free_port, modules, states):
    name = tmp_path / "test_archive_extracted_signature"
    source = f"http://localhost:{free_port}/custom.tar.gz"
    signature = source + ".asc"
    source_hash = source + ".SHA256"
    ret = states.archive.extracted(
        str(name),
        source=source,
        source_hash=source_hash,
        archive_format="tar",
        options="z",
        signature=signature,
        gnupghome=str(gpghome),
    )
    assert ret.result is True
    assert ret.changes
    assert name.exists()
    assert modules.file.find(str(name))


@pytest.mark.requires_salt_modules("asymmetric.verify")
@pytest.mark.parametrize("is_list", (False, True))
def test_archive_extracted_signature_sig_backend(
    tmp_path, free_port, modules, states, pub_ec, pub_ec2, is_list
):
    name = tmp_path / "test_archive_extracted_signature"
    source = f"http://localhost:{free_port}/custom.tar.gz"
    signature = source + ".sig"
    source_hash = source + ".SHA256"
    ret = states.archive.extracted(
        str(name),
        source=source,
        source_hash=source_hash,
        archive_format="tar",
        options="z",
        signature=[signature] if is_list else signature,
        signed_by_any=[pub_ec2, pub_ec] if is_list else pub_ec,
        sig_backend="asymmetric",
    )
    assert ret.result is True
    assert ret.changes
    assert name.exists()
    assert modules.file.find(str(name))


@pytest.mark.skipif(HAS_GNUPG is False, reason="Needs python-gnupg library")
@pytest.mark.usefixtures("gpg_keys_present")
def test_archive_extracted_signature_fail(
    tmp_path, gpghome, free_port, modules, states
):
    name = tmp_path / "test_archive_extracted_signature_fail"
    source = f"http://localhost:{free_port}/custom.tar.gz"
    signature = source + ".asc"
    source_hash = source + ".SHA256"
    # although there are valid signatures, this will be denied since the one below is required
    signed_by_all = ["DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF"]
    ret = states.archive.extracted(
        str(name),
        source=source,
        source_hash=source_hash,
        archive_format="tar",
        options="z",
        signature=signature,
        signed_by_all=signed_by_all,
        gnupghome=str(gpghome),
    )
    assert ret.result is False
    assert "signature could not be verified" in ret.comment
    assert not ret.changes
    assert not name.exists()
    assert not modules.cp.is_cached(source)
    assert not modules.cp.is_cached(signature)


@pytest.mark.requires_salt_modules("asymmetric.verify")
def test_archive_extracted_signature_sig_backend_fail(
    tmp_path, free_port, modules, states, pub_ec2
):
    name = tmp_path / "test_archive_extracted_signature"
    source = f"http://localhost:{free_port}/custom.tar.gz"
    signature = source + ".sig"
    source_hash = source + ".SHA256"
    ret = states.archive.extracted(
        str(name),
        source=source,
        source_hash=source_hash,
        archive_format="tar",
        options="z",
        signature=signature,
        signed_by_any=[pub_ec2],
        sig_backend="asymmetric",
    )
    assert ret.result is False
    assert "signature could not be verified" in ret.comment
    assert not ret.changes
    assert not name.exists()
    assert not modules.cp.is_cached(source)
    assert not modules.cp.is_cached(signature)


@pytest.mark.skipif(HAS_GNUPG is False, reason="Needs python-gnupg library")
@pytest.mark.usefixtures("gpg_keys_present")
@pytest.mark.parametrize("sig", [True, ".asc"])
def test_archive_extracted_source_hash_sig(
    tmp_path, sig, gpghome, free_port, modules, states
):
    name = tmp_path / "test_archive_extracted_source_hash_sig"
    source = f"http://localhost:{free_port}/custom.tar.gz"
    source_hash = source + ".SHA256"
    if sig is True:
        source_hash += ".clearsign.asc"
    else:
        sig = source_hash + sig
    ret = states.archive.extracted(
        str(name),
        source=source,
        source_hash=source_hash,
        archive_format="tar",
        options="z",
        source_hash_sig=sig,
        gnupghome=str(gpghome),
    )
    assert ret.result is True
    assert ret.changes
    assert name.exists()
    assert modules.file.find(str(name))


@pytest.mark.requires_salt_modules("asymmetric.verify")
@pytest.mark.parametrize("is_list", (False, True))
def test_archive_extracted_source_hash_sig_sig_backend(
    tmp_path, pub_ec, free_port, modules, states, is_list
):
    name = tmp_path / "test_archive_extracted_source_hash_sig"
    source = f"http://localhost:{free_port}/custom.tar.gz"
    source_hash = source + ".SHA256"
    sig = source_hash + ".sig"
    ret = states.archive.extracted(
        str(name),
        source=source,
        source_hash=source_hash,
        archive_format="tar",
        options="z",
        source_hash_sig=[sig] if is_list else sig,
        signed_by_any=[pub_ec2, pub_ec] if is_list else pub_ec,
        sig_backend="asymmetric",
    )
    assert ret.result is True
    assert ret.changes
    assert name.exists()
    assert modules.file.find(str(name))


@pytest.mark.skipif(HAS_GNUPG is False, reason="Needs python-gnupg library")
@pytest.mark.usefixtures("gpg_keys_present")
@pytest.mark.parametrize("sig", [True, ".asc"])
def test_archive_extracted_source_hash_sig_fail(
    tmp_path, sig, gpghome, free_port, modules, states
):
    name = tmp_path / "test_archive_extracted_source_hash_sig_fail"
    source = f"http://localhost:{free_port}/custom.tar.gz"
    source_hash = source + ".SHA256.clearsign.asc"
    signed_by_any = ["DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF"]
    ret = states.archive.extracted(
        str(name),
        source=source,
        source_hash=source_hash,
        archive_format="tar",
        options="z",
        source_hash_sig=True,
        signed_by_any=signed_by_any,
        gnupghome=str(gpghome),
    )
    assert ret.result is False
    assert "signature could not be verified" in ret.comment
    assert not ret.changes
    assert not name.exists()
    assert not modules.cp.is_cached(source)
    assert not modules.cp.is_cached(source_hash)


@pytest.mark.requires_salt_modules("asymmetric.verify")
def test_archive_extracted_source_hash_sig_sig_backend_fail(
    tmp_path, pub_ec2, free_port, modules, states
):
    name = tmp_path / "test_archive_extracted_source_hash_sig"
    source = f"http://localhost:{free_port}/custom.tar.gz"
    source_hash = source + ".SHA256"
    sig = source_hash + ".sig"
    ret = states.archive.extracted(
        str(name),
        source=source,
        source_hash=source_hash,
        archive_format="tar",
        options="z",
        source_hash_sig=[sig],
        signed_by_any=pub_ec2,
        sig_backend="asymmetric",
    )
    assert ret.result is False
    assert "signature could not be verified" in ret.comment
    assert not ret.changes
    assert not name.exists()
    assert not modules.cp.is_cached(source)
    assert not modules.cp.is_cached(source_hash)
