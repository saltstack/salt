"""
Unit tests for ``salt.metaproxy.deltaproxy.subproxy_post_master_init``.

These tests pin down the data flow inside ``subproxy_post_master_init`` so
each sub-proxy ends up with grains/pillar values that reflect *that*
sub-proxy's own proxymodule, not whatever was loaded the first time through
the parent (control) proxy's loader.
"""

import logging

import pytest
import tornado.concurrent
import tornado.gen
import tornado.ioloop

import salt.loader.lazy
import salt.metaproxy.deltaproxy as deltaproxy
import salt.minion
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


class _FakeLoader(dict):
    """
    Mimic ``salt.loader.LazyLoader``'s ``.pack`` attribute, dict-style
    function access and ``.reload_modules`` for the deltaproxy code path.
    """

    def __init__(self, items=None, pack=None):
        super().__init__(items or {})
        self.pack = pack if pack is not None else {}
        self.utils = None

    def reload_modules(self):
        # Real LazyLoaders re-read self.pack into the underlying module
        # namespaces. The test only cares that the pack dict is what the
        # code finally stamped, so a no-op is fine.
        pass


@pytest.fixture
def fake_main_proxy():
    return _FakeLoader()


@pytest.fixture
def fake_main_utils():
    return _FakeLoader()


@pytest.fixture
def proxy_opts(tmp_path):
    return {
        "id": "control_proxy",
        "conf_file": str(tmp_path / "proxy"),
        "cachedir": str(tmp_path / "cache"),
        "saltenv": "base",
        "pillarenv": None,
        "extension_modules": str(tmp_path / "ext"),
        "proxy": {"proxytype": "deltaproxy", "ids": ["minion1", "minion2"]},
        "user": None,
        "proxy_keep_alive": False,
    }


def _make_subproxy_patches(per_minion_grains):
    """
    Build the patches needed to call ``subproxy_post_master_init`` without
    touching disk or spinning up real loaders. ``per_minion_grains`` maps
    sub-proxy id -> the grains dict that the *second* ``salt.loader.grains``
    call (the post-init refresh) should return for that id.
    """

    proxy_config_mock = MagicMock(
        side_effect=lambda conf_file, defaults, minion_id: defaults
    )

    # The pillar load for each sub-proxy gives that minion a proxy config so
    # the function does not bail out at the "no proxy in pillar" guard.
    # ``subproxy_post_master_init`` is a ``@tornado.gen.coroutine`` that
    # ``yield``s on ``get_async_pillar(...).compile_pillar()``; the mocked
    # ``compile_pillar()`` must return a resolved Future so the yield
    # resolves to the proxy-config dict.
    def _fake_pillar(opts, grains, minion_id, **kwargs):
        compiler = MagicMock()
        future = tornado.concurrent.Future()
        future.set_result({"proxy": {"proxytype": "dummy_test_proxy"}})
        compiler.compile_pillar.return_value = future
        return compiler

    get_pillar_mock = MagicMock(side_effect=_fake_pillar)

    # The grains loader is called twice per sub-proxy: first with the parent
    # control proxy (returns the placeholder), then again post-init with the
    # sub-proxy's own proxymodule (returns the per-id distinguishing dict).
    placeholder_grains = {"placeholder": True}
    call_state = {"count": 0}

    def _fake_grains(opts, proxy=None, context=None, **kwargs):
        call_state["count"] += 1
        # Return a fresh dict each call so identity comparisons stay honest.
        if call_state["count"] % 2 == 1:
            return dict(placeholder_grains)
        return dict(per_minion_grains[opts["id"]])

    grains_mock = MagicMock(side_effect=_fake_grains)

    # The proxy/utils loaders just need to look like LazyLoaders that already
    # contain the per-proxy ``init``/``alive`` callables the code touches.
    def _fake_proxy_loader(opts, utils=None, context=None, **kwargs):
        proxytype = opts["proxy"]["proxytype"]
        return _FakeLoader(
            items={
                f"{proxytype}.init": MagicMock(return_value=True),
                f"{proxytype}.shutdown": MagicMock(return_value=True),
                f"{proxytype}.module_executors": MagicMock(
                    return_value=["direct_call"]
                ),
            }
        )

    proxy_loader_mock = MagicMock(side_effect=_fake_proxy_loader)
    utils_loader_mock = MagicMock(side_effect=lambda *a, **kw: _FakeLoader())

    # The ProxyMinion is replaced with a lightweight stand-in so we do not
    # touch the real network/event-loop machinery. We still need
    # ``_load_modules`` to feed real-looking LazyLoaders (with ``.pack``)
    # into the function under test.
    def _fake_load_modules(self, opts=None, grains=None, context=None, **kwargs):
        functions = _FakeLoader(
            items={"saltutil.sync_all": MagicMock(return_value=[])},
            pack={"__grains__": grains, "__opts__": opts},
        )
        returners = _FakeLoader(pack={"__grains__": grains, "__opts__": opts})
        executors = _FakeLoader(pack={"__grains__": grains, "__opts__": opts})
        return functions, returners, {}, executors

    class _FakeProxyMinion:
        def __init__(self, opts, loaded_base_name=None):
            self.opts = opts
            self.loaded_base_name = loaded_base_name
            self.subprocess_list = MagicMock()
            self.connected = False

        _load_modules = _fake_load_modules

    fake_proxy_minion_cls = _FakeProxyMinion
    get_proc_dir_mock = MagicMock(return_value="/tmp/proc")
    schedule_mock = MagicMock()

    return {
        "proxy_config": proxy_config_mock,
        "get_pillar": get_pillar_mock,
        "grains": grains_mock,
        "proxy_loader": proxy_loader_mock,
        "utils_loader": utils_loader_mock,
        "proxy_minion_cls": fake_proxy_minion_cls,
        "get_proc_dir": get_proc_dir_mock,
        "schedule": schedule_mock,
    }


