"""Compilation caches must not replace the minion snapshots used for targeting."""

import datetime
from types import SimpleNamespace

import pytest

import salt.cache
import salt.master
import salt.pillar
import salt.utils.minions
from tests.support.mock import AsyncMock, MagicMock, patch

MINION_ID = "minion-1"
PILLARS = {
    None: {"role": "all", "base_key": 1, "dev_key": 2},
    "base": {"role": "web", "base_key": 1},
    "dev": {"role": "db", "dev_key": 2},
}


@pytest.fixture
def opts(master_opts):
    master_opts.update(
        {
            "pillar_cache": True,
            "minion_data_cache": True,
            "minion_data_cache_events": False,
            "memcache_expire_seconds": 0,
            "cache": "localfs",
            "pillar.cache_driver": None,
        }
    )
    return master_opts


def _handler(opts, cache=None):
    handler = salt.master.AESFuncs.__new__(salt.master.AESFuncs)
    handler.opts = opts
    handler.masterapi = SimpleNamespace(cache=cache or salt.cache.factory(opts))
    handler.fs_ = MagicMock()
    return handler


def _request(handler, env, **kwargs):
    return handler._sync_pillar(
        {"id": MINION_ID, "grains": {}, "pillarenv": env, **kwargs}
    )


def _compiler(opts, env):
    return salt.pillar.get_pillar(opts, {}, MINION_ID, pillarenv=env)


def _matched(handler, role):
    matcher = salt.utils.minions.CkMinions.__new__(salt.utils.minions.CkMinions)
    matcher.opts = handler.opts
    matcher.cache = handler.masterapi.cache
    matcher._pki_minions = lambda: [MINION_ID]
    for method in (matcher._check_pillar_minions, matcher._check_pillar_pcre_minions):
        assert set(method(f"role:{role}", ":", True)["minions"]) == {MINION_ID}


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("env", [None, "base", "dev"])
def test_targeting_snapshot_refreshed_on_cache_hits(opts, enabled, env):
    opts["pillar_cache"] = enabled
    handler = _handler(opts)
    with patch(
        "salt.pillar.Pillar.compile_pillar", return_value=PILLARS[env]
    ) as compile_:
        assert _request(handler, env) == PILLARS[env]
        _matched(handler, PILLARS[env]["role"])
        # Clearing minion data must not require a recompilation to repair it.
        handler.masterapi.cache.flush("pillar", MINION_ID)
        assert _request(handler, env) == PILLARS[env]
        assert compile_.call_count == (1 if enabled else 2)
        _matched(handler, PILLARS[env]["role"])


def test_environment_isolation_and_queries_do_not_replace_snapshots(opts):
    handler = _handler(opts)
    with patch(
        "salt.pillar.Pillar.compile_pillar",
        autospec=True,
        side_effect=lambda pillar: PILLARS[pillar.opts["pillarenv"]],
    ) as compile_:
        assert _request(handler, None) == PILLARS[None]
        assert _request(handler, "base") == PILLARS["base"]
        assert _request(handler, None) == PILLARS[None]
        assert compile_.call_count == 2
        _matched(handler, "all")
        assert _compiler(opts, "dev").compile_pillar() == PILLARS["dev"]
        assert handler.masterapi.cache.fetch("pillar", MINION_ID) == PILLARS[None]


def test_compilation_cache_and_snapshot_clear_independently(opts):
    handler = _handler(opts)
    compiler = _compiler(opts, "base")
    with patch(
        "salt.pillar.Pillar.compile_pillar", return_value=PILLARS["base"]
    ) as compile_:
        _request(handler, "base")
        compiler.clear_pillar()
        assert handler.masterapi.cache.fetch("pillar", MINION_ID) == PILLARS["base"]
        _request(handler, "base")
        assert compile_.call_count == 2
        handler.masterapi.cache.flush("pillar", MINION_ID)
        assert compiler.cached_pillar() == PILLARS["base"]


def test_clean_cache_recompiles_and_refreshes_snapshot(opts):
    handler = _handler(opts)
    updated = {"role": "updated"}
    with patch(
        "salt.pillar.Pillar.compile_pillar", side_effect=[PILLARS["base"], updated]
    ) as compile_:
        assert _request(handler, "base") == PILLARS["base"]
        assert _request(handler, "base", clean_cache=True) == updated
        assert compile_.call_count == 2
    _matched(handler, "updated")


