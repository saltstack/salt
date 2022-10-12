import logging
import os
import plistlib
import pprint

import msgpack
import pytest

import salt.serializers.json as jsonserializer
import salt.serializers.msgpack as msgpackserializer
import salt.serializers.plist as plistserializer
import salt.serializers.python as pythonserializer
import salt.serializers.yaml as yamlserializer
import salt.states.file as filestate
import salt.utils.files
import salt.utils.json
import salt.utils.yaml
from tests.support.mock import Mock, mock_open, patch

log = logging.getLogger(__name__)


@pytest.fixture
def configure_loader_modules():
    return {
        filestate: {
            "__env__": "base",
            "__salt__": {},
            "__serializers__": {
                "yaml.serialize": yamlserializer.serialize,
                "yaml.deserialize": yamlserializer.deserialize,
                "python.serialize": pythonserializer.serialize,
                "json.serialize": jsonserializer.serialize,
                "json.deserialize": jsonserializer.deserialize,
                "plist.serialize": plistserializer.serialize,
                "msgpack.serialize": msgpackserializer.serialize,
            },
            "__opts__": {"test": False, "cachedir": ""},
            "__instance_id__": "",
            "__low__": {},
            "__utils__": {},
        }
    }


def test_serialize_check_cmd():
    name = "/tmp"
    tmpfile = "/tmpfile"
    check_cmd = "config-test"
    dataset = {"foo": True, "bar": 42, "baz": [1, 2, 3], "qux": 2.0}

    def returner(contents, ret, *args, **kwargs):
        returner.returned = contents
        return {"changes": True}

    returner.returned = None

    def return_value(**kwargs):
        ret = {"name": name, "result": False, "comment": "", "changes": {}}
        ret.update(kwargs)
        return ret

    mock_f = Mock(return_value=False)
    mock_t = Mock(return_value=True)
    mock_tmpfile = Mock(return_value=tmpfile)
    mock_check_fail = Mock(
        return_value={"retcode": 127, "stdout": "config check failed"}
    )

    with patch.object(salt.utils.files, "mkstemp", mock_tmpfile):
        with patch.dict(
            filestate.__salt__,
            {"file.file_exists": mock_f, "file.manage_file": returner},
        ):

            with patch.dict(
                filestate.__salt__,
                {"cmd.run_all": mock_check_fail},
            ):
                # Test check_cmd failure
                ret = filestate.serialize(name, dataset, check_cmd=check_cmd)
                assert ret == return_value(
                    comment="check_cmd execution failed\nconfig check failed",
                    skip_watch=True,
                )

            with patch.object(filestate, "mod_run_check_cmd", mock_t):
                # Check that we're sending the correct args to mod_run_check_cmd
                filestate.serialize(name, dataset, check_cmd=check_cmd)
                mock_t.assert_called_with(check_cmd, tmpfile)
                mock_t.reset_mock()

                # Check that after all the check_cmd shenanigans we still write the correct contents
                filestate.serialize(name, dataset, check_cmd=check_cmd)
                assert salt.utils.yaml.safe_load(returner.returned) == dataset


def test_serializers():
    name = "/tmp"

    def returner(contents, ret, *args, **kwargs):
        returner.returned = contents
        return ret

    returner.returned = None

    with patch.dict(filestate.__salt__, {"file.manage_file": returner}):

        dataset = {"foo": True, "bar": 42, "baz": [1, 2, 3], "qux": 2.0}

        # If no serializer passed, result should be serialized as YAML
        filestate.serialize(name, dataset)
        assert salt.utils.yaml.safe_load(returner.returned) == dataset

        # YAML
        filestate.serialize(name, dataset, serializer="yaml")
        assert salt.utils.yaml.safe_load(returner.returned) == dataset
        filestate.serialize(name, dataset, formatter="yaml")
        assert salt.utils.yaml.safe_load(returner.returned) == dataset

        # JSON
        filestate.serialize(name, dataset, serializer="json")
        assert salt.utils.json.loads(returner.returned) == dataset
        filestate.serialize(name, dataset, formatter="json")
        assert salt.utils.json.loads(returner.returned) == dataset

        # plist
        filestate.serialize(name, dataset, serializer="plist")
        assert plistlib.loads(returner.returned) == dataset
        filestate.serialize(name, dataset, formatter="plist")
        assert plistlib.loads(returner.returned) == dataset

        # Python
        filestate.serialize(name, dataset, serializer="python")
        assert returner.returned == pprint.pformat(dataset) + "\n"
        filestate.serialize(name, dataset, formatter="python")
        assert returner.returned == pprint.pformat(dataset) + "\n"

        # msgpack
        filestate.serialize(name, dataset, serializer="msgpack")
        assert returner.returned == msgpack.packb(dataset)
        filestate.serialize(name, dataset, formatter="msgpack")
        assert returner.returned == msgpack.packb(dataset)

        mock_serializer = Mock(return_value="")
        with patch.dict(filestate.__serializers__, {"json.serialize": mock_serializer}):
            # Test with "serializer" arg
            filestate.serialize(
                name, dataset, formatter="json", serializer_opts=[{"indent": 8}]
            )
            mock_serializer.assert_called_with(
                dataset, indent=8, separators=(",", ": "), sort_keys=True
            )
            # Test with "formatter" arg
            mock_serializer.reset_mock()
            filestate.serialize(
                name, dataset, formatter="json", serializer_opts=[{"indent": 8}]
            )
            mock_serializer.assert_called_with(
                dataset, indent=8, separators=(",", ": "), sort_keys=True
            )


