"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.states.boto_sns as boto_sns
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {boto_sns: {}}


def test_present():
    """
    Test to ensure the SNS topic exists.
    """
    name = "test.example.com."

    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    mock = MagicMock(side_effect=[True, False, False])
    mock_bool = MagicMock(return_value=False)
    with patch.dict(
        boto_sns.__salt__, {"boto_sns.exists": mock, "boto_sns.create": mock_bool}
    ):
        comt = f"AWS SNS topic {name} present."
        ret.update({"comment": comt})
        assert boto_sns.present(name) == ret

        with patch.dict(boto_sns.__opts__, {"test": True}):
            comt = f"AWS SNS topic {name} is set to be created."
            ret.update({"comment": comt, "result": None})
            assert boto_sns.present(name) == ret

        with patch.dict(boto_sns.__opts__, {"test": False}):
            comt = f"Failed to create {name} AWS SNS topic"
            ret.update({"comment": comt, "result": False})
            assert boto_sns.present(name) == ret


def test_absent():
    """
    Test to ensure the named sns topic is deleted.
    """
    name = "test.example.com."

    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    exists_mock = MagicMock(side_effect=[False, True, True, True, True, True, True])
    with patch.dict(boto_sns.__salt__, {"boto_sns.exists": exists_mock}):
        # tests topic already absent
        comt = f"AWS SNS topic {name} does not exist."
        ret.update({"comment": comt})
        assert boto_sns.absent(name) == ret

        with patch.dict(boto_sns.__opts__, {"test": True}):
            # tests topic present, test option, unsubscribe is False
            comt = (
                "AWS SNS topic {} is set to be removed.  "
                "0 subscription(s) will be removed.".format(name)
            )
            ret.update({"comment": comt, "result": None})
            assert boto_sns.absent(name) == ret

        subscriptions = [
            dict(
                Endpoint="arn:aws:lambda:us-west-2:123456789:function:test",
                Owner=123456789,
                Protocol="Lambda",
                TopicArn="arn:aws:sns:us-west-2:123456789:test",
                SubscriptionArn="arn:aws:sns:us-west-2:123456789:test:some_uuid",
            )
        ]
        with patch.dict(boto_sns.__opts__, {"test": True}):
            subs_mock = MagicMock(return_value=subscriptions)
            with patch.dict(
                boto_sns.__salt__,
                {"boto_sns.get_all_subscriptions_by_topic": subs_mock},
            ):
                # tests topic present, 1 subscription, test option, unsubscribe is True
                comt = (
                    "AWS SNS topic {} is set to be removed.  "
                    "1 subscription(s) will be removed.".format(name)
                )
                ret.update({"comment": comt, "result": None})
                assert boto_sns.absent(name, unsubscribe=True) == ret

        subs_mock = MagicMock(return_value=subscriptions)
        unsubscribe_mock = MagicMock(side_effect=[True, False])
        with patch.dict(boto_sns.__salt__, {"boto_sns.unsubscribe": unsubscribe_mock}):
            with patch.dict(
                boto_sns.__salt__,
                {"boto_sns.get_all_subscriptions_by_topic": subs_mock},
            ):
                delete_mock = MagicMock(side_effect=[True, True, True, False])
                with patch.dict(boto_sns.__salt__, {"boto_sns.delete": delete_mock}):
                    # tests topic present, unsubscribe flag True, unsubscribe succeeded,
                    # delete succeeded
                    comt = f"AWS SNS topic {name} deleted."
                    ret.update(
                        {
                            "changes": {
                                "new": None,
                                "old": {"topic": name, "subscriptions": subscriptions},
                            },
                            "result": True,
                            "comment": comt,
                        }
                    )
                    assert boto_sns.absent(name, unsubscribe=True) == ret

                    # tests topic present, unsubscribe flag True, unsubscribe fails,
                    # delete succeeded
                    ret.update(
                        {
                            "changes": {
                                "new": {"subscriptions": subscriptions},
                                "old": {"topic": name, "subscriptions": subscriptions},
                            },
                            "result": True,
                            "comment": comt,
                        }
                    )
                    assert boto_sns.absent(name, unsubscribe=True) == ret

                    # tests topic present, unsubscribe flag False, delete succeeded
                    ret.update(
                        {
                            "changes": {"new": None, "old": {"topic": name}},
                            "result": True,
                            "comment": comt,
                        }
                    )
                    assert boto_sns.absent(name) == ret

                    # tests topic present, unsubscribe flag False, delete failed
                    comt = f"Failed to delete {name} AWS SNS topic."
                    ret.update({"changes": {}, "result": False, "comment": comt})
                    assert boto_sns.absent(name) == ret
