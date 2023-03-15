import logging
import os
import subprocess
import sys

import pytest
import six  # pylint: disable=blacklisted-external-import,3rd-party-module-not-gated

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
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            env=env,
            shell=False,
            check=False,
            universal_newlines=True,
        )
        assert ret.returncode == 0
        assert ret.stdout.strip() == "salt.ext.tornado"


@pytest.mark.parametrize(
    "six_import_line,six_print_line",
    (
        ("import salt.ext.six", "print(salt.ext.six.__name__, salt.ext.six.__file__)"),
        ("import salt.ext.six as six", "print(six.__name__, six.__file__)"),
        ("from salt.ext import six", "print(six.__name__, six.__file__)"),
        ("import six", "print(six.__name__, six.__file__)"),
    ),
)
def test_salt_ext_six_import_override(tmp_path, six_import_line, six_print_line):
    """
    Ensure we are not using, the now non existent, vendor'ed six
    """
    test_source = """
    import salt
    {}
    {}
    """.format(
        six_import_line, six_print_line
    )
    with pytest.helpers.temp_file(
        "test.py", directory=tmp_path, contents=test_source
    ) as test_source_path:
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(sys.path)
        ret = subprocess.run(
            [sys.executable, str(test_source_path)],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            env=env,
            shell=False,
            check=False,
            universal_newlines=True,
        )
        assert ret.returncode == 0
        assert ret.stdout.strip() == "six {}".format(six.__file__)


def test_regression_56063():
    importer = salt.TornadoImporter()
    try:
        importer.find_module("tornado")
    except TypeError:
        assert False, "TornadoImporter raised type error when one argument passed"
