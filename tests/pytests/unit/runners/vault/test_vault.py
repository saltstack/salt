"""
Unit tests for the Vault runner
"""

import logging

import pytest

import salt.runners.vault as vault
from tests.support.mock import MagicMock, Mock, patch

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


@pytest.fixture
def pillar():
    return {
        "role": "test",
    }


@pytest.fixture
def expand_pattern_lists():
    with patch.dict(
        vault.__utils__,
        {
            "vault.expand_pattern_lists": Mock(
                side_effect=lambda x, *args, **kwargs: [x]
            )
        },
    ):
        yield


@pytest.mark.usefixtures("expand_pattern_lists")
def test_get_policies_for_nonexisting_minions():
    minion_id = "salt_master"
    # For non-existing minions, or the master-minion, grains will be None
    cases = {
        "no-tokens-to-replace": ["no-tokens-to-replace"],
        "single-dict:{minion}": [f"single-dict:{minion_id}"],
        "single-grain:{grains[os]}": [],
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


@pytest.mark.usefixtures("expand_pattern_lists")
def test_get_policies(grains):
    """
    Ensure _get_policies works as intended.
    The expansion of lists is tested in the vault utility module unit tests.
    """
    cases = {
        "no-tokens-to-replace": ["no-tokens-to-replace"],
        "single-dict:{minion}": ["single-dict:test-minion"],
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


@pytest.mark.usefixtures("expand_pattern_lists")
@pytest.mark.parametrize(
    "pattern,count",
    [
        ("salt_minion_{minion}", 0),
        ("salt_grain_{grains[id]}", 0),
        ("unset_{foo}", 0),
        ("salt_pillar_{pillar[role]}", 1),
    ],
)
def test_get_policies_does_not_render_pillar_unnecessarily(
    pattern, count, grains, pillar
):
    """
    The pillar data should only be refreshed in case items are accessed.
    """
    with patch("salt.utils.minions.get_minion_data", autospec=True) as get_minion_data:
        get_minion_data.return_value = (None, grains, None)
        with patch("salt.pillar.get_pillar", autospec=True) as get_pillar:
            get_pillar.return_value.compile_pillar.return_value = pillar
            test_config = {"policies": [pattern]}
            vault._get_policies(
                "test-minion", test_config, refresh_pillar=True
            )  # pylint: disable=protected-access
            assert get_pillar.call_count == count


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
