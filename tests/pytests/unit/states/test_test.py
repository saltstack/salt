"""
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
"""

import pytest
import salt.states.test as test
from salt.exceptions import SaltInvocationError
from salt.utils.odict import OrderedDict
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {test: {"__low__": {"__reqs__": {"watch": ""}}}}


def test_succeed_without_changes():
    """
    Test to returns successful.
    """
    ret = {"name": "salt", "changes": {}, "result": True, "comment": ""}
    with patch.dict(test.__opts__, {"test": False}):
        ret.update({"comment": "Success!"})
        assert test.succeed_without_changes("salt") == ret

    with patch.dict(test.__opts__, {"test": False}):
        ret.update({"comment": "A success comment!"})
        assert test.succeed_without_changes("salt", comment="A success comment!") == ret


def test_fail_without_changes():
    """
    Test to returns failure.
    """
    ret = {"name": "salt", "changes": {}, "result": False, "comment": ""}
    with patch.dict(test.__opts__, {"test": False}):
        ret.update({"comment": "Failure!"})
        assert test.fail_without_changes("salt") == ret

    with patch.dict(test.__opts__, {"test": False}):
        ret.update({"comment": "A failure comment!"})
        assert test.fail_without_changes("salt", comment="A failure comment!") == ret

    with patch.dict(test.__opts__, {"test": True}):
        ret.update({"comment": "If we weren't testing, this would be a failure!"})
        assert test.fail_without_changes("salt") == ret


def test_succeed_with_changes():
    """
    Test to returns successful and changes is not empty
    """
    ret = {"name": "salt", "changes": {}, "result": False, "comment": ""}
    with patch.dict(test.__opts__, {"test": False}):
        ret.update(
            {
                "changes": {
                    "testing": {
                        "new": "Something pretended to change",
                        "old": "Unchanged",
                    }
                },
                "comment": "Success!",
                "result": True,
            }
        )
        assert test.succeed_with_changes("salt") == ret

    with patch.dict(test.__opts__, {"test": False}):
        ret.update(
            {
                "changes": {
                    "testing": {
                        "new": "Something pretended to change",
                        "old": "Unchanged",
                    }
                },
                "comment": "A success comment!",
                "result": True,
            }
        )
        assert test.succeed_with_changes("salt", comment="A success comment!") == ret

    with patch.dict(test.__opts__, {"test": True}):
        ret.update(
            {
                "changes": {
                    "testing": {
                        "new": "Something pretended to change",
                        "old": "Unchanged",
                    }
                },
                "comment": (
                    "If we weren't testing, this would be successful with changes"
                ),
                "result": None,
            }
        )
        assert test.succeed_with_changes("salt", comment="A success comment!") == ret


def test_fail_with_changes():
    """
    Test to returns failure and changes is not empty.
    """
    ret = {"name": "salt", "changes": {}, "result": False, "comment": ""}
    with patch.dict(test.__opts__, {"test": False}):
        ret.update(
            {
                "changes": {
                    "testing": {
                        "new": "Something pretended to change",
                        "old": "Unchanged",
                    }
                },
                "comment": "Failure!",
                "result": False,
            }
        )
        assert test.fail_with_changes("salt") == ret

    with patch.dict(test.__opts__, {"test": False}):
        ret.update(
            {
                "changes": {
                    "testing": {
                        "new": "Something pretended to change",
                        "old": "Unchanged",
                    }
                },
                "comment": "A failure comment!",
                "result": False,
            }
        )
        assert test.fail_with_changes("salt", comment="A failure comment!") == ret

    with patch.dict(test.__opts__, {"test": True}):
        ret.update(
            {
                "changes": {
                    "testing": {
                        "new": "Something pretended to change",
                        "old": "Unchanged",
                    }
                },
                "comment": "If we weren't testing, this would be failed with changes",
                "result": None,
            }
        )
        assert test.fail_with_changes("salt", comment="A failure comment!") == ret


def test_configurable_test_state():
    """
    Test test.configurable_test_state with and without comment
    """
    mock_name = "cheese_shop"
    mock_comment = "I'm afraid we're fresh out of Red Leicester sir."
    mock_changes = {
        "testing": {"old": "Unchanged", "new": "Something pretended to change"}
    }

    with patch.dict(test.__opts__, {"test": False}):
        mock_ret = {
            "name": mock_name,
            "changes": mock_changes,
            "result": True,
            "comment": "",
        }
        ret = test.configurable_test_state(mock_name)
        assert ret == mock_ret

    with patch.dict(test.__opts__, {"test": False}):
        mock_ret = {
            "name": mock_name,
            "changes": mock_changes,
            "result": True,
            "comment": mock_comment,
        }
        ret = test.configurable_test_state(mock_name, comment=mock_comment)
        assert ret == mock_ret


