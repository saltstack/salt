"""
    Unit tests for the salt.modules.state module
"""

import salt.loader.context
import salt.modules.state
from tests.support.mock import patch


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
            pillar = salt.modules.state._get_initial_pillar(opts)
            assert pillar == pillar_data