def test_serialize():
    name = "/tmp"
    dataset = {"foo": True, "bar": 42, "baz": [1, 2, 3], "qux": 2.0}

    def returner(contents, ret, *args, **kwargs):
        returner.returned = contents
        return ret

    returner.returned = None

    def return_value(**kwargs):
        ret = {"name": name, "result": False, "comment": "", "changes": {}}
        ret.update(kwargs)
        return ret

    mock = Mock(return_value=return_value())
    mock_t = Mock(return_value=True)
    mock_f = Mock(return_value=False)

    # Missing name
    with pytest.raises(TypeError):
        # pylint: disable=no-value-for-parameter
        filestate.serialize(dataset=dataset, serializer="json")

    # File missing, but create=False
    with patch.object(os.path, "isfile", mock_f):
        ret = filestate.serialize(name, dataset, create=False)
        assert ret == return_value(
            comment="File {} is not present and is not set for creation".format(name),
            result=True,
        )

    # Both serializer and formatter given
    ret = filestate.serialize(name, dataset, serializer="yaml", formatter="json")
    assert ret == return_value(
        comment="Only one of serializer and formatter are allowed"
    )

    # Both dataset and dataset_pillar given
    ret = filestate.serialize(name, dataset, dataset_pillar=True)
    assert ret == return_value(
        comment="Only one of 'dataset' and 'dataset_pillar' is permitted"
    )

    # Neither dataset or dataset_pillar given
    ret = filestate.serialize(name)
    assert ret == return_value(
        comment="Neither 'dataset' nor 'dataset_pillar' was defined"
    )

    # Serializer doesn't support deserialization
    with patch.object(os.path, "isfile", mock_t):
        ret = filestate.serialize(
            name, dataset=True, merge_if_exists=True, formatter="python"
        )
        assert ret == return_value(
            comment="merge_if_exists is not supported for the python serializer"
        )

    # Missing serializer
    ret = filestate.serialize(name, dataset, formatter="A")
    assert ret == return_value(
        comment=(
            "The a serializer could not be found. "
            "It either does not exist or its prerequisites are not installed."
        )
    )

    # __opts__['test']=True with changes
    with patch.dict(filestate.__salt__, {"file.check_managed_changes": mock_t}):
        with patch.dict(filestate.__opts__, {"test": True}):
            ret = filestate.serialize(name, dataset)
            assert ret == return_value(
                comment="Dataset will be serialized and stored into {}".format(name),
                result=None,
                changes=True,
            )

    # __opts__['test']=True without changes
    with patch.dict(filestate.__salt__, {"file.check_managed_changes": mock_f}):
        with patch.dict(filestate.__opts__, {"test": True}):
            ret = filestate.serialize(name, dataset)
            assert ret == return_value(
                comment="The file {} is in the correct state".format(name),
                result=True,
                changes=False,
            )

    # Merging existing file content that deserializes successfully
    with patch.object(os.path, "isfile", mock_t):
        with patch.object(
            salt.utils.files, "fopen", mock_open(read_data='{"merge": "content"}')
        ):
            with patch.dict(filestate.__salt__, {"file.manage_file": returner}):
                ret = filestate.serialize(
                    name, dataset, serializer="json", merge_if_exists=True
                )
                dataset.update({"merge": "content"})
                assert salt.utils.json.loads(returner.returned) == dataset

    # Merging existing file content that fails to deserializes (missing quote before content)
    with patch.object(os.path, "isfile", mock_t):
        with patch.object(
            salt.utils.files, "fopen", mock_open(read_data='{"merge": content"}')
        ):
            with patch.dict(filestate.__salt__, {"file.manage_file": returner}):
                ret = filestate.serialize(
                    name, dataset, serializer="json", merge_if_exists=True
                )
                assert ret == return_value(
                    comment="Failed to deserialize existing data: Expecting value: line 1 column 11 (char 10)",
                    result=False,
                )
