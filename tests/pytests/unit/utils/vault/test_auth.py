import pytest

import salt.utils.vault as vault
import salt.utils.vault.auth as vauth
import salt.utils.vault.cache as vcache
import salt.utils.vault.client as vclient
import salt.utils.vault.leases as vleases
from tests.support.mock import Mock, patch


@pytest.fixture
def token(token_auth):
    return vleases.VaultToken(**token_auth["auth"])


@pytest.fixture
def token_invalid(token_auth):
    token_auth["auth"]["num_uses"] = 1
    token_auth["auth"]["use_count"] = 1
    return vleases.VaultToken(**token_auth["auth"])


@pytest.fixture
def token_unrenewable(token_auth):
    token_auth["auth"]["renewable"] = False
    return vleases.VaultToken(**token_auth["auth"])


@pytest.fixture
def secret_id(secret_id_response):
    return vleases.VaultSecretId(**secret_id_response["data"])


@pytest.fixture
def secret_id_invalid(secret_id_response):
    secret_id_response["data"]["secret_id_num_uses"] = 1
    secret_id_response["data"]["use_count"] = 1
    return vleases.VaultSecretId(**secret_id_response["data"])


@pytest.fixture(params=["secret_id"])
def approle(request):
    secret_id = request.param
    if secret_id is not None:
        secret_id = request.getfixturevalue(secret_id)
    return vauth.VaultAppRole("test-role-id", secret_id)


@pytest.fixture
def approle_invalid(secret_id_invalid):
    return vauth.VaultAppRole("test-role-id", secret_id_invalid)


@pytest.fixture
def token_store(token):
    store = Mock(spec=vauth.VaultTokenAuth)
    store.is_valid.return_value = True
    store.get_token.return_value = token
    return store


@pytest.fixture
def token_store_empty(token_store):
    token_store.is_valid.return_value = False
    token_store.get_token.side_effect = vault.VaultAuthExpired
    return token_store


@pytest.fixture
def token_store_empty_first(token_store, token):
    token_store.is_valid.side_effect = (False, True)
    token_store.get_token.side_effect = (token, vault.VaultException)
    return token_store


@pytest.fixture
def uncached():
    cache = Mock(spec=vcache.VaultAuthCache)
    cache.exists.return_value = False
    cache.get.return_value = None
    return cache


@pytest.fixture
def cached_token(uncached, token):
    uncached.exists.return_value = True
    uncached.get.return_value = token
    return uncached


@pytest.fixture
def client(token_auth):
    token_auth["auth"]["client_token"] = "new-test-token"
    client = Mock(spec=vclient.VaultClient)
    client.post.return_value = token_auth
    return client


def test_token_auth_uninitialized(uncached):
    """
    Test that an exception is raised when a token is requested
    and the authentication container was not passed a valid token.
    """
    auth = vauth.VaultTokenAuth(cache=uncached)
    uncached.get.assert_called_once()
    assert auth.is_valid() is False
    assert auth.is_renewable() is False
    auth.used()
    with pytest.raises(vault.VaultAuthExpired):
        auth.get_token()


def test_token_auth_cached(cached_token, token):
    """
    Test that tokens are read from cache.
    """
    auth = vauth.VaultTokenAuth(cache=cached_token)
    assert auth.is_valid()
    assert auth.get_token() == token


def test_token_auth_invalid_token(invalid_token):
    """
    Test that an exception is raised when a token is requested
    and the container's token is invalid.
    """
    auth = vauth.VaultTokenAuth(token=invalid_token)
    assert auth.is_valid() is False
    assert auth.is_renewable() is False
    with pytest.raises(vault.VaultAuthExpired):
        auth.get_token()


def test_token_auth_unrenewable_token(token_unrenewable):
    """
    Test that it is reported correctly by the container
    when a token is not renewable.
    """
    auth = vauth.VaultTokenAuth(token=token_unrenewable)
    assert auth.is_valid() is True
    assert auth.is_renewable() is False
    assert auth.get_token() == token_unrenewable


@pytest.mark.parametrize("num_uses", [0, 1, 10])
def test_token_auth_used_num_uses(uncached, token, num_uses):
    """
    Ensure that cache writes for use count are only done when
    num_uses is not 0 (= unlimited).
    Single-use tokens still require cache writes for updating
    ``uses``. The cache cannot be flushed here since
    exceptions might be used to indicate the token expiry
    to factory methods.
    """
    token = token.with_renewed(num_uses=num_uses)
    auth = vauth.VaultTokenAuth(cache=uncached, token=token)
    auth.used()
    if num_uses > 0:
        uncached.store.assert_called_once_with(token)
    else:
        uncached.store.assert_not_called()


