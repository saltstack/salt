import glob
import logging
import os
import pprint
import shutil
import sys

import pytest

import salt.utils.files
import salt.utils.path
import salt.utils.platform
import salt.utils.versions
import salt.utils.win_dacl
import salt.utils.win_functions
import salt.utils.win_runas
from tests.support.helpers import SKIP_INITIAL_PHOTONOS_FAILURES, patched_environ

try:
    import pwd

    HAS_PWD = True
except ImportError:
    HAS_PWD = False

log = logging.getLogger(__name__)


def _win_user_where(username, password, program):
    cmd = "cmd.exe /c where {}".format(program)
    ret = salt.utils.win_runas.runas(cmd, username, password)
    assert ret["retcode"] == 0, "{} returned {}".format(cmd, ret["retcode"])
    return ret["stdout"].strip().split("\n")[-1].strip()


@pytest.fixture(scope="module")
def create_virtualenv(modules):
    def run_command(path, **kwargs):
        """
        The reason why the virtualenv creation is proxied by this function is mostly
        because under windows, we can't seem to properly create a virtualenv off of
        another virtualenv(we can on linux) and also because, we really don't want to
        test virtualenv creation off of another virtualenv, we want a virtualenv created
        from the original python.
        Also, one windows, we must also point to the virtualenv binary outside the existing
        virtualenv because it will fail otherwise
        """
        if "python" not in kwargs:
            try:
                if salt.utils.platform.is_windows():
                    python = os.path.join(
                        sys.real_prefix, os.path.basename(sys.executable)
                    )
                else:
                    python_binary_names = [
                        "python{}.{}".format(*sys.version_info),
                        "python{}".format(*sys.version_info),
                        "python",
                    ]
                    for binary_name in python_binary_names:
                        python = os.path.join(sys.real_prefix, "bin", binary_name)
                        if os.path.exists(python):
                            break
                    else:
                        pytest.fail(
                            "Couldn't find a python binary name under '{}' matching: {}".format(
                                os.path.join(sys.real_prefix, "bin"),
                                python_binary_names,
                            )
                        )
                # We're running off a virtualenv, and we don't want to create a virtualenv off of
                # a virtualenv, let's point to the actual python that created the virtualenv
                kwargs["python"] = python
            except AttributeError:
                # We're running off of the system python
                pass
        return modules.virtualenv.create(path, **kwargs)

    return run_command


@pytest.mark.slow_test
def test_pip_installed_removed(modules, states):
    """
    Tests installed and removed states
    """
    name = "pudb"
    if name in modules.pip.list():
        pytest.skip("{} is already installed, uninstall to run this test".format(name))
    ret = states.pip.installed(name=name)
    assert ret.result is True
    ret = states.pip.removed(name=name)
    assert ret.result is True


@pytest.mark.slow_test
def test_pip_installed_removed_venv(tmp_path, create_virtualenv, states):
    venv_dir = tmp_path / "pip_installed_removed"
    create_virtualenv(str(venv_dir))
    name = "pudb"
    ret = states.pip.installed(name=name, bin_env=str(venv_dir))
    assert ret.result is True
    ret = states.pip.removed(name=name, bin_env=str(venv_dir))
    assert ret.result is True


@pytest.mark.slow_test
def test_pip_installed_errors(tmp_path, modules, state_tree):
    venv_dir = tmp_path / "pip-installed-errors"
    # Since we don't have the virtualenv created, pip.installed will
    # throw an error.
    # Example error strings:
    #  * "Error installing 'pep8': /tmp/pip-installed-errors: not found"
    #  * "Error installing 'pep8': /bin/sh: 1: /tmp/pip-installed-errors: not found"
    #  * "Error installing 'pep8': /bin/bash: /tmp/pip-installed-errors: No such file or directory"
    sls_contents = """
pep8-pip:
  pip.installed:
    - name: pep8
    - bin_env: '{}'
""".format(
        str(venv_dir)
    )

    with patched_environ(SHELL="/bin/sh"):
        with pytest.helpers.temp_file(
            "pip-installed-errors.sls", sls_contents, state_tree
        ):
            ret = modules.state.sls("pip-installed-errors")
            for state_return in ret:
                assert state_return.result is False
                assert "Error installing 'pep8':" in state_return.comment

            # We now create the missing virtualenv
            ret = modules.virtualenv.create(str(venv_dir))
            assert ret["retcode"] == 0

            # The state should not have any issues running now
            ret = modules.state.sls(mods="pip-installed-errors")
            for state_return in ret:
                assert state_return.result is True


