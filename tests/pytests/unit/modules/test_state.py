"""
    Unit tests for the salt.modules.state module
"""

import pytest

import salt.loader.context
import salt.modules.config as config
import salt.modules.state as state
from tests.support.mock import patch


@pytest.fixture
def configure_loader_modules():
    return {
        state: {"__salt__": {"config.get": config.get}, "__opts__": {"test": True}},
        config: {"__opts__": {}},
    }


def test_get_initial_pillar():
    """
    _get_initial_pillar returns pillar data not named context
    """
    ctx = salt.loader.context.LoaderContext()
    pillar_data = {"foo": "bar"}
    named_ctx = ctx.named_context("__pillar__", pillar_data)
    opts = {"__cli": "salt-call", "pillarenv": "base"}
    with patch("salt.modules.state.__pillar__", named_ctx, create=True):
        with patch("salt.modules.state.__opts__", opts, create=True):
            pillar = state._get_initial_pillar(opts)
            assert pillar == pillar_data


def test_check_test_value_is_boolean():
    """
    Ensure that the test value is always returned as a boolean
    """
    with patch.dict(state.__opts__, {"test": True}, create=True):
        assert state._get_test_value() is True
        assert state._get_test_value(True) is True
        assert state._get_test_value(False) is False
        assert state._get_test_value("test") is True
        assert state._get_test_value(123) is True

    with patch.dict(state.__opts__, {"test": False}, create=True):
        assert state._get_test_value() is False
