import pytest

import salt.serializers.json as jsonserializer
import salt.serializers.msgpack as msgpackserializer
import salt.serializers.plist as plistserializer
import salt.serializers.python as pythonserializer
import salt.serializers.yaml as yamlserializer
import salt.states.file as filestate
from tests.support.mock import MagicMock, patch


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


def test_file_serialize_tmp_dir_system_temp(tmp_path):
    tmp_file = tmp_path / "tmp.txt"
    mock_mkstemp = MagicMock()
    with patch("salt.utils.files.mkstemp", mock_mkstemp), patch.dict(
        filestate.__salt__,
        {
            "cmd.run_all": MagicMock(return_value={"retcode": 0}),
            "file.file_exists": MagicMock(return_value=False),
            "file.manage_file": MagicMock(),
        },
    ):
        filestate.serialize(str(tmp_file), dataset={"wollo": "herld"}, check_cmd="true")
        mock_mkstemp.assert_called_with(suffix="", dir=None)
