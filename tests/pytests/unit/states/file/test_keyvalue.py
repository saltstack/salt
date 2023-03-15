import collections
import logging

import pytest

import salt.serializers.json as jsonserializer
import salt.serializers.msgpack as msgpackserializer
import salt.serializers.plist as plistserializer
import salt.serializers.python as pythonserializer
import salt.serializers.yaml as yamlserializer
import salt.states.file as filestate
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
    contents = dedent(
        """\
        #PermitRootLogin prohibit-password
        #StrictMode yes
        """
    )
    with pytest.helpers.temp_file(
        "tempfile", contents=contents, directory=tmp_path
    ) as tempfile:
        ret = filestate.keyvalue(
            name=str(tempfile),
            key_values=collections.OrderedDict(PermitRootLogin="yes"),
            separator=" ",
            uncomment="#",
            key_ignore_case=True,
        )

        f_contents = tempfile.read_text()
        assert "PermitRootLogin yes" in f_contents
        assert "#StrictMode yes" in f_contents


def test_file_keyvalue_empty(tmp_path):
    """
    test file.keyvalue when key_values is empty
    """
    contents = dedent(
        """\
        #PermitRootLogin prohibit-password
        #StrictMode yes
        """
    )
    with pytest.helpers.temp_file(
        "tempfile", contents=contents, directory=tmp_path
    ) as tempfile:
        ret = filestate.keyvalue(
            name=str(tempfile),
            key_values={},
            separator=" ",
            uncomment="#",
            key_ignore_case=True,
        )

        assert (
            ret["comment"]
            == "file.keyvalue key and value not supplied and key_values is empty"
        )
        f_contents = tempfile.read_text()
        assert "PermitRootLogin yes" not in f_contents
        assert "#StrictMode yes" in f_contents


def test_file_keyvalue_not_dict(tmp_path):
    """
    test file.keyvalue when key_values not a dict
    """
    contents = dedent(
        """\
        #PermitRootLogin prohibit-password
        #StrictMode yes
        """
    )
    with pytest.helpers.temp_file(
        "tempfile", contents=contents, directory=tmp_path
    ) as tempfile:
        ret = filestate.keyvalue(
            name=str(tempfile),
            key_values=["PermiteRootLogin", "yes"],
            separator=" ",
            uncomment="#",
            key_ignore_case=True,
        )

        assert (
            ret["comment"]
            == "file.keyvalue key and value not supplied and key_values is not a dictionary"
        )
        f_contents = tempfile.read_text()
        assert "PermitRootLogin yes" not in f_contents
        assert "#StrictMode yes" in f_contents