def test_pip_installed_name_test_mode(tmp_path, create_virtualenv, states):
    """
    Test pip.installed state while test=true
    """
    venv_dir = tmp_path / "pip_installed_test_mode_name"
    create_virtualenv(str(venv_dir))

    name = "pudb"
    msg = "Python package(s) set to be installed:\npudb"
    ret = states.pip.installed(name=name, bin_env=str(venv_dir), test=True)
    assert name in ret.comment


def test_pip_installed_pkgs_test_mode(tmp_path, create_virtualenv, states):
    """
    Test pip.installed state while test=true
    """
    venv_dir = tmp_path / "pip_installed_test_mode_pkgs"
    create_virtualenv(str(venv_dir))

    pkgs = ["boto", "pudb", "black"]
    msg = "Python package(s) set to be installed:\nboto\npudb\nblack"
    ret = states.pip.installed(name=None, pkgs=pkgs, bin_env=str(venv_dir), test=True)
    assert msg in ret.comment


@pytest.mark.slow_test
def test_issue_2028_pip_installed_state(
    tmp_path, modules, state_tree, get_python_executable
):

    venv_dir = tmp_path / "issue-2028-pip-installed"
    python_executable = get_python_executable

    sls_contents = """
{%- set virtualenv_base = salt['pillar.get']('venv_dir') %}
{%- set python_executable = salt['pillar.get']('python_executable') %}

{{ virtualenv_base }}:
  virtualenv.managed:
    - system_site_packages: False
    - distribute: False
    {#- Provide the real path for the python executable in case tests are running inside a virtualenv #}
    {%- if python_executable %}
    - python: {{ python_executable }}
    {%- endif %}

install-working-setuptools:
  pip.installed:
    - name: 'setuptools!=50.*,!=51.*,!=52.*'
    - bin_env: {{ virtualenv_base }}
    - require:
      - virtualenv: {{ virtualenv_base }}

pep8-pip:
  pip.installed:
    - name: pep8
    - bin_env: {{ virtualenv_base }}
    - require:
      - pip: install-working-setuptools
      - virtualenv: {{ virtualenv_base }}
"""
    with pytest.helpers.temp_file(
        "issue-2028-pip-installed.sls", sls_contents, state_tree
    ):
        ret = modules.state.sls(
            mods="issue-2028-pip-installed",
            pillar={
                "venv_dir": str(venv_dir),
                "python_exeutable": get_python_executable,
            },
        )

        pep8_bin = venv_dir / "bin" / "pep8"

        if salt.utils.platform.is_windows():
            pep8_bin = venv_dir / "Scripts" / "pep8.exe"

        for state_return in ret:
            assert state_return.result is True

        assert os.path.isfile(str(pep8_bin)) is True


