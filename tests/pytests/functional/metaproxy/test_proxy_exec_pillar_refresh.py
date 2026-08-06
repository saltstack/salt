"""
Functional regression test for issue #59393.

``Minion.pillar_refresh`` calls ``module_refresh()`` at the top -- rebuilding
the execution-module loaders (``functions``/``returners``/``executors`` and
``utils``) from ``self.opts`` -- and only *afterwards* compiles the new pillar
and rebinds ``self.opts["pillar"]``. Each exec loader snapshots
``opts["pillar"]`` by value when it is built (``salt.loader.lazy`` deep-copies
opts and stashes the pillar in its context dict), so those loaders capture the
*old* pillar.

On a regular minion this is masked: every job rebuilds the loaders through
``gen_modules()`` before it runs. A proxy minion's ``metaproxy`` job path never
does, so an exec module keeps serving the previous refresh's ``__pillar__``
until the *next* ``refresh_pillar`` -- the confusing "run the same command
twice, get two answers" symptom.

The fix re-runs ``module_refresh()`` after the rebind, gated on ``opts["proxy"]``
so a regular minion pays no extra rebuild::

    if self.opts.get("proxy") and getattr(self, "proxy", None):
        self.proxy.pack["__pillar__"] = self.opts["pillar"]
        self.module_refresh(force_refresh)

These tests drive the *real* ``Minion.pillar_refresh`` (with the pillar compile
and event bus mocked, exactly like the #58197 tests). The direct pin builds a
*real* execution-module loader (``salt.loader.minion_mods``) over an on-disk
module that reads ``__pillar__`` at call time, and asserts that after a single
refresh that exec module observes the freshly compiled pillar. The remaining
tests pin the ordering (second refresh runs after the rebind, sees the new
pillar) and the no-regression boundary (a regular minion still refreshes its
modules exactly once; a failed compile triggers no second rebuild).
"""

import textwrap

import pytest

import salt.ext.tornado.concurrent
import salt.ext.tornado.ioloop
import salt.loader
import salt.minion
from salt.exceptions import SaltClientError
from tests.support.mock import MagicMock, patch


