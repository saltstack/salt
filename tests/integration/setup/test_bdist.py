# -*- coding: utf-8 -*-
"""
tests.integration.setup.test_bdist
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import os
import re

# Import salt libs
import salt.utils.path
import salt.utils.platform
from salt.modules.virtualenv_mod import KNOWN_BINARY_NAMES
from tests.support.case import ModuleCase
from tests.support.helpers import VirtualEnv, skip_if_not_root

# Import Salt Testing libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import skipIf


@skip_if_not_root
@skipIf(
    salt.utils.path.which_bin(KNOWN_BINARY_NAMES) is None, "virtualenv not installed"
)
class BdistSetupTest(ModuleCase):
    """
    Tests for building and installing bdist_wheel packages
    """

    def test_wheel_build(self):
        """
        test building a bdist_wheel package
        """
        # Let's create the testing virtualenv
        with VirtualEnv() as venv:
            ret = self.run_function(
                "cmd.run",
                [
                    "{0} setup.py bdist_wheel --dist-dir={1}".format(
                        venv.venv_python, venv.venv_dir
                    )
                ],
                cwd=RUNTIME_VARS.CODE_DIR,
            )

            for _file in os.listdir(venv.venv_dir):
                if _file.endswith("whl"):
                    whl = os.path.join(venv.venv_dir, _file)
                    break

            ret = self.run_function("pip.install", pkgs=whl, bin_env=venv.venv_dir)

            # Let's ensure the version is correct
            pip_ver = self.run_function("pip.list", bin_env=venv.venv_dir).get("salt")
            whl_ver = [
                x for x in whl.split("/")[-1:][0].split("-") if re.search(r"^\d.\d*", x)
            ][0]
            assert pip_ver == whl_ver.replace("_", "-")
