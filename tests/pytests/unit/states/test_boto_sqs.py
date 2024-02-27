"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import textwrap

import pytest

import salt.config
import salt.loader
import salt.states.boto_sqs as boto_sqs
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules(minion_opts):
    utils = salt.loader.utils(
        minion_opts,
        whitelist=["boto3", "yaml", "args", "systemd", "path", "platform"],
        context={},
    )
    return {boto_sqs: {"__utils__": utils}}


def test_present():
    """
    Test to ensure the SQS queue exists.
    """
    name = "mysqs"
    attributes = {"DelaySeconds": 20}
    base_ret = {"name": name, "changes": {}}

    mock = MagicMock(
        side_effect=[{"result": b} for b in [False, False, True, True]],
    )
    mock_bool = MagicMock(return_value={"error": "create error"})
    mock_attr = MagicMock(return_value={"result": {}})
    with patch.dict(
        boto_sqs.__salt__,
        {
            "boto_sqs.exists": mock,
            "boto_sqs.create": mock_bool,
            "boto_sqs.get_attributes": mock_attr,
        },
    ):
        with patch.dict(boto_sqs.__opts__, {"test": False}):
            comt = [
                "Failed to create SQS queue {}: create error".format(
                    name,
                )
            ]
            ret = base_ret.copy()
            ret.update({"result": False, "comment": comt})
            assert boto_sqs.present(name) == ret

        with patch.dict(boto_sqs.__opts__, {"test": True}):
            comt = [f"SQS queue {name} is set to be created."]
            ret = base_ret.copy()
            ret.update(
                {
                    "result": None,
                    "comment": comt,
                    "changes": {"old": None, "new": "mysqs"},
                }
            )
            assert boto_sqs.present(name) == ret
            diff = textwrap.dedent(
                """\
                ---
                +++
                @@ -1 +1 @@
                -{}
                +DelaySeconds: 20

            """
            ).splitlines()
            for idx in (0, 1):
                diff[idx] += " "
            diff = "\n".join(diff)

            comt = [
                "SQS queue mysqs present.",
                "Attribute(s) DelaySeconds set to be updated:\n{}".format(
                    diff,
                ),
            ]
            ret.update({"comment": comt, "changes": {"attributes": {"diff": diff}}})
            assert boto_sqs.present(name, attributes) == ret

        comt = ["SQS queue mysqs present."]
        ret = base_ret.copy()
        ret.update({"result": True, "comment": comt})
        assert boto_sqs.present(name) == ret


def test_absent():
    """
    Test to ensure the named sqs queue is deleted.
    """
    name = "test.example.com."
    base_ret = {"name": name, "changes": {}}

    mock = MagicMock(side_effect=[{"result": False}, {"result": True}])
    with patch.dict(boto_sqs.__salt__, {"boto_sqs.exists": mock}):
        comt = f"SQS queue {name} does not exist in None."
        ret = base_ret.copy()
        ret.update({"result": True, "comment": comt})
        assert boto_sqs.absent(name) == ret

        with patch.dict(boto_sqs.__opts__, {"test": True}):
            comt = f"SQS queue {name} is set to be removed."
            ret = base_ret.copy()
            ret.update(
                {
                    "result": None,
                    "comment": comt,
                    "changes": {"old": name, "new": None},
                }
            )
            assert boto_sqs.absent(name) == ret
