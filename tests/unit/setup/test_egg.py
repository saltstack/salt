# -*- coding: utf-8 -*-
"""
tests.integration.setup.test_egg
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""
from __future__ import absolute_import, print_function, unicode_literals

import json
import os
import re

import salt.utils.path
import salt.utils.platform
from salt.modules.virtualenv_mod import KNOWN_BINARY_NAMES
from tests.support.helpers import VirtualEnv, slowTest, with_tempdir
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase, skipIf


@skipIf(
    salt.utils.path.which_bin(KNOWN_BINARY_NAMES) is None, "virtualenv not installed"
)
class EggSetupTest(TestCase):
    """
    Tests for building and installing egg packages
    """

    @slowTest
    @with_tempdir()
    def test_egg_install(self, tempdir):
        """
        test installing an egg package
        """
        # Let's create the testing virtualenv
        with VirtualEnv() as venv:
            venv.run(venv.venv_python, "setup.py", "clean", cwd=RUNTIME_VARS.CODE_DIR)

            # Setuptools installs pre-release packages if we don't pin to an exact version
            # Let's download and install requirements before, running salt's install test
            venv.run(
                venv.venv_python,
                "-m",
                "pip",
                "download",
                "--dest",
                tempdir,
                RUNTIME_VARS.CODE_DIR,
            )
            packages = []
            for fname in os.listdir(tempdir):
                packages.append(os.path.join(tempdir, fname))
            venv.install(*packages)

            venv.run(
                venv.venv_python,
                "setup.py",
                "install",
                "--prefix",
                venv.venv_dir,
                cwd=RUNTIME_VARS.CODE_DIR,
            )
            venv.run(venv.venv_python, "setup.py", "clean", cwd=RUNTIME_VARS.CODE_DIR)
            lib_dir = os.path.join(venv.venv_dir, "lib")
            for _dir in os.listdir(lib_dir):
                site_pkg = os.path.join(lib_dir, _dir, "site-packages")
                for _file in os.listdir(site_pkg):
                    if _file.startswith("salt-"):
                        egg = os.path.join(venv.venv_dir, _file)
                        assert os.path.exists(
                            os.path.join(site_pkg, _file, "salt", "_version.py")
                        )
                        break

            # Let's ensure the version is correct
            cmd = venv.run(venv.venv_python, "-m", "pip", "list", "--format", "json")
            for details in json.loads(cmd.stdout):
                if details["name"] != "salt":
                    continue
                pip_ver = details["version"]
                break
            else:
                self.fail("Salt was not found installed")
            egg_ver = [
                x for x in egg.split("/")[-1:][0].split("-") if re.search(r"^\d.\d*", x)
            ][0]
            assert pip_ver == egg_ver.replace("_", "-")
