import pytest

import salt.config
import salt.loader
import salt.modules.saltutil
import salt.state
from tests.support.mock import patch


@pytest.fixture
def opts(salt_master_factory):
    config_overrides = {"master_uri": "tcp://127.0.0.1:11111"}
    factory = salt_master_factory.salt_minion_daemon(
        "get-tops-minion",
        overrides=config_overrides,
    )
    yield factory.config.copy()


@pytest.fixture
def modules(opts):
    yield salt.loader.minion_mods(opts, context={})


@pytest.fixture
def configure_mocks(opts):
    with patch("salt.utils.extmods.sync", return_value=(None, None)):
        with patch.object(salt.state.HighState, "top_matches", return_value={}):
            # Mock the __gen_opts method of HighState so it doesn't try to auth to master.
            with patch.object(
                salt.state.BaseHighState, "_BaseHighState__gen_opts", return_value=opts
            ):
                # Mock the _gather_pillar method of State so it doesn't try to auth to master.
                with patch.object(salt.state.State, "_gather_pillar", return_value={}):
                    yield


@pytest.fixture
def destroy(configure_mocks):
    with patch.object(salt.state.HighState, "destroy") as destroy:
        yield destroy


@pytest.fixture
def get_top(configure_mocks):
    with patch.object(salt.state.HighState, "get_top") as get_top:
        yield get_top


def test__get_top_file_envs(modules, get_top, destroy):
    """
    Ensure we cleanup objects created by saltutil._get_top_file_envs #60449
    """
    modules["saltutil.sync_clouds"]()
    assert get_top.called
    # Ensure destroy is getting called
    assert destroy.called
