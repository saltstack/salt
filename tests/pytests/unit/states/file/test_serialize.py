import pytest

import salt.serializers.json as jsonserializer
import salt.serializers.msgpack as msgpackserializer
import salt.serializers.yaml as yamlserializer
import salt.states.file as filestate
import salt.utils.secret
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
                "json.serialize": jsonserializer.serialize,
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


def _pillar_get(masked_pillar):
    """
    A fake pillar.get that mirrors salt.modules.pillar.get masking: it hands
    back redacted values unless the caller passes unmask=True.
    """

    def _get(key, default=None, unmask=None, **kwargs):
        value = masked_pillar.get(key, default if default is not None else {})
        if unmask:
            return salt.utils.secret.expose(value)
        return salt.utils.secret.serial(value)

    return _get


def test_serialize_dataset_pillar_unmasks_pillar_values(tmp_path):
    """
    Regression test for issue #69709: file.serialize with dataset_pillar must
    request unmasked pillar values, otherwise scalar string values are written
    to the managed file as the redaction placeholder instead of the real data.
    """
    dataset = {"db_password": "hunter2", "api_key": "abcdef123456", "port": 5432}
    masked_pillar = salt.utils.secret.hide({"app_config": dataset})

    captured = {}

    def fake_manage_file(name, **kwargs):
        # contents is the serialized payload the state would write to disk
        captured["contents"] = kwargs.get("contents")
        return {"result": True, "changes": {}, "comment": "", "name": name}

    target = tmp_path / "config.yaml"
    with patch.dict(
        filestate.__salt__,
        {
            "pillar.get": _pillar_get(masked_pillar),
            "file.manage_file": fake_manage_file,
        },
    ):
        filestate.serialize(str(target), dataset_pillar="app_config", serializer="yaml")

    written = captured["contents"]
    assert salt.utils.secret.REDACT_PLACEHOLDER not in written
    assert "hunter2" in written
    assert "abcdef123456" in written


def test_serialize_direct_dataset_bypasses_pillar_get_69709(tmp_path):
    """
    Guard against overcorrection of the issue #69709 fix: when a 'dataset'
    argument is supplied directly (the non-pillar path), file.serialize must
    not start routing the data through pillar.get at all, with or without
    unmask=True. The dataset must be serialized exactly as given. This test
    passes both with and without the fix applied.
    """
    dataset = {"db_password": "hunter2", "port": 5432}
    captured = {}

    def fake_manage_file(name, **kwargs):
        captured["contents"] = kwargs.get("contents")
        return {"result": True, "changes": {}, "comment": "", "name": name}

    # pillar.get is a strict mock so any call to it is detectable
    pillar_get = MagicMock()

    target = tmp_path / "config.yaml"
    with patch.dict(
        filestate.__salt__,
        {
            "pillar.get": pillar_get,
            "file.manage_file": fake_manage_file,
        },
    ):
        filestate.serialize(str(target), dataset=dataset, serializer="yaml")

    pillar_get.assert_not_called()
    assert "hunter2" in captured["contents"]
    assert salt.utils.secret.REDACT_PLACEHOLDER not in captured["contents"]
