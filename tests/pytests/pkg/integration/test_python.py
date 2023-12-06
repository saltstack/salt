import subprocess
import textwrap

import pytest


@pytest.fixture
def python_script_bin(install_salt):
    # Tiamat builds run scripts via `salt python`
    if not install_salt.relenv and not install_salt.classic:
        return install_salt.binary_paths["python"][:1] + ["python"]
    return install_salt.binary_paths["python"]


@pytest.fixture
def check_python_file(tmp_path):
    script_path = tmp_path / "check_python.py"
    script_path.write_text(
        textwrap.dedent(
            """
        import sys

        import salt.utils.data

        user_arg = sys.argv

        if user_arg[1] == "raise":
            raise Exception("test")

        if salt.utils.data.is_true(user_arg[1]):
            sys.exit(0)
        else:
            sys.exit(1)
        """
        )
    )
    return script_path


@pytest.mark.parametrize("exp_ret,user_arg", [(1, "false"), (0, "true")])
def test_python_script(
    install_salt, exp_ret, user_arg, python_script_bin, check_python_file
):
    ret = install_salt.proc.run(
        *(
            python_script_bin
            + [
                str(check_python_file),
                user_arg,
            ]
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        universal_newlines=True,
    )

    assert ret.returncode == exp_ret, ret.stderr


def test_python_script_exception(install_salt, python_script_bin, check_python_file):
    ret = install_salt.proc.run(
        *(
            python_script_bin
            + [
                str(check_python_file),
                "raise",
            ]
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        universal_newlines=True,
    )
    assert "Exception: test" in ret.stderr