@pytest.fixture
def echo_extension_modules(tmp_path):
    """
    Lay down an ``extension_modules`` tree with:

    * ``modules/echo_pillar_exec.py`` -- an *execution* module that reads
      ``__pillar__`` at call time (what #59393 is about), and
    * ``proxy/echo_pillar_proxy.py`` -- a minimal proxy module so a real
      ``salt.loader.proxy`` loader can be built to satisfy the proxy gate in
      ``pillar_refresh``.
    """
    ext = tmp_path / "ext_echo"
    modules_dir = ext / "modules"
    proxy_dir = ext / "proxy"
    modules_dir.mkdir(parents=True)
    proxy_dir.mkdir(parents=True)
    (ext / "__init__.py").write_text("")

    exec_module = textwrap.dedent(
        '''
        """
        Test-only execution module for tests/pytests/functional/metaproxy.

        ``read_pillar_key`` resolves ``__pillar__`` through the loader's
        ``NamedLoaderContext`` on every call, so it reflects whatever pillar
        the loader snapshotted when it was built.
        """

        __virtualname__ = "echo_pillar_exec"


        def __virtual__():
            return True


        def read_pillar_key(key):
            return __pillar__.get(key)
        '''
    ).lstrip()
    (modules_dir / "echo_pillar_exec.py").write_text(exec_module)

    proxy_module = textwrap.dedent(
        '''
        """
        Minimal proxy module so a real proxy loader can be built.
        """

        __proxyenabled__ = ["*"]


        def __virtual__():
            return True


        def init(opts):
            return True


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
    Build a proxy ``opts`` dict wired to the echo extension-module tree.
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
    A real proxy loader packed like ``salt.metaproxy.proxy`` so the proxy gate
    in ``pillar_refresh`` (``opts["proxy"]`` and ``self.proxy``) is satisfied.
    """
    proxy = salt.loader.proxy(opts, utils=salt.loader.utils(opts))
    proxy.pack["__pillar__"] = opts["pillar"]
    assert proxy["echo_pillar_proxy.init"](opts) is True
    return proxy


def _build_exec_loader(opts, proxy):
    """
    A real execution-module loader, exactly as ``_load_modules`` builds it:
    ``minion_mods`` snapshots ``opts["pillar"]`` by value at construction.
    """
    return salt.loader.minion_mods(
        opts, utils=salt.loader.utils(opts, proxy=proxy), proxy=proxy
    )


def _resolved_future(result):
    future = salt.ext.tornado.concurrent.Future()
    future.set_result(result)
    return future


def _make_minion(opts, proxy, io_loop, module_refresh):
    """
    A ``ProxyMinion`` carrying only what ``pillar_refresh`` touches. ``proxy``,
    ``opts`` and ``pillar_schedule_refresh`` are real; ``module_refresh`` is
    supplied by the caller (a real rebuild for the direct pin, a mock for the
    ordering/count pins).
    """
    minion = salt.minion.ProxyMinion.__new__(salt.minion.ProxyMinion)
    minion.opts = opts
    minion.proxy = proxy
    minion.connected = True
    minion.io_loop = io_loop
    minion.module_refresh = module_refresh
    minion.matchers_refresh = MagicMock()
    minion.beacons_refresh = MagicMock()
    return minion


def _run_pillar_refresh(minion, new_pillar=None, compile_error=False):
    """
    Drive the real ``Minion.pillar_refresh`` coroutine to completion with the
    pillar compile and event bus mocked out.
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
def test_pillar_refresh_refreshes_exec_module_pillar(
    minion_opts, echo_extension_modules, tmp_path
):
    """
    Direct pin of #59393.

    Drive the real ``pillar_refresh`` on a proxy minion and assert that a
    *real* execution-module loader reflects the freshly compiled pillar after a
    single refresh. ``module_refresh`` here is a faithful rebuild of the exec
    loader from ``self.opts`` -- the same thing production's ``module_refresh``
    does to ``self.functions``.

    Fails on the pre-fix code: the only ``module_refresh`` runs *before* the
    rebind, so the exec loader is snapshotted against the old pillar and the
    read returns "v1".
    """
    pillar_v1 = {"role": "v1", "token": "old"}
    opts = _proxy_opts(minion_opts, echo_extension_modules, tmp_path, pillar_v1)
    proxy = _build_proxy_loader(opts)

    io_loop = salt.ext.tornado.ioloop.IOLoop()
    try:
        minion = salt.minion.ProxyMinion.__new__(salt.minion.ProxyMinion)
        minion.opts = opts
        minion.proxy = proxy
        minion.connected = True
        minion.io_loop = io_loop
        minion.matchers_refresh = MagicMock()
        minion.beacons_refresh = MagicMock()

        def module_refresh(force_refresh=False, notify=False):
            # Mirror production module_refresh's exec-loader rebuild: a fresh
            # minion_mods off the current opts (which snapshots opts["pillar"]).
            minion.functions = _build_exec_loader(minion.opts, minion.proxy)

        minion.module_refresh = module_refresh

        # Baseline: before the refresh the exec loader serves the old pillar.
        module_refresh()
        assert minion.functions["echo_pillar_exec.read_pillar_key"]("role") == "v1"

        pillar_v2 = {"role": "v2", "token": "new"}
        _run_pillar_refresh(minion, new_pillar=pillar_v2)
    finally:
        io_loop.close()

    assert minion.opts["pillar"] is pillar_v2
    # The exec loader was rebuilt after the rebind, so it now serves v2.
    assert minion.functions["echo_pillar_exec.read_pillar_key"]("role") == "v2"
    assert minion.functions["echo_pillar_exec.read_pillar_key"]("token") == "new"


@pytest.mark.slow_test
def test_proxy_reruns_module_refresh_after_pillar_rebind(
    minion_opts, echo_extension_modules, tmp_path
):
    """
    Ordering pin: on a proxy minion ``module_refresh`` runs twice -- once before
    the rebind (against the old pillar) and once after (against the new pillar).
    The post-rebind call is what freshens the exec loaders.

    Fails on the pre-fix code, which calls ``module_refresh`` exactly once.
    """
    pillar_v1 = {"role": "v1"}
    opts = _proxy_opts(minion_opts, echo_extension_modules, tmp_path, pillar_v1)
    proxy = _build_proxy_loader(opts)
    pillar_v2 = {"role": "v2"}

    seen = []
    module_refresh = MagicMock(
        side_effect=lambda *a, **k: seen.append(minion.opts["pillar"])
    )

    io_loop = salt.ext.tornado.ioloop.IOLoop()
    try:
        minion = _make_minion(opts, proxy, io_loop, module_refresh)
        _run_pillar_refresh(minion, new_pillar=pillar_v2)
    finally:
        io_loop.close()

    assert module_refresh.call_count == 2
    assert seen[0] is pillar_v1
    assert seen[1] is pillar_v2


@pytest.mark.slow_test
def test_compile_error_skips_second_module_refresh(
    minion_opts, echo_extension_modules, tmp_path
):
    """
    Inverse: a failed pillar compile must not trigger the post-rebind rebuild.
    The second ``module_refresh`` lives in the success (``else``) branch, so a
    ``SaltClientError`` leaves ``module_refresh`` at its single pre-compile call
    and does not rebind ``opts["pillar"]``.
    """
    pillar_v1 = {"role": "v1"}
    opts = _proxy_opts(minion_opts, echo_extension_modules, tmp_path, pillar_v1)
    proxy = _build_proxy_loader(opts)
    module_refresh = MagicMock()

    io_loop = salt.ext.tornado.ioloop.IOLoop()
    try:
        minion = _make_minion(opts, proxy, io_loop, module_refresh)
        _run_pillar_refresh(minion, compile_error=True)
    finally:
        io_loop.close()

    assert module_refresh.call_count == 1
    assert minion.opts["pillar"] is pillar_v1


@pytest.mark.slow_test
def test_regular_minion_module_refresh_not_rerun(minion_opts, tmp_path):
    """
    No-regression: a regular (non-proxy) minion is untouched by the fix. Its
    ``pillar_refresh`` still rebinds ``opts["pillar"]`` and still calls
    ``module_refresh`` exactly once -- the proxy-gated second rebuild does not
    fire, so a regular minion pays no extra loader rebuild.
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
    module_refresh = MagicMock()

    io_loop = salt.ext.tornado.ioloop.IOLoop()
    try:
        minion = salt.minion.Minion.__new__(salt.minion.Minion)
        minion.opts = opts
        minion.proxy = None
        minion.connected = True
        minion.io_loop = io_loop
        minion.module_refresh = module_refresh
        minion.matchers_refresh = MagicMock()
        minion.beacons_refresh = MagicMock()
        _run_pillar_refresh(minion, new_pillar=pillar_v2)
    finally:
        io_loop.close()

    assert minion.opts["pillar"] is pillar_v2
    assert module_refresh.call_count == 1
