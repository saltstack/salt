import pytest

import salt.config
import salt.loader


@pytest.fixture
def matchers():
    opts = salt.config.DEFAULT_MINION_OPTS.copy()
    return salt.loader.matchers(opts)


def test_sanity(matchers):
    match = matchers["confirm_top.confirm_top"]
    assert match("*", []) is True