def test_configurable_test_state_changes():
    """
    Test test.configurable_test_state with permutations of changes and with
    comment
    """
    mock_name = "cheese_shop"
    mock_comment = "I'm afraid we're fresh out of Red Leicester sir."
    mock_changes = {
        "testing": {"old": "Unchanged", "new": "Something pretended to change"}
    }

    with patch.dict(test.__opts__, {"test": False}):
        ret = test.configurable_test_state(
            mock_name, changes="Random", comment=mock_comment
        )
        assert ret["name"] == mock_name
        assert ret["changes"] in [mock_changes, {}]
        assert ret["result"] is True
        assert ret["comment"] == mock_comment

    with patch.dict(test.__opts__, {"test": False}):
        mock_ret = {
            "name": mock_name,
            "changes": mock_changes,
            "result": True,
            "comment": mock_comment,
        }
        ret = test.configurable_test_state(
            mock_name, changes=True, comment=mock_comment
        )
        assert ret == mock_ret

    with patch.dict(test.__opts__, {"test": False}):
        mock_ret = {
            "name": mock_name,
            "changes": {},
            "result": True,
            "comment": mock_comment,
        }
        ret = test.configurable_test_state(
            mock_name, changes=False, comment=mock_comment
        )
        assert ret == mock_ret

    with patch.dict(test.__opts__, {"test": False}):
        pytest.raises(
            SaltInvocationError,
            test.configurable_test_state,
            mock_name,
            changes="Cheese",
        )


def test_configurable_test_state_result():
    """
    Test test.configurable_test_state with permutations of result and with
    comment
    """
    mock_name = "cheese_shop"
    mock_comment = "I'm afraid we're fresh out of Red Leicester sir."
    mock_changes = {
        "testing": {"old": "Unchanged", "new": "Something pretended to change"}
    }

    with patch.dict(test.__opts__, {"test": False}):
        ret = test.configurable_test_state(
            mock_name, result="Random", comment=mock_comment
        )
        assert ret["name"] == mock_name
        assert ret["changes"] == mock_changes
        assert ret["result"] in [True, False]
        assert ret["comment"] == mock_comment

    with patch.dict(test.__opts__, {"test": False}):
        mock_ret = {
            "name": mock_name,
            "changes": mock_changes,
            "result": True,
            "comment": mock_comment,
        }
        ret = test.configurable_test_state(mock_name, result=True, comment=mock_comment)
        assert ret == mock_ret

    with patch.dict(test.__opts__, {"test": False}):
        mock_ret = {
            "name": mock_name,
            "changes": mock_changes,
            "result": False,
            "comment": mock_comment,
        }
        ret = test.configurable_test_state(
            mock_name, result=False, comment=mock_comment
        )
        assert ret == mock_ret

    with patch.dict(test.__opts__, {"test": False}):
        pytest.raises(
            SaltInvocationError,
            test.configurable_test_state,
            mock_name,
            result="Cheese",
        )


def test_configurable_test_state_warnings():
    """
    Test test.configurable_test_state with and without warnings
    """
    # Configure mock parameters
    mock_name = "cheese_shop"
    mock_comment = "I'm afraid we're fresh out of Red Leicester sir."
    mock_warning = "Today the van broke down."
    mock_warning_list = [mock_warning, "Oooooooooohhh........!"]
    mock_changes = {
        "testing": {"old": "Unchanged", "new": "Something pretended to change"}
    }

    with patch.dict(test.__opts__, {"test": False}):
        mock_ret = {
            "name": mock_name,
            "changes": mock_changes,
            "result": True,
            "comment": "",
        }
        ret = test.configurable_test_state(mock_name)
        assert ret == mock_ret

    with patch.dict(test.__opts__, {"test": False}):
        mock_ret = {
            "name": mock_name,
            "changes": mock_changes,
            "result": True,
            "comment": "",
            "warnings": mock_warning_list,
        }
        ret = test.configurable_test_state(mock_name, warnings=mock_warning_list)
        assert ret == mock_ret

    with patch.dict(test.__opts__, {"test": False}):
        mock_ret = {
            "name": mock_name,
            "changes": mock_changes,
            "result": True,
            "comment": "",
            "warnings": ["Today the van broke down."],
        }
        ret = test.configurable_test_state(mock_name, warnings=mock_warning)

        assert ret == mock_ret


def test_configurable_test_state_test():
    """
    Test test.configurable_test_state with test=True with and without
    comment
    """
    mock_name = "cheese_shop"
    mock_comment = "I'm afraid we're fresh out of Red Leicester sir."
    mock_changes = {
        "testing": {"old": "Unchanged", "new": "Something pretended to change"}
    }

    with patch.dict(test.__opts__, {"test": True}):
        mock_ret = {
            "name": mock_name,
            "changes": mock_changes,
            "result": None,
            "comment": "This is a test",
        }
        ret = test.configurable_test_state(mock_name)
        assert ret == mock_ret

    with patch.dict(test.__opts__, {"test": True}):
        mock_ret = {
            "name": mock_name,
            "changes": mock_changes,
            "result": None,
            "comment": mock_comment,
        }
        ret = test.configurable_test_state(mock_name, comment=mock_comment)
        assert ret == mock_ret

    with patch.dict(test.__opts__, {"test": True}):
        mock_ret = {
            "name": mock_name,
            "changes": mock_changes,
            "result": None,
            "comment": mock_comment,
        }
        ret = test.configurable_test_state(
            mock_name, changes=True, comment=mock_comment
        )
        assert ret == mock_ret

    with patch.dict(test.__opts__, {"test": True}):
        mock_ret = {
            "name": mock_name,
            "changes": {},
            "result": True,
            "comment": mock_comment,
        }
        ret = test.configurable_test_state(
            mock_name, changes=False, comment=mock_comment
        )
        assert ret == mock_ret


