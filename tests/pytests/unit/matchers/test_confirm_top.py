import pytest

import salt.config
import salt.loader


@pytest.fixture
def matchers(minion_opts):
    return salt.loader.matchers(minion_opts)


def test_sanity(matchers):
    match = matchers["confirm_top.confirm_top"]
    assert match("*", []) is True
