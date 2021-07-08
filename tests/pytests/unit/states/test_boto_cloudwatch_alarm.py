"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest
import salt.states.boto_cloudwatch_alarm as boto_cloudwatch_alarm
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {boto_cloudwatch_alarm: {}}


def test_present():
    """
    Test to ensure the cloudwatch alarm exists.
    """
    name = "my test alarm"
    attributes = {
        "metric": "ApproximateNumberOfMessagesVisible",
        "namespace": "AWS/SQS",
    }

    ret = {"name": name, "result": None, "changes": {}, "comment": ""}

    mock = MagicMock(side_effect=[["ok_actions"], [], []])
    mock_bool = MagicMock(return_value=True)
    with patch.dict(
        boto_cloudwatch_alarm.__salt__,
        {
            "boto_cloudwatch.get_alarm": mock,
            "boto_cloudwatch.create_or_update_alarm": mock_bool,
        },
    ):
        with patch.dict(boto_cloudwatch_alarm.__opts__, {"test": True}):
            comt = "alarm my test alarm is to be created/updated."
            ret.update({"comment": comt})
            assert boto_cloudwatch_alarm.present(name, attributes) == ret

            comt = "alarm my test alarm is to be created/updated."
            ret.update({"comment": comt})
            assert boto_cloudwatch_alarm.present(name, attributes) == ret

        with patch.dict(boto_cloudwatch_alarm.__opts__, {"test": False}):
            changes = {
                "new": {
                    "metric": "ApproximateNumberOfMessagesVisible",
                    "namespace": "AWS/SQS",
                }
            }
            comt = "alarm my test alarm is to be created/updated."
            ret.update({"changes": changes, "comment": "", "result": True})
            assert boto_cloudwatch_alarm.present(name, attributes) == ret


def test_absent():
    """
    Test to ensure the named cloudwatch alarm is deleted.
    """
    name = "my test alarm"

    ret = {"name": name, "result": None, "changes": {}, "comment": ""}

    mock = MagicMock(side_effect=[True, False])
    with patch.dict(
        boto_cloudwatch_alarm.__salt__, {"boto_cloudwatch.get_alarm": mock}
    ):
        with patch.dict(boto_cloudwatch_alarm.__opts__, {"test": True}):
            comt = "alarm {} is set to be removed.".format(name)
            ret.update({"comment": comt})
            assert boto_cloudwatch_alarm.absent(name) == ret

            comt = "my test alarm does not exist in None."
            ret.update({"comment": comt, "result": True})
            assert boto_cloudwatch_alarm.absent(name) == ret
