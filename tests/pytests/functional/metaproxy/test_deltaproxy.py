"""
Functional regression test for issue #68248.

``salt.metaproxy.deltaproxy.subproxy_post_master_init`` computes per
sub-proxy grains twice: first through the parent (control) proxy's loader
- which only produces placeholder values shared across all sub-proxies -
and then again, after the sub-proxy's own ``proxymodule`` ``init()`` has
been called, through that sub-proxy's loader.

The unit test for this is mock-heavy. This functional test stands up real
``salt.loader.proxy`` / ``salt.loader.grains`` loaders against an on-disk
``extension_modules`` tree containing a purpose-built proxy module that
returns ``serial_number = <sub-proxy id>``. We then drive
``subproxy_post_master_init`` for two distinct sub-proxy ids and assert
that the ``__grains__`` packed into each sub-proxy's execution-module
loader reflects *that* sub-proxy's device - not the placeholder shared
with its siblings.

Without the fix (the four ``pack["__grains__"] = proxy_grains``
assignments in ``subproxy_post_master_init``) both sub-proxies see the
same first-pass grains and ``grains.item serial_number`` would return
identical values for every controlled minion.
"""

import logging

import pytest
import tornado.concurrent
import tornado.gen
import tornado.ioloop

import salt.metaproxy.deltaproxy as deltaproxy
import salt.modules.saltutil
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


@pytest.fixture
def sub_proxy_opts(minion_opts, extension_modules, tmp_path):
    """
    Build a sub-proxy ``opts`` dict suitable for ``subproxy_post_master_init``.

    ``conf_file`` points at a file we never read from disk (we patch
    ``salt.config.proxy_config`` to a passthrough), ``extension_modules``
    points at the tree with our test-only proxymodule, and ``file_client``
    is ``local`` so the real ``saltutil.sync_all`` invocation inside the
    function under test does not try to talk to a master.
    """
    opts = dict(minion_opts)
    conf_file = tmp_path / "proxy.conf"
    conf_file.write_text("")
    opts.update(
        {
            "id": "control_proxy",
            "conf_file": str(conf_file),
            "cachedir": str(tmp_path / "cache"),
            "extension_modules": str(extension_modules),
            "saltenv": "base",
            "pillarenv": None,
            "user": None,
            "file_client": "local",
            "proxy": {
                "proxytype": "deltaproxy",
                "ids": ["device-aaa-001", "device-bbb-002"],
            },
            "proxy_keep_alive": False,
            "proxy_merge_grains_in_module": True,
            "subproxy": False,
        }
    )
    (tmp_path / "cache").mkdir(exist_ok=True)
    return opts


@pytest.fixture
def patched_subproxy_post_master_init(sub_proxy_opts):
    """
    Patch the few side-effecting pieces of ``subproxy_post_master_init``
    that are *not* part of the fix-under-test, leaving the loader stack
    real.

    - ``salt.config.proxy_config``      -> passthrough (no disk read)
    - ``salt.pillar.get_pillar``        -> returns ``proxy.proxytype`` =
                                           ``serial_test_proxy`` so the
                                           sub-proxy uses our test module
    - ``salt.utils.extmods.sync``       -> no-op so ``saltutil.sync_all``
                                           does not hit the (absent) master
    - ``salt.utils.schedule.Schedule``  -> mock; the scheduler has heavy
                                           threading state we don't exercise
    - ``salt.minion.get_proc_dir``      -> tmp dir
    """

    def _passthrough_proxy_config(conf_file, defaults, minion_id):
        return defaults

    # ``subproxy_post_master_init`` is a ``@tornado.gen.coroutine`` that
    # ``yield``s on ``get_async_pillar(...).compile_pillar()``; the mocked
    # ``compile_pillar()`` returns a resolved Future so the yield resolves
    # to the proxy-config dict.
    def _fake_pillar(opts, grains, minion_id, **kwargs):
        compiler = MagicMock()
        future = tornado.concurrent.Future()
        future.set_result({"proxy": {"proxytype": "serial_test_proxy"}})
        compiler.compile_pillar.return_value = future
        return compiler

    extmods_sync = MagicMock(return_value=({}, False))
    refresh_modules = MagicMock(return_value=True)
    schedule_mock = MagicMock()
    get_proc_dir_mock = MagicMock(return_value=sub_proxy_opts["cachedir"])

    with patch.object(
        deltaproxy.salt.config, "proxy_config", side_effect=_passthrough_proxy_config
    ), patch.object(
        deltaproxy.salt.pillar, "get_async_pillar", side_effect=_fake_pillar
    ), patch(
        "salt.utils.extmods.sync", extmods_sync
    ), patch.object(
        salt.modules.saltutil, "refresh_modules", refresh_modules
    ), patch.object(
        deltaproxy.salt.minion, "get_proc_dir", get_proc_dir_mock
    ), patch.object(
        deltaproxy.salt.utils.schedule, "Schedule", schedule_mock
    ):
        yield


