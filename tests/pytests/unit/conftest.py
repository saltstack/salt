import os

import pytest

import salt.config


@pytest.fixture(scope="package", autouse=True)
def _onedir_env():
    """
    Unit tests cannot currently test the
    onedir artifact. This will need to be removed
    when we do add onedir support for functional tests.
    """
    if os.environ.get("ONEDIR_TESTRUN", "0") == "1":
        try:
            os.environ["ONEDIR_TESTRUN"] = "0"
            yield
        finally:
            os.environ["ONEDIR_TESTRUN"] = "1"
    else:
        yield


@pytest.fixture
def minion_opts(tmp_path):
    """
    Default minion configuration with relative temporary paths to not require root permissions.
    """
    root_dir = tmp_path / "minion"
    opts = salt.config.DEFAULT_MINION_OPTS.copy()
    opts["__role"] = "minion"
    opts["root_dir"] = str(root_dir)
    for name in ("cachedir", "pki_dir", "sock_dir", "conf_dir"):
        dirpath = root_dir / name
        dirpath.mkdir(parents=True)
        opts[name] = str(dirpath)
    opts["log_file"] = "logs/minion.log"
    return opts


@pytest.fixture
def master_opts(tmp_path):
    """
    Default master configuration with relative temporary paths to not require root permissions.
    """
    root_dir = tmp_path / "master"
    opts = salt.config.DEFAULT_MASTER_OPTS.copy()
    opts["__role"] = "master"
    opts["root_dir"] = str(root_dir)
    for name in ("cachedir", "pki_dir", "sock_dir", "conf_dir"):
        dirpath = root_dir / name
        dirpath.mkdir(parents=True)
        opts[name] = str(dirpath)
    opts["log_file"] = "logs/master.log"
    return opts