def test_subproxy_post_master_init_packs_per_minion_grains(
    proxy_opts, fake_main_proxy, fake_main_utils
):
    """
    Regression test for #68248.

    Each sub-proxy must end up with grains in its execution-module loader
    that reflect the values produced by *its own* proxymodule, not the
    placeholder values the control proxy returned on the first pass.
    """
    per_minion_grains = {
        "minion1": {"serial_number": "SN-AAA-001", "id": "minion1"},
        "minion2": {"serial_number": "SN-BBB-002", "id": "minion2"},
    }
    p = _make_subproxy_patches(per_minion_grains)

    # ``subproxy_post_master_init`` is a ``@tornado.gen.coroutine``; drive it
    # via a dedicated IOLoop so the mocked pillar Future resolves on the
    # current loop and the coroutine runs to completion.
    loop = tornado.ioloop.IOLoop()
    with patch.object(
        deltaproxy.salt.config, "proxy_config", p["proxy_config"]
    ), patch.object(
        deltaproxy.salt.pillar, "get_async_pillar", p["get_pillar"]
    ), patch.object(
        deltaproxy.salt.loader, "grains", p["grains"]
    ), patch.object(
        deltaproxy.salt.loader, "proxy", p["proxy_loader"]
    ), patch.object(
        deltaproxy.salt.loader, "utils", p["utils_loader"]
    ), patch.object(
        deltaproxy, "ProxyMinion", p["proxy_minion_cls"]
    ), patch.object(
        deltaproxy.salt.minion, "get_proc_dir", p["get_proc_dir"]
    ), patch.object(
        deltaproxy.salt.utils.schedule, "Schedule", p["schedule"]
    ):
        try:
            result1 = loop.run_sync(
                lambda: deltaproxy.subproxy_post_master_init(
                    "minion1", 0, proxy_opts, fake_main_proxy, fake_main_utils
                )
            )
            result2 = loop.run_sync(
                lambda: deltaproxy.subproxy_post_master_init(
                    "minion2", 0, proxy_opts, fake_main_proxy, fake_main_utils
                )
            )
        finally:
            loop.close()

    sub1 = result1["proxy_minion"]
    sub2 = result2["proxy_minion"]
    assert sub1 is not None
    assert sub2 is not None

    # The per-sub-proxy grains dict computed *after* init must be what the
    # execution-module loader exposes to modules via ``__grains__``. Without
    # the fix, both sub-proxies see the placeholder grains from the first
    # (parent-proxy) pass.
    assert sub1.functions.pack["__grains__"]["serial_number"] == "SN-AAA-001"
    assert sub2.functions.pack["__grains__"]["serial_number"] == "SN-BBB-002"

    # And the proxy loader's pack must agree, otherwise grain modules that
    # consult ``__grains__`` from within the proxy module will also see
    # stale values.
    assert sub1.proxy.pack["__grains__"]["serial_number"] == "SN-AAA-001"
    assert sub2.proxy.pack["__grains__"]["serial_number"] == "SN-BBB-002"

    # ``proxyopts["grains"]`` returned to the caller must match too so the
    # control proxy stores the right grains in ``self.deltaproxy_opts``.
    assert result1["proxy_opts"]["grains"]["serial_number"] == "SN-AAA-001"
    assert result2["proxy_opts"]["grains"]["serial_number"] == "SN-BBB-002"


