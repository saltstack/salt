import os
import tempfile

import pytest
import salt.utils.path
from salt.modules.virtualenv_mod import KNOWN_BINARY_NAMES
from tests.support.case import ModuleCase
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import skipIf


@skipIf(
    salt.utils.path.which_bin(KNOWN_BINARY_NAMES) is None, "virtualenv not installed"
)
class VirtualenvModuleTest(ModuleCase):
    """
    Validate the virtualenv module
    """

    def setUp(self):
        super().setUp()
        self.venv_test_dir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        self.venv_dir = os.path.join(self.venv_test_dir, "venv")

    @pytest.mark.slow_test
    def test_create_defaults(self):
        """
        virtualenv.managed
        """
        self.run_function("virtualenv.create", [self.venv_dir])
        pip_file = os.path.join(self.venv_dir, "bin", "pip")
        self.assertTrue(os.path.exists(pip_file))

    @pytest.mark.slow_test
    def test_site_packages(self):
        pip_bin = os.path.join(self.venv_dir, "bin", "pip")
        self.run_function(
            "virtualenv.create", [self.venv_dir], system_site_packages=True
        )
        with_site = self.run_function("pip.freeze", bin_env=pip_bin)
        self.run_function("file.remove", [self.venv_dir])
        self.run_function("virtualenv.create", [self.venv_dir])
        without_site = self.run_function("pip.freeze", bin_env=pip_bin)
        self.assertFalse(with_site == without_site)

    @pytest.mark.slow_test
    def test_clear(self):
        pip_bin = os.path.join(self.venv_dir, "bin", "pip")
        self.run_function("virtualenv.create", [self.venv_dir])
        self.run_function("pip.install", [], pkgs="pep8", bin_env=pip_bin)
        self.run_function("virtualenv.create", [self.venv_dir], clear=True)
        packages = self.run_function("pip.list", prefix="pep8", bin_env=pip_bin)
        self.assertFalse("pep8" in packages)

    def test_virtualenv_ver(self):
        ret = self.run_function("virtualenv.virtualenv_ver", [self.venv_dir])
        assert isinstance(ret, list)
        assert all([isinstance(x, int) for x in ret])

    def tearDown(self):
        self.run_function("file.remove", [self.venv_test_dir])
