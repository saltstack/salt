"""
unittests for json outputter
"""
import pytest

import salt.output.json_out as json_out
import salt.utils.stringutils
from tests.support.mock import patch


@pytest.fixture
def configure_loader_modules():
    return {json_out: {}}


@pytest.fixture
def data():
    return {"test": "two", "example": "one"}


def test_default_output(data):
    ret = json_out.output(data)
    assert '"test": "two"' in ret
    assert '"example": "one"' in ret


def test_pretty_output(data):
    with patch.dict(json_out.__opts__, {"output_indent": "pretty"}):
        ret = json_out.output(data)
        assert '"test": "two"' in ret
        assert '"example": "one"' in ret


def test_indent_output(data):
    with patch.dict(json_out.__opts__, {"output_indent": 2}):
        ret = json_out.output(data)
        assert '"test": "two"' in ret
        assert '"example": "one"' in ret


def test_negative_zero_output(data):
    with patch.dict(json_out.__opts__, {"output_indent": 0}):
        ret = json_out.output(data)
        assert '"test": "two"' in ret
        assert '"example": "one"' in ret


def test_negative_int_output(data):
    with patch.dict(json_out.__opts__, {"output_indent": -1}):
        ret = json_out.output(data)
        assert '"test": "two"' in ret
        assert '"example": "one"' in ret


def test_unicode_output():
    with patch.dict(json_out.__opts__, {"output_indent": "pretty"}):
        decoded = {"test": "Д", "example": "one"}
        encoded = {"test": salt.utils.stringutils.to_str("Д"), "example": "one"}
        # json.dumps on Python 2 adds a space before a newline while in the
        # process of dumping a dictionary.
        expected = '{\n    "example": "one",\n    "test": "Д"\n}'
        assert json_out.output(decoded) == expected
        assert json_out.output(encoded) == expected
