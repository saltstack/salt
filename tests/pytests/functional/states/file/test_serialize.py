import json
import logging

import pytest

import salt.serializers.configparser
import salt.serializers.plist

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.windows_whitelisted,
]


def test_serialize(file, tmp_path):
    """
    Test to ensure that file.serialize returns a data structure that's
    both serialized and formatted properly
    """
    path_test = tmp_path / "test_serialize"
    dataset = {
        "name": "naive",
        "description": "A basic test",
        "a_list": ["first_element", "second_element"],
        "finally": "the last item",
    }
    ret = file.serialize(
        name=str(path_test),
        dataset=dataset,
        formatter="json",
    )
    assert ret.result is True

    assert json.loads(path_test.read_text()) == dataset


def test_serializer_deserializer_opts(file, tmp_path):
    """
    Test the serializer_opts and deserializer_opts options
    """
    name = tmp_path / "testfile"

    data1 = {"foo": {"bar": "%(x)s"}}
    data2 = {"foo": {"abc": 123}}
    merged = {"foo": {"y": "not_used", "x": "baz", "abc": 123, "bar": "baz"}}

    ret = file.serialize(
        name=str(name),
        dataset=data1,
        formatter="configparser",
        deserializer_opts=[{"defaults": {"y": "not_used"}}],
    )
    assert ret.result is True

    # We should have warned about deserializer_opts being used when
    # merge_if_exists was not set to True.
    assert "warnings" in ret.filtered
    assert (
        "The 'deserializer_opts' option is ignored unless merge_if_exists is set to True."
        in ret.filtered["warnings"]
    )

    # Run with merge_if_exists, as well as serializer and deserializer opts
    # deserializer opts will be used for string interpolation of the %(x)s
    # that was written to the file with data1 (i.e. bar should become baz)
    ret = file.serialize(
        name=str(name),
        dataset=data2,
        formatter="configparser",
        merge_if_exists=True,
        serializer_opts=[{"defaults": {"y": "not_used"}}],
        deserializer_opts=[{"defaults": {"x": "baz"}}],
    )
    assert ret.result is True

    serialized_data = salt.serializers.configparser.deserialize(name.read_text())

    # If this test fails, this debug logging will help tell us how the
    # serialized data differs from what was serialized.
    log.debug("serialized_data = %r", serialized_data)
    log.debug("merged = %r", merged)
    # serializing with a default of 'y' will add y = not_used into foo
    assert serialized_data["foo"]["y"] == merged["foo"]["y"]
    # deserializing with default of x = baz will perform interpolation on %(x)s
    # and bar will then = baz
    assert serialized_data["foo"]["bar"] == merged["foo"]["bar"]


def test_serializer_plist_binary_file_open(file, tmp_path):
    """
    Test the serialization and deserialization of plists which should include
    the "rb" file open arguments change specifically for this formatter to handle
    binary plists.
    """
    name = tmp_path / "testfile"
    data1 = {"foo": {"bar": "%(x)s"}}
    data2 = {"foo": {"abc": 123}}
    merged = {"foo": {"abc": 123, "bar": "%(x)s"}}

    ret = file.serialize(
        name=str(name),
        dataset=data1,
        formatter="plist",
        serializer_opts=[{"fmt": "FMT_BINARY"}],
    )
    assert ret.result is True

    # Run with merge_if_exists so we test the deserializer.
    ret = file.serialize(
        name=str(name),
        dataset=data2,
        formatter="plist",
        merge_if_exists=True,
        serializer_opts=[{"fmt": "FMT_BINARY"}],
    )
    assert ret.result is True

    serialized_data = salt.serializers.plist.deserialize(name.read_bytes())

    # make sure our serialized data matches what we expect
    assert serialized_data["foo"] == merged["foo"]


def test_serializer_plist_file_open(file, tmp_path):
    """
    Test the serialization and deserialization of non binary plists with
    the new line concatenation.
    """
    name = tmp_path / "testfile"
    data1 = {"foo": {"bar": "%(x)s"}}
    data2 = {"foo": {"abc": 123}}
    merged = {"foo": {"abc": 123, "bar": "%(x)s"}}

    ret = file.serialize(name=str(name), dataset=data1, formatter="plist")
    assert ret.result is True

    # Run with merge_if_exists so we test the deserializer.
    ret = file.serialize(
        name=str(name),
        dataset=data2,
        formatter="plist",
        merge_if_exists=True,
    )
    assert ret.result is True

    serialized_data = salt.serializers.plist.deserialize(name.read_bytes())
    # make sure our serialized data matches what we expect
    assert serialized_data["foo"] == merged["foo"]
