# -*- coding: utf-8 -*-
# Import Python libs
from __future__ import absolute_import, unicode_literals

import logging
import os
import subprocess
import sys
import tempfile

# Import Salt libs
import salt
import salt.ext.six
import salt.modules.cmdmod
import salt.utils.files
import salt.utils.platform
import tests.support.helpers
from tests.support.runtests import RUNTIME_VARS

# Import Salt Testing libs
from tests.support.unit import TestCase, skipIf

log = logging.getLogger(__name__)


@skipIf(not salt.utils.path.which("bash"), "Bash needed for this test")
class VendorTornadoTest(TestCase):
    """
    Ensure we are not using any non vendor'ed tornado
    """

    def test_import_override(self):
        tmp = tempfile.mkdtemp()
        test_source = tests.support.helpers.dedent(
            """
        from __future__ import absolute_import, print_function
        import salt
        import tornado
        print(tornado.__name__)
        """
        )
        test_source_path = os.path.join(tmp, "test.py")
        tornado_source = tests.support.helpers.dedent(
            """
        foo = 'bar'
        """
        )
        tornado_source_path = os.path.join(tmp, "tornado.py")
        with salt.utils.files.fopen(test_source_path, "w") as fp:
            fp.write(test_source)
        with salt.utils.files.fopen(tornado_source_path, "w") as fp:
            fp.write(tornado_source)
        # Preserve the virtual environment
        env = os.environ.copy()
        if salt.utils.platform.is_windows():
            if salt.ext.six.PY2:
                env[b"PYTHONPATH"] = b";".join([a.encode() for a in sys.path])
            else:
                env["PYTHONPATH"] = ";".join(sys.path)
        else:
            env["PYTHONPATH"] = ":".join(sys.path)
        p = subprocess.Popen(
            [sys.executable, test_source_path],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            env=env,
        )
        p.wait()
        pout = p.stdout.read().strip().decode()
        assert pout == "salt.ext.tornado", pout

    def test_vendored_tornado_import(self):
        grep_call = salt.modules.cmdmod.run_stdout(
            cmd="bash -c 'grep -r \"import tornado\" ./salt/*'",
            cwd=RUNTIME_VARS.CODE_DIR,
            ignore_retcode=True,
        ).split("\n")
        valid_lines = []
        for line in grep_call:
            if line == "":
                continue
            # Skip salt/ext/tornado/.. since there are a bunch of imports like
            # this in docstrings.
            if "salt/ext/tornado/" in line:
                continue
            log.error("Test found bad line: %s", line)
            valid_lines.append(line)
        assert valid_lines == [], len(valid_lines)

    def test_vendored_tornado_import_from(self):
        grep_call = salt.modules.cmdmod.run_stdout(
            cmd="bash -c 'grep -r \"from tornado\" ./salt/*'",
            cwd=RUNTIME_VARS.CODE_DIR,
            ignore_retcode=True,
        ).split("\n")
        valid_lines = []
        for line in grep_call:
            if line == "":
                continue
            log.error("Test found bad line: %s", line)
            valid_lines.append(line)
        assert valid_lines == [], len(valid_lines)

    def test_regression_56063(self):
        importer = salt.TornadoImporter()
        try:
            importer.find_module("tornado")
        except TypeError:
            assert False, "TornadoImporter raised type error when one argument passed"
