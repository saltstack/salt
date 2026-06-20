import logging
import os
import subprocess
import sys

import pytest

import salt

log = logging.getLogger(__name__)


def test_tornado_import_override(tmp_path):
    """
    Ensure we are not using any non vendor'ed tornado
    """
    test_source = """
    from __future__ import absolute_import, print_function
    import salt
    import tornado
    print(tornado.__name__)
    """
    tornado_source = """
    foo = 'bar'
    """
    with pytest.helpers.temp_file(
        "test.py", directory=tmp_path, contents=test_source
    ) as test_source_path, pytest.helpers.temp_file(
        "tornado.py", directory=tmp_path, contents=tornado_source
    ):
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(sys.path)
        ret = subprocess.run(
            [sys.executable, str(test_source_path)],
            capture_output=True,
            env=env,
            shell=False,
            check=False,
            text=True,
        )
        assert ret.returncode == 0
        assert ret.stdout.strip() == "salt.ext.tornado"


def test_regression_56063():
    importer = salt.TornadoImporter()
    try:
        importer.find_module("tornado")
    except TypeError:
        assert False, "TornadoImporter raised type error when one argument passed"


def test_regression_65360_tornado_netutil_imports_without_backports(tmp_path):
    """
    Regression test for #65360.

    On Python 3.12 ``ssl.match_hostname`` was removed, which made the
    vendored ``salt.ext.tornado.netutil`` module fall through to
    ``import backports.ssl_match_hostname``. The ``backports`` package
    is not part of the standard library and is not installed by default
    on Fedora 39+/Ubuntu 24.04 (both ship Python 3.12), which broke any
    Salt master-initiated job on those platforms because nearly every
    Salt transport import path eventually imports ``netutil``.

    Ensure ``salt.ext.tornado.netutil`` imports successfully without
    requiring the ``backports`` package, and that the public attributes
    consumed by the rest of vendored tornado (``ssl_match_hostname`` and
    ``SSLCertificateError``) are populated.
    """
    test_source = """
import sys

# Force ImportError for the optional backports package so we exercise
# the standalone match_hostname path even if backports happens to be
# installed in the test environment.
class _BlockBackports:
    def find_module(self, name, path=None):
        if name == "backports" or name.startswith("backports."):
            return self
        return None

    def load_module(self, name):
        raise ImportError("backports blocked for regression test")

sys.meta_path.insert(0, _BlockBackports())

import salt.ext.tornado.netutil as netutil

assert netutil.ssl_match_hostname is not None, "ssl_match_hostname unset"
assert netutil.SSLCertificateError is not None, "SSLCertificateError unset"
print("OK")
"""
    with pytest.helpers.temp_file(
        "test_65360.py", directory=tmp_path, contents=test_source
    ) as test_source_path:
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(sys.path)
        ret = subprocess.run(
            [sys.executable, str(test_source_path)],
            capture_output=True,
            env=env,
            shell=False,
            check=False,
            text=True,
        )
        assert (
            ret.returncode == 0
        ), f"netutil import failed:\nstdout: {ret.stdout}\nstderr: {ret.stderr}"
        assert ret.stdout.strip().endswith("OK")
