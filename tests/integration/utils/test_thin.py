# -*- coding: utf-8 -*-
from __future__ import absolute_import

import os
import subprocess
import sys
import tarfile
import tempfile

import salt.utils.files
import salt.utils.thin
from tests.support.unit import TestCase

try:
    import virtualenv

    HAS_VENV = True
except ImportError:
    HAS_VENV = False


class TestThinDir(TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        salt.utils.files.rm_rf(self.tmpdir)

    def test_thin_dir(self):
        """
        Test the thin dir to make sure salt-call can run

        Run salt call via a python in a new virtual environment to ensure
        salt-call has all dependencies needed.
        """
        venv_dir = os.path.join(self.tmpdir, "venv")
        virtualenv.create_environment(venv_dir)
        salt.utils.thin.gen_thin(self.tmpdir)
        thin_dir = os.path.join(self.tmpdir, "thin")
        thin_archive = os.path.join(thin_dir, "thin.tgz")
        tar = tarfile.open(thin_archive)
        tar.extractall(thin_dir)
        tar.close()
        bins = "bin"
        if sys.platform == "win32":
            bins = "Scripts"
        cmd = [
            os.path.join(venv_dir, bins, "python"),
            os.path.join(thin_dir, "salt-call"),
            "--version",
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()
        proc.wait()
        assert proc.returncode == 0, (stdout, stderr, proc.returncode)
