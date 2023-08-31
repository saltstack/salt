import pytest

import salt.modules.saltutil as saltutil
from salt.client import LocalClient
from tests.support.mock import create_autospec, patch
from tests.support.mock import sentinel as s


@pytest.fixture
def configure_loader_modules():
    return {saltutil: {"__opts__": {"file_client": "local"}}}


def test_exec_kwargs():
    _cmd_expected_kwargs = {
        "tgt": s.tgt,
        "fun": s.fun,
        "arg": s.arg,
        "timeout": s.timeout,
        "tgt_type": s.tgt_type,
        "ret": s.ret,
        "kwarg": s.kwarg,
    }
    client = create_autospec(LocalClient)

    saltutil._exec(client, **_cmd_expected_kwargs)
    client.cmd_iter.assert_called_with(**_cmd_expected_kwargs)

    saltutil._exec(
        client,
        s.tgt,
        s.fun,
        s.arg,
        s.timeout,
        s.tgt_type,
        s.ret,
        s.kwarg,
        **{"batch": s.batch}
    )
    client.cmd_batch.assert_called_with(batch=s.batch, **_cmd_expected_kwargs)

    saltutil._exec(
        client,
        s.tgt,
        s.fun,
        s.arg,
        s.timeout,
        s.tgt_type,
        s.ret,
        s.kwarg,
        **{"subset": s.subset}
    )
    client.cmd_subset.assert_called_with(
        subset=s.subset, cli=True, **_cmd_expected_kwargs
    )

    saltutil._exec(
        client,
        s.tgt,
        s.fun,
        s.arg,
        s.timeout,
        s.tgt_type,
        s.ret,
        s.kwarg,
        **{"subset": s.subset, "cli": s.cli}
    )
    client.cmd_subset.assert_called_with(
        subset=s.subset, cli=s.cli, **_cmd_expected_kwargs
    )

    # cmd_batch doesn't know what to do with 'subset', don't pass it along.
    saltutil._exec(
        client,
        s.tgt,
        s.fun,
        s.arg,
        s.timeout,
        s.tgt_type,
        s.ret,
        s.kwarg,
        **{"subset": s.subset, "batch": s.batch}
    )
    client.cmd_batch.assert_called_with(batch=s.batch, **_cmd_expected_kwargs)


def test_refresh_grains_default_clean_pillar_cache():
    with patch("salt.modules.saltutil.refresh_pillar") as refresh_pillar:
        saltutil.refresh_grains()
        refresh_pillar.assert_called_with(clean_cache=False)


def test_refresh_grains_clean_pillar_cache():
    with patch("salt.modules.saltutil.refresh_pillar") as refresh_pillar:
        saltutil.refresh_grains(clean_pillar_cache=True)
        refresh_pillar.assert_called_with(clean_cache=True)


def test_sync_grains_default_clean_pillar_cache():
    with patch("salt.modules.saltutil._sync"):
        with patch("salt.modules.saltutil.refresh_pillar") as refresh_pillar:
            saltutil.sync_grains()
            refresh_pillar.assert_called_with(clean_cache=False)


def test_sync_grains_clean_pillar_cache():
    with patch("salt.modules.saltutil._sync"):
        with patch("salt.modules.saltutil.refresh_pillar") as refresh_pillar:
            saltutil.sync_grains(clean_pillar_cache=True)
            refresh_pillar.assert_called_with(clean_cache=True)


def test_sync_pillar_default_clean_pillar_cache():
    with patch("salt.modules.saltutil._sync"):
        with patch("salt.modules.saltutil.refresh_pillar") as refresh_pillar:
            saltutil.sync_pillar()
            refresh_pillar.assert_called_with(clean_cache=False)


def test_sync_pillar_clean_pillar_cache():
    with patch("salt.modules.saltutil._sync"):
        with patch("salt.modules.saltutil.refresh_pillar") as refresh_pillar:
            saltutil.sync_pillar(clean_pillar_cache=True)
            refresh_pillar.assert_called_with(clean_cache=True)


def test_sync_all_default_clean_pillar_cache():
    with patch("salt.modules.saltutil._sync"):
        with patch("salt.modules.saltutil.refresh_pillar") as refresh_pillar:
            saltutil.sync_all()
            refresh_pillar.assert_called_with(clean_cache=False)


def test_sync_all_clean_pillar_cache():
    with patch("salt.modules.saltutil._sync"):
        with patch("salt.modules.saltutil.refresh_pillar") as refresh_pillar:
            saltutil.sync_all(clean_pillar_cache=True)
            refresh_pillar.assert_called_with(clean_cache=True)