def test_mod_watch():
    """
    Test to call this function via a watch statement
    """
    ret = {"name": "salt", "changes": {}, "result": True, "comment": ""}
    ret.update(
        {
            "changes": {"Requisites with changes": []},
            "comment": "Watch statement fired.",
        }
    )
    assert test.mod_watch("salt") == ret


def test_check_pillar_present():
    """
    Test to ensure the check_pillar function works properly with the 'present'
    keyword in the absence of a 'type' keyword.
    """
    ret = {"name": "salt", "changes": {}, "result": True, "comment": ""}
    pillar_return = "I am a pillar."
    pillar_mock = MagicMock(return_value=pillar_return)
    with patch.dict(test.__salt__, {"pillar.get": pillar_mock}):
        assert test.check_pillar("salt", present="my_pillar") == ret


def test_check_pillar_string():
    """
    Test to ensure the check_pillar function works properly with the 'key_type'
    checks, using the string key_type.
    """
    ret = {"name": "salt", "changes": {}, "result": True, "comment": ""}
    pillar_return = "I am a pillar."
    pillar_mock = MagicMock(return_value=pillar_return)
    with patch.dict(test.__salt__, {"pillar.get": pillar_mock}):
        assert test.check_pillar("salt", string="my_pillar") == ret
    pillar_return = "I am a pillar."
    pillar_mock = MagicMock(return_value=pillar_return)
    with patch.dict(test.__salt__, {"pillar.get": pillar_mock}):
        assert test.check_pillar("salt", string="my_pillar") == ret
    pillar_return = {"this": "dictionary"}
    pillar_mock = MagicMock(return_value=pillar_return)
    with patch.dict(test.__salt__, {"pillar.get": pillar_mock}):
        assert not test.check_pillar("salt", string="my_pillar")["result"]
    pillar_return = ["I am a pillar."]
    pillar_mock = MagicMock(return_value=pillar_return)
    with patch.dict(test.__salt__, {"pillar.get": pillar_mock}):
        assert not test.check_pillar("salt", string="my_pillar")["result"]
    # With a boolean
    pillar_return = True
    pillar_mock = MagicMock(return_value=pillar_return)
    with patch.dict(test.__salt__, {"pillar.get": pillar_mock}):
        assert not test.check_pillar("salt", string="my_pillar")["result"]
    pillar_return = 1
    pillar_mock = MagicMock(return_value=pillar_return)
    with patch.dict(test.__salt__, {"pillar.get": pillar_mock}):
        assert not test.check_pillar("salt", string="my_pillar")["result"]


def test_check_pillar_dictionary():
    """
    Test to ensure the check_pillar function works properly with the 'key_type'
    checks, using the dictionary key_type.
    """
    ret = {"name": "salt", "changes": {}, "result": True, "comment": ""}
    pillar_return = {"this": "dictionary"}
    pillar_mock = MagicMock(return_value=pillar_return)
    with patch.dict(test.__salt__, {"pillar.get": pillar_mock}):
        assert test.check_pillar("salt", dictionary="my_pillar") == ret
    pillar_return = OrderedDict({"this": "dictionary"})
    pillar_mock = MagicMock(return_value=pillar_return)
    with patch.dict(test.__salt__, {"pillar.get": pillar_mock}):
        assert test.check_pillar("salt", dictionary="my_pillar") == ret
    pillar_return = "I am a pillar."
    pillar_mock = MagicMock(return_value=pillar_return)
    with patch.dict(test.__salt__, {"pillar.get": pillar_mock}):
        assert not test.check_pillar("salt", dictionary="my_pillar")["result"]
    pillar_return = ["I am a pillar."]
    pillar_mock = MagicMock(return_value=pillar_return)
    with patch.dict(test.__salt__, {"pillar.get": pillar_mock}):
        assert not test.check_pillar("salt", dictionary="my_pillar")["result"]
    pillar_return = True
    pillar_mock = MagicMock(return_value=pillar_return)
    with patch.dict(test.__salt__, {"pillar.get": pillar_mock}):
        assert not test.check_pillar("salt", dictionary="my_pillar")["result"]
    pillar_return = 1
    pillar_mock = MagicMock(return_value=pillar_return)
    with patch.dict(test.__salt__, {"pillar.get": pillar_mock}):
        assert not test.check_pillar("salt", dictionary="my_pillar")["result"]
