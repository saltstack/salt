import copy
import textwrap

import pytest
from saltfactories.utils import random_string

import salt.config
import salt.loader.lazy
import salt.minion
from tests.support.mock import patch


@pytest.mark.slow_test
async def test_handle_decoded_payload_metaproxy_called(io_loop):
    """
    Tests that when the _handle_decoded_payload function is called, _metaproxy_call is also called.
    """
    mock_opts = salt.config.DEFAULT_MINION_OPTS.copy()
    mock_opts.update(salt.config.DEFAULT_PROXY_MINION_OPTS)

    mock_data = {"fun": "foo.bar", "jid": 123}
    mock_jid_queue = [123]
    proxy_minion = salt.minion.ProxyMinion(
        mock_opts,
        jid_queue=copy.copy(mock_jid_queue),
        io_loop=io_loop,
    )

    async def mock_metaproxy_call(*args, **kwargs):
        mock_metaproxy_call.calls += 1

    mock_metaproxy_call.calls = 0
    with patch(
        "salt.minion._metaproxy_call",
        return_value=mock_metaproxy_call,
        autospec=True,
    ):
        try:
            ret = await proxy_minion._handle_decoded_payload(mock_data)
            assert proxy_minion.jid_queue, mock_jid_queue
            assert mock_metaproxy_call.calls == 1
        finally:
            proxy_minion.destroy()


@pytest.mark.slow_test
async def test_handle_payload_metaproxy_called(io_loop):
    """
    Tests that when the _handle_payload function is called, _metaproxy_call is also called.
    """
    mock_opts = salt.config.DEFAULT_MINION_OPTS.copy()
    mock_opts.update(salt.config.DEFAULT_PROXY_MINION_OPTS)

    mock_data = {"fun": "foo.bar", "jid": 123}
    mock_jid_queue = [123]
    proxy_minion = salt.minion.ProxyMinion(
        mock_opts,
        jid_queue=copy.copy(mock_jid_queue),
        io_loop=io_loop,
    )

    async def mock_metaproxy_call(*args, **kwargs):
        mock_metaproxy_call.calls += 1

    mock_metaproxy_call.calls = 0
    with patch(
        "salt.minion._metaproxy_call",
        return_value=mock_metaproxy_call,
        autospec=True,
    ):
        try:
            ret = await proxy_minion._handle_decoded_payload(mock_data)
            assert proxy_minion.jid_queue == mock_jid_queue
            assert mock_metaproxy_call.calls == 1
        finally:
            proxy_minion.destroy()


def test_proxy_config_default_include(tmp_path):
    """
    Tests that when the proxy_config function is called,
    for the proxy minion, eg. /etc/salt/proxy.d/<The-Proxy-ID>/*.conf
    """
    proxyid = random_string("proxy-")
    root_dir = tmp_path / "root"
    conf_dir = root_dir / "conf"
    conf_file = conf_dir / "proxy"
    conf_d_dir = conf_dir / "proxy.d"
    proxy_conf_d = conf_d_dir / proxyid
    proxy_conf_d.mkdir(parents=True)

    with salt.utils.files.fopen(str(conf_file), "w") as wfh:
        wfh.write(
            textwrap.dedent(
                """\
                id: {id}
                root_dir: {root_dir}
                pidfile: run/proxy.pid
                pki_dir: pki
                cachedir: cache
                sock_dir: run/proxy
                log_file: logs/proxy.log
                """.format(
                    id=proxyid, root_dir=root_dir
                )
            )
        )

    with salt.utils.files.fopen(str(proxy_conf_d / "_schedule.conf"), "w") as wfh:
        wfh.write(
            textwrap.dedent(
                """\
                schedule:
                  test_job:
                    args: [arg1, arg2]
                    enabled: true
                    function: test.arg
                    jid_include: true
                    kwargs: {key1: value1, key2: value2}
                    maxrunning: 1
                    name: test_job
                    return_job: false
                """
            )
        )
    opts = salt.config.proxy_config(
        str(conf_file),
        minion_id=proxyid,
        cache_minion_id=False,
    )
    assert "schedule" in opts
    assert "test_job" in opts["schedule"]


