import pytest

import salt.config


@pytest.fixture
def minion_opts(tmp_path):
    """
    Default minion configuration with relative temporary paths to not require root permissions.
    """
    opts = salt.config.DEFAULT_MINION_OPTS.copy()
    opts["root_dir"] = str(tmp_path)
    for name in ("cachedir", "pki_dir", "sock_dir", "conf_dir"):
        dirpath = tmp_path / name
        dirpath.mkdir()
        opts[name] = str(dirpath)
    opts["log_file"] = "logs/minion.log"
    return opts
