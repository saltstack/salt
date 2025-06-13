"""
unit tests for the cache runner
"""

import pytest

import salt.config
import salt.runners.cache as cache
import salt.utils.master
from tests.support.mock import MagicMock, call, patch


@pytest.fixture
def master_opts(master_opts, tmp_path):
    master_opts.update(
        {
            "cache": "localfs",
            "pki_dir": str(tmp_path),
            "key_cache": True,
            "keys.cache_driver": "localfs_key",
            "__role": "master",
            "eauth_tokens.cache_driver": "localfs",
            "pillar.cache_driver": "localfs",
        }
    )
    return master_opts


@pytest.fixture
def configure_loader_modules(master_opts):
    return {cache: {"__opts__": master_opts}}


def test_grains():
    """
    test cache.grains runner
    """
    mock_minion = ["Larry"]
    mock_ret = {}
    assert cache.grains(tgt="*", minion=mock_minion) == mock_ret

    mock_data = "grain stuff"

    class MockMaster:
        def __init__(self, *args, **kwargs):
            pass

        def get_minion_grains(self):
            return mock_data

    with patch.object(salt.utils.master, "MasterPillarUtil", MockMaster):
        assert cache.grains(tgt="*") == mock_data


def test_migrate_all_banks(master_opts):
    """
    Test migrate function when migrating all banks
    """
    mock_key_cache = MagicMock()
    mock_token_cache = MagicMock()
    mock_mdc_cache = MagicMock()
    mock_base_cache = MagicMock()
    mock_dst_cache = MagicMock()

    mock_key_cache.list.side_effect = [["key1", "key2"], ["key3"], ["key4"]]
    mock_token_cache.list.return_value = ["token1"]
    mock_mdc_cache.list.return_value = ["pillar1"]
    mock_base_cache.list.side_effect = [["grain1"], ["mine1"]]

    mock_key_cache.fetch.side_effect = ["value1", "value2", "value3", "value4"]
    mock_token_cache.fetch.return_value = "token_value"
    mock_mdc_cache.fetch.return_value = "pillar_value"
    mock_base_cache.fetch.side_effect = ["grain_value", "mine_value"]

    mock_caches = [
        mock_key_cache,
        mock_token_cache,
        mock_mdc_cache,
        mock_base_cache,
        mock_dst_cache,
    ]

    with patch("salt.cache.Cache") as mock_cache_factory:
        mock_cache_factory.side_effect = mock_caches

        result = cache.migrate(target="redis")

        # Assert the result is True
        assert result is True

        # Assert Cache initialized with correct drivers
        assert mock_cache_factory.call_count == 5
        mock_cache_factory.assert_any_call(
            master_opts, driver=master_opts["keys.cache_driver"]
        )
        mock_cache_factory.assert_any_call(
            master_opts, driver=master_opts["eauth_tokens.cache_driver"]
        )
        mock_cache_factory.assert_any_call(
            master_opts, driver=master_opts["pillar.cache_driver"]
        )
        mock_cache_factory.assert_any_call(master_opts)
        mock_cache_factory.assert_any_call(master_opts, driver="redis")

        # Assert all banks were listed
        mock_key_cache.list.assert_any_call("keys")
        mock_key_cache.list.assert_any_call("master_keys")
        mock_key_cache.list.assert_any_call("denied_keys")
        mock_token_cache.list.assert_called_once_with("tokens")
        mock_mdc_cache.list.assert_called_once_with("pillar")
        mock_base_cache.list.assert_any_call("grains")
        mock_base_cache.list.assert_any_call("mine")

        # Assert data was fetched and stored
        expected_fetch_calls = [
            call("keys", "key1"),
            call("keys", "key2"),
            call("master_keys", "key3"),
            call("denied_keys", "key4"),
        ]
        mock_key_cache.fetch.assert_has_calls(expected_fetch_calls, any_order=True)
        mock_token_cache.fetch.assert_called_once_with("tokens", "token1")
        mock_mdc_cache.fetch.assert_called_once_with("pillar", "pillar1")

        # Assert data was stored in destination cache
        expected_store_calls = [
            call("keys", "key1", "value1"),
            call("keys", "key2", "value2"),
            call("master_keys", "key3", "value3"),
            call("denied_keys", "key4", "value4"),
            call("tokens", "token1", "token_value"),
            call("pillar", "pillar1", "pillar_value"),
            call("grains", "grain1", "grain_value"),
            call("mine", "mine1", "mine_value"),
        ]
        mock_dst_cache.store.assert_has_calls(expected_store_calls, any_order=True)


def test_migrate_specific_banks():
    """
    Test migrate function when specifying specific banks
    """
    mock_key_cache = MagicMock()
    mock_token_cache = MagicMock()
    mock_mdc_cache = MagicMock()
    mock_base_cache = MagicMock()
    mock_dst_cache = MagicMock()

    mock_key_cache.list.side_effect = [["key1", "key2"], ["key3"]]

    mock_key_cache.fetch.side_effect = ["value1", "value2", "value3"]

    mock_caches = [
        mock_key_cache,
        mock_token_cache,
        mock_mdc_cache,
        mock_base_cache,
        mock_dst_cache,
    ]

    with patch("salt.cache.Cache") as mock_cache_factory:
        mock_cache_factory.side_effect = mock_caches

        result = cache.migrate(target="redis", bank="keys,master_keys")

        # Assert the result is True
        assert result is True

        # Assert Cache initialized with correct drivers
        assert mock_cache_factory.call_count == 5

        # Assert only specified banks were listed
        mock_key_cache.list.assert_any_call("keys")
        mock_key_cache.list.assert_any_call("master_keys")

        # Assert specified banks were NOT listed
        assert call("denied_keys") not in mock_key_cache.list.call_args_list
        assert not mock_token_cache.list.called
        assert not mock_mdc_cache.list.called
        assert not mock_base_cache.list.called

        # Assert data was fetched and stored only for specified banks
        expected_fetch_calls = [
            call("keys", "key1"),
            call("keys", "key2"),
            call("master_keys", "key3"),
        ]
        mock_key_cache.fetch.assert_has_calls(expected_fetch_calls, any_order=True)

        # Assert data was stored in destination cache
        expected_store_calls = [
            call("keys", "key1", "value1"),
            call("keys", "key2", "value2"),
            call("master_keys", "key3", "value3"),
        ]
        mock_dst_cache.store.assert_has_calls(expected_store_calls, any_order=True)


def test_migrate_empty_bank(caplog):
    """
    Test migrate function with a bank that has no keys
    """
    mock_key_cache = MagicMock()
    mock_token_cache = MagicMock()
    mock_mdc_cache = MagicMock()
    mock_base_cache = MagicMock()
    mock_dst_cache = MagicMock()

    # Empty list of keys
    mock_key_cache.list.return_value = []

    mock_caches = [
        mock_key_cache,
        mock_token_cache,
        mock_mdc_cache,
        mock_base_cache,
        mock_dst_cache,
    ]

    with patch("salt.cache.Cache") as mock_cache_factory:
        mock_cache_factory.side_effect = mock_caches

        # Set caplog to capture INFO level messages
        caplog.set_level("INFO")

        result = cache.migrate(target="redis", bank="keys")

        # Assert the result is True
        assert result is True

        # Assert bank was listed but found empty
        mock_key_cache.list.assert_called_once_with("keys")

        # Assert no data was fetched since bank was empty
        assert not mock_key_cache.fetch.called

        # Assert no data was stored since bank was empty
        assert not mock_dst_cache.store.called

        # Check that the empty migration was logged
        assert "bank keys: migrating 0 keys" in caplog.text
