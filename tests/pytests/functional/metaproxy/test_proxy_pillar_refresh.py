"""
Functional regression test for issue #58197.

A proxy minion packs the compiled pillar into its proxy module loader once,
at init, by reference::

    self.proxy.pack["__pillar__"] = self.opts["pillar"]

``Minion.pillar_refresh`` compiles a fresh pillar and *rebinds*
``self.opts["pillar"]`` to the new dict. That rebind orphans the dict the
proxy loader's ``pack["__pillar__"]`` still aliases, so already-loaded proxy
modules keep serving the pillar they were first packed with -- forever, until
the proxy is restarted.

The fix re-packs the loader after the rebind::

    if getattr(self, "proxy", None):
        self.proxy.pack["__pillar__"] = self.opts["pillar"]

These tests stand up a *real* ``salt.loader.proxy`` loader against an on-disk
``extension_modules`` tree containing a purpose-built proxy module that reads
``__pillar__`` at call time (the stock ``dummy`` proxy does not). They assert
that after a refresh an already-loaded proxy module observes the new pillar,
that the fix does not reload the modules (same ``LoadedFunc`` identity, the
``init()``-populated ``__context__`` connection object survives), and -- for
deltaproxy -- that each sub-proxy is refreshed with *its own* pillar.

The out-of-scope boundary is deliberately not asserted here: ``__opts__``,
``__opts__["pillar"]`` and any value a module copied out of pillar during
``init()`` are load-time snapshots that stay stale under any non-reload fix.
"""

import textwrap

import pytest
import tornado.concurrent
import tornado.ioloop

import salt.loader
import salt.minion
from salt.exceptions import SaltClientError
from tests.support.mock import MagicMock, patch


@pytest.fixture
def echo_extension_modules(tmp_path):
    """
    Lay down an ``extension_modules`` tree with a proxy module that reads
    ``__pillar__`` at call time and stashes a sentinel "connection" object in
    ``__context__`` during ``init()``.
    """
    ext = tmp_path / "ext_echo"
    proxy_dir = ext / "proxy"
    proxy_dir.mkdir(parents=True)
    (ext / "__init__.py").write_text("")

    proxy_module = textwrap.dedent(
        '''
        """
        Test-only proxy module for tests/pytests/functional/metaproxy.

        ``read_pillar_key`` resolves ``__pillar__`` through the loader's
        ``NamedLoaderContext`` on every call, so it reflects whatever the
        loader currently has packed for ``__pillar__``. ``init()`` stashes a
        unique object in ``__context__`` so a test can prove the module was
        not reloaded / re-initialised across a pillar refresh.
        """

        __proxyenabled__ = ["*"]


        def __virtual__():
            return True


        def init(opts):
            __context__["conn"] = object()
            return True


        def initialized():
            return "conn" in __context__


        def read_pillar_key(key):
            return __pillar__.get(key)


        def conn_token():
            return __context__.get("conn")


        def shutdown(opts):
            return True


        def ping():
            return True
        '''
    ).lstrip()
    (proxy_dir / "echo_pillar_proxy.py").write_text(proxy_module)
    return ext


def _proxy_opts(minion_opts, echo_extension_modules, tmp_path, pillar):
    """
    Build a proxy ``opts`` dict wired to the echo proxymodule tree.
    """
    opts = dict(minion_opts)
    opts.update(
        {
            "id": "proxy_echo",
            "cachedir": str(tmp_path / "cache"),
            "extension_modules": str(echo_extension_modules),
            "saltenv": "base",
            "pillarenv": None,
            "grains": {},
            "pillar": pillar,
            "proxy": {"proxytype": "echo_pillar_proxy"},
        }
    )
    (tmp_path / "cache").mkdir(parents=True, exist_ok=True)
    return opts