def test_attach_req_channel_gives_the_subproxy_a_token():
    """
    Regression test for #70071.

    A sub-proxy is constructed directly rather than going through
    ``connect_master``, which is where an ordinary minion picks up
    ``self.tok``, so the attribute was simply missing.  Every read of it
    raised ``AttributeError`` -- in practice from
    ``_register_resources_with_master``, which ``pillar_refresh`` calls, so
    each ``saltutil.refresh_pillar`` and ``saltutil.refresh_grains`` failed to
    register that sub-proxy's resources with the master.
    """
    proxy_minion = MagicMock(spec=["req_channel", "tok"])
    channel = MagicMock()
    channel.auth.gen_token.return_value = b"a-real-token"

    with patch.object(
        deltaproxy.salt.channel.client.AsyncReqChannel, "factory", return_value=channel
    ) as factory:
        returned = deltaproxy.attach_req_channel(
            proxy_minion, {"id": "minion1"}, "an-io-loop"
        )

    # The channel is still built exactly as before ...
    assert factory.called
    assert factory.call_args[0][0] == {"id": "minion1"}
    assert factory.call_args[1]["io_loop"] == "an-io-loop"
    assert returned is channel
    assert proxy_minion.req_channel is channel

    # ... and the sub-proxy now has a real token derived from its auth.
    channel.auth.gen_token.assert_called_once_with(b"salt")
    assert proxy_minion.tok == b"a-real-token"


def test_attach_req_channel_without_auth_does_not_raise():
    """
    Inverse: a clear channel has no ``auth``, and that must leave the
    sub-proxy usable rather than blowing up while wiring it in.
    """
    proxy_minion = MagicMock(spec=["req_channel"])
    channel = MagicMock(spec=[])  # no .auth

    with patch.object(
        deltaproxy.salt.channel.client.AsyncReqChannel, "factory", return_value=channel
    ):
        deltaproxy.attach_req_channel(proxy_minion, {"id": "minion1"}, None)

    assert proxy_minion.req_channel is channel
    assert not hasattr(proxy_minion, "tok")


# ---------------------------------------------------------------------------
# parallel_startup must behave like serial startup
# ---------------------------------------------------------------------------


