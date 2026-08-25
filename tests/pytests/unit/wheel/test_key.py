import pytest

import salt.wheel.key as key
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules(tmp_path):
    return {key: {"__opts__": {"pki_dir": str(tmp_path)}}}


def _stub_gen_keys(tmp_path):
    """
    Return a MagicMock standing in for salt.crypt.gen_keys, backed by real
    on-disk pem/pub files so gen() can read them after the (mocked) call.
    """
    priv = tmp_path / "minion.pem"
    priv.write_text("priv", encoding="utf-8")
    (tmp_path / "minion.pub").write_text("pub", encoding="utf-8")
    return MagicMock(return_value=str(priv))


def test_gen_coerces_string_keysize(tmp_path):
    """
    Regression test for #56425.

    The salt-api ``POST /keys`` endpoint passes ``keysize`` as a string, because
    cherrypy form values are always strings. ``gen()`` must coerce it to an int
    before handing it to ``salt.crypt.gen_keys`` (which feeds it to
    ``rsa.generate_private_key``, whose ``key_size`` must be an int). This pins
    the bug: without the coercion ``gen_keys`` receives the raw ``"4096"``
    string and this assertion fails.
    """
    gen_keys = _stub_gen_keys(tmp_path)
    with patch("salt.crypt.gen_keys", gen_keys):
        key.gen(id_="minion", keysize="4096")
    passed_keysize = gen_keys.call_args[0][2]
    assert passed_keysize == 4096
    assert isinstance(passed_keysize, int)


def test_gen_enforces_2048_floor(tmp_path):
    """
    #56425: a keysize below the documented 2048-bit minimum is rounded up to
    2048, which ``gen()``'s docstring has always promised but the code never
    implemented.
    """
    gen_keys = _stub_gen_keys(tmp_path)
    with patch("salt.crypt.gen_keys", gen_keys):
        key.gen(id_="minion", keysize="1024")
    assert gen_keys.call_args[0][2] == 2048


def test_gen_int_keysize_unchanged(tmp_path):
    """
    Inverse of #56425: a valid integer keysize at or above the floor passes
    through unchanged, so the coercion never alters a correct caller.
    """
    gen_keys = _stub_gen_keys(tmp_path)
    with patch("salt.crypt.gen_keys", gen_keys):
        key.gen(id_="minion", keysize=4096)
    assert gen_keys.call_args[0][2] == 4096
