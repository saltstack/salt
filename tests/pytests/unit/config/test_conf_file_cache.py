"""
Tests for the ``salt.config._read_conf_file`` parse cache (#59807).
"""

import salt.config
import salt.utils.files
from tests.support.mock import patch


def test_read_conf_file_parses_unchanged_file_once(tmp_path):
    """
    ``_read_conf_file`` parses a config file once and reuses the result while
    the file is unchanged, so the same file read repeatedly during daemon
    startup is not parsed hundreds of times. Regression test for #59807.
    """
    conf = tmp_path / "master"
    conf.write_text("timeout: 5\n")
    salt.config._conf_file_cache.pop(str(conf), None)
    with patch("salt.utils.files.fopen", wraps=salt.utils.files.fopen) as fopen_spy:
        first = salt.config._read_conf_file(str(conf))
        second = salt.config._read_conf_file(str(conf))
    assert first["timeout"] == 5
    assert second["timeout"] == 5
    # The second read is served from the cache -- the file is opened only once.
    assert fopen_spy.call_count == 1


def test_read_conf_file_returns_isolated_copies(tmp_path):
    """
    Each call returns a distinct object, so a caller that mutates the result
    cannot corrupt the cached copy handed to the next caller.
    """
    conf = tmp_path / "master"
    conf.write_text("timeout: 5\n")
    salt.config._conf_file_cache.pop(str(conf), None)
    first = salt.config._read_conf_file(str(conf))
    first["timeout"] = 999
    second = salt.config._read_conf_file(str(conf))
    assert first is not second
    assert second["timeout"] == 5


def test_read_conf_file_rereads_changed_file(tmp_path):
    """
    A changed file (different size or mtime) invalidates the cache and is
    re-read, so a reload is never served stale data.
    """
    conf = tmp_path / "master"
    conf.write_text("timeout: 5\n")
    salt.config._conf_file_cache.pop(str(conf), None)
    assert salt.config._read_conf_file(str(conf))["timeout"] == 5
    conf.write_text("timeout: 12345\n")
    assert salt.config._read_conf_file(str(conf))["timeout"] == 12345