def _build_proxy_loader(opts):
    """
    Build a real proxy loader packed exactly like ``salt.metaproxy.proxy``:
    ``pack["__pillar__"]`` is the *same dict object* as ``opts["pillar"]``.
    Then load and initialise the echo module.
    """
    proxy = salt.loader.proxy(opts, utils=salt.loader.utils(opts))
    # Mirror salt/metaproxy/proxy.py: pack the pillar by reference.
    proxy.pack["__pillar__"] = opts["pillar"]
    # Load + init the echo module so __context__ gets its sentinel and the
    # LoadedFunc objects are materialised (as they are on a live proxy).
    assert proxy["echo_pillar_proxy.init"](opts) is True
    return proxy


def _resolved_future(result):
    future = tornado.concurrent.Future()
    future.set_result(result)
    return future


def _make_minion(opts, proxy, io_loop):
    """
    A ``ProxyMinion`` instance with only the attributes ``pillar_refresh``
    touches, built without running the real (network/event-loop) ``__init__``.
    The collaborators that are not part of the fix are stubbed; the loader,
    ``self.opts`` and ``pillar_schedule_refresh`` are real.
    """
    minion = salt.minion.ProxyMinion.__new__(salt.minion.ProxyMinion)
    minion.opts = opts
    minion.proxy = proxy
    minion.connected = True
    minion.io_loop = io_loop
    minion.module_refresh = MagicMock()
    minion.matchers_refresh = MagicMock()
    minion.beacons_refresh = MagicMock()
    return minion


def _run_pillar_refresh(minion, new_pillar=None, compile_error=False):
    """
    Drive the real ``Minion.pillar_refresh`` coroutine to completion with the
    pillar compile and event bus mocked out. Returns nothing; inspect the
    minion / loader afterwards.
    """
    compiler = MagicMock()
    if compile_error:
        compiler.compile_pillar.side_effect = SaltClientError("master down")
    else:
        compiler.compile_pillar.return_value = _resolved_future(new_pillar)
    compiler.destroy.return_value = None

    event_ctx = MagicMock()
    event_obj = MagicMock()
    event_obj.fire_event_async.return_value = _resolved_future(None)
    event_ctx.__enter__.return_value = event_obj
    event_ctx.__exit__.return_value = False

    with patch("salt.pillar.get_async_pillar", MagicMock(return_value=compiler)), patch(
        "salt.utils.event.get_event", MagicMock(return_value=event_ctx)
    ):
        minion.io_loop.run_sync(minion.pillar_refresh)


@pytest.mark.slow_test
def test_repack_refreshes_loaded_proxy_module(
    minion_opts, echo_extension_modules, tmp_path
):
    """
    Loader-altitude pin of the #58197 mechanism, independent of the Minion.

    A module loaded against ``pack["__pillar__"] = opts["pillar"]`` sees v1.
    Rebinding ``opts["pillar"]`` (what ``pillar_refresh`` does) leaves the
    module stale; re-packing the loader (what the fix does) makes it fresh --
    with no reload.
    """
    pillar_v1 = {"role": "v1"}
    opts = _proxy_opts(minion_opts, echo_extension_modules, tmp_path, pillar_v1)
    proxy = _build_proxy_loader(opts)

    func = proxy["echo_pillar_proxy.read_pillar_key"]
    # The stable "did we reload?" handle is the underlying module function
    # (LoadedFunc is a thin wrapper re-created on each subscript access).
    underlying = func.func
    assert func("role") == "v1"

    # Simulate the pillar_refresh rebind: opts["pillar"] now points at a new
    # dict, but the loader's pack still aliases the original -> stale.
    pillar_v2 = {"role": "v2"}
    opts["pillar"] = pillar_v2
    assert proxy["echo_pillar_proxy.read_pillar_key"]("role") == "v1"

    # The fix: re-pack. The already-loaded module now sees v2 on its next
    # call, and it is backed by the *same* function object (no reload).
    proxy.pack["__pillar__"] = opts["pillar"]
    assert proxy["echo_pillar_proxy.read_pillar_key"].func is underlying
    assert func("role") == "v2"


