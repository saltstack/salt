import importlib
import os
import shutil
import tempfile

import pytest

import salt.exceptions
import salt.utils.files
from tests.support.mock import MagicMock, patch

# "pass" is a reserved keyword, we need to import it differently
pass_ = importlib.import_module("salt.renderers.pass")


@pytest.fixture
def configure_loader_modules(master_opts):
    return {
        pass_: {
            "__opts__": master_opts,
            "_get_pass_exec": MagicMock(return_value="/usr/bin/pass"),
        }
    }


@pytest.fixture()
def pass_executable(request):
    tmp_dir = tempfile.mkdtemp(prefix="salt_pass_")
    pass_path = os.path.join(tmp_dir, "pass")
    with salt.utils.files.fopen(pass_path, "w") as f:
        f.write("#!/bin/sh\n")
        # return path path wrapped into unicode characters
        # pass args ($1, $2) are ("show", <pass_path>)
        f.write('echo "α>>> $2 <<<β"\n')
    os.chmod(pass_path, 0o755)
    yield pass_path
    shutil.rmtree(tmp_dir)


@pytest.fixture()
def pass_executable_error(request):
    tmp_dir = tempfile.mkdtemp(prefix="salt_pass_")
    pass_path = os.path.join(tmp_dir, "pass")
    with salt.utils.files.fopen(pass_path, "w") as f:
        f.write("#!/bin/sh\n")
        # return error message with unicode characters
        f.write('echo "ERROR: αβγ" >&2\n')
        f.write("exit 1\n")
    os.chmod(pass_path, 0o755)
    yield pass_path
    shutil.rmtree(tmp_dir)


@pytest.fixture()
def pass_executable_invalid_utf8(request):
    tmp_dir = tempfile.mkdtemp(prefix="salt_pass_")
    pass_path = os.path.join(tmp_dir, "pass")
    with salt.utils.files.fopen(pass_path, "wb") as f:
        f.write(b"#!/bin/sh\n")
        # return invalid utf-8 sequence
        f.write(b'echo "\x80\x81"\n')
    os.chmod(pass_path, 0o755)
    yield pass_path
    shutil.rmtree(tmp_dir)


# The default behavior is that if fetching a secret from pass fails,
# the value is passed through. Even the trailing newlines are preserved.
def test_passthrough():
    pass_path = "secret\n"
    expected = pass_path
    result = pass_.render(pass_path)

    assert result == expected


# Fetch a secret in the strict mode.
def test_strict_fetch():
    config = {
        "pass_variable_prefix": "pass:",
        "pass_strict_fetch": True,
    }

    popen_mock = MagicMock(spec=pass_.Popen)
    popen_mock.return_value.communicate.return_value = ("password123456\n", "")
    popen_mock.return_value.returncode = 0

    mocks = {
        "Popen": popen_mock,
    }

    pass_path = "pass:secret"
    expected = "password123456"
    with patch.dict(pass_.__opts__, config), patch.dict(pass_.__dict__, mocks):
        result = pass_.render(pass_path)

    assert result == expected


# Fail to fetch a secret in the strict mode.
def test_strict_fetch_fail():
    config = {
        "pass_variable_prefix": "pass:",
        "pass_strict_fetch": True,
    }

    popen_mock = MagicMock(spec=pass_.Popen)
    popen_mock.return_value.communicate.return_value = ("", "Secret not found")
    popen_mock.return_value.returncode = 1

    mocks = {
        "Popen": popen_mock,
    }

    pass_path = "pass:secret"
    with patch.dict(pass_.__opts__, config), patch.dict(pass_.__dict__, mocks):
        with pytest.raises(salt.exceptions.SaltRenderError):
            pass_.render(pass_path)


# Passthrough a value that doesn't have a pass prefix.
def test_strict_fetch_passthrough():
    config = {
        "pass_variable_prefix": "pass:",
        "pass_strict_fetch": True,
    }

    pass_path = "variable-without-pass-prefix\n"
    expected = pass_path
    with patch.dict(pass_.__opts__, config):
        result = pass_.render(pass_path)

    assert result == expected


