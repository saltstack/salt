import subprocess

import pytest

from tests.support.helpers import TESTS_DIR


@pytest.fixture
def python_script_bin(install_salt):
    # Tiamat builds run scripts via `salt python`
    if not install_salt.relenv and not install_salt.classic:
        return install_salt.binary_paths["python"][:1] + ["python"]
    return install_salt.binary_paths["python"]


@pytest.mark.parametrize("exp_ret,user_arg", [(1, "false"), (0, "true")])
def test_python_script(install_salt, exp_ret, user_arg, python_script_bin):
    ret = install_salt.proc.run(
        *(python_script_bin + [str(TESTS_DIR / "files" / "check_python.py"), user_arg]),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        universal_newlines=True,
    )

    assert ret.returncode == exp_ret, ret.stderr


def test_python_script_exception(install_salt, python_script_bin):
    ret = install_salt.proc.run(
        *(python_script_bin + [str(TESTS_DIR / "files" / "check_python.py"), "raise"]),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        universal_newlines=True,
    )
    assert "Exception: test" in ret.stderr
