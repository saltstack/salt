"""
Tests for the choice of the top file merging strategy in
salt.state.BaseHighState.merge_tops
"""

from types import SimpleNamespace

import pytest

import salt.state
from tests.support.mock import MagicMock

pytestmark = [
    pytest.mark.core_test,
]


def _highstate(strategy, **attributes):
    return SimpleNamespace(
        opts={"top_file_merging_strategy": strategy},
        _merge_tops_merge=MagicMock(return_value="merge"),
        **attributes,
    )


def test_merge_tops_uses_the_configured_strategy():
    state = _highstate("same", _merge_tops_same=MagicMock(return_value="same"))
    assert salt.state.BaseHighState.merge_tops(state, {}) == "same"
    state._merge_tops_merge.assert_not_called()


def test_merge_tops_falls_back_to_merge_for_an_unknown_strategy():
    state = _highstate("does_not_exist")
    assert salt.state.BaseHighState.merge_tops(state, {}) == "merge"


def test_merge_tops_falls_back_to_merge_when_the_strategy_is_not_callable():
    state = _highstate("broken", _merge_tops_broken="not a function")
    assert salt.state.BaseHighState.merge_tops(state, {}) == "merge"