@pytest.mark.slow_test
def test_pillar_refresh_repacks_proxy_loader(
    minion_opts, echo_extension_modules, tmp_path
):
    """
    Direct pin of the production line: drive the real ``pillar_refresh`` and
    assert the freshly compiled pillar reaches an already-loaded proxy module,
    without a reload.

    This is the test that fails if the ``self.proxy.pack["__pillar__"]``
    re-pack is removed from ``Minion.pillar_refresh``.
    """
    pillar_v1 = {"role": "v1", "token": "old"}
    opts = _proxy_opts(minion_opts, echo_extension_modules, tmp_path, pillar_v1)
    proxy = _build_proxy_loader(opts)

    read = proxy["echo_pillar_proxy.read_pillar_key"]
    read_func = read.func
    conn_before = proxy["echo_pillar_proxy.conn_token"]()
    assert conn_before is not None
    assert read("role") == "v1"

    pillar_v2 = {"role": "v2", "token": "new"}
    io_loop = tornado.ioloop.IOLoop()
    try:
        minion = _make_minion(opts, proxy, io_loop)
        _run_pillar_refresh(minion, new_pillar=pillar_v2)
    finally:
        io_loop.close()

    # opts was rebound to the new pillar ...
    assert minion.opts["pillar"] is pillar_v2
    # ... and the loader was re-packed to the very same object (the fix).
    assert proxy.pack["__pillar__"] is pillar_v2

    # End-to-end: the already-loaded proxy module now serves the new pillar.
    assert read("role") == "v2"
    assert read("token") == "new"

    # Reload lock-out: the module function backing the loader entry is the
    # same object (no reload), and init() was not re-run so the __context__
    # connection sentinel survives untouched.
    assert proxy["echo_pillar_proxy.read_pillar_key"].func is read_func
    assert proxy["echo_pillar_proxy.conn_token"]() is conn_before


@pytest.mark.slow_test
def test_pillar_refresh_saltclienterror_keeps_pack_identity(
    minion_opts, echo_extension_modules, tmp_path
):
    """
    Inverse: if the pillar compile raises ``SaltClientError`` the refresh must
    not rebind opts["pillar"] and must leave ``pack["__pillar__"]`` pointing at
    the original object (no torn / half-applied state).
    """
    pillar_v1 = {"role": "v1"}
    opts = _proxy_opts(minion_opts, echo_extension_modules, tmp_path, pillar_v1)
    proxy = _build_proxy_loader(opts)
    packed_before = proxy.pack["__pillar__"]
    assert packed_before is pillar_v1

    io_loop = tornado.ioloop.IOLoop()
    try:
        minion = _make_minion(opts, proxy, io_loop)
        _run_pillar_refresh(minion, compile_error=True)
    finally:
        io_loop.close()

    assert minion.opts["pillar"] is pillar_v1
    assert proxy.pack["__pillar__"] is pillar_v1
    assert proxy["echo_pillar_proxy.read_pillar_key"]("role") == "v1"


@pytest.mark.slow_test
def test_pillar_refresh_non_proxy_minion_does_not_raise(minion_opts, tmp_path):
    """
    Inverse: a regular (non-proxy) minion has ``self.proxy is None``. The
    guarded re-pack must be skipped -- no ``AttributeError`` -- and the refresh
    must still rebind opts["pillar"] as usual.
    """
    opts = dict(minion_opts)
    opts.update(
        {
            "id": "regular_minion",
            "saltenv": "base",
            "pillarenv": None,
            "grains": {},
            "pillar": {"role": "v1"},
        }
    )
    pillar_v2 = {"role": "v2"}
    io_loop = tornado.ioloop.IOLoop()
    try:
        minion = salt.minion.Minion.__new__(salt.minion.Minion)
        minion.opts = opts
        minion.proxy = None
        minion.connected = True
        minion.io_loop = io_loop
        minion.module_refresh = MagicMock()
        minion.matchers_refresh = MagicMock()
        minion.beacons_refresh = MagicMock()
        _run_pillar_refresh(minion, new_pillar=pillar_v2)
    finally:
        io_loop.close()

    assert minion.opts["pillar"] is pillar_v2


