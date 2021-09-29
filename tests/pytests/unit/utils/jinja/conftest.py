"""
Tests for salt.utils.jinja
"""

import os

import pytest
import salt.config
import salt.loader

# dateutils is needed so that the strftime jinja filter is loaded
import salt.utils.dateutils  # pylint: disable=unused-import
import salt.utils.files
import salt.utils.json
import salt.utils.stringutils
import salt.utils.yaml

try:
    import timelib  # pylint: disable=W0611

    HAS_TIMELIB = True
except ImportError:
    HAS_TIMELIB = False

BLINESEP = salt.utils.stringutils.to_bytes(os.linesep)


class MockFileClient:
    """
    Does not download files but records any file request for testing
    """

    def __init__(self, loader=None):
        if loader:
            loader._file_client = self
        self.requests = []

    def get_file(self, template, dest="", makedirs=False, saltenv="base"):
        self.requests.append(
            {"path": template, "dest": dest, "makedirs": makedirs, "saltenv": saltenv}
        )


@pytest.fixture
def mock_file_client(loader=None):
    return MockFileClient(loader)


def _setup_test_dir(src_dir, test_dir):
    os.makedirs(test_dir)
    salt.utils.files.recursive_copy(src_dir, test_dir)
    filename = os.path.join(test_dir, "non_ascii")
    with salt.utils.files.fopen(filename, "wb") as fp:
        fp.write(b"Assun\xc3\xa7\xc3\xa3o" + BLINESEP)
    filename = os.path.join(test_dir, "hello_simple")
    with salt.utils.files.fopen(filename, "wb") as fp:
        fp.write(b"world" + BLINESEP)
    filename = os.path.join(test_dir, "hello_import")
    lines = [
        r"{% from 'macro' import mymacro -%}",
        r"{% from 'macro' import mymacro -%}",
        r"{{ mymacro('Hey') ~ mymacro(a|default('a'), b|default('b')) }}",
    ]
    with salt.utils.files.fopen(filename, "wb") as fp:
        for line in lines:
            fp.write(line.encode("utf-8") + BLINESEP)
