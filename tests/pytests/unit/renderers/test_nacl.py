import pytest

import salt.renderers.nacl as nacl
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {nacl: {}}


def test__decrypt_object():
    """
    test _decrypt_object
    """
    secret = "Use more salt."
    crypted = "NACL[MRN3cc+fmdxyQbz6WMF+jq1hKdU5X5BBI7OjK+atvHo1ll+w1gZ7XyWtZVfq9gK9rQaMfkDxmidJKwE0Mw==]"

    secret_map = {"secret": secret}
    crypted_map = {"secret": crypted}

    secret_list = [secret]
    crypted_list = [crypted]

    with patch.dict(nacl.__salt__, {"nacl.dec": MagicMock(return_value=secret)}):
        assert nacl._decrypt_object(secret) == secret
        assert nacl._decrypt_object(crypted) == secret
        assert nacl._decrypt_object(crypted_map) == secret_map
        assert nacl._decrypt_object(crypted_list) == secret_list
        assert nacl._decrypt_object(None) is None


def test_render():
    """
    test render
    """
    secret = "Use more salt."
    crypted = "NACL[MRN3cc+fmdxyQbz6WMF+jq1hKdU5X5BBI7OjK+atvHo1ll+w1gZ7XyWtZVfq9gK9rQaMfkDxmidJKwE0Mw==]"
    with patch.dict(nacl.__salt__, {"nacl.dec": MagicMock(return_value=secret)}):
        assert nacl.render(crypted) == secret