@pytest.mark.parametrize("num_uses", [0, 1, 10])
def test_token_auth_update_token(uncached, token, num_uses):
    """
    Ensure that partial updates to the token in use are possible
    and that the cache writes are independent from num_uses.
    Also ensure the token is treated as immutable
    """
    auth = vauth.VaultTokenAuth(cache=uncached, token=token)
    old_token = token
    old_token_ttl = old_token.duration
    auth.update_token({"num_uses": num_uses, "ttl": 8483})
    updated_token = token.with_renewed(num_uses=num_uses, ttl=8483)
    assert auth.token == updated_token
    assert old_token.duration == old_token_ttl
    uncached.store.assert_called_once_with(updated_token)


def test_token_auth_replace_token(uncached, token):
    """
    Ensure completely replacing the token is possible and
    results in a cache write. This is important when an
    InvalidVaultToken has to be replaced with a VaultToken,
    eg by a different authentication method.
    """
    auth = vauth.VaultTokenAuth(cache=uncached)
    assert isinstance(auth.token, vauth.InvalidVaultToken)
    auth.replace_token(token)
    assert isinstance(auth.token, vleases.VaultToken)
    assert auth.token == token
    uncached.store.assert_called_once_with(token)


@pytest.mark.parametrize("token", [False, True])
@pytest.mark.parametrize("approle", [False, True])
def test_approle_auth_is_valid(token, approle):
    """
    Test that is_valid reports true when either the token
    or the secret ID is valid
    """
    token = Mock(spec=vleases.VaultToken)
    token.is_valid.return_value = token
    approle = Mock(spec=vleases.VaultSecretId)
    approle.is_valid.return_value = approle
    auth = vauth.VaultAppRoleAuth(approle, None, token_store=token)
    assert auth.is_valid() is (token or approle)


def test_approle_auth_get_token_store_available(token_store, approle, token):
    """
    Ensure no login attempt is made when a cached token is available
    """
    auth = vauth.VaultAppRoleAuth(approle, None, token_store=token_store)
    with patch("salt.utils.vault.auth.VaultAppRoleAuth._login") as login:
        res = auth.get_token()
        login.assert_not_called()
        assert res == token


def test_approle_auth_get_token_store_empty(token_store_empty, approle, token):
    """
    Ensure a token is returned if no cached token is available
    """
    auth = vauth.VaultAppRoleAuth(approle, None, token_store=token_store_empty)
    with patch("salt.utils.vault.auth.VaultAppRoleAuth._login") as login:
        login.return_value = token
        res = auth.get_token()
        login.assert_called_once()
        assert res == token


def test_approle_auth_get_token_invalid(token_store_empty, approle_invalid):
    """
    Ensure VaultAuthExpired is raised if a token request was made, but
    cannot be fulfilled
    """
    auth = vauth.VaultAppRoleAuth(approle_invalid, None, token_store=token_store_empty)
    with pytest.raises(vault.VaultAuthExpired):
        auth.get_token()


@pytest.mark.parametrize("mount", ["approle", "salt_minions"])
@pytest.mark.parametrize("approle", ["secret_id", None], indirect=True)
def test_approle_auth_get_token_login(
    approle, mount, client, token_store_empty_first, token
):
    """
    Ensure that login with secret-id returns a token that is passed to the
    token store/cache as well
    """
    auth = vauth.VaultAppRoleAuth(
        approle, client, mount=mount, token_store=token_store_empty_first
    )
    res = auth.get_token()
    assert res == token
    args, kwargs = client.post.call_args
    endpoint = args[0]
    payload = kwargs.get("payload", {})
    assert endpoint == f"auth/{mount}/login"
    assert "role_id" in payload
    if approle.secret_id is not None:
        assert "secret_id" in payload
    token_store_empty_first.replace_token.assert_called_once_with(res)


@pytest.mark.parametrize("num_uses", [0, 1, 10])
def test_approle_auth_used_num_uses(
    token_store_empty_first, approle, client, uncached, num_uses, token
):
    """
    Ensure that cache writes for use count are only done when
    num_uses is not 0 (= unlimited)
    """
    approle.secret_id = approle.secret_id.with_renewed(num_uses=num_uses)
    auth = vauth.VaultAppRoleAuth(
        approle, client, cache=uncached, token_store=token_store_empty_first
    )
    res = auth.get_token()
    assert res == token
    if num_uses > 1:
        uncached.store.assert_called_once_with(approle.secret_id)
    elif num_uses:
        uncached.store.assert_not_called()
        uncached.flush.assert_called_once()
    else:
        uncached.store.assert_not_called()


def test_approle_auth_used_locally_configured(
    token_store_empty_first, approle, client, uncached, token
):
    """
    Ensure that locally configured secret IDs are not cached.
    """
    approle.secret_id = vault.LocalVaultSecretId(**approle.secret_id.to_dict())
    auth = vauth.VaultAppRoleAuth(
        approle, client, cache=uncached, token_store=token_store_empty_first
    )
    res = auth.get_token()
    assert res == token
    uncached.store.assert_not_called()


def test_approle_allows_no_secret_id():
    """
    Ensure AppRole containers are still valid if no
    secret ID has been set (bind_secret_id can be set to False!)
    """
    role = vauth.VaultAppRole("test-role-id")
    assert role.is_valid()
