import logging
import os

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
from tests.support.mock import MagicMock, mock_open, patch

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


# 'prepend' function tests: 1
def test_prepend():
    """
    Test to ensure that some text appears at the beginning of a file.
    """
    name = "/tmp/etc/motd"
    if salt.utils.platform.is_windows():
        name = "c:\\tmp\\etc\\motd"
    assert not os.path.exists(os.path.split(name)[0])
    source = ["salt://motd/hr-messages.tmpl"]
    sources = ["salt://motd/devops-messages.tmpl"]
    text = ["Trust no one unless you have eaten much salt with him."]

    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    comt = "Must provide name to file.prepend"
    ret.update({"comment": comt, "name": ""})
    assert filestate.prepend("") == ret

    comt = "source and sources are mutually exclusive"
    ret.update({"comment": comt, "name": name})
    assert filestate.prepend(name, source=source, sources=sources) == ret

    mock_t = MagicMock(return_value=True)
    mock_f = MagicMock(return_value=False)
    with patch.dict(
        filestate.__salt__,
        {
            "file.directory_exists": mock_f,
            "file.makedirs": mock_t,
            "file.stats": mock_f,
            "cp.get_template": mock_f,
            "file.search": mock_f,
            "file.prepend": mock_t,
        },
    ):
        comt = "The following files will be changed:\n/tmp/etc: directory - new\n"
        changes = {"/tmp/etc": {"directory": "new"}}
        if salt.utils.platform.is_windows():
            comt = 'The directory "c:\\tmp\\etc" will be changed'
            changes = {"c:\\tmp\\etc": {"directory": "new"}}
        ret.update({"comment": comt, "name": name, "changes": changes})
        assert filestate.prepend(name, makedirs=True) == ret

        with patch.object(os.path, "isabs", mock_f):
            comt = f"Specified file {name} is not an absolute path"
            ret.update({"comment": comt, "changes": {}})
            assert filestate.prepend(name) == ret

        with patch.object(os.path, "isabs", mock_t):
            with patch.object(os.path, "exists", mock_t):
                comt = f"Failed to load template file {source}"
                ret.update({"comment": comt, "name": source, "data": []})
                assert filestate.prepend(name, source=source) == ret

                ret.pop("data", None)
                ret.update({"name": name})
                with patch.object(
                    salt.utils.files, "fopen", MagicMock(mock_open(read_data=""))
                ):
                    with patch.dict(filestate.__utils__, {"files.is_text": mock_f}):
                        with patch.dict(filestate.__opts__, {"test": True}):
                            change = {"diff": "Replace binary file"}
                            comt = f"File {name} is set to be updated"
                            ret.update(
                                {"comment": comt, "result": None, "changes": change}
                            )
                            assert filestate.prepend(name, text=text) == ret

                        with patch.dict(filestate.__opts__, {"test": False}):
                            comt = "Prepended 1 lines"
                            ret.update({"comment": comt, "result": True, "changes": {}})
                            assert filestate.prepend(name, text=text) == ret
