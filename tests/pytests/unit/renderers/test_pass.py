import importlib

import pytest

import salt.exceptions
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
