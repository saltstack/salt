import subprocess

import pytest

from tests.support.helpers import TESTS_DIR


@pytest.mark.parametrize("exp_ret,user_arg", [(1, "false"), (0, "true")])
def test_python_script(install_salt, exp_ret, user_arg):
    ret = subprocess.run(
        install_salt.binary_paths["python"]
        + [str(TESTS_DIR / "files" / "check_python.py"), user_arg],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        universal_newlines=True,
    )

    assert ret.returncode == exp_ret, ret.stderr


def test_python_script_exception(install_salt):
    ret = subprocess.run(
        install_salt.binary_paths["python"]
        + [str(TESTS_DIR / "files" / "check_python.py"), "raise"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        universal_newlines=True,
    )
    assert "Exception: test" in ret.stderr
