"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""
import pytest
import salt.states.aws_sqs as aws_sqs
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {aws_sqs: {}}


def test_exists():
    """
    Test to ensure the SQS queue exists.
    """
    name = "myqueue"
    region = "eu-west-1"

    ret = {"name": name, "result": None, "changes": {}, "comment": ""}

    mock = MagicMock(side_effect=[False, True])
    with patch.dict(aws_sqs.__salt__, {"aws_sqs.queue_exists": mock}):
        comt = "AWS SQS queue {} is set to be created".format(name)
        ret.update({"comment": comt})
        with patch.dict(aws_sqs.__opts__, {"test": True}):
            assert aws_sqs.exists(name, region) == ret

        comt = "{} exists in {}".format(name, region)
        ret.update({"comment": comt, "result": True})
        assert aws_sqs.exists(name, region) == ret


def test_absent():
    """
    Test to remove the named SQS queue if it exists.
    """
    name = "myqueue"
    region = "eu-west-1"

    ret = {"name": name, "result": None, "changes": {}, "comment": ""}

    mock = MagicMock(side_effect=[True, False])
    with patch.dict(aws_sqs.__salt__, {"aws_sqs.queue_exists": mock}):
        comt = "AWS SQS queue {} is set to be removed".format(name)
        ret.update({"comment": comt})
        with patch.dict(aws_sqs.__opts__, {"test": True}):
            assert aws_sqs.absent(name, region) == ret

        comt = "{} does not exist in {}".format(name, region)
        ret.update({"comment": comt, "result": True})
        assert aws_sqs.absent(name, region) == ret