def test_gather_subproxies_skips_the_one_that_failed():
    """
    One sub-proxy failing to initialise must not take the others down.

    A bad ``proxytype`` makes the proxy loader raise ``KeyError`` on
    ``<proxytype>.init``.  Before the fix that exception propagated out of
    ``asyncio.gather`` and aborted the control proxy's ``post_master_init``,
    killing the salt-proxy daemon and every healthy sub-proxy with it, while
    the non-parallel branch skipped the failure and carried on.
    """

    async def _ok(value):
        return value

    async def _boom():
        raise KeyError("nosuchproxytype_xyz.init")

    loop = tornado.ioloop.IOLoop()
    try:
        collected = loop.run_sync(
            lambda: deltaproxy.gather_subproxies(
                [_ok("A"), _boom(), _ok("C")],
                ["minionA", "minionB", "minionC"],
            )
        )
    finally:
        loop.close()

    # The healthy sub-proxies survive and the failure is dropped, rather than
    # the whole coroutine raising.
    assert collected == ["A", "C"]


def test_gather_subproxies_passes_everything_through_when_all_succeed():
    """
    Inverse of the above: with no failures nothing may be dropped or
    reordered, so the skip path cannot silently eat healthy sub-proxies.
    """

    async def _ok(value):
        return value

    loop = tornado.ioloop.IOLoop()
    try:
        collected = loop.run_sync(
            lambda: deltaproxy.gather_subproxies(
                [_ok("A"), _ok("B"), _ok("C")],
                ["minionA", "minionB", "minionC"],
            )
        )
    finally:
        loop.close()

    assert collected == ["A", "B", "C"]


def test_subproxy_tune_in_starts_periodics_on_the_running_loop():
    """
    ``PeriodicCallback.start()`` binds to ``IOLoop.current()``.  Under
    ``parallel_startup`` ``subproxy_tune_in`` runs on a ThreadPoolExecutor
    worker whose current asyncio loop is a throwaway that is never run, so
    starting the timers inline bound every one of them to a dead loop and the
    sub-proxy silently got no schedule, no beacons and no subprocess cleanup.

    The registration must therefore be handed to the sub-proxy's own
    ``io_loop`` instead of being run inline.
    """
    calls = []

    class _FakeSubProxy:
        def __init__(self):
            self.io_loop = MagicMock()

        def setup_scheduler(self):
            calls.append("scheduler")

        def setup_beacons(self):
            calls.append("beacons")

        def add_periodic_callback(self, name, method):
            calls.append(f"periodic:{name}")

        def cleanup_subprocesses(self):
            pass

        def _state_run(self):
            calls.append("state_run")

    proxy_minion = _FakeSubProxy()
    deltaproxy.subproxy_tune_in(proxy_minion)

    # Inverse must-not: none of the periodic registrations may happen inline,
    # because inline means "bound to whatever loop this thread happens to
    # have", which is the dead one under parallel_startup.
    assert "scheduler" not in calls
    assert "beacons" not in calls
    assert "periodic:cleanup" not in calls

    # They must instead be queued onto the sub-proxy's own loop, thread-safely.
    assert proxy_minion.io_loop.call_soon_threadsafe.called
    queued = proxy_minion.io_loop.call_soon_threadsafe.call_args[0][0]

    # And running what was queued must perform all three registrations.
    # ``_state_run`` still happens inline, so it lands ahead of them.
    assert calls == ["state_run"]
    queued()
    assert calls == ["state_run", "scheduler", "beacons", "periodic:cleanup"]


