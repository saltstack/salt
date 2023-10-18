import os
import pprint
import re
import shutil

import pytest

import salt.utils.files
import salt.utils.path
import salt.utils.platform
from salt.modules.virtualenv_mod import KNOWN_BINARY_NAMES
from tests.support.helpers import VirtualEnv, patched_environ

pytestmark = [
    pytest.mark.skip_if_binaries_missing(*KNOWN_BINARY_NAMES, check_all=False),
    pytest.mark.windows_whitelisted,
]


@pytest.fixture(autouse=True)
def patch_environment():
    with patched_environ(
        PIP_SOURCE_DIR="",
        PIP_BUILD_DIR="",
        __cleanup__=[k for k in os.environ if k.startswith("PIP_")],
    ):
        yield


@pytest.fixture
def venv_dir(tmp_path):
    return str(tmp_path / "venv_dir")


def _check_download_error(ret):
    """
    Checks to see if a download error looks transitory
    """
    return any(w in ret for w in ["URLError", "Download error"])


def _pip_successful_install(
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
def test_issue_2087_missing_pip(venv_dir, salt_cli, salt_minion):
    # Let's create the testing virtualenv
    with VirtualEnv(venv_dir):

        # Let's remove the pip binary
        pip_bin = os.path.join(venv_dir, "bin", "pip")
        site_dir = salt_cli.run(
            "virtualenv.get_distribution_path",
            venv_dir,
            "pip",
            minion_tgt=salt_minion.id,
        ).data
        if salt.utils.platform.is_windows():
            pip_bin = os.path.join(venv_dir, "Scripts", "pip.exe")
            site_dir = os.path.join(venv_dir, "lib", "site-packages")
        if not os.path.isfile(pip_bin):
            pytest.skip("Failed to find the pip binary to the test virtualenv")
        os.remove(pip_bin)

        # Also remove the pip dir from site-packages
        # This is needed now that we're using python -m pip instead of the
        # pip binary directly. python -m pip will still work even if the
        # pip binary is missing
        shutil.rmtree(os.path.join(site_dir, "pip"))

        # Let's run a pip depending functions
        for func in ("pip.freeze", "pip.list"):
            ret = salt_cli.run(func, bin_env=venv_dir, minion_tgt=salt_minion.id).data
            assert (
                "Command required for '{}' not found: Could not find a `pip` binary".format(
                    func
                )
                in ret
            )


@pytest.mark.slow_test
def test_requirements_as_list_of_chains__cwd_set__absolute_file_path(
    venv_dir, salt_cli, salt_minion
):
    with VirtualEnv(venv_dir):

        # Create a requirements file that depends on another one.

        req1_filename = os.path.join(venv_dir, "requirements1.txt")
        req1b_filename = os.path.join(venv_dir, "requirements1b.txt")
        req2_filename = os.path.join(venv_dir, "requirements2.txt")
        req2b_filename = os.path.join(venv_dir, "requirements2b.txt")

        with salt.utils.files.fopen(req1_filename, "w") as f:
            f.write("-r requirements1b.txt\n")
        with salt.utils.files.fopen(req1b_filename, "w") as f:
            f.write("irc3-plugins-test\n")
        with salt.utils.files.fopen(req2_filename, "w") as f:
            f.write("-r requirements2b.txt\n")
        with salt.utils.files.fopen(req2b_filename, "w") as f:
            f.write("pep8\n")

        requirements_list = [req1_filename, req2_filename]

        ret = salt_cli.run(
            "pip.install",
            requirements=requirements_list,
            bin_env=venv_dir,
            cwd=venv_dir,
            minion_tgt=salt_minion.id,
        )
        if not isinstance(ret.data, dict):
            pytest.fail(
                "The 'pip.install' command did not return the expected dictionary."
                " Output:\n{}".format(ret)
            )

        try:
            assert ret.returncode == 0
            found = _pip_successful_install(ret.stdout)
            assert found
        except KeyError as exc:
            pytest.fail(
                "The returned dictionary is missing an expected key. Error: '{}'."
                " Dictionary: {}".format(exc, pprint.pformat(ret))
            )


@pytest.mark.slow_test
def test_requirements_as_list_of_chains__cwd_not_set__absolute_file_path(
    venv_dir, salt_cli, salt_minion
):
    with VirtualEnv(venv_dir):

        # Create a requirements file that depends on another one.

        req1_filename = os.path.join(venv_dir, "requirements1.txt")
        req1b_filename = os.path.join(venv_dir, "requirements1b.txt")
        req2_filename = os.path.join(venv_dir, "requirements2.txt")
        req2b_filename = os.path.join(venv_dir, "requirements2b.txt")

        with salt.utils.files.fopen(req1_filename, "w") as f:
            f.write("-r requirements1b.txt\n")
        with salt.utils.files.fopen(req1b_filename, "w") as f:
            f.write("irc3-plugins-test\n")
        with salt.utils.files.fopen(req2_filename, "w") as f:
            f.write("-r requirements2b.txt\n")
        with salt.utils.files.fopen(req2b_filename, "w") as f:
            f.write("pep8\n")

        requirements_list = [req1_filename, req2_filename]

        ret = salt_cli.run(
            "pip.install",
            requirements=requirements_list,
            bin_env=venv_dir,
            minion_tgt=salt_minion.id,
        )

        if not isinstance(ret.data, dict):
            pytest.fail(
                "The 'pip.install' command did not return the expected dictionary."
                " Output:\n{}".format(ret)
            )

        try:
            assert ret.returncode == 0
            found = _pip_successful_install(ret.stdout)
            assert found
        except KeyError as exc:
            pytest.fail(
                "The returned dictionary is missing an expected key. Error: '{}'."
                " Dictionary: {}".format(exc, pprint.pformat(ret))
            )


@pytest.mark.slow_test
def test_requirements_as_list__absolute_file_path(venv_dir, salt_cli, salt_minion):
    with VirtualEnv(venv_dir):

        req1_filename = os.path.join(venv_dir, "requirements.txt")
        req2_filename = os.path.join(venv_dir, "requirements2.txt")

        with salt.utils.files.fopen(req1_filename, "w") as f:
            f.write("irc3-plugins-test\n")
        with salt.utils.files.fopen(req2_filename, "w") as f:
            f.write("pep8\n")

        requirements_list = [req1_filename, req2_filename]

        ret = salt_cli.run(
            "pip.install",
            requirements=requirements_list,
            bin_env=venv_dir,
            minion_tgt=salt_minion.id,
        )

        if not isinstance(ret.data, dict):
            pytest.fail(
                "The 'pip.install' command did not return the expected dictionary."
                " Output:\n{}".format(ret)
            )

        try:
            assert ret.returncode == 0
            found = _pip_successful_install(ret.stdout)
            assert found
        except KeyError as exc:
            pytest.fail(
                "The returned dictionary is missing an expected key. Error: '{}'."
                " Dictionary: {}".format(exc, pprint.pformat(ret))
            )


@pytest.mark.slow_test
def test_requirements_as_list__non_absolute_file_path(venv_dir, salt_cli, salt_minion):
    with VirtualEnv(venv_dir):

        # Create a requirements file that depends on another one.

        req1_filename = "requirements.txt"
        req2_filename = "requirements2.txt"
        req_cwd = venv_dir

        req1_filepath = os.path.join(req_cwd, req1_filename)
        req2_filepath = os.path.join(req_cwd, req2_filename)

        with salt.utils.files.fopen(req1_filepath, "w") as f:
            f.write("irc3-plugins-test\n")
        with salt.utils.files.fopen(req2_filepath, "w") as f:
            f.write("pep8\n")

        requirements_list = [req1_filename, req2_filename]

        ret = salt_cli.run(
            "pip.install",
            f"cwd={req_cwd}",
            requirements=requirements_list,
            bin_env=venv_dir,
            minion_tgt=salt_minion.id,
        )

        if not isinstance(ret.data, dict):
            pytest.fail(
                "The 'pip.install' command did not return the expected dictionary."
                " Output:\n{}".format(ret)
            )

        try:
            assert ret.returncode == 0
            found = _pip_successful_install(ret.stdout)
            assert found
        except KeyError as exc:
            pytest.fail(
                "The returned dictionary is missing an expected key. Error: '{}'."
                " Dictionary: {}".format(exc, pprint.pformat(ret))
            )


@pytest.mark.slow_test
def test_chained_requirements__absolute_file_path(venv_dir, salt_cli, salt_minion):
    with VirtualEnv(venv_dir):

        # Create a requirements file that depends on another one.

        req1_filename = os.path.join(venv_dir, "requirements.txt")
        req2_filename = os.path.join(venv_dir, "requirements2.txt")

        with salt.utils.files.fopen(req1_filename, "w") as f:
            f.write("-r requirements2.txt")
        with salt.utils.files.fopen(req2_filename, "w") as f:
            f.write("pep8")

        ret = salt_cli.run(
            "pip.install",
            requirements=req1_filename,
            bin_env=venv_dir,
            minion_tgt=salt_minion.id,
        )
        if not isinstance(ret.data, dict):
            pytest.fail(
                "The 'pip.install' command did not return the expected dictionary."
                " Output:\n{}".format(ret)
            )

        try:
            assert ret.returncode == 0
            assert "installed pep8" in ret.stdout
        except KeyError as exc:
            pytest.fail(
                "The returned dictionary is missing an expected key. Error: '{}'."
                " Dictionary: {}".format(exc, pprint.pformat(ret))
            )


@pytest.mark.slow_test
def test_chained_requirements__non_absolute_file_path(venv_dir, salt_cli, salt_minion):
    with VirtualEnv(venv_dir):

        # Create a requirements file that depends on another one.
        req_basepath = venv_dir

        req1_filename = "requirements.txt"
        req2_filename = "requirements2.txt"

        req1_file = os.path.join(venv_dir, req1_filename)
        req2_file = os.path.join(venv_dir, req2_filename)

        with salt.utils.files.fopen(req1_file, "w") as f:
            f.write("-r requirements2.txt")
        with salt.utils.files.fopen(req2_file, "w") as f:
            f.write("pep8")

        ret = salt_cli.run(
            "pip.install",
            f"cwd={req_basepath}",
            requirements=req1_filename,
            bin_env=venv_dir,
            minion_tgt=salt_minion.id,
        )
        if not isinstance(ret.data, dict):
            pytest.fail(
                "The 'pip.install' command did not return the expected dictionary."
                " Output:\n{}".format(ret)
            )

        try:
            assert ret.returncode == 0
            assert "installed pep8" in ret.stdout
        except KeyError as exc:
            pytest.fail(
                "The returned dictionary is missing an expected key. Error: '{}'."
                " Dictionary: {}".format(exc, pprint.pformat(ret))
            )


@pytest.mark.slow_test
def test_issue_4805_nested_requirements(venv_dir, salt_cli, salt_minion):
    with VirtualEnv(venv_dir):

        # Create a requirements file that depends on another one.
        req1_filename = os.path.join(venv_dir, "requirements.txt")
        req2_filename = os.path.join(venv_dir, "requirements2.txt")
        with salt.utils.files.fopen(req1_filename, "w") as f:
            f.write("-r requirements2.txt")
        with salt.utils.files.fopen(req2_filename, "w") as f:
            f.write("pep8")

        ret = salt_cli.run(
            "pip.install",
            requirements=req1_filename,
            bin_env=venv_dir,
            timeout=300,
            minion_tgt=salt_minion.id,
        )

        if not isinstance(ret.data, dict):
            pytest.fail(
                "The 'pip.install' command did not return the expected dictionary."
                " Output:\n{}".format(ret)
            )

        try:
            if _check_download_error(ret.stdout):
                pytest.skip("Test skipped due to pip download error")
            assert ret.returncode == 0
            assert "installed pep8" in ret.stdout
        except KeyError as exc:
            pytest.fail(
                "The returned dictionary is missing an expected key. Error: '{}'."
                " Dictionary: {}".format(exc, pprint.pformat(ret))
            )


@pytest.mark.slow_test
def test_pip_uninstall(venv_dir, salt_cli, salt_minion):
    # Let's create the testing virtualenv
    with VirtualEnv(venv_dir):
        ret = salt_cli.run(
            "pip.install", ["pep8"], bin_env=venv_dir, minion_tgt=salt_minion.id
        )

        if not isinstance(ret.data, dict):
            pytest.fail(
                "The 'pip.install' command did not return the expected dictionary."
                " Output:\n{}".format(ret)
            )

        try:
            if _check_download_error(ret.stdout):
                pytest.skip("Test skipped due to pip download error")
            assert ret.returncode == 0
            assert "installed pep8" in ret.stdout
        except KeyError as exc:
            pytest.fail(
                "The returned dictionary is missing an expected key. Error: '{}'."
                " Dictionary: {}".format(exc, pprint.pformat(ret))
            )
        ret = salt_cli.run(
            "pip.uninstall", ["pep8"], bin_env=venv_dir, minion_tgt=salt_minion.id
        )

        if not isinstance(ret.data, dict):
            pytest.fail(
                "The 'pip.uninstall' command did not return the expected dictionary."
                " Output:\n{}".format(ret)
            )

        try:
            assert ret.returncode == 0
            assert "uninstalled pep8" in ret.stdout
        except KeyError as exc:
            pytest.fail(
                "The returned dictionary is missing an expected key. Error: '{}'."
                " Dictionary: {}".format(exc, pprint.pformat(ret))
            )


@pytest.mark.slow_test
def test_pip_install_upgrade(venv_dir, salt_cli, salt_minion):
    # Create the testing virtualenv
    with VirtualEnv(venv_dir):
        ret = salt_cli.run(
            "pip.install", "pep8==1.3.4", bin_env=venv_dir, minion_tgt=salt_minion.id
        )

        if not isinstance(ret.data, dict):
            pytest.fail(
                "The 'pip.install' command did not return the expected dictionary."
                " Output:\n{}".format(ret)
            )

        try:
            if _check_download_error(ret.stdout):
                pytest.skip("Test skipped due to pip download error")
            assert ret.returncode == 0
            assert "installed pep8" in ret.stdout
        except KeyError as exc:
            pytest.fail(
                "The returned dictionary is missing an expected key. Error: '{}'."
                " Dictionary: {}".format(exc, pprint.pformat(ret))
            )

        ret = salt_cli.run(
            "pip.install",
            "pep8",
            bin_env=venv_dir,
            upgrade=True,
            minion_tgt=salt_minion.id,
        )

        if not isinstance(ret.data, dict):
            pytest.fail(
                "The 'pip.install' command did not return the expected dictionary."
                " Output:\n{}".format(ret)
            )

        try:
            if _check_download_error(ret.stdout):
                pytest.skip("Test skipped due to pip download error")
            assert ret.returncode == 0
            assert "installed pep8" in ret.stdout
        except KeyError as exc:
            pytest.fail(
                "The returned dictionary is missing an expected key. Error: '{}'."
                " Dictionary: {}".format(exc, pprint.pformat(ret))
            )

        ret = salt_cli.run(
            "pip.uninstall", "pep8", bin_env=venv_dir, minion_tgt=salt_minion.id
        )

        if not isinstance(ret.data, dict):
            pytest.fail(
                "The 'pip.uninstall' command did not return the expected dictionary."
                " Output:\n{}".format(ret)
            )

        try:
            assert ret.returncode == 0
            assert "uninstalled pep8" in ret.stdout
        except KeyError as exc:
            pytest.fail(
                "The returned dictionary is missing an expected key. Error: '{}'."
                " Dictionary: {}".format(exc, pprint.pformat(ret))
            )


@pytest.mark.slow_test
def test_pip_install_multiple_editables(venv_dir, salt_cli, salt_minion):
    editables = [
        "git+https://github.com/saltstack/istr.git@v1.0.1#egg=iStr",
        "git+https://github.com/saltstack/salt-testing.git#egg=SaltTesting",
    ]

    # Create the testing virtualenv
    with VirtualEnv(venv_dir):
        ret = salt_cli.run(
            "pip.install",
            [],
            editable="{}".format(",".join(editables)),
            bin_env=venv_dir,
            minion_tgt=salt_minion.id,
        )

        if not isinstance(ret.data, dict):
            pytest.fail(
                "The 'pip.install' command did not return the expected dictionary."
                " Output:\n{}".format(ret)
            )

        try:
            if _check_download_error(ret.stdout):
                pytest.skip("Test skipped due to pip download error")
            assert ret.returncode == 0
            for package in ("iStr", "SaltTesting"):
                match = re.search(
                    r"(?:.*)(Successfully installed)(?:.*)({})(?:.*)".format(package),
                    ret.stdout,
                )
                assert match is not None
        except KeyError as exc:
            pytest.fail(
                "The returned dictionary is missing an expected key. Error: '{}'."
                " Dictionary: {}".format(exc, pprint.pformat(ret))
            )


@pytest.mark.slow_test
def test_pip_install_multiple_editables_and_pkgs(venv_dir, salt_cli, salt_minion):
    editables = [
        "git+https://github.com/saltstack/istr.git@v1.0.1#egg=iStr",
        "git+https://github.com/saltstack/salt-testing.git#egg=SaltTesting",
    ]

    # Create the testing virtualenv
    with VirtualEnv(venv_dir):
        ret = salt_cli.run(
            "pip.install",
            ["pep8"],
            editable="{}".format(",".join(editables)),
            bin_env=venv_dir,
            minion_tgt=salt_minion.id,
        )

        if not isinstance(ret.data, dict):
            pytest.fail(
                "The 'pip.install' command did not return the expected dictionary."
                " Output:\n{}".format(ret)
            )

        try:
            if _check_download_error(ret.stdout):
                pytest.skip("Test skipped due to pip download error")
            assert ret.returncode == 0
            for package in ("iStr", "SaltTesting", "pep8"):
                match = re.search(
                    r"(?:.*)(Successfully installed)(?:.*)({})(?:.*)".format(package),
                    ret.stdout,
                )
                assert match is not None
        except KeyError as exc:
            pytest.fail(
                "The returned dictionary is missing an expected key. Error: '{}'."
                " Dictionary: {}".format(exc, pprint.pformat(ret))
            )


@pytest.mark.parametrize("touch", [True, False])
@pytest.mark.slow_test
def test_pip_non_existent_log_file(venv_dir, salt_cli, salt_minion, tmp_path, touch):
    log_file = tmp_path / "tmp-pip-install.log"
    if touch:
        log_file.touch()
    # Create the testing virtualenv
    with VirtualEnv(venv_dir):
        ret = salt_cli.run(
            "pip.install",
            ["pep8"],
            log=str(log_file),
            bin_env=venv_dir,
            minion_tgt=salt_minion.id,
        )

        if not isinstance(ret.data, dict):
            pytest.fail(
                "The 'pip.install' command did not return the expected dictionary."
                " Output:\n{}".format(ret)
            )

        if _check_download_error(ret.stdout):
            pytest.skip("Test skipped due to pip download error")
        assert ret.returncode == 0
        assert log_file.exists()
        assert "pep8" in log_file.read_text()


@pytest.mark.skipif(
    shutil.which("/bin/pip3") is None, reason="Could not find /bin/pip3"
)
@pytest.mark.skip_on_windows(reason="test specific for linux usage of /bin/python")
@pytest.mark.skip_initial_gh_actions_failure(
    reason="This was skipped on older golden images and is failing on newer."
)
def test_system_pip3(salt_cli, salt_minion):
    salt_cli.run(
        "pip.install",
        pkgs=["lazyimport==0.0.1"],
        bin_env="/bin/pip3",
        minion_tgt=salt_minion.id,
    )
    ret1 = salt_cli.run(
        "cmd.run_all", "/bin/pip3 freeze | grep lazyimport", minion_tgt=salt_minion.id
    )
    assert "lazyimport==0.0.1" in ret1.stdout

    salt_cli.run(
        "pip.uninstall",
        pkgs=["lazyimport"],
        bin_env="/bin/pip3",
        minion_tgt=salt_minion.id,
    )
    ret2 = salt_cli.run(
        "cmd.run_all", "/bin/pip3 freeze | grep lazyimport", minion_tgt=salt_minion.id
    )
    assert ret2.data["stdout"] == ""
