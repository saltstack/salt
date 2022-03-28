import json
import subprocess
import sys

import pytest
import salt.utils.tiamatpkg


@pytest.fixture(params=("LD_LIBRARY_PATH", "LIBPATH"))
def envvar(request):
    return request.param


def test_subprocess_popen_environ_cleanup_existing(envvar):
    envvar_value = "foo"
    orig_envvar = "{}_ORIG".format(envvar)
    env = {
        orig_envvar: envvar_value,
    }
    instance = salt.utils.tiamatpkg.TiamatPopen(
        [sys.executable, "-c", "import os, json; print(json.dumps(dict(os.environ)))"],
        env=env.copy(),
        stdout=subprocess.PIPE,
    )
    stdout, _ = instance.communicate()
    assert instance.returncode == 0
    returned_env = json.loads(stdout)
    assert returned_env != env
    assert envvar in returned_env
    assert orig_envvar not in returned_env
    assert returned_env[envvar] == envvar_value


def test_subprocess_popen_environ_cleanup(envvar):
    envvar_value = "foo"
    env = {
        envvar: envvar_value,
    }
    instance = salt.utils.tiamatpkg.TiamatPopen(
        [sys.executable, "-c", "import os, json; print(json.dumps(dict(os.environ)))"],
        env=env.copy(),
        stdout=subprocess.PIPE,
    )
    stdout, _ = instance.communicate()
    assert instance.returncode == 0
    returned_env = json.loads(stdout)
    assert returned_env != env
    assert envvar not in returned_env


def test_vt_terminal_environ_cleanup_existing(envvar):
    envvar_value = "foo"
    orig_envvar = "{}_ORIG".format(envvar)
    env = {
        orig_envvar: envvar_value,
    }
    instance = salt.utils.tiamatpkg.TiamatTerminal(
        [sys.executable, "-c", "import os, json; print(json.dumps(dict(os.environ)))"],
        env=env.copy(),
        stream_stdout=False,
        stream_stderr=False,
    )
    buffer_o = buffer_e = ""
    while instance.has_unread_data:
        stdout, stderr = instance.recv()
        if stdout:
            buffer_o += stdout
        if stderr:
            buffer_e += stderr
    instance.terminate()

    assert instance.exitstatus == 0
    returned_env = json.loads(buffer_o)
    assert returned_env != env
    assert envvar in returned_env
    assert orig_envvar not in returned_env
    assert returned_env[envvar] == envvar_value


def test_vt_terminal_environ_cleanup(envvar):
    envvar_value = "foo"
    env = {
        envvar: envvar_value,
    }
    instance = salt.utils.tiamatpkg.TiamatTerminal(
        [sys.executable, "-c", "import os, json; print(json.dumps(dict(os.environ)))"],
        env=env.copy(),
        stream_stdout=False,
        stream_stderr=False,
    )
    buffer_o = buffer_e = ""
    while instance.has_unread_data:
        stdout, stderr = instance.recv()
        if stdout:
            buffer_o += stdout
        if stderr:
            buffer_e += stderr
    instance.terminate()

    assert instance.exitstatus == 0
    returned_env = json.loads(buffer_o)
    assert returned_env != env
    assert envvar not in returned_env