def test_subproxy_post_master_init_gives_each_subproxy_its_own_loader_namespace(
    proxy_opts, fake_main_proxy, fake_main_utils
):
    """
    Regression test for #70144.

    Every sub-proxy must be built with its own ``loaded_base_name`` so the
    loader gives it distinct module objects.  Sharing one namespace makes the
    loader hand every sub-proxy the *same* execution-module objects, so
    whichever sub-proxy packs a module last owns that module's ``__opts__``
    for the life of the process.  On a proxy running ``multiprocessing:
    False`` that made every later SLS render resolve grains/pillar/``id``
    from the wrong sub-proxy until the deltaproxy was restarted.
    """
    per_minion_grains = {
        "minion1": {"serial_number": "SN-AAA-001", "id": "minion1"},
        "minion2": {"serial_number": "SN-BBB-002", "id": "minion2"},
    }
    p = _make_subproxy_patches(per_minion_grains)

    loop = tornado.ioloop.IOLoop()
    with patch.object(
        deltaproxy.salt.config, "proxy_config", p["proxy_config"]
    ), patch.object(
        deltaproxy.salt.pillar, "get_async_pillar", p["get_pillar"]
    ), patch.object(
        deltaproxy.salt.loader, "grains", p["grains"]
    ), patch.object(
        deltaproxy.salt.loader, "proxy", p["proxy_loader"]
    ), patch.object(
        deltaproxy.salt.loader, "utils", p["utils_loader"]
    ), patch.object(
        deltaproxy, "ProxyMinion", p["proxy_minion_cls"]
    ), patch.object(
        deltaproxy.salt.minion, "get_proc_dir", p["get_proc_dir"]
    ), patch.object(
        deltaproxy.salt.utils.schedule, "Schedule", p["schedule"]
    ):
        try:
            result1 = loop.run_sync(
                lambda: deltaproxy.subproxy_post_master_init(
                    "minion1", 0, proxy_opts, fake_main_proxy, fake_main_utils
                )
            )
            result2 = loop.run_sync(
                lambda: deltaproxy.subproxy_post_master_init(
                    "minion2", 0, proxy_opts, fake_main_proxy, fake_main_utils
                )
            )
        finally:
            loop.close()

    sub1 = result1["proxy_minion"]
    sub2 = result2["proxy_minion"]

    # Each sub-proxy is namespaced by its own minion id.
    assert sub1.loaded_base_name == f"minion1.{salt.loader.lazy.LOADED_BASE_NAME}"
    assert sub2.loaded_base_name == f"minion2.{salt.loader.lazy.LOADED_BASE_NAME}"

    # Inverse must-not: the two sub-proxies must never share a namespace, and
    # neither may fall back to the global default that caused #70144.
    assert sub1.loaded_base_name != sub2.loaded_base_name
    assert sub1.loaded_base_name is not None
    assert sub2.loaded_base_name is not None
    assert salt.loader.lazy.LOADED_BASE_NAME not in (
        sub1.loaded_base_name.split(".")[0],
        sub2.loaded_base_name.split(".")[0],
    )


def test_load_modules_forwards_loaded_base_name_to_minion_mods(minion_opts):
    """
    Regression test for #70144.

    ``subproxy_post_master_init`` handing each sub-proxy a ``loaded_base_name``
    only isolates them if ``_load_modules`` actually forwards it to
    ``salt.loader.minion_mods``.  The non-multimaster branch used to drop it,
    which left every sub-proxy back in the shared default namespace.
    """
    minion_opts["grains"] = {}
    minion = salt.minion.Minion(
        minion_opts,
        loaded_base_name="sub1.salt.loaded",
        io_loop=tornado.ioloop.IOLoop(),
    )
    try:
        with patch.object(
            salt.loader, "minion_mods", return_value={}
        ) as minion_mods_mock, patch.object(
            salt.loader, "returners", return_value={}
        ), patch.object(
            salt.loader, "executors", return_value={}
        ), patch.object(
            salt.loader, "utils", return_value={}
        ), patch.object(
            salt.loader, "grains", return_value={}
        ):
            minion._load_modules(grains={})

        assert minion_mods_mock.called
        assert (
            minion_mods_mock.call_args.kwargs["loaded_base_name"] == "sub1.salt.loaded"
        )
    finally:
        minion.destroy()


