# -*- coding: utf-8 -*-
"""
tests.integration.setup.test_egg
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import os
import re
import shutil

# Import salt libs
import salt.utils.path
import salt.utils.platform
from salt.modules.virtualenv_mod import KNOWN_BINARY_NAMES
from tests.support.case import ModuleCase
from tests.support.helpers import VirtualEnv, destructiveTest

# Import Salt Testing libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import skipIf


@destructiveTest
@skipIf(
    salt.utils.path.which_bin(KNOWN_BINARY_NAMES) is None, "virtualenv not installed"
)
class EggSetupTest(ModuleCase):
    """
    Tests for building and installing egg packages
    """

    def setUp(self):
        # ensure we have a clean build dir
        self._clean_build()

    def _clean_build(self):
        """
        helper method to clean the build dir
        """
        dirs = [
            os.path.join(RUNTIME_VARS.CODE_DIR, "build"),
            os.path.join(RUNTIME_VARS.CODE_DIR, "salt.egg-info"),
            os.path.join(RUNTIME_VARS.CODE_DIR, "dist"),
        ]
        for _dir in dirs:
            if os.path.exists(_dir):
                shutil.rmtree(_dir)

    def test_egg_install(self):
        """
        test installing an egg package
        """
        # Let's create the testing virtualenv
        with VirtualEnv() as venv:
            ret = self.run_function(
                "cmd.run",
                [
                    "{0} setup.py install --prefix={1}".format(
                        venv.venv_python, venv.venv_dir
                    )
                ],
                cwd=RUNTIME_VARS.CODE_DIR,
            )
            self._clean_build()
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
            pip_ver = self.run_function("pip.list", bin_env=venv.venv_dir).get("salt")
            egg_ver = [
                x for x in egg.split("/")[-1:][0].split("-") if re.search(r"^\d.\d*", x)
            ][0]
            assert pip_ver == egg_ver.replace("_", "-")
