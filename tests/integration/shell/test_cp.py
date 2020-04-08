# -*- coding: utf-8 -*-
"""
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    tests.integration.shell.cp
    ~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

from __future__ import absolute_import

import logging
import os

import pytest
import salt.utils.files
from tests.support.runtests import RUNTIME_VARS

log = logging.getLogger(__name__)


@pytest.fixture
def source_testfile():
    yield os.path.abspath(os.path.join(RUNTIME_VARS.BASE_FILES, "testfile"))


@pytest.fixture
def dest_testfile():
    _copy_testfile_path = os.path.join(RUNTIME_VARS.TMP, "test_cp_testfile_copy")
    yield _copy_testfile_path
    if os.path.exists(_copy_testfile_path):
        os.unlink(_copy_testfile_path)


@pytest.mark.windows_whitelisted
def test_cp_testfile(salt_minion, salt_cp_cli, source_testfile, dest_testfile):
    """
    test salt-cp
    """
    ret = salt_cp_cli.run(
        source_testfile, dest_testfile, minion_tgt=salt_minion.config["id"]
    )
    assert ret.exitcode == 0
    assert ret.json[dest_testfile] is True
    assert os.path.exists(dest_testfile)
    with salt.utils.files.fopen(source_testfile) as rfh:
        source_testfile_contents = rfh.read()
    with salt.utils.files.fopen(dest_testfile) as rfh:
        dest_test_file = rfh.read()
    assert source_testfile_contents == dest_test_file
