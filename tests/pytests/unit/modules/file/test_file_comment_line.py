import logging
import os
import shutil
import textwrap

import pytest

import salt.config
import salt.loader
import salt.modules.cmdmod as cmdmod
import salt.modules.config as configmod
import salt.modules.file as filemod
import salt.utils.data
import salt.utils.files
import salt.utils.platform
import salt.utils.stringutils
from tests.support.mock import MagicMock

log = logging.getLogger(__name__)


@pytest.fixture
def configure_loader_modules():
    return {
        filemod: {
            "__salt__": {
                "config.manage_mode": configmod.manage_mode,
                "cmd.run": cmdmod.run,
                "cmd.run_all": cmdmod.run_all,
            },
            "__opts__": {
                "test": False,
                "file_roots": {"base": "tmp"},
                "pillar_roots": {"base": "tmp"},
                "cachedir": "tmp",
                "grains": {},
            },
            "__grains__": {"kernel": "Linux"},
            "__utils__": {
                "files.is_text": MagicMock(return_value=True),
                "stringutils.get_diff": salt.utils.stringutils.get_diff,
            },
        }
    }


@pytest.fixture
def multiline_string():
    multiline_string = textwrap.dedent(
        """\
        Lorem
        ipsum
        #dolor
        """
    )

    multiline_string = os.linesep.join(multiline_string.splitlines())

    return multiline_string


@pytest.fixture
def multiline_file(tmp_path, multiline_string):
    multiline_file = str(tmp_path / "multiline-file.txt")

    with salt.utils.files.fopen(multiline_file, "w+") as file_handle:
        file_handle.write(multiline_string)

    yield multiline_file
    shutil.rmtree(str(tmp_path))


def test_comment_line(multiline_file):
    filemod.comment_line(multiline_file, "^ipsum")

    with salt.utils.files.fopen(multiline_file, "r") as fp:
        filecontent = fp.read()
    assert "#ipsum" in filecontent


def test_comment(multiline_file):
    filemod.comment(multiline_file, "^ipsum")

    with salt.utils.files.fopen(multiline_file, "r") as fp:
        filecontent = fp.read()
    assert "#ipsum" in filecontent


def test_comment_different_character(multiline_file):
    filemod.comment_line(multiline_file, "^ipsum", "//")

    with salt.utils.files.fopen(multiline_file, "r") as fp:
        filecontent = fp.read()
    assert "//ipsum" in filecontent


def test_comment_not_found(multiline_file):
    filemod.comment_line(multiline_file, "^sit")

    with salt.utils.files.fopen(multiline_file, "r") as fp:
        filecontent = fp.read()
    assert "#sit" not in filecontent
    assert "sit" not in filecontent


def test_uncomment(multiline_file):
    filemod.uncomment(multiline_file, "dolor")

    with salt.utils.files.fopen(multiline_file, "r") as fp:
        filecontent = fp.read()
    assert "dolor" in filecontent
    assert "#dolor" not in filecontent
