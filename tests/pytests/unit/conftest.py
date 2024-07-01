import os

import pytest

import salt.config
from tests.conftest import FIPS_TESTRUN


@pytest.fixture
def minion_opts(tmp_path):
    """
    Default minion configuration with relative temporary paths to not require root permissions.
    """
    root_dir = tmp_path / "minion"
    opts = salt.config.DEFAULT_MINION_OPTS.copy()
    opts["__role"] = "minion"
    opts["root_dir"] = str(root_dir)
    opts["master_uri"] = "tcp://{ip}:{port}".format(
        ip="127.0.0.1", port=opts["master_port"]
    )
    for name in ("cachedir", "pki_dir", "sock_dir", "conf_dir"):
        dirpath = root_dir / name
        dirpath.mkdir(parents=True)
        opts[name] = str(dirpath)
    opts["log_file"] = "logs/minion.log"
    opts["conf_file"] = os.path.join(opts["conf_dir"], "minion")
    opts["fips_mode"] = FIPS_TESTRUN
    opts["encryption_algorithm"] = "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1"
    opts["signing_algorithm"] = "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
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
    opts["conf_file"] = os.path.join(opts["conf_dir"], "master")
    opts["fips_mode"] = FIPS_TESTRUN
    opts["publish_signing_algorithm"] = (
        "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
    )
    return opts


@pytest.fixture
def syndic_opts(tmp_path):
    """
    Default master configuration with relative temporary paths to not require root permissions.
    """
    root_dir = tmp_path / "syndic"
    opts = salt.config.DEFAULT_MINION_OPTS.copy()
    opts["syndic_master"] = "127.0.0.1"
    opts["__role"] = "minion"
    opts["root_dir"] = str(root_dir)
    for name in ("cachedir", "pki_dir", "sock_dir", "conf_dir"):
        dirpath = root_dir / name
        dirpath.mkdir(parents=True)
        opts[name] = str(dirpath)
    opts["log_file"] = "logs/syndic.log"
    opts["conf_file"] = os.path.join(opts["conf_dir"], "syndic")
    return opts
