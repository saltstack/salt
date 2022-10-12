import json
import os
import subprocess
import sys

import pytest

import salt.utils.pyinstaller.rthooks._overrides as overrides
from tests.support import mock
from tests.support.helpers import PatchedEnviron


@pytest.fixture(params=("LD_LIBRARY_PATH", "LIBPATH"))
def envvar(request):
    return request.param


@pytest.fixture
def meipass(envvar):
    with mock.patch("salt.utils.pyinstaller.rthooks._overrides.sys") as patched_sys:
        patched_sys._MEIPASS = "{}_VALUE".format(envvar)
        assert overrides.sys._MEIPASS == "{}_VALUE".format(envvar)
        yield "{}_VALUE".format(envvar)
    assert not hasattr(sys, "_MEIPASS")
    assert not hasattr(overrides.sys, "_MEIPASS")


def test_subprocess_popen_environ_cleanup_original(envvar, meipass):
    orig_envvar = "{}_ORIG".format(envvar)
    with PatchedEnviron(**{orig_envvar: meipass}):
        original_env = dict(os.environ)
        assert orig_envvar in original_env
        instance = overrides.PyinstallerPopen(
            [
                sys.executable,
                "-c",
                "import os, json; print(json.dumps(dict(os.environ)))",
            ],
            stdout=subprocess.PIPE,
            universal_newlines=True,
        )
        stdout, _ = instance.communicate()
        assert instance.returncode == 0
        returned_env = json.loads(stdout)
        assert returned_env != original_env
        assert envvar in returned_env
        assert orig_envvar not in returned_env
        assert returned_env[envvar] == meipass


def test_subprocess_popen_environ_cleanup_original_passed_directly(envvar, meipass):
    orig_envvar = "{}_ORIG".format(envvar)
    env = {
        orig_envvar: meipass,
    }
    original_env = dict(os.environ)

    instance = overrides.PyinstallerPopen(
        [sys.executable, "-c", "import os, json; print(json.dumps(dict(os.environ)))"],
        env=env.copy(),
        stdout=subprocess.PIPE,
        universal_newlines=True,
    )
    stdout, _ = instance.communicate()
    assert instance.returncode == 0
    returned_env = json.loads(stdout)
    assert returned_env != original_env
    assert envvar in returned_env
    assert orig_envvar not in returned_env
    assert returned_env[envvar] == meipass


def test_subprocess_popen_environ_cleanup(envvar, meipass):
    with PatchedEnviron(**{envvar: meipass}):
        original_env = dict(os.environ)
        assert envvar in original_env
        instance = overrides.PyinstallerPopen(
            [
                sys.executable,
                "-c",
                "import os, json; print(json.dumps(dict(os.environ)))",
            ],
            stdout=subprocess.PIPE,
            universal_newlines=True,
        )
        stdout, _ = instance.communicate()
        assert instance.returncode == 0
        returned_env = json.loads(stdout)
        assert returned_env != original_env
        assert envvar in returned_env
        assert returned_env[envvar] == ""


def test_subprocess_popen_environ_cleanup_passed_directly_not_removed(envvar, meipass):
    env = {
        envvar: envvar,
    }
    original_env = dict(os.environ)

    instance = overrides.PyinstallerPopen(
        [sys.executable, "-c", "import os, json; print(json.dumps(dict(os.environ)))"],
        env=env.copy(),
        stdout=subprocess.PIPE,
        universal_newlines=True,
    )
    stdout, _ = instance.communicate()
    assert instance.returncode == 0
    returned_env = json.loads(stdout)
    assert returned_env != original_env
    assert envvar in returned_env
    assert returned_env[envvar] == envvar
