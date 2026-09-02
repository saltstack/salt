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

import salt.metaproxy.deltaproxy as deltaproxy
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
        def __init__(self, opts):
            self.opts = opts
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


# ---------------------------------------------------------------------------
# job dispatch: no double-fork, and no process-title pollution
# ---------------------------------------------------------------------------


def _run_thread_return(tmp_path, multiprocessing):
    """
    Drive ``deltaproxy.thread_return`` far enough to cover the process setup at
    the top of the function, and report what it did to the process.
    """
    proc_dir = tmp_path / "proc"
    proc_dir.mkdir()

    minion_instance = MagicMock()
    minion_instance.proc_dir = str(proc_dir)

    opts = {
        "multiprocessing": multiprocessing,
        "id": "minion1",
        "cachedir": str(tmp_path),
        "module_executors": ["direct_call"],
    }
    data = {"jid": "20260101000000000001", "fun": "test.ping", "arg": [], "ret": ""}

    class ProxyMinion:
        """Stand-in for the class deltaproxy names in the process title."""

    with patch("salt.utils.process.appendproctitle") as appendproctitle, patch(
        "salt.utils.process.daemonize_if"
    ) as daemonize_if:
        deltaproxy.thread_return(ProxyMinion, minion_instance, opts, data)

    return appendproctitle, daemonize_if


def test_thread_return_does_not_daemonize(tmp_path):
    """
    The job must stay inside the salt-proxy process tree.

    ``daemonize_if`` double-forks and ``setsid``s the job out of the proxy's
    process tree, so the parent's ``SubprocessList`` entry dies immediately and
    neither ``process_count_max`` nor the shutdown path can see or control the
    process that is really doing the work.  The same block was removed from
    ``salt/minion.py`` and ``salt/metaproxy/proxy.py`` in 9f1fe42b3cc; the
    deltaproxy copy kept it.
    """
    _, daemonize_if = _run_thread_return(tmp_path, multiprocessing=True)
    assert not daemonize_if.called


def test_thread_return_sets_proctitle_only_when_multiprocessing(tmp_path):
    """
    With ``multiprocessing: False`` the job runs in a thread of the live
    salt-proxy process, so appending to the process title rewrites the title of
    the running daemon.  Every job appends again until the argv buffer is full,
    leaving ``ps`` output a wall of repeated ``_thread_return``.  This is the
    same pollution #68553 fixed for ``salt/minion.py``.
    """
    appendproctitle, _ = _run_thread_return(tmp_path, multiprocessing=False)
    assert not appendproctitle.called


def test_thread_return_still_sets_proctitle_when_forking(tmp_path):
    """
    Inverse of the above: when the job really does get its own process the
    title is that process's own, so it must still be set -- the guard must not
    silently drop the title everywhere.
    """
    appendproctitle, _ = _run_thread_return(tmp_path, multiprocessing=True)
    assert appendproctitle.called
