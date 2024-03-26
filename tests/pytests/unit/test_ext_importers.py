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
