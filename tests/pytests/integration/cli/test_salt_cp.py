"""
tests.integration.shell.cp
~~~~~~~~~~~~~~~~~~~~~~~~~~
"""


import logging
import os
import pathlib

import pytest
import salt.utils.files
from tests.support.runtests import RUNTIME_VARS

log = logging.getLogger(__name__)


@pytest.fixture
def source_testfile():
    src = pathlib.Path(RUNTIME_VARS.BASE_FILES) / "testfile"
    return str(src.resolve())


@pytest.fixture
def dest_testfile():
    dst = pathlib.Path(RUNTIME_VARS.TMP) / "test_cp_testfile_copy"
    try:
        yield str(dst)
    finally:
        if dst.exists():
            dst.unlink()


@pytest.mark.slow_test
@pytest.mark.windows_whitelisted
def test_cp_testfile(salt_minion, salt_cp_cli, source_testfile, dest_testfile):
    """
    test salt-cp
    """
    ret = salt_cp_cli.run(source_testfile, dest_testfile, minion_tgt=salt_minion.id)
    assert ret.exitcode == 0
    assert ret.json[dest_testfile] is True
    assert os.path.exists(dest_testfile)
    with salt.utils.files.fopen(source_testfile) as rfh:
        source_testfile_contents = rfh.read()
    with salt.utils.files.fopen(dest_testfile) as rfh:
        dest_test_file = rfh.read()
    assert source_testfile_contents == dest_test_file
