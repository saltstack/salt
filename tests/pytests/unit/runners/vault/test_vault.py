"""
Unit tests for the Vault runner
"""


import logging

import pytest

import salt.runners.vault as vault
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


@pytest.fixture
def configure_loader_modules():
    return {vault: {}}


@pytest.fixture
def grains():
    return {
        "id": "test-minion",
        "roles": ["web", "database"],
        "aux": ["foo", "bar"],
        "deep": {"foo": {"bar": {"baz": ["hello", "world"]}}},
        "mixedcase": "UP-low-UP",
    }


def test_pattern_list_expander(grains):
    """
    Ensure _expand_pattern_lists works as intended:
    - Expand list-valued patterns
    - Do not change non-list-valued tokens
    """
    cases = {
        "no-tokens-to-replace": ["no-tokens-to-replace"],
        "single-dict:{minion}": ["single-dict:{minion}"],
        "single-list:{grains[roles]}": ["single-list:web", "single-list:database"],
        "multiple-lists:{grains[roles]}+{grains[aux]}": [
            "multiple-lists:web+foo",
            "multiple-lists:web+bar",
            "multiple-lists:database+foo",
            "multiple-lists:database+bar",
        ],
        "single-list-with-dicts:{grains[id]}+{grains[roles]}+{grains[id]}": [
            "single-list-with-dicts:{grains[id]}+web+{grains[id]}",
            "single-list-with-dicts:{grains[id]}+database+{grains[id]}",
        ],
        "deeply-nested-list:{grains[deep][foo][bar][baz]}": [
            "deeply-nested-list:hello",
            "deeply-nested-list:world",
        ],
    }

    # The mappings dict is assembled in _get_policies, so emulate here
    mappings = {"minion": grains["id"], "grains": grains}
    for case, correct_output in cases.items():
        output = vault._expand_pattern_lists(
            case, **mappings
        )  # pylint: disable=protected-access
        diff = set(output).symmetric_difference(set(correct_output))
        if diff:
            log.debug("Test %s failed", case)
            log.debug("Expected:\n\t%s\nGot\n\t%s", output, correct_output)
            log.debug("Difference:\n\t%s", diff)
        assert output == correct_output


def test_get_policies_for_nonexisting_minions():
    minion_id = "salt_master"
    # For non-existing minions, or the master-minion, grains will be None
    cases = {
        "no-tokens-to-replace": ["no-tokens-to-replace"],
        "single-dict:{minion}": ["single-dict:{}".format(minion_id)],
        "single-list:{grains[roles]}": [],
    }
    with patch(
        "salt.utils.minions.get_minion_data",
        MagicMock(return_value=(None, None, None)),
    ):
        for case, correct_output in cases.items():
            test_config = {"policies": [case]}
            output = vault._get_policies(
                minion_id, test_config
            )  # pylint: disable=protected-access
            diff = set(output).symmetric_difference(set(correct_output))
            if diff:
                log.debug("Test %s failed", case)
                log.debug("Expected:\n\t%s\nGot\n\t%s", output, correct_output)
                log.debug("Difference:\n\t%s", diff)
            assert output == correct_output


def test_get_policies(grains):
    """
    Ensure _get_policies works as intended, including expansion of lists
    """
    cases = {
        "no-tokens-to-replace": ["no-tokens-to-replace"],
        "single-dict:{minion}": ["single-dict:test-minion"],
        "single-list:{grains[roles]}": ["single-list:web", "single-list:database"],
        "multiple-lists:{grains[roles]}+{grains[aux]}": [
            "multiple-lists:web+foo",
            "multiple-lists:web+bar",
            "multiple-lists:database+foo",
            "multiple-lists:database+bar",
        ],
        "single-list-with-dicts:{grains[id]}+{grains[roles]}+{grains[id]}": [
            "single-list-with-dicts:test-minion+web+test-minion",
            "single-list-with-dicts:test-minion+database+test-minion",
        ],
        "deeply-nested-list:{grains[deep][foo][bar][baz]}": [
            "deeply-nested-list:hello",
            "deeply-nested-list:world",
        ],
        "should-not-cause-an-exception,but-result-empty:{foo}": [],
        "Case-Should-Be-Lowered:{grains[mixedcase]}": [
            "case-should-be-lowered:up-low-up"
        ],
    }

    with patch(
        "salt.utils.minions.get_minion_data",
        MagicMock(return_value=(None, grains, None)),
    ):
        for case, correct_output in cases.items():
            test_config = {"policies": [case]}
            output = vault._get_policies(
                "test-minion", test_config
            )  # pylint: disable=protected-access
            diff = set(output).symmetric_difference(set(correct_output))
            if diff:
                log.debug("Test %s failed", case)
                log.debug("Expected:\n\t%s\nGot\n\t%s", output, correct_output)
                log.debug("Difference:\n\t%s", diff)
            assert output == correct_output


def test_get_token_create_url():
    """
    Ensure _get_token_create_url parses config correctly
    """
    assert (
        vault._get_token_create_url(  # pylint: disable=protected-access
            {"url": "http://127.0.0.1"}
        )
        == "http://127.0.0.1/v1/auth/token/create"
    )
    assert (
        vault._get_token_create_url(  # pylint: disable=protected-access
            {"url": "https://127.0.0.1/"}
        )
        == "https://127.0.0.1/v1/auth/token/create"
    )
    assert (
        vault._get_token_create_url(  # pylint: disable=protected-access
            {"url": "http://127.0.0.1:8200", "role_name": "therole"}
        )
        == "http://127.0.0.1:8200/v1/auth/token/create/therole"
    )
    assert (
        vault._get_token_create_url(  # pylint: disable=protected-access
            {"url": "https://127.0.0.1/test", "role_name": "therole"}
        )
        == "https://127.0.0.1/test/v1/auth/token/create/therole"
    )