@pytest.mark.slow_test
def test_issue_2087_missing_pip(tmp_path, create_virtualenv, modules):
    venv_dir = tmp_path / "issue-2087-missing-pip"

    sls_contents = """pep8-pip:
pip.installed:
    - name: pep8
    - bin_env: {}
""".format(
        str(venv_dir)
    )

    # Let's create the testing virtualenv
    ret = create_virtualenv(str(venv_dir))
    assert ret["retcode"] == 0

    # Let's remove the pip binary
    pip_bin = venv_dir / "bin" / "pip"
    site_dir = modules.virtualenv.get_distribution_path(str(venv_dir), "pip")
    if salt.utils.platform.is_windows():
        pip_bin = venv_dir / "Scripts" / "pip.exe"
        site_dir = venv_dir / "lib" / "site-packages"
    if not os.path.isfile(str(pip_bin)):
        pytest.skip("Failed to find the pip binary to the test virtualenv")
    os.remove(str(pip_bin))

    # Also remove the pip dir from site-packages
    # This is needed now that we're using python -m pip instead of the
    # pip binary directly. python -m pip will still work even if the
    # pip binary is missing
    shutil.rmtree(os.path.join(str(site_dir), "pip"))

    # Let's run the state which should fail because pip is missing
    ret = modules.state.sls(mods="issue-2087-missing-pip")
    for state_return in ret:
        assert state_return.result is True
        assert (
            "Error installing 'pep8': Could not find a `pip` binary"
            in state_return.comment
        )


@SKIP_INITIAL_PHOTONOS_FAILURES
@pytest.mark.destructive_test
@pytest.mark.slow_test
@pytest.mark.skip_if_not_root
def test_issue_6912_wrong_owner(tmp_path, create_virtualenv, modules, states):
    # Setup virtual environment directory to be used throughout the test
    venv_dir = tmp_path / "6912-wrong-owner"
    venv_kwargs = {}

    with pytest.helpers.create_account(
        username="issue-6912", password="PassWord1!"
    ) as account:
        # The virtual environment needs to be in a location that is accessible
        # by both the user running the test and the runas user
        if salt.utils.platform.is_windows():
            salt.utils.win_dacl.set_permissions(
                tmp_path, account.username, "full_control"
            )
            # Make sure we're calling a virtualenv and python
            # program that the user has access too.
            venv_kwargs["venv_bin"] = _win_user_where(
                account.username,
                "PassWord1!",
                "virtualenv",
            )
            venv_kwargs["python"] = _win_user_where(
                account.username,
                "PassWord1!",
                "python",
            )
        else:
            uid = modules.file.user_to_uid(account.username)
            os.chown(str(tmp_path), uid, -1)

        # Create the virtual environment
        venv_create = create_virtualenv(
            str(venv_dir), user=account.username, password="PassWord1!", **venv_kwargs
        )
        if venv_create.get("retcode", 1) > 0:
            pytest.skip(
                "Failed to create testcase virtual environment: {}".format(venv_create)
            )

        # pip install passing the package name in `name`
        ret = states.pip.installed(
            name="pep8",
            user=account.username,
            bin_env=str(venv_dir),
            password="PassWord1!",
        )
        assert ret.result is True

        if HAS_PWD:
            uid = pwd.getpwnam(account.username).pw_uid
        for globmatch in (
            os.path.join(str(venv_dir), "**", "pep8*"),
            os.path.join(str(venv_dir), "*", "**", "pep8*"),
            os.path.join(str(venv_dir), "*", "*", "**", "pep8*"),
        ):
            for path in glob.glob(globmatch):
                if HAS_PWD:
                    assert uid == os.stat(path).st_uid
                elif salt.utils.platform.is_windows():
                    assert salt.utils.win_dacl.get_owner(path) == account.username


