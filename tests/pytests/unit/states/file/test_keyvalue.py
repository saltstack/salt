import collections
import logging

import pytest
import salt.serializers.json as jsonserializer
import salt.serializers.msgpack as msgpackserializer
import salt.serializers.plist as plistserializer
import salt.serializers.python as pythonserializer
import salt.serializers.yaml as yamlserializer
import salt.states.file as filestate
import salt.utils.files
import salt.utils.json
import salt.utils.platform
import salt.utils.win_functions
import salt.utils.yaml
from tests.support.helpers import dedent

log = logging.getLogger(__name__)


@pytest.fixture
def configure_loader_modules():
    return {
        filestate: {
            "__env__": "base",
            "__salt__": {"file.manage_file": False},
            "__serializers__": {
                "yaml.serialize": yamlserializer.serialize,
                "yaml.seserialize": yamlserializer.serialize,
                "python.serialize": pythonserializer.serialize,
                "json.serialize": jsonserializer.serialize,
                "plist.serialize": plistserializer.serialize,
                "msgpack.serialize": msgpackserializer.serialize,
            },
            "__opts__": {"test": False, "cachedir": ""},
            "__instance_id__": "",
            "__low__": {},
            "__utils__": {},
        }
    }


def test_file_keyvalue_key_values(tmp_path):
    """
    test file.keyvalue when using key_values kwarg
    """
    content = dedent(
        """\
        #PermitRootLogin prohibit-password
        #StrictMode yes
        """
    )
    tempfile = str(tmp_path / "tempfile")

    with salt.utils.files.fopen(tempfile, "w+") as fp_:
        fp_.write(content)

    ret = filestate.keyvalue(
        name=tempfile,
        key_values=collections.OrderedDict(PermitRootLogin="yes"),
        separator=" ",
        uncomment="#",
        key_ignore_case=True,
    )

    with salt.utils.files.fopen(tempfile, "r") as fp_:
        f_contents = fp_.read()
        assert "PermitRootLogin yes" in f_contents
        assert "#StrictMode yes" in f_contents


def test_file_keyvalue_empty(tmp_path):
    """
    test file.keyvalue when key_values is empty
    """
    content = dedent(
        """\
        #PermitRootLogin prohibit-password
        #StrictMode yes
        """
    )
    tempfile = str(tmp_path / "tempfile")

    with salt.utils.files.fopen(tempfile, "w+") as fp_:
        fp_.write(content)

    ret = filestate.keyvalue(
        name=tempfile,
        key_values={},
        separator=" ",
        uncomment="#",
        key_ignore_case=True,
    )

    assert (
        ret["comment"]
        == "file.keyvalue key and value not supplied and key_values is empty"
    )
    with salt.utils.files.fopen(tempfile, "r") as fp_:
        f_contents = fp_.read()
        assert "PermitRootLogin yes" not in f_contents
        assert "#StrictMode yes" in f_contents


def test_file_keyvalue_not_dict(tmp_path):
    """
    test file.keyvalue when key_values not a dict
    """
    content = dedent(
        """\
        #PermitRootLogin prohibit-password
        #StrictMode yes
        """
    )
    tempfile = str(tmp_path / "tempfile")

    with salt.utils.files.fopen(tempfile, "w+") as fp_:
        fp_.write(content)

    ret = filestate.keyvalue(
        name=tempfile,
        key_values=["PermiteRootLogin", "yes"],
        separator=" ",
        uncomment="#",
        key_ignore_case=True,
    )

    assert (
        ret["comment"]
        == "file.keyvalue key and value not supplied and key_values is not a dictionary"
    )
    with salt.utils.files.fopen(tempfile, "r") as fp_:
        f_contents = fp_.read()
        assert "PermitRootLogin yes" not in f_contents
        assert "#StrictMode yes" in f_contents
