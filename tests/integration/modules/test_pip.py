import os
import pprint
import re
import shutil
import tempfile

import pytest

import salt.utils.files
import salt.utils.path
import salt.utils.platform
from salt.modules.virtualenv_mod import KNOWN_BINARY_NAMES
from tests.support.case import ModuleCase
from tests.support.helpers import VirtualEnv, patched_environ
from tests.support.runtests import RUNTIME_VARS


@pytest.mark.skip_if_binaries_missing(*KNOWN_BINARY_NAMES, check_all=False)
@pytest.mark.windows_whitelisted
class PipModuleTest(ModuleCase):
    def setUp(self):
        super().setUp()
        self.venv_test_dir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        # Remove the venv test directory
        self.addCleanup(shutil.rmtree, self.venv_test_dir, ignore_errors=True)
        self.venv_dir = os.path.join(self.venv_test_dir, "venv")
        self.patched_environ = patched_environ(
            PIP_SOURCE_DIR="",
            PIP_BUILD_DIR="",
            __cleanup__=[k for k in os.environ if k.startswith("PIP_")],
        )
        self.patched_environ.__enter__()
        self.addCleanup(self.patched_environ.__exit__)

    def _check_download_error(self, ret):
        """
        Checks to see if a download error looks transitory
        """
        return any(w in ret for w in ["URLError", "Download error"])

    def pip_successful_install(
        self,
        target,
        expect=(
            "irc3-plugins-test",
            "pep8",
        ),
    ):
        """
        isolate regex for extracting `successful install` message from pip
        """

        expect = set(expect)
        expect_str = "|".join(expect)

        success = re.search(
            r"^.*Successfully installed\s([^\n]+)(?:Clean.*)?", target, re.M | re.S
        )

        success_for = (
            re.findall(r"({})(?:-(?:[\d\.-]))?".format(expect_str), success.groups()[0])
            if success
            else []
        )

        return expect.issubset(set(success_for))

    @pytest.mark.slow_test
    def test_issue_2087_missing_pip(self):
        # Let's create the testing virtualenv
        with VirtualEnv(self.venv_dir):

            # Let's remove the pip binary
            pip_bin = os.path.join(self.venv_dir, "bin", "pip")
            site_dir = self.run_function(
                "virtualenv.get_distribution_path", [self.venv_dir, "pip"]
            )
            if salt.utils.platform.is_windows():
                pip_bin = os.path.join(self.venv_dir, "Scripts", "pip.exe")
                site_dir = os.path.join(self.venv_dir, "lib", "site-packages")
            if not os.path.isfile(pip_bin):
                self.skipTest("Failed to find the pip binary to the test virtualenv")
            os.remove(pip_bin)

            # Also remove the pip dir from site-packages
            # This is needed now that we're using python -m pip instead of the
            # pip binary directly. python -m pip will still work even if the
            # pip binary is missing
            shutil.rmtree(os.path.join(site_dir, "pip"))

            # Let's run a pip depending functions
            for func in ("pip.freeze", "pip.list"):
                ret = self.run_function(func, bin_env=self.venv_dir)
                assert (
                    "Command required for '{}' not found: Could not find a `pip` binary".format(
                        func
                    )
                    in ret
                )

    @pytest.mark.slow_test
    def test_requirements_as_list_of_chains__cwd_set__absolute_file_path(self):
        with VirtualEnv(self.venv_dir):

            # Create a requirements file that depends on another one.

            req1_filename = os.path.join(self.venv_dir, "requirements1.txt")
            req1b_filename = os.path.join(self.venv_dir, "requirements1b.txt")
            req2_filename = os.path.join(self.venv_dir, "requirements2.txt")
            req2b_filename = os.path.join(self.venv_dir, "requirements2b.txt")

            with salt.utils.files.fopen(req1_filename, "w") as f:
                f.write("-r requirements1b.txt\n")
            with salt.utils.files.fopen(req1b_filename, "w") as f:
                f.write("irc3-plugins-test\n")
            with salt.utils.files.fopen(req2_filename, "w") as f:
                f.write("-r requirements2b.txt\n")
            with salt.utils.files.fopen(req2b_filename, "w") as f:
                f.write("pep8\n")

            requirements_list = [req1_filename, req2_filename]

            ret = self.run_function(
                "pip.install",
                requirements=requirements_list,
                bin_env=self.venv_dir,
                cwd=self.venv_dir,
            )
            if not isinstance(ret, dict):
                self.fail(
                    "The 'pip.install' command did not return the excepted dictionary."
                    " Output:\n{}".format(ret)
                )

            try:
                assert ret["retcode"] == 0
                found = self.pip_successful_install(ret["stdout"])
                assert found
            except KeyError as exc:
                self.fail(
                    "The returned dictionary is missing an expected key. Error: '{}'."
                    " Dictionary: {}".format(exc, pprint.pformat(ret))
                )

    @pytest.mark.slow_test
    def test_requirements_as_list_of_chains__cwd_not_set__absolute_file_path(self):
        with VirtualEnv(self.venv_dir):

            # Create a requirements file that depends on another one.

            req1_filename = os.path.join(self.venv_dir, "requirements1.txt")
            req1b_filename = os.path.join(self.venv_dir, "requirements1b.txt")
            req2_filename = os.path.join(self.venv_dir, "requirements2.txt")
            req2b_filename = os.path.join(self.venv_dir, "requirements2b.txt")

            with salt.utils.files.fopen(req1_filename, "w") as f:
                f.write("-r requirements1b.txt\n")
            with salt.utils.files.fopen(req1b_filename, "w") as f:
                f.write("irc3-plugins-test\n")
            with salt.utils.files.fopen(req2_filename, "w") as f:
                f.write("-r requirements2b.txt\n")
            with salt.utils.files.fopen(req2b_filename, "w") as f:
                f.write("pep8\n")

            requirements_list = [req1_filename, req2_filename]

            ret = self.run_function(
                "pip.install", requirements=requirements_list, bin_env=self.venv_dir
            )

            if not isinstance(ret, dict):
                self.fail(
                    "The 'pip.install' command did not return the excepted dictionary."
                    " Output:\n{}".format(ret)
                )

            try:
                assert ret["retcode"] == 0
                found = self.pip_successful_install(ret["stdout"])
                assert found
            except KeyError as exc:
                self.fail(
                    "The returned dictionary is missing an expected key. Error: '{}'."
                    " Dictionary: {}".format(exc, pprint.pformat(ret))
                )

    @pytest.mark.slow_test
    def test_requirements_as_list__absolute_file_path(self):
        with VirtualEnv(self.venv_dir):

            req1_filename = os.path.join(self.venv_dir, "requirements.txt")
            req2_filename = os.path.join(self.venv_dir, "requirements2.txt")

            with salt.utils.files.fopen(req1_filename, "w") as f:
                f.write("irc3-plugins-test\n")
            with salt.utils.files.fopen(req2_filename, "w") as f:
                f.write("pep8\n")

            requirements_list = [req1_filename, req2_filename]

            ret = self.run_function(
                "pip.install", requirements=requirements_list, bin_env=self.venv_dir
            )

            if not isinstance(ret, dict):
                self.fail(
                    "The 'pip.install' command did not return the excepted dictionary."
                    " Output:\n{}".format(ret)
                )

            try:
                assert ret["retcode"] == 0
                found = self.pip_successful_install(ret["stdout"])
                assert found
            except KeyError as exc:
                self.fail(
                    "The returned dictionary is missing an expected key. Error: '{}'."
                    " Dictionary: {}".format(exc, pprint.pformat(ret))
                )

    @pytest.mark.slow_test
    def test_requirements_as_list__non_absolute_file_path(self):
        with VirtualEnv(self.venv_dir):

            # Create a requirements file that depends on another one.

            req1_filename = "requirements.txt"
            req2_filename = "requirements2.txt"
            req_cwd = self.venv_dir

            req1_filepath = os.path.join(req_cwd, req1_filename)
            req2_filepath = os.path.join(req_cwd, req2_filename)

            with salt.utils.files.fopen(req1_filepath, "w") as f:
                f.write("irc3-plugins-test\n")
            with salt.utils.files.fopen(req2_filepath, "w") as f:
                f.write("pep8\n")

            requirements_list = [req1_filename, req2_filename]

            ret = self.run_function(
                "pip.install",
                requirements=requirements_list,
                bin_env=self.venv_dir,
                cwd=req_cwd,
            )

            if not isinstance(ret, dict):
                self.fail(
                    "The 'pip.install' command did not return the excepted dictionary."
                    " Output:\n{}".format(ret)
                )

            try:
                assert ret["retcode"] == 0
                found = self.pip_successful_install(ret["stdout"])
                assert found
            except KeyError as exc:
                self.fail(
                    "The returned dictionary is missing an expected key. Error: '{}'."
                    " Dictionary: {}".format(exc, pprint.pformat(ret))
                )

    @pytest.mark.slow_test
    def test_chained_requirements__absolute_file_path(self):
        with VirtualEnv(self.venv_dir):

            # Create a requirements file that depends on another one.

            req1_filename = os.path.join(self.venv_dir, "requirements.txt")
            req2_filename = os.path.join(self.venv_dir, "requirements2.txt")

            with salt.utils.files.fopen(req1_filename, "w") as f:
                f.write("-r requirements2.txt")
            with salt.utils.files.fopen(req2_filename, "w") as f:
                f.write("pep8")

            ret = self.run_function(
                "pip.install", requirements=req1_filename, bin_env=self.venv_dir
            )
            if not isinstance(ret, dict):
                self.fail(
                    "The 'pip.install' command did not return the excepted dictionary."
                    " Output:\n{}".format(ret)
                )

            try:
                assert ret["retcode"] == 0
                assert "installed pep8" in ret["stdout"]
            except KeyError as exc:
                self.fail(
                    "The returned dictionary is missing an expected key. Error: '{}'."
                    " Dictionary: {}".format(exc, pprint.pformat(ret))
                )

    @pytest.mark.slow_test
    def test_chained_requirements__non_absolute_file_path(self):
        with VirtualEnv(self.venv_dir):

            # Create a requirements file that depends on another one.
            req_basepath = self.venv_dir

            req1_filename = "requirements.txt"
            req2_filename = "requirements2.txt"

            req1_file = os.path.join(self.venv_dir, req1_filename)
            req2_file = os.path.join(self.venv_dir, req2_filename)

            with salt.utils.files.fopen(req1_file, "w") as f:
                f.write("-r requirements2.txt")
            with salt.utils.files.fopen(req2_file, "w") as f:
                f.write("pep8")

            ret = self.run_function(
                "pip.install",
                requirements=req1_filename,
                cwd=req_basepath,
                bin_env=self.venv_dir,
            )
            if not isinstance(ret, dict):
                self.fail(
                    "The 'pip.install' command did not return the excepted dictionary."
                    " Output:\n{}".format(ret)
                )

            try:
                assert ret["retcode"] == 0
                assert "installed pep8" in ret["stdout"]
            except KeyError as exc:
                self.fail(
                    "The returned dictionary is missing an expected key. Error: '{}'."
                    " Dictionary: {}".format(exc, pprint.pformat(ret))
                )

    @pytest.mark.slow_test
    def test_issue_4805_nested_requirements(self):
        with VirtualEnv(self.venv_dir):

            # Create a requirements file that depends on another one.
            req1_filename = os.path.join(self.venv_dir, "requirements.txt")
            req2_filename = os.path.join(self.venv_dir, "requirements2.txt")
            with salt.utils.files.fopen(req1_filename, "w") as f:
                f.write("-r requirements2.txt")
            with salt.utils.files.fopen(req2_filename, "w") as f:
                f.write("pep8")

            ret = self.run_function(
                "pip.install",
                requirements=req1_filename,
                bin_env=self.venv_dir,
                timeout=300,
            )

            if not isinstance(ret, dict):
                self.fail(
                    "The 'pip.install' command did not return the excepted dictionary."
                    " Output:\n{}".format(ret)
                )

            try:
                if self._check_download_error(ret["stdout"]):
                    self.skipTest("Test skipped due to pip download error")
                assert ret["retcode"] == 0
                assert "installed pep8" in ret["stdout"]
            except KeyError as exc:
                self.fail(
                    "The returned dictionary is missing an expected key. Error: '{}'."
                    " Dictionary: {}".format(exc, pprint.pformat(ret))
                )

    @pytest.mark.slow_test
    def test_pip_uninstall(self):
        # Let's create the testing virtualenv
        with VirtualEnv(self.venv_dir):
            ret = self.run_function("pip.install", ["pep8"], bin_env=self.venv_dir)

            if not isinstance(ret, dict):
                self.fail(
                    "The 'pip.install' command did not return the excepted dictionary."
                    " Output:\n{}".format(ret)
                )

            try:
                if self._check_download_error(ret["stdout"]):
                    self.skipTest("Test skipped due to pip download error")
                assert ret["retcode"] == 0
                assert "installed pep8" in ret["stdout"]
            except KeyError as exc:
                self.fail(
                    "The returned dictionary is missing an expected key. Error: '{}'."
                    " Dictionary: {}".format(exc, pprint.pformat(ret))
                )
            ret = self.run_function("pip.uninstall", ["pep8"], bin_env=self.venv_dir)

            if not isinstance(ret, dict):
                self.fail(
                    "The 'pip.uninstall' command did not return the excepted dictionary."
                    " Output:\n{}".format(ret)
                )

            try:
                assert ret["retcode"] == 0
                assert "uninstalled pep8" in ret["stdout"]
            except KeyError as exc:
                self.fail(
                    "The returned dictionary is missing an expected key. Error: '{}'."
                    " Dictionary: {}".format(exc, pprint.pformat(ret))
                )

    @pytest.mark.slow_test
    def test_pip_install_upgrade(self):
        # Create the testing virtualenv
        with VirtualEnv(self.venv_dir):
            ret = self.run_function(
                "pip.install", ["pep8==1.3.4"], bin_env=self.venv_dir
            )

            if not isinstance(ret, dict):
                self.fail(
                    "The 'pip.install' command did not return the excepted dictionary."
                    " Output:\n{}".format(ret)
                )

            try:
                if self._check_download_error(ret["stdout"]):
                    self.skipTest("Test skipped due to pip download error")
                assert ret["retcode"] == 0
                assert "installed pep8" in ret["stdout"]
            except KeyError as exc:
                self.fail(
                    "The returned dictionary is missing an expected key. Error: '{}'."
                    " Dictionary: {}".format(exc, pprint.pformat(ret))
                )

            ret = self.run_function(
                "pip.install", ["pep8"], bin_env=self.venv_dir, upgrade=True
            )

            if not isinstance(ret, dict):
                self.fail(
                    "The 'pip.install' command did not return the excepted dictionary."
                    " Output:\n{}".format(ret)
                )

            try:
                if self._check_download_error(ret["stdout"]):
                    self.skipTest("Test skipped due to pip download error")
                assert ret["retcode"] == 0
                assert "installed pep8" in ret["stdout"]
            except KeyError as exc:
                self.fail(
                    "The returned dictionary is missing an expected key. Error: '{}'."
                    " Dictionary: {}".format(exc, pprint.pformat(ret))
                )

            ret = self.run_function("pip.uninstall", ["pep8"], bin_env=self.venv_dir)

            if not isinstance(ret, dict):
                self.fail(
                    "The 'pip.uninstall' command did not return the excepted dictionary."
                    " Output:\n{}".format(ret)
                )

            try:
                assert ret["retcode"] == 0
                assert "uninstalled pep8" in ret["stdout"]
            except KeyError as exc:
                self.fail(
                    "The returned dictionary is missing an expected key. Error: '{}'."
                    " Dictionary: {}".format(exc, pprint.pformat(ret))
                )

    @pytest.mark.slow_test
    def test_pip_install_multiple_editables(self):
        editables = [
            "git+https://github.com/saltstack/istr.git@v1.0.1#egg=iStr",
            "git+https://github.com/saltstack/salt-testing.git#egg=SaltTesting",
        ]

        # Create the testing virtualenv
        with VirtualEnv(self.venv_dir):
            ret = self.run_function(
                "pip.install",
                [],
                editable="{}".format(",".join(editables)),
                bin_env=self.venv_dir,
            )

            if not isinstance(ret, dict):
                self.fail(
                    "The 'pip.install' command did not return the excepted dictionary."
                    " Output:\n{}".format(ret)
                )

            try:
                if self._check_download_error(ret["stdout"]):
                    self.skipTest("Test skipped due to pip download error")
                assert ret["retcode"] == 0
                for package in ("iStr", "SaltTesting"):
                    match = re.search(
                        r"(?:.*)(Successfully installed)(?:.*)({})(?:.*)".format(
                            package
                        ),
                        ret["stdout"],
                    )
                    assert match is not None
            except KeyError as exc:
                self.fail(
                    "The returned dictionary is missing an expected key. Error: '{}'."
                    " Dictionary: {}".format(exc, pprint.pformat(ret))
                )

    @pytest.mark.slow_test
    def test_pip_install_multiple_editables_and_pkgs(self):
        editables = [
            "git+https://github.com/saltstack/istr.git@v1.0.1#egg=iStr",
            "git+https://github.com/saltstack/salt-testing.git#egg=SaltTesting",
        ]

        # Create the testing virtualenv
        with VirtualEnv(self.venv_dir):
            ret = self.run_function(
                "pip.install",
                ["pep8"],
                editable="{}".format(",".join(editables)),
                bin_env=self.venv_dir,
            )

            if not isinstance(ret, dict):
                self.fail(
                    "The 'pip.install' command did not return the excepted dictionary."
                    " Output:\n{}".format(ret)
                )

            try:
                if self._check_download_error(ret["stdout"]):
                    self.skipTest("Test skipped due to pip download error")
                assert ret["retcode"] == 0
                for package in ("iStr", "SaltTesting", "pep8"):
                    match = re.search(
                        r"(?:.*)(Successfully installed)(?:.*)({})(?:.*)".format(
                            package
                        ),
                        ret["stdout"],
                    )
                    assert match is not None
            except KeyError as exc:
                self.fail(
                    "The returned dictionary is missing an expected key. Error: '{}'."
                    " Dictionary: {}".format(exc, pprint.pformat(ret))
                )

    @pytest.mark.skipif(
        shutil.which("/bin/pip3") is None, reason="Could not find /bin/pip3"
    )
    @pytest.mark.skip_on_windows(reason="test specific for linux usage of /bin/python")
    @pytest.mark.skip_initial_gh_actions_failure(
        reason="This was skipped on older golden images and is failing on newer."
    )
    def test_system_pip3(self):

        self.run_function(
            "pip.install", pkgs=["lazyimport==0.0.1"], bin_env="/bin/pip3"
        )
        ret1 = self.run_function("cmd.run_all", ["/bin/pip3 freeze | grep lazyimport"])
        assert "lazyimport==0.0.1" in ret1["stdout"]

        self.run_function("pip.uninstall", pkgs=["lazyimport"], bin_env="/bin/pip3")
        ret2 = self.run_function("cmd.run_all", ["/bin/pip3 freeze | grep lazyimport"])
        assert ret2["stdout"] == ""