def test_subproxy_post_master_init_sets_module_executors(
    proxy_opts, fake_main_proxy, fake_main_utils
):
    """
    A proxymodule may declare the executors its functions must run through.
    ``post_master_init`` reads that for the control proxy, but sub-proxies never
    had it set, so ``thread_return`` fell through to the opts default and the
    proxymodule's declaration was silently ignored for every sub-proxy.
    """
    per_minion_grains = {
        "minion1": {"serial_number": "SN-AAA-001", "id": "minion1"},
        "minion2": {"serial_number": "SN-BBB-002", "id": "minion2"},
    }
    p = _make_subproxy_patches(per_minion_grains)

    loop = tornado.ioloop.IOLoop()
    with patch.object(
        deltaproxy.salt.config, "proxy_config", p["proxy_config"]
    ), patch.object(
        deltaproxy.salt.pillar, "get_async_pillar", p["get_pillar"]
    ), patch.object(
        deltaproxy.salt.loader, "grains", p["grains"]
    ), patch.object(
        deltaproxy.salt.loader, "proxy", p["proxy_loader"]
    ), patch.object(
        deltaproxy.salt.loader, "utils", p["utils_loader"]
    ), patch.object(
        deltaproxy, "ProxyMinion", p["proxy_minion_cls"]
    ), patch.object(
        deltaproxy.salt.minion, "get_proc_dir", p["get_proc_dir"]
    ), patch.object(
        deltaproxy.salt.utils.schedule, "Schedule", p["schedule"]
    ):
        try:
            result = loop.run_sync(
                lambda: deltaproxy.subproxy_post_master_init(
                    "minion1", 0, proxy_opts, fake_main_proxy, fake_main_utils
                )
            )
        finally:
            loop.close()

    sub = result["proxy_minion"]
    assert sub is not None
    # thread_return reads this off the sub-proxy via getattr; it must be there.
    assert getattr(sub, "module_executors", None) == ["direct_call"]


@pytest.mark.parametrize("deep_merge", [False, True])
@pytest.mark.parametrize("merge_pillar_in_opts", [False, True])
def test_post_master_init_pillar_proxy_block_wins_over_opts(
    merge_pillar_in_opts, deep_merge
):
    """
    The control proxy's proxytype and ids live in its pillar, so the pillar
    ``proxy`` block must still win over a ``proxy`` block in its config when
    ``proxy_merge_pillar_in_opts`` is off.  Gating the whole merge left
    ``proxytype``/``ids`` from config in place, so no sub-proxy started.
    Only the rest of the pillar is gated by the option.
    """

    class _StopAfterMerge(Exception):
        pass

    pillar = {
        "proxy": {
            "proxytype": "deltaproxy",
            "ids": ["minion1", "minion2"],
            "parallel_startup": True,
        },
        "n_marker": "FROM_PILLAR",
    }
    opts = {
        "id": "control_proxy",
        "proxy": {"proxytype": "dummy", "ids": ["minion1"], "only_in_opts": True},
        "pillar": pillar,
        "proxy_merge_pillar_in_opts": merge_pillar_in_opts,
        "proxy_merge_pillar_in_opts_strategy": "smart",
        "proxy_deep_merge_pillar_in_opts": deep_merge,
        "proxy_mines_pillar": True,
    }
    # Stop at the first call after the merge; only the resulting opts matter.
    fake_self = MagicMock(
        connected=False,
        opts=opts,
        _load_modules=MagicMock(side_effect=_StopAfterMerge),
    )

    loop = tornado.ioloop.IOLoop()
    try:
        with pytest.raises(_StopAfterMerge):
            loop.run_sync(lambda: deltaproxy.post_master_init(fake_self, "master"))
    finally:
        loop.close()

    # Merged, not replaced, and ``ids`` is not doubled up.
    assert fake_self.opts["proxy"] == {
        "proxytype": "deltaproxy",
        "ids": ["minion1", "minion2"],
        "parallel_startup": True,
        "only_in_opts": True,
    }
    # Inverse must-not: the rest of the pillar only reaches opts when asked.
    assert ("n_marker" in fake_self.opts) is merge_pillar_in_opts