# Fetch a secret in the strict mode. The pass path contains spaces.
def test_strict_fetch_pass_path_with_spaces():
    config = {
        "pass_variable_prefix": "pass:",
        "pass_strict_fetch": True,
    }

    popen_mock = MagicMock(spec=pass_.Popen)
    popen_mock.return_value.communicate.return_value = ("password123456\n", "")
    popen_mock.return_value.returncode = 0

    mocks = {
        "Popen": popen_mock,
    }

    pass_path = "pass:se cr et"
    with patch.dict(pass_.__opts__, config), patch.dict(pass_.__dict__, mocks):
        pass_.render(pass_path)

    call_args, call_kwargs = popen_mock.call_args_list[0]
    assert call_args[0] == ["/usr/bin/pass", "show", "se cr et"]


# Fetch a secret in the strict mode. The secret contains leading and trailing whitespaces.
def test_strict_fetch_secret_with_whitespaces():
    config = {
        "pass_variable_prefix": "pass:",
        "pass_strict_fetch": True,
    }

    popen_mock = MagicMock(spec=pass_.Popen)
    popen_mock.return_value.communicate.return_value = (" \tpassword123456\t \r\n", "")
    popen_mock.return_value.returncode = 0

    mocks = {
        "Popen": popen_mock,
    }

    pass_path = "pass:secret"
    expected = " \tpassword123456\t "  # only the trailing newlines get striped
    with patch.dict(pass_.__opts__, config), patch.dict(pass_.__dict__, mocks):
        result = pass_.render(pass_path)

    assert result == expected


# Test setting env variables based on config values:
# - pass_gnupghome -> GNUPGHOME
# - pass_dir -> PASSWORD_STORE_DIR
def test_env():
    config = {
        "pass_variable_prefix": "pass:",
        "pass_strict_fetch": True,
        "pass_gnupghome": "/path/to/gnupghome",
        "pass_dir": "/path/to/secretstore",
    }

    popen_mock = MagicMock(spec=pass_.Popen)
    popen_mock.return_value.communicate.return_value = ("password123456\n", "")
    popen_mock.return_value.returncode = 0

    mocks = {
        "Popen": popen_mock,
    }

    pass_path = "pass:secret"
    expected = " \tpassword123456\t "  # only the trailing newlines get striped
    with patch.dict(pass_.__opts__, config), patch.dict(pass_.__dict__, mocks):
        result = pass_.render(pass_path)

    call_args, call_kwargs = popen_mock.call_args_list[0]
    assert call_kwargs["env"]["GNUPGHOME"] == config["pass_gnupghome"]
    assert call_kwargs["env"]["PASSWORD_STORE_DIR"] == config["pass_dir"]


@pytest.mark.skip_on_windows(reason="Not supported on Windows")
def test_utf8(pass_executable):
    config = {
        "pass_variable_prefix": "pass:",
        "pass_strict_fetch": True,
    }
    mocks = {
        "_get_pass_exec": MagicMock(return_value=pass_executable),
    }

    pass_path = "pass:secret"
    with patch.dict(pass_.__opts__, config), patch.dict(pass_.__dict__, mocks):
        result = pass_.render(pass_path)
    assert result == "α>>> secret <<<β"


@pytest.mark.skip_on_windows(reason="Not supported on Windows")
def test_utf8_error(pass_executable_error):
    config = {
        "pass_variable_prefix": "pass:",
        "pass_strict_fetch": True,
    }
    mocks = {
        "_get_pass_exec": MagicMock(return_value=pass_executable_error),
    }

    pass_path = "pass:secret"
    with patch.dict(pass_.__opts__, config), patch.dict(pass_.__dict__, mocks):
        with pytest.raises(
            salt.exceptions.SaltRenderError,
            match=r"Could not fetch secret 'secret' from the password store: ERROR: αβγ",
        ):
            result = pass_.render(pass_path)


@pytest.mark.skip_on_windows(reason="Not supported on Windows")
def test_invalid_utf8(pass_executable_invalid_utf8):
    config = {
        "pass_variable_prefix": "pass:",
        "pass_strict_fetch": True,
    }
    mocks = {
        "_get_pass_exec": MagicMock(return_value=pass_executable_invalid_utf8),
    }

    pass_path = "pass:secret"
    with patch.dict(pass_.__opts__, config), patch.dict(pass_.__dict__, mocks):
        with pytest.raises(
            salt.exceptions.SaltRenderError,
            match=r"Could not fetch secret 'secret' from the password store: 'utf-8' codec can't decode byte 0x80 in position 0: invalid start byte",
        ):
            result = pass_.render(pass_path)
