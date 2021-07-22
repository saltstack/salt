"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""

import logging

import pytest  # pylint: disable=unused-import
from salt.utils.decorators import state as statedecorators

log = logging.getLogger(__name__)


def test_state_output_check_changes_is_dict():
    """
    Test that changes key contains a dictionary.
    :return:
    """
    data = {"changes": []}
    out = statedecorators.OutputUnifier("content_check")(lambda: data)()
    assert "'Changes' should be a dictionary" in out["comment"]
    assert not out["result"]


def test_state_output_check_return_is_dict():
    """
    Test for the entire return is a dictionary
    :return:
    """
    data = ["whatever"]
    out = statedecorators.OutputUnifier("content_check")(lambda: data)()
    assert "Malformed state return. Data must be a dictionary type" in out["comment"]
    assert not out["result"]


def test_state_output_check_return_has_nrc():
    """
    Test for name/result/comment keys are inside the return.
    :return:
    """
    data = {"arbitrary": "data", "changes": {}}
    out = statedecorators.OutputUnifier("content_check")(lambda: data)()
    assert (
        " The following keys were not present in the state return: name, result, comment"
        in out["comment"]
    )
    assert not out["result"]


def test_state_output_unifier_comment_is_not_list():
    """
    Test for output is unified so the comment is converted to a multi-line string
    :return:
    """
    data = {
        "comment": ["data", "in", "the", "list"],
        "changes": {},
        "name": None,
        "result": "fantastic!",
    }
    expected = {
        "comment": "data\nin\nthe\nlist",
        "changes": {},
        "name": None,
        "result": True,
    }
    assert statedecorators.OutputUnifier("unify")(lambda: data)() == expected

    data = {
        "comment": ["data", "in", "the", "list"],
        "changes": {},
        "name": None,
        "result": None,
    }
    expected = "data\nin\nthe\nlist"
    assert statedecorators.OutputUnifier("unify")(lambda: data)()["comment"] == expected


def test_state_output_unifier_result_converted_to_true():
    """
    Test for output is unified so the result is converted to True
    :return:
    """
    data = {
        "comment": ["data", "in", "the", "list"],
        "changes": {},
        "name": None,
        "result": "Fantastic",
    }
    assert statedecorators.OutputUnifier("unify")(lambda: data)()["result"] is True


def test_state_output_unifier_result_converted_to_false():
    """
    Test for output is unified so the result is converted to False
    :return:
    """
    data = {
        "comment": ["data", "in", "the", "list"],
        "changes": {},
        "name": None,
        "result": "",
    }
    assert statedecorators.OutputUnifier("unify")(lambda: data)()["result"] is False
