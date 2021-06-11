import logging
import os
import subprocess
import sys
import tempfile

import salt
import salt.modules.cmdmod
import salt.utils.files
import salt.utils.platform
import tests.support.helpers
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


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
        env["PYTHONPATH"] = os.pathsep.join(sys.path)
        p = subprocess.Popen(
            [sys.executable, test_source_path],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            env=env,
        )
        p.wait()
        pout = p.stdout.read().strip().decode()
        assert pout == "salt.ext.tornado", pout

    def test_regression_56063(self):
        importer = salt.TornadoImporter()
        try:
            importer.find_module("tornado")
        except TypeError:
            assert False, "TornadoImporter raised type error when one argument passed"
