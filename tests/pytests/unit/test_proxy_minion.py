import textwrap

import pytest

import salt.loader.lazy
import salt.minion

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
