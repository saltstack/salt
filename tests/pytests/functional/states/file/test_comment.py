"""
Tests for file.comment state function
"""
import re

import pytest

import salt.utils.files
from tests.support.helpers import dedent

pytestmark = [
    pytest.mark.windows_whitelisted,
]


@pytest.fixture(scope="module")
def file(states):
    return states.file


@pytest.fixture(scope="function")
def source():
    with pytest.helpers.temp_file(
        name="file.txt",
        contents=dedent(
            """
            things = stuff
            port = 5432                             # (change requires restart)
            # commented = something
            moar = things
            """
        ),
    ) as source:
        yield source


def test_issue_62121(file, source):
    """
    Test file.comment when the comment character is
    later in the line, after the text
    """
    regex = r"^port\s*=.+"
    reg_cmp = re.compile(regex, re.MULTILINE)
    cmt_regex = r"^#port\s*=.+"
    cmt_cmp = re.compile(cmt_regex, re.MULTILINE)

    with salt.utils.files.fopen(str(source)) as _fp:
        assert reg_cmp.findall(_fp.read())

    file.comment(name=str(source), regex=regex)

    with salt.utils.files.fopen(str(source)) as _fp:
        assert not reg_cmp.findall(_fp.read())
        _fp.seek(0)
        assert cmt_cmp.findall(_fp.read())
