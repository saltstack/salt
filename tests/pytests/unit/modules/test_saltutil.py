import pytest

import salt.modules.saltutil as saltutil
from salt.client import LocalClient
from tests.support.mock import create_autospec
from tests.support.mock import sentinel as s


@pytest.fixture
def configure_loader_modules():
    return {saltutil: {}}


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
