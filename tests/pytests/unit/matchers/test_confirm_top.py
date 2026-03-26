import pytest

import salt.config
import salt.loader
from tests.support.mock import patch


@pytest.fixture
def matchers(minion_opts):
    return salt.loader.matchers(minion_opts)


def test_sanity(matchers):
    match = matchers["confirm_top.confirm_top"]
    assert match("*", []) is True


@pytest.mark.parametrize("in_context", [False, True])
def test_matchers_from_context(matchers, in_context):
    match = matchers["confirm_top.confirm_top"]
    with patch.dict(
        matchers.pack["__context__"], {"matchers": matchers} if in_context else {}
    ), patch("salt.loader.matchers", return_value=matchers) as loader_matchers:
        assert match("*", []) is True
        assert id(matchers.pack["__context__"]["matchers"]) == id(matchers)
        if in_context:
            loader_matchers.assert_not_called()
        else:
            loader_matchers.assert_called_once()