@SKIP_INITIAL_PHOTONOS_FAILURES
@pytest.mark.destructive_test
@pytest.mark.skip_on_darwin(reason="Test is flaky on macosx")
@pytest.mark.slow_test
@pytest.mark.skip_if_not_root
def test_issue_6912_wrong_owner_requirements_file(
    tmp_path, create_virtualenv, state_tree, modules, states
):
    # Setup virtual environment directory to be used throughout the test
    venv_dir = tmp_path / "6912-wrong-owner"
    venv_kwargs = {}

    with pytest.helpers.create_account(
        username="issue-6912", password="PassWord1!"
    ) as account:
        # The virtual environment needs to be in a location that is accessible
        # by both the user running the test and the runas user
        if salt.utils.platform.is_windows():
            salt.utils.win_dacl.set_permissions(
                str(tmp_path), account.username, "full_control"
            )
            # Make sure we're calling a virtualenv and python
            # program that the user has access too.
            venv_kwargs["venv_bin"] = _win_user_where(
                account.username,
                "PassWord1!",
                "virtualenv",
            )
            venv_kwargs["python"] = _win_user_where(
                account.username,
                "PassWord1!",
                "python",
            )
        else:
            uid = modules.file.user_to_uid(account.username)
            os.chown(str(tmp_path), uid, -1)

        # Create the virtual environment again as it should have been removed
        venv_create = create_virtualenv(
            str(venv_dir), user=account.username, password="PassWord1!", **venv_kwargs
        )
        if venv_create.get("retcode", 1) > 0:
            pytest.skip(
                "failed to create testcase virtual environment: {}".format(venv_create)
            )

        # pip install using a requirements file
        contents = "pep8\n"
        with pytest.helpers.temp_file(
            "issue-6912-requirements.txt", contents, state_tree
        ):
            ret = states.pip.installed(
                name="",
                user=account.username,
                bin_env=str(venv_dir),
                requirements="salt://issue-6912-requirements.txt",
                password="PassWord1!",
            )
            assert ret.result is True

        if HAS_PWD:
            uid = pwd.getpwnam(account.username).pw_uid
        for globmatch in (
            os.path.join(str(venv_dir), "**", "pep8*"),
            os.path.join(str(venv_dir), "*", "**", "pep8*"),
            os.path.join(str(venv_dir), "*", "*", "**", "pep8*"),
        ):
            for path in glob.glob(globmatch):
                if HAS_PWD:
                    assert uid == os.stat(path).st_uid
                elif salt.utils.platform.is_windows():
                    assert salt.utils.win_dacl.get_owner(path) == account.username


@pytest.mark.destructive_test
@pytest.mark.slow_test
def test_issue_6833_pip_upgrade_pip(tmp_path, create_virtualenv, modules, states):
    # Create the testing virtualenv
    if sys.platform == "win32":
        # To keeps the path short, we'll create this directory on the root
        # of the system drive. Otherwise the path is too long and the pip
        # upgrade will fail. Also, I don't know why salt.utils.platform
        # doesn't work in this function, that's why I used sys.platform
        # Need to use os.sep.join here instead of os.path.join because of
        # the colon in SystemDrive
        venv_dir = os.sep.join([os.environ["SystemDrive"], "tmp-6833-pip-upgrade-pip"])
    else:
        venv_dir = str(tmp_path / "6833-pip-upgrade-pip")
    ret = create_virtualenv(venv_dir)

    assert ret["retcode"] == 0

    if not (
        "New python executable" in ret["stdout"]
        or "created virtual environment" in ret["stdout"]
    ):
        assert (
            False
        ), "Expected STDOUT did not match. Full return dictionary:\n{}".format(
            pprint.pformat(ret)
        )

    # Let's install a fixed version pip over whatever pip was
    # previously installed
    ret = modules.pip.install("pip==19.3.1", upgrade=True, bin_env=venv_dir)

    if not isinstance(ret, dict):
        pytest.fail(
            "The 'pip.install' command did not return the excepted dictionary."
            " Output:\n{}".format(ret)
        )

    assert ret["retcode"] == 0
    assert "Successfully installed pip" in ret["stdout"]

    # Let's make sure we have pip 9.0.1 installed
    assert modules.pip.list("pip", bin_env=venv_dir) == {"pip": "19.3.1"}

    # Now the actual pip upgrade pip test
    ret = states.pip.installed(name="pip==20.0.1", upgrade=True, bin_env=venv_dir)

    if not isinstance(ret.raw, dict):
        pytest.fail(
            "The 'pip.install' command did not return the excepted dictionary."
            " Output:\n{}".format(ret)
        )

    assert ret.result is True
    assert ret.changes == {"pip==20.0.1": "Installed"}


