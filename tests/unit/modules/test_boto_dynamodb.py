import salt.modules.boto_dynamodb as boto_dynamodb
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase

ARN = "arn:aws:dynamodb:us-east-1:012345678901:table/my-table"
TAGS = {"foo": "bar", "hello": "world"}
TAGS_AS_LIST = [{"Key": "foo", "Value": "bar"}, {"Key": "hello", "Value": "world"}]


class DummyConn:
    def __init__(self):
        self.list_tags_of_resource = MagicMock(
            return_value={"Tags": TAGS_AS_LIST, "NextToken": None}
        )
        self.tag_resource = MagicMock(return_value=True)
        self.untag_resource = MagicMock(return_value=True)


class BotoDynamoDBTestCase(TestCase, LoaderModuleMockMixin):
    """
    TestCase for salt.modules.boto_elb module
    """

    def setup_loader_modules(self):
        return {boto_dynamodb: {"__opts__": {}, "__utils__": {}}}

    def test_list_tags_of_resource(self):
        """
        Test that the correct API call is made and correct return format is
        returned.
        """
        conn = DummyConn()
        utils = {"boto3.get_connection": MagicMock(return_value=conn)}
        with patch.dict(boto_dynamodb.__utils__, utils):
            ret = boto_dynamodb.list_tags_of_resource(resource_arn=ARN)

        assert ret == TAGS, ret
        conn.list_tags_of_resource.assert_called_once_with(
            ResourceArn=ARN, NextToken=""
        )

    def test_tag_resource(self):
        """
        Test that the correct API call is made and correct return format is
        returned.
        """
        conn = DummyConn()
        utils = {"boto3.get_connection": MagicMock(return_value=conn)}
        with patch.dict(boto_dynamodb.__utils__, utils):
            ret = boto_dynamodb.tag_resource(resource_arn=ARN, tags=TAGS)

        assert ret is True, ret
        # Account for differing dict iteration order among Python versions by
        # being more explicit in asserts.
        assert len(conn.tag_resource.mock_calls) == 1
        call = conn.tag_resource.mock_calls[0]
        # No positional args
        assert not call.args
        # Make sure there aren't any additional kwargs beyond what we expect
        assert len(call.kwargs) == 2
        assert call.kwargs["ResourceArn"] == ARN
        # Make sure there aren't any additional tags beyond what we expect
        assert len(call.kwargs["Tags"]) == 2
        for tag_dict in TAGS_AS_LIST:
            assert tag_dict in call.kwargs["Tags"]

    def test_untag_resource(self):
        """
        Test that the correct API call is made and correct return format is
        returned.
        """
        conn = DummyConn()
        utils = {"boto3.get_connection": MagicMock(return_value=conn)}
        with patch.dict(boto_dynamodb.__utils__, utils):
            ret = boto_dynamodb.untag_resource(resource_arn=ARN, tag_keys=sorted(TAGS))

        assert ret is True, ret
        conn.untag_resource.assert_called_once_with(
            ResourceArn=ARN, TagKeys=sorted(TAGS)
        )