def test_legacy_pillar_entries_are_not_used_as_compilation_cache(opts):
    cache = salt.cache.factory(opts)
    legacy = {"role": "legacy"}
    cache.store("pillar", MINION_ID, legacy)
    cache.store("pillar", f"{MINION_ID}:base", legacy)
    with patch(
        "salt.pillar.Pillar.compile_pillar", return_value=PILLARS["base"]
    ) as compile_:
        assert _compiler(opts, "base").compile_pillar() == PILLARS["base"]
        assert _compiler(opts, None).cached_pillar() == {}
        compile_.assert_called_once()
    assert cache.fetch("pillar", MINION_ID) == legacy


def test_compilation_cache_uses_separate_backend(opts, tmp_path):
    snapshot_cache = salt.cache.factory(
        {**opts, "cachedir": str(tmp_path / "snapshots")}
    )
    compile_cache = salt.cache.factory({**opts, "cachedir": str(tmp_path / "compiled")})
    opts["pillar.cache_driver"] = "separate"

    def factory(config, **kwargs):
        return compile_cache if kwargs.get("driver") == "separate" else snapshot_cache

    with patch("salt.cache.factory", side_effect=factory), patch(
        "salt.pillar.Pillar.compile_pillar", return_value=PILLARS["base"]
    ) as compile_:
        handler = _handler(opts)
        _request(handler, "base")
        _request(handler, "base")
        assert compile_.call_count == 1
        _matched(handler, "web")
    assert snapshot_cache.fetch("pillar", MINION_ID) == PILLARS["base"]
    assert snapshot_cache.fetch("pillar_compile", f"{MINION_ID}:base") == {}
    assert compile_cache.fetch("pillar_compile", f"{MINION_ID}:base") == PILLARS["base"]
    assert compile_cache.fetch("pillar", MINION_ID) == {}


def test_no_snapshot_without_minion_data_cache(opts):
    opts["minion_data_cache"] = False
    handler = _handler(opts)
    with patch(
        "salt.pillar.Pillar.compile_pillar", return_value=PILLARS["base"]
    ) as compile_:
        _request(handler, "base")
        _request(handler, "base")
        compile_.assert_called_once()
    assert handler.masterapi.cache.fetch("pillar", MINION_ID) == {}


def test_request_overrides_do_not_enter_compilation_cache(opts):
    handler = _handler(opts)
    override = {"temporary": "request-only"}
    with patch("salt.pillar.Pillar.compile_pillar", return_value=PILLARS["base"]):
        result = _request(handler, "base", pillar_override=override)
        assert result == {**PILLARS["base"], **override}
        assert handler.masterapi.cache.fetch("pillar", MINION_ID) == result
        assert _compiler(opts, "base").cached_pillar() == PILLARS["base"]
        assert _request(handler, "base") == PILLARS["base"]


def test_compilation_ttl_does_not_expire_snapshot(opts):
    real_datetime = datetime.datetime
    elapsed = datetime.timedelta()

    class Clock(real_datetime):
        @classmethod
        def now(cls, tz=None):
            return real_datetime.now(tz) + elapsed

    opts["pillar_cache_ttl"] = 60
    handler = _handler(opts)
    with patch("salt.cache.datetime.datetime", Clock), patch(
        "salt.pillar.Pillar.compile_pillar", return_value=PILLARS["base"]
    ) as compile_:
        _request(handler, "base")
        elapsed = datetime.timedelta(seconds=61)
        assert _compiler(opts, "base").cached_pillar() == {}
        assert handler.masterapi.cache.fetch("pillar", MINION_ID) == PILLARS["base"]
        _request(handler, "base")
        assert compile_.call_count == 2


@pytest.mark.parametrize("enabled", [False, True])
async def test_async_master_updates_snapshot(opts, enabled):
    opts["minion_data_cache"] = enabled
    handler = _handler(opts)
    pillar = SimpleNamespace(compile_pillar=AsyncMock(return_value=PILLARS["base"]))
    with patch("salt.pillar.get_async_pillar", return_value=pillar):
        assert (
            await handler._pillar({"id": MINION_ID, "grains": {}, "pillarenv": "base"})
            == PILLARS["base"]
        )
    snapshot = handler.masterapi.cache.fetch("pillar", MINION_ID)
    assert snapshot == (PILLARS["base"] if enabled else {})
    if enabled:
        _matched(handler, "web")
