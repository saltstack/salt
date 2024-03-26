"""
    Test cases for salt.modules.boto_dynamodb
"""

import pytest

import salt.modules.boto_dynamodb as boto_dynamodb
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {boto_dynamodb: {"__opts__": {}, "__utils__": {}}}


@pytest.fixture
def arn():
    return "arn:aws:dynamodb:us-east-1:012345678901:table/my-table"


@pytest.fixture
def tags():
    return {"foo": "bar", "hello": "world"}


@pytest.fixture
def tags_as_list():
    return [{"Key": "foo", "Value": "bar"}, {"Key": "hello", "Value": "world"}]


class DummyConn:
    def __init__(self, tags_as_list):
        self.list_tags_of_resource = MagicMock(
            return_value={"Tags": tags_as_list, "NextToken": None}
        )
        self.tag_resource = MagicMock(return_value=True)
        self.untag_resource = MagicMock(return_value=True)


def test_list_tags_of_resource(arn, tags, tags_as_list):
    """
    Test that the correct API call is made and correct return format is
    returned.
    """
    conn = DummyConn(tags_as_list)
    utils = {"boto3.get_connection": MagicMock(return_value=conn)}
    with patch.dict(boto_dynamodb.__utils__, utils):
        ret = boto_dynamodb.list_tags_of_resource(resource_arn=arn)

    assert ret == tags, ret
    conn.list_tags_of_resource.assert_called_once_with(ResourceArn=arn, NextToken="")


def test_tag_resource(arn, tags, tags_as_list):
    """
    Test that the correct API call is made and correct return format is
    returned.
    """
    conn = DummyConn(tags_as_list)
    utils = {"boto3.get_connection": MagicMock(return_value=conn)}
    with patch.dict(boto_dynamodb.__utils__, utils):
        ret = boto_dynamodb.tag_resource(resource_arn=arn, tags=tags)

    assert ret is True, ret
    # Account for differing dict iteration order among Python versions by
    # being more explicit in asserts.
    assert len(conn.tag_resource.mock_calls) == 1
    call = conn.tag_resource.mock_calls[0]
    # No positional args
    assert not call.args
    # Make sure there aren't any additional kwargs beyond what we expect
    assert len(call.kwargs) == 2
    assert call.kwargs["ResourceArn"] == arn
    # Make sure there aren't any additional tags beyond what we expect
    assert len(call.kwargs["Tags"]) == 2
    for tag_dict in tags_as_list:
        assert tag_dict in call.kwargs["Tags"]


def test_untag_resource(arn, tags, tags_as_list):
    """
    Test that the correct API call is made and correct return format is
    returned.
    """
    conn = DummyConn(tags_as_list)
    utils = {"boto3.get_connection": MagicMock(return_value=conn)}
    with patch.dict(boto_dynamodb.__utils__, utils):
        ret = boto_dynamodb.untag_resource(resource_arn=arn, tag_keys=sorted(tags))

    assert ret is True, ret
    conn.untag_resource.assert_called_once_with(ResourceArn=arn, TagKeys=sorted(tags))