# ---------------------------------------------------------------------------
# Regression for #69139
# ---------------------------------------------------------------------------

PROXY_MODULE_WITH_BAD_VIRTUAL = textwrap.dedent(
    """
    __proxyenabled__ = ["*"]

    def __virtual__():
        return (
            False,
            "NAPALM is not installed: ``pip install napalm``",
        )

    def init(opts):
        return True

    def shutdown(opts):
        return True
    """
)

PROXY_MODULE_VIRTUAL_FALSE_NO_REASON = textwrap.dedent(
    """
    __proxyenabled__ = ["*"]

    def __virtual__():
        return False

    def init(opts):
        return True

    def shutdown(opts):
        return True
    """
)

PROXY_MODULE_NO_INIT = textwrap.dedent(
    """
    __proxyenabled__ = ["*"]

    def __virtual__():
        return True

    def shutdown(opts):
        return True
    """
)


@pytest.fixture
def proxy_loader_factory(tmp_path):
    """
    Build a proxy LazyLoader from a temp directory containing a single
    module file. Returns a callable that takes module contents and
    returns a configured LazyLoader.
    """

    def _make(name, contents):
        mod_dir = tmp_path / name
        mod_dir.mkdir()
        (mod_dir / f"{name}.py").write_text(contents)
        opts = {
            "optimization_order": [0, 1, 2],
            "proxy": {"proxytype": name},
        }
        return salt.loader.lazy.LazyLoader(
            [str(mod_dir)],
            opts,
            tag="proxy",
        )

    return _make


def test_proxy_load_failure_message_surfaces_virtual_reason(proxy_loader_factory):
    """
    Regression for #69139.

    When a proxy module's ``__virtual__()`` returns ``(False, reason)``
    (for example because a required dependency could not be imported),
    salt-proxy used to abort with the misleading message "Proxymodule X
    is missing an init() or a shutdown() or both" even when the module
    defined both ``init()`` and ``shutdown()``. The user had no way to
    learn the real cause was the failed ``__virtual__()``.

    The helper must surface the ``__virtual__`` reason so the operator
    can act on it (e.g. install the missing dependency).
    """
    loader = proxy_loader_factory("napalm", PROXY_MODULE_WITH_BAD_VIRTUAL)

    # Sanity: the module is not loaded and the reason is recorded.
    assert "napalm.init" not in loader
    assert "napalm" in loader.missing_modules

    errmsg = salt.minion.proxy_load_failure_message(loader, "napalm")

    # The misleading wording must not be the *only* thing the user sees.
    assert "NAPALM is not installed" in errmsg, errmsg
    assert "could not be loaded" in errmsg or "__virtual__" in errmsg, errmsg
    assert "Salt-proxy aborted" in errmsg


def test_proxy_load_failure_message_virtual_false_no_reason(proxy_loader_factory):
    """
    A ``__virtual__()`` that returns plain ``False`` still produces a
    message that indicates the module did not load (rather than claiming
    init/shutdown were missing).
    """
    loader = proxy_loader_factory("zilch", PROXY_MODULE_VIRTUAL_FALSE_NO_REASON)
    assert "zilch.init" not in loader

    errmsg = salt.minion.proxy_load_failure_message(loader, "zilch")
    assert "could not be loaded" in errmsg or "__virtual__" in errmsg, errmsg
    assert "Salt-proxy aborted" in errmsg


def test_proxy_load_failure_message_truly_missing_init(proxy_loader_factory):
    """
    The original "missing an init() or a shutdown()" wording is still
    used when the proxy module *did* load but really is missing one of
    the required functions. This preserves the historical message for
    its actual use case.
    """
    loader = proxy_loader_factory("noinit", PROXY_MODULE_NO_INIT)
    # The module loaded (shutdown is exposed), but init isn't.
    assert "noinit.shutdown" in loader
    assert "noinit.init" not in loader

    errmsg = salt.minion.proxy_load_failure_message(loader, "noinit")
    assert "missing an init() or a shutdown()" in errmsg
    assert "Salt-proxy aborted" in errmsg