@pytest.mark.slow_test
def test_pip_installed_specific_env(
    tmp_path, state_tree_prod, states, create_virtualenv
):
    # Create the testing virtualenv
    venv_dir = tmp_path / "pip-installed-specific-env"

    contents = "pep8\n"

    # Let's write a requirements file
    with pytest.helpers.temp_file(
        "prod-env-requirements.txt", contents, state_tree_prod
    ):

        create_virtualenv(str(venv_dir))

        # The requirements file should not be found the base environment
        ret = states.pip.installed(
            name="",
            bin_env=str(venv_dir),
            requirements="salt://prod-env-requirements.txt",
        )
        assert ret.result is False
        assert "'salt://prod-env-requirements.txt' not found" in ret.comment

        # The requirements file must be found in the prod environment
        ret = states.pip.installed(
            name="",
            bin_env=str(venv_dir),
            saltenv="prod",
            requirements="salt://prod-env-requirements.txt",
        )
        assert ret.result is True
        assert (
            "Successfully processed requirements file salt://prod-env-requirements.txt"
            in ret.comment
        )

        # We're using the base environment but we're passing the prod
        # environment as an url arg to salt://
        ret = states.pip.installed(
            name="",
            bin_env=str(venv_dir),
            requirements="salt://prod-env-requirements.txt?saltenv=prod",
        )
        assert ret.result is True
        assert "Requirements were already installed." in ret.comment


@pytest.mark.slow_test
def test_22359_pip_installed_unless_does_not_trigger_warnings(
    create_virtualenv, tmp_path, states
):
    # This test case should be moved to a format_call unit test specific to
    # the state internal keywords
    venv_dir = str(tmp_path / "pip-installed-unless")
    venv_create = create_virtualenv(venv_dir)
    if venv_create["retcode"] > 0:
        pytest.skip(
            "Failed to create testcase virtual environment: {}".format(venv_create)
        )

    false_cmd = salt.utils.path.which("false")
    if salt.utils.platform.is_windows():
        false_cmd = "exit 1 >nul"
    try:
        ret = states.pip.installed(
            name="pep8",
            bin_env=str(venv_dir),
            unless=false_cmd,
            timeout=600,
        )
        assert ret.result is True
        assert "warnings" not in next(iter(ret.raw.values()))
    finally:
        if os.path.isdir(str(venv_dir)):
            shutil.rmtree(str(venv_dir), ignore_errors=True)


@pytest.mark.windows_whitelisted
@pytest.mark.slow_test
def test_issue_54755(tmp_path, state_tree, modules):
    """
    Verify github issue 54755 is resolved. This only fails when there is no
    pip module in the python environment. Since the test suite normally has
    a pip module this test will pass and is here for posterity. See also

    unit.states.test_pip_state.PipStateUtilsTest.test_pip_purge_method_with_pip

     and

    unit.states.test_pip_state.PipStateUtilsTest.test_pip_purge_method_without_pip

    Which also validate this issue and will pass/fail regardless of whether
    or not pip is installed.
    """
    file_path = tmp_path / "issue-54755"
    sls_contents = """issue-54755:
    file.managed:
        - name: {{ pillar['file_path'] }}
        - contents: issue-54755
        - unless: /bin/bash -c false
    """

    with pytest.helpers.temp_file("issue-54755.sls", sls_contents, state_tree):
        ret = modules.state.sls(mods="issue-54755", pillar={"file_path": file_path})
        key = "file_|-issue-54755_|-{}_|-managed".format(file_path)
        assert key in ret.raw
        assert ret.raw[key]["result"] is True
        with salt.utils.files.fopen(str(file_path), "r") as fp:
            assert fp.read().strip() == "issue-54755"