@pytest.mark.slow_test
def test_pillar_refresh_regular_minion_with_proxy_loader_skips_repack(
    minion_opts, tmp_path
):
    """
    Scoping guard: a regular minion still builds a lazy proxy loader in
    ``gen_modules()`` (``self.proxy`` is a truthy LazyLoader, not None), but it
    is not a proxy minion (no ``opts["proxy"]``). The re-pack must be gated on
    ``opts["proxy"]`` so it does NOT touch that loader's pack on a regular
    minion -- otherwise the guard would fire wherever a proxy loader exists.
    """
    opts = dict(minion_opts)
    opts.update(
        {
            "id": "regular_minion",
            "saltenv": "base",
            "pillarenv": None,
            "grains": {},
            "pillar": {"role": "v1"},
        }
    )
    opts.pop("proxy", None)
    pillar_v2 = {"role": "v2"}
    # A truthy stand-in for the lazy proxy loader a regular minion carries.
    proxy_loader = MagicMock()
    io_loop = tornado.ioloop.IOLoop()
    try:
        minion = salt.minion.Minion.__new__(salt.minion.Minion)
        minion.opts = opts
        minion.proxy = proxy_loader
        minion.connected = True
        minion.io_loop = io_loop
        minion.module_refresh = MagicMock()
        minion.matchers_refresh = MagicMock()
        minion.beacons_refresh = MagicMock()
        _run_pillar_refresh(minion, new_pillar=pillar_v2)
    finally:
        io_loop.close()

    assert minion.opts["pillar"] is pillar_v2
    # The proxy loader's pack must never have been written on a regular minion.
    proxy_loader.pack.__setitem__.assert_not_called()


@pytest.mark.slow_test
def test_pillar_refresh_per_subproxy_isolated(
    minion_opts, echo_extension_modules, tmp_path
):
    """
    Deltaproxy coverage.

    Every deltaproxy sub-proxy is a ``ProxyMinion`` with its own loader and
    its own ``opts``. ``handle_event`` routes each sub-proxy's ``pillar_refresh``
    event to *that* sub-proxy instance (``_minion =
    self.deltaproxy_objs[proxy_target]``), so the single re-pack in
    ``Minion.pillar_refresh`` runs per sub-proxy against its own loader.

    Drive ``pillar_refresh`` on two independent sub-proxy objects with distinct
    freshly-compiled pillars and assert each loader ends up with *its own* new
    pillar -- no cross-contamination.
    """
    opts_a = _proxy_opts(
        minion_opts, echo_extension_modules, tmp_path / "a", {"device": "a-old"}
    )
    opts_a["id"] = "sub-a"
    opts_b = _proxy_opts(
        minion_opts, echo_extension_modules, tmp_path / "b", {"device": "b-old"}
    )
    opts_b["id"] = "sub-b"
    proxy_a = _build_proxy_loader(opts_a)
    proxy_b = _build_proxy_loader(opts_b)

    new_a = {"device": "a-new"}
    new_b = {"device": "b-new"}
    io_loop = tornado.ioloop.IOLoop()
    try:
        sub_a = _make_minion(opts_a, proxy_a, io_loop)
        sub_b = _make_minion(opts_b, proxy_b, io_loop)
        _run_pillar_refresh(sub_a, new_pillar=new_a)
        _run_pillar_refresh(sub_b, new_pillar=new_b)
    finally:
        io_loop.close()

    assert proxy_a.pack["__pillar__"] is new_a
    assert proxy_b.pack["__pillar__"] is new_b
    assert proxy_a["echo_pillar_proxy.read_pillar_key"]("device") == "a-new"
    assert proxy_b["echo_pillar_proxy.read_pillar_key"]("device") == "b-new"
