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


@pytest.mark.slow_test
def test__get_top_file_envs(modules, get_top, destroy):
    """
    Ensure we cleanup objects created by saltutil._get_top_file_envs #60449
    """
    modules["saltutil.sync_clouds"]()
    assert get_top.called
    # Ensure destroy is getting called
    assert destroy.called


def test_refresh_grains_regenerates_cached_grain_value(
    minion_opts, tmp_path, monkeypatch
):
    """
    Functional regression test for #55667.

    With ``grains_cache`` enabled, ``salt.loader.grains`` serves grain values
    from the on-disk cache without re-running the grain functions.
    ``saltutil.refresh_grains`` must invalidate that cache so a changed grain
    value actually takes effect on the next load -- the real end-to-end
    behaviour the unit tests only approximate. Exercised through the real
    ``minion_mods`` loader and the real grains loader; only the orthogonal
    pillar refresh is mocked (it just avoids master auth and does not touch the
    grains cache). Without the fix the cache survives, the stale value persists,
    and the final assertion fails.
    """
    # A custom grain whose value we drive via an environment variable, so we can
    # change "the source" between loads without touching the grains cache.
    grains_dir = tmp_path / "grains"
    grains_dir.mkdir()
    (grains_dir / "refresh55667.py").write_text(
        "import os\n\n\n"
        "def refresh55667():\n"
        '    return {"refresh55667_grain": os.environ.get("REFRESH55667_CTL", "")}\n'
    )
    minion_opts["cachedir"] = str(tmp_path)
    minion_opts["grains_cache"] = True
    minion_opts["grains_dirs"] = [str(grains_dir)]
    cache_file = tmp_path / "grains.cache.p"

    # First load runs the grain and writes the on-disk cache.
    monkeypatch.setenv("REFRESH55667_CTL", "before")
    assert salt.loader.grains(minion_opts)["refresh55667_grain"] == "before"
    assert cache_file.is_file()

    # The source changes, but a plain load still serves the stale cached value.
    monkeypatch.setenv("REFRESH55667_CTL", "after")
    assert salt.loader.grains(minion_opts)["refresh55667_grain"] == "before"

    # refresh_grains (real module, real __opts__) invalidates the cache.
    modules = salt.loader.minion_mods(minion_opts, context={})
    with patch("salt.modules.saltutil.refresh_pillar"):
        modules["saltutil.refresh_grains"]()
    assert not cache_file.exists()

    # The refreshed grain value now takes effect.
    assert salt.loader.grains(minion_opts)["refresh55667_grain"] == "after"
