"""
unittests for yaml outputter
"""
import pytest

import salt.output.yaml_out as yaml
from tests.support.mock import patch


@pytest.fixture
def configure_loader_modules():
    return {yaml: {}}


@pytest.fixture
def data():
    return {"test": "two", "example": "one"}


def test_default_output(data):
    ret = yaml.output(data)
    expect = "example: one\ntest: two\n"
    assert expect == ret


def test_negative_int_output(data):
    with patch.dict(yaml.__opts__, {"output_indent": -1}):
        ret = yaml.output(data)
        expect = "{example: one, test: two}\n"
        assert expect == ret
