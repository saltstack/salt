import importlib

import pytest

import salt.config
import salt.utils
from tests.support.mock import patch


def os_config(os):
    """Fixture helper that manipulates all is_<platform> functions.
    The is_<platform> function for the passed ``os`` returns True, all others
    return ``False``.
    """
    is_os_functions = [f for f in dir(salt.utils.platform) if f.startswith("is_")]

    def gen_return(is_os_func, os):
        if is_os_func.endswith(os):
            return lambda: True
        return lambda: False

    patch_args = {func: gen_return(func, os) for func in is_os_functions}

    with patch.multiple("salt.utils.platform", **patch_args):
        yield importlib.reload(salt.config)
    importlib.reload(salt.config)


@pytest.fixture
def linux_config():
    yield from os_config("linux")


@pytest.fixture
def proxy_config():
    yield from os_config("proxy")


@pytest.fixture
def windows_config():
    yield from os_config("windows")


@pytest.fixture
def macos_config():
    yield from os_config("darwin")


def test_disabled_grains_defaults_linux(linux_config):
    with patch("salt.config", linux_config):
        result = salt.config.DEFAULT_MINION_OPTS["disabled_grains"]
        expected = ["fibre_channel", "iscsi", "metadata_server", "nvme"]
    assert sorted(result) == sorted(expected)


def test_disabled_grains_defaults_proxy(proxy_config):
    with patch("salt.config", proxy_config):
        result = salt.config.DEFAULT_MINION_OPTS["disabled_grains"]
        expected = ["fibre_channel", "iscsi", "metadata_server", "nvme"]
    assert sorted(result) == sorted(expected)


def test_disabled_grains_defaults_windows(windows_config):
    with patch("salt.config", windows_config):
        result = salt.config.DEFAULT_MINION_OPTS["disabled_grains"]
        expected = ["fibre_channel", "fqdns", "iscsi", "metadata_server", "nvme"]
    assert sorted(result) == sorted(expected)


def test_disabled_grains_defaults_macos(macos_config):
    with patch("salt.config", macos_config):
        result = salt.config.DEFAULT_MINION_OPTS["disabled_grains"]
        expected = ["fibre_channel", "fqdns", "iscsi", "metadata_server", "nvme"]
    assert sorted(result) == sorted(expected)
