import pytest

import salt.utils.vault as vault
import salt.utils.vault.cache as vcache
import salt.utils.vault.client as vclient
import salt.utils.vault.leases as leases
from tests.support.mock import Mock, call, patch


@pytest.fixture(autouse=True, params=[0])
def time_stopped(request):
    with patch(
        "salt.utils.vault.leases.time.time", autospec=True, return_value=request.param
    ):
        yield


@pytest.fixture
def lease_renewed_response():
    return {
        "lease_id": "database/creds/testrole/abcd",
        "renewable": True,
        "lease_duration": 2000,
    }


@pytest.fixture
def lease_renewed_extended_response():
    return {
        "lease_id": "database/creds/testrole/abcd",
        "renewable": True,
        "lease_duration": 3000,
    }


@pytest.fixture
def store(events):
    client = Mock(spec=vclient.AuthenticatedVaultClient)
    cache = Mock(spec=vcache.VaultLeaseCache)
    cache.exists.return_value = False
    cache.get.return_value = None
    return leases.LeaseStore(client, cache, expire_events=events)


@pytest.fixture
def store_valid(store, lease, lease_renewed_response):
    store.cache.exists.return_value = True
    store.cache.get.return_value = leases.VaultLease(**lease)
    store.client.post.return_value = lease_renewed_response
    return store


@pytest.mark.parametrize(
    "creation_time",
    [
        1661188581,
        "1661188581",
        "2022-08-22T17:16:21.473219641+00:00",
        "2022-08-22T17:16:21.47321964+00:00",
        "2022-08-22T17:16:21.4732196+00:00",
        "2022-08-22T17:16:21.473219+00:00",
        "2022-08-22T17:16:21.47321+00:00",
        "2022-08-22T17:16:21.4732+00:00",
        "2022-08-22T17:16:21.473+00:00",
        "2022-08-22T17:16:21.47+00:00",
        "2022-08-22T17:16:21.4+00:00",
    ],
)
def test_vault_lease_creation_time_normalization(creation_time):
    """
    Ensure the normalization of different creation_time formats works as expected -
    many token endpoints report a timestamp, while other endpoints report RFC3339-formatted
    strings that may have a variable number of digits for sub-second precision (0 omitted)
    while datetime.fromisoformat expects exactly 6 digits
    """
    data = {
        "lease_id": "id",
        "renewable": False,
        "lease_duration": 1337,
        "creation_time": creation_time,
        "data": None,
    }
    res = leases.VaultLease(**data)
    assert res.creation_time == 1661188581


@pytest.mark.parametrize(
    "time_stopped,duration,offset,expected",
    [
        (0, 50, 0, True),
        (50, 10, 0, False),
        (0, 60, 10, True),
        (0, 60, 600, False),
    ],
    indirect=["time_stopped"],
)
def test_vault_lease_is_valid_accounts_for_time(duration, offset, expected):
    """
    Ensure lease validity is checked correctly and can look into the future
    """
    data = {
        "lease_id": "id",
        "renewable": False,
        "lease_duration": duration,
        "creation_time": 0,
        "expire_time": duration,
        "data": None,
    }
    res = leases.VaultLease(**data)
    assert res.is_valid_for(offset) is expected


@pytest.mark.parametrize(
    "time_stopped,duration,offset,expected",
    [
        (0, 50, 0, True),
        (50, 10, 0, False),
        (0, 60, 10, True),
        (0, 60, 600, False),
    ],
    indirect=["time_stopped"],
)
def test_vault_token_is_valid_accounts_for_time(duration, offset, expected):
    """
    Ensure token time validity is checked correctly and can look into the future
    """
    data = {
        "client_token": "id",
        "renewable": False,
        "lease_duration": duration,
        "num_uses": 0,
        "creation_time": 0,
        "expire_time": duration,
    }
    res = vault.VaultToken(**data)
    assert res.is_valid_for(offset) is expected


@pytest.mark.parametrize(
    "num_uses,uses,expected",
    [(0, 999999, True), (1, 0, True), (1, 1, False), (1, 2, False)],
)
def test_vault_token_is_valid_accounts_for_num_uses(num_uses, uses, expected):
    """
    Ensure token uses validity is checked correctly
    """
    data = {
        "client_token": "id",
        "renewable": False,
        "lease_duration": 0,
        "num_uses": num_uses,
        "creation_time": 0,
        "use_count": uses,
    }
    with patch(
        "salt.utils.vault.leases.BaseLease.is_valid_for",
        autospec=True,
        return_value=True,
    ):
        res = vault.VaultToken(**data)
        assert res.is_valid() is expected


@pytest.mark.parametrize(
    "time_stopped,duration,offset,expected",
    [
        (0, 50, 0, True),
        (50, 10, 0, False),
        (0, 60, 10, True),
        (0, 60, 600, False),
    ],
    indirect=["time_stopped"],
)
def test_vault_approle_secret_id_is_valid_accounts_for_time(duration, offset, expected):
    """
    Ensure secret ID time validity is checked correctly and can look into the future
    """
    data = {
        "secret_id": "test-secret-id",
        "renewable": False,
        "creation_time": 0,
        "expire_time": duration,
        "secret_id_num_uses": 0,
        "secret_id_ttl": duration,
    }
    res = vault.VaultSecretId(**data)
    assert res.is_valid(offset) is expected


@pytest.mark.parametrize(
    "num_uses,uses,expected",
    [(0, 999999, True), (1, 0, True), (1, 1, False), (1, 2, False)],
)
def test_vault_approle_secret_id_is_valid_accounts_for_num_uses(
    num_uses, uses, expected
):
    """
    Ensure secret ID uses validity is checked correctly
    """
    data = {
        "secret_id": "test-secret-id",
        "renewable": False,
        "creation_time": 0,
        "secret_id_ttl": 0,
        "secret_id_num_uses": num_uses,
        "use_count": uses,
    }
    with patch(
        "salt.utils.vault.leases.BaseLease.is_valid_for",
        autospec=True,
        return_value=True,
    ):
        res = vault.VaultSecretId(**data)
        assert res.is_valid() is expected