def _run_subproxy_post_master_init(minion_id, sub_proxy_opts):
    """
    Drive ``subproxy_post_master_init`` for a single sub-proxy id and
    return the result dict.

    ``main_proxy`` and ``main_utils`` are loaders from the control proxy's
    perspective. For this test they only need to *exist* so the first-pass
    ``salt.loader.grains(..., proxy=main_proxy, ...)`` call has something
    to dereference; they intentionally don't contain a ``serial_test_proxy
    .grains`` callable, which is what forces the (post-init) second-pass
    grains to be the per-sub-proxy values.

    ``subproxy_post_master_init`` is a ``@tornado.gen.coroutine``; drive it
    via a dedicated IOLoop and unwrap the synchronous result.
    """
    import salt.loader

    main_proxy = salt.loader.proxy(sub_proxy_opts)
    main_utils = salt.loader.utils(sub_proxy_opts)
    loop = tornado.ioloop.IOLoop()
    try:
        return loop.run_sync(
            lambda: deltaproxy.subproxy_post_master_init(
                minion_id, 0, sub_proxy_opts, main_proxy, main_utils
            )
        )
    finally:
        loop.close()


@pytest.mark.slow_test
def test_subproxy_post_master_init_grains_are_per_device(
    sub_proxy_opts, patched_subproxy_post_master_init
):
    """
    Regression test for #68248.

    After ``subproxy_post_master_init`` returns for two distinct sub-proxy
    ids, each sub-proxy's execution-module loader must expose a
    ``__grains__`` dict whose ``serial_number`` reflects that sub-proxy's
    own device (the value the proxymodule's ``grains()`` produced under
    that sub-proxy's id) - not the placeholder shared with its siblings.

    Before the fix, both sub-proxies' loaders pointed at the same
    first-pass grains dict and ``grains.item serial_number`` returned the
    same value for every controlled minion.
    """
    result_a = _run_subproxy_post_master_init("device-aaa-001", sub_proxy_opts)
    result_b = _run_subproxy_post_master_init("device-bbb-002", sub_proxy_opts)

    sub_a = result_a["proxy_minion"]
    sub_b = result_b["proxy_minion"]
    assert sub_a is not None, "device-aaa-001 sub-proxy was not initialised"
    assert sub_b is not None, "device-bbb-002 sub-proxy was not initialised"

    # The per-sub-proxy grains dict computed *after* proxy_init must be
    # the one packed into the sub-proxy's execution-module loader. This
    # is the dict that backs ``__grains__`` inside every loaded module.
    grains_a = sub_a.functions.pack["__grains__"]
    grains_b = sub_b.functions.pack["__grains__"]
    assert grains_a["serial_number"] == "device-aaa-001"
    assert grains_b["serial_number"] == "device-bbb-002"

    # The same dict must be packed into every loader the deltaproxy fix
    # touches (functions / returners / executors / proxy) so any module
    # that reads ``__grains__`` from any of those scopes sees the right
    # device.
    for loader in (sub_a.functions, sub_a.returners, sub_a.executors, sub_a.proxy):
        assert loader.pack["__grains__"]["serial_number"] == "device-aaa-001"
    for loader in (sub_b.functions, sub_b.returners, sub_b.executors, sub_b.proxy):
        assert loader.pack["__grains__"]["serial_number"] == "device-bbb-002"

    # And the ``proxy_opts["grains"]`` returned to the caller (which the
    # control proxy stores in ``self.deltaproxy_opts``) must match so the
    # control side also has the right grains.
    assert result_a["proxy_opts"]["grains"]["serial_number"] == "device-aaa-001"
    assert result_b["proxy_opts"]["grains"]["serial_number"] == "device-bbb-002"

    # End-to-end view through the execution-module loader: calling
    # ``grains.items()`` walks the loader's ``__grains__`` pack via the
    # ``NamedLoaderContext`` wrapper. With the fix this returns the per
    # sub-proxy device grains; without the fix both sub-proxies return
    # the same shared first-pass dict.
    items_a = sub_a.functions["grains.items"]()
    items_b = sub_b.functions["grains.items"]()
    assert items_a["serial_number"] == "device-aaa-001"
    assert items_b["serial_number"] == "device-bbb-002"
    assert items_a["serial_number"] != items_b["serial_number"]
