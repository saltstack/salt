"""Refresh and reload must preserve device-specific execution/proxy dunders."""

import asyncio
import copy
import sys

import pytest

import salt.loader
import salt.minion
from salt.utils.optsdict import OptsDict
from tests.support.mock import AsyncMock, MagicMock, patch


@pytest.mark.parametrize("reload_proxy", [False, True])
def test_dunders_after_grains_pillar_refresh_and_reload(
    minion_opts, tmp_path, monkeypatch, reload_proxy
):
    """Real loaders expose fresh values without contaminating another device."""
    proxy_dir = tmp_path / "proxy"
    module_dir = tmp_path / "modules"
    proxy_dir.mkdir()
    module_dir.mkdir()
    proxy_code = """
    __proxyenabled__ = ["dunder_test"]
    DETAILS = {}

    def __virtual__():
        return True

    def init(opts):
        DETAILS["host"] = opts["proxy"]["host"]
        __context__["proxy_host"] = opts["proxy"]["host"]

    def host():
        return DETAILS["host"]

    def snapshot():
        return {
            "context": __context__["proxy_host"],
            "grains": __grains__["device_revision"],
            "pillar": __pillar__["device_revision"],
            "proxy": __proxy__["dunder_test.host"](),
        }
    """
    execution_code = """
    __proxyenabled__ = ["dunder_test"]

    def snapshot():
        return {
            "execution": {
                "context": __context__.setdefault("execution_host", __opts__["proxy"]["host"]),
                "grains": __grains__["device_revision"],
                "pillar": __pillar__["device_revision"],
                "proxy": __proxy__["dunder_test.host"](),
            },
            "proxy": __proxy__["dunder_test.snapshot"](),
        }
    """
    grain_revisions = {"device1": "grain-1", "device2": "grain-2"}
    pillar_revisions = {"device1": "pillar-1", "device2": "pillar-2"}

    def grains(opts, *args, **kwargs):
        # Like salt.loader.grains, replace the configured grains before
        # returning freshly computed device grains. An in-place update would
        # hide a stale proxy pack by leaving its original dict aliased.
        opts["grains"] = {}
        return {"device_revision": grain_revisions[opts["id"]]}

    def pillar(opts, *args, **kwargs):
        return MagicMock(
            compile_pillar=AsyncMock(
                return_value={"device_revision": pillar_revisions[opts["id"]]}
            ),
            aclose=AsyncMock(),
        )

    monkeypatch.setattr(salt.loader, "grains", grains)
    monkeypatch.setattr(salt.pillar, "get_async_pillar", pillar)
    monkeypatch.setattr(salt.utils.event, "get_event", MagicMock())

    with pytest.helpers.temp_file(
        "dunder_test.py", proxy_code, directory=proxy_dir
    ), pytest.helpers.temp_file(
        "dunder_test.py", execution_code, directory=module_dir
    ), patch.dict(
        sys.modules
    ):
        minions = []
        for minion_id in grain_revisions:
            opts = copy.deepcopy(dict(minion_opts))
            opts.update(
                id=minion_id,
                proxy={"proxytype": "dunder_test", "host": minion_id},
                proxy_dirs=[str(proxy_dir)],
                module_dirs=[str(module_dir)],
                grains={"device_revision": grain_revisions[minion_id]},
                pillar={"device_revision": pillar_revisions[minion_id]},
            )
            minion = salt.minion.ProxyMinion.__new__(salt.minion.ProxyMinion)
            # No event loop, channels or processes: only the real refresh logic
            # and loaders are under test. There are no daemon resources to close.
            minion.destroy = MagicMock()
            minion.opts = OptsDict.from_dict(opts)
            minion.loaded_base_name = f"{minion_id}.{salt.loader.lazy.LOADED_BASE_NAME}"
            minion.connected = True
            minion.beacons_refresh = MagicMock()
            minion.matchers_refresh = MagicMock()
            minion._discover_resources = MagicMock(return_value={})
            minion._register_resources_with_master = AsyncMock()
            context = {}
            minion.proxy = salt.loader.proxy(
                minion.opts, context=context, loaded_base_name=minion.loaded_base_name
            )
            minion.proxy.pack["__pillar__"] = minion.opts["pillar"]
            minion.proxy.pack["__grains__"] = minion.opts["grains"]
            minion.proxy["dunder_test.init"](minion.opts)
            (
                minion.functions,
                minion.returners,
                _,
                minion.executors,
            ) = minion._load_modules(grains=minion.opts["grains"], context=context)
            minion.schedule = MagicMock()
            minions.append(minion)

        def assert_dunders():
            for minion in minions:
                minion_id = minion.opts["id"]
                expected = {
                    "context": minion_id,
                    "grains": grain_revisions[minion_id],
                    "pillar": pillar_revisions[minion_id],
                    "proxy": minion_id,
                }
                assert minion.functions["dunder_test.snapshot"]() == {
                    "execution": expected,
                    "proxy": expected,
                }

        assert_dunders()
        for minion in minions:
            minion_id = minion.opts["id"]
            grain_revisions[minion_id] += "-refreshed"
            minion.module_refresh()
            assert_dunders()

            pillar_revisions[minion_id] += "-refreshed"
            asyncio.run(minion.pillar_refresh())
            assert_dunders()

            if reload_proxy:
                minion.proxy.reload_modules()
                minion.proxy["dunder_test.init"](minion.opts)
            else:
                (
                    minion.functions,
                    minion.returners,
                    _,
                    minion.executors,
                ) = minion._load_modules()
            assert_dunders()