class TestLeaseStore:
    def test_get_uncached_or_invalid(self, store):
        """
        Ensure uncached or invalid leases are reported as None.
        """
        ret = store.get("test")
        assert ret is None
        store.client.post.assert_not_called()
        store.cache.flush.assert_not_called()
        store.cache.store.assert_not_called()

    def test_get_cached_valid(self, store_valid, lease):
        """
        Ensure valid leases are returned without extra behavior.
        """
        ret = store_valid.get("test")
        assert ret == lease
        store_valid.client.post.assert_not_called()
        store_valid.cache.flush.assert_not_called()
        store_valid.cache.store.assert_not_called()

    @pytest.mark.parametrize(
        "valid_for", [2000, pytest.param(2002, id="2002_renewal_leeway")]
    )
    def test_get_valid_renew_default_period(self, store_valid, lease, valid_for):
        """
        Ensure renewals are attempted by default, cache is updated accordingly
        and validity checks after renewal allow for a little leeway to account
        for latency.
        """
        ret = store_valid.get("test", valid_for=valid_for)
        lease["duration"] = lease["expire_time"] = 2000
        assert ret == lease
        store_valid.client.post.assert_called_once_with(
            "sys/leases/renew", payload={"lease_id": lease["id"]}
        )
        store_valid.cache.flush.assert_not_called()
        store_valid.cache.store.assert_called_once_with("test", ret)
        store_valid.expire_events.assert_not_called()

    def test_get_valid_renew_increment(self, store_valid, lease):
        """
        Ensure renew_increment is honored when renewing.
        """
        ret = store_valid.get("test", valid_for=1400, renew_increment=2000)
        lease["duration"] = lease["expire_time"] = 2000
        assert ret == lease
        store_valid.client.post.assert_called_once_with(
            "sys/leases/renew", payload={"lease_id": lease["id"], "increment": 2000}
        )
        store_valid.cache.flush.assert_not_called()
        store_valid.cache.store.assert_called_once_with("test", ret)
        store_valid.expire_events.assert_not_called()

    def test_get_valid_renew_increment_insufficient(self, store_valid, lease):
        """
        Ensure that when renewal_increment is set, valid_for is respected and that
        a second renewal using valid_for as increment is not attempted when the
        Vault server does not allow renewals for at least valid_for.
        If an event factory was passed, an event should be sent.
        """
        ret = store_valid.get("test", valid_for=2100, renew_increment=3000)
        assert ret is None
        store_valid.client.post.assert_has_calls(
            (
                call(
                    "sys/leases/renew",
                    payload={"lease_id": lease["id"], "increment": 3000},
                ),
                call(
                    "sys/leases/renew",
                    payload={"lease_id": lease["id"], "increment": 60},
                ),
            )
        )
        store_valid.cache.flush.assert_called_once_with("test")
        store_valid.expire_events.assert_called_once_with(
            tag="vault/lease/test/expire", data={"valid_for_less": 2100}
        )

    @pytest.mark.parametrize(
        "valid_for", [3000, pytest.param(3002, id="3002_renewal_leeway")]
    )
    def test_get_valid_renew_valid_for(
        self,
        store_valid,
        lease,
        valid_for,
        lease_renewed_response,
        lease_renewed_extended_response,
    ):
        """
        Ensure that, if renew_increment was not set and the default period
        does not yield valid_for, a second renewal is attempted by valid_for.
        There should be some leeway by default to account for latency.
        """
        store_valid.client.post.side_effect = (
            lease_renewed_response,
            lease_renewed_extended_response,
        )
        ret = store_valid.get("test", valid_for=valid_for)
        lease["duration"] = lease["expire_time"] = 3000
        assert ret == lease
        store_valid.client.post.assert_has_calls(
            (
                call("sys/leases/renew", payload={"lease_id": lease["id"]}),
                call(
                    "sys/leases/renew",
                    payload={"lease_id": lease["id"], "increment": valid_for},
                ),
            )
        )
        store_valid.cache.flush.assert_not_called()
        store_valid.cache.store.assert_called_with("test", ret)
        store_valid.expire_events.assert_not_called()

    def test_get_valid_not_renew(self, store_valid, lease):
        """
        Currently valid leases should not be returned if they undercut
        valid_for. By default, revocation should be attempted and cache
        should be flushed. If an event factory was passed, an event should be sent.
        """
        ret = store_valid.get("test", valid_for=2000, renew=False)
        assert ret is None
        store_valid.cache.store.assert_not_called()
        store_valid.client.post.assert_called_once_with(
            "sys/leases/renew", payload={"lease_id": lease["id"], "increment": 60}
        )
        store_valid.cache.flush.assert_called_once_with("test")
        store_valid.expire_events.assert_called_once_with(
            tag="vault/lease/test/expire", data={"valid_for_less": 2000}
        )

    def test_get_valid_not_flush(self, store_valid):
        """
        Currently valid leases should not be returned if they undercut
        valid_for and should not be revoked if requested so.
        If an event factory was passed, an event should be sent.
        """
        ret = store_valid.get("test", valid_for=2000, revoke=False, renew=False)
        assert ret is None
        store_valid.cache.flush.assert_not_called()
        store_valid.client.post.assert_not_called()
        store_valid.cache.store.assert_not_called()
        store_valid.expire_events.assert_called_once_with(
            tag="vault/lease/test/expire", data={"valid_for_less": 2000}
        )
