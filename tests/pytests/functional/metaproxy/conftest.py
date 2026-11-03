"""
Functional test fixtures for ``salt.metaproxy.deltaproxy``.

These fixtures lay down a real ``extension_modules`` tree containing a
purpose-built proxy module that returns *id-distinguishing* grains, so the
test can drive ``subproxy_post_master_init`` end-to-end through the real
``salt.loader.proxy`` / ``salt.loader.grains`` loaders.
"""

import textwrap

import pytest


@pytest.fixture
def extension_modules(tmp_path):
    """
    Create a tmp extension_modules tree with a custom proxy module whose
    ``grains()`` callable returns the sub-proxy's ``id`` as a grain.

    The deltaproxy code path that #68248 fixes runs ``salt.loader.grains``
    twice for every sub-proxy: once via the parent control proxy
    (placeholder grains shared across siblings) and again via the sub-proxy's
    own proxymodule. ``proxy_merge_grains_in_module=True`` (the default) then
    merges the proxymodule's ``grains()`` output into the grains dict, which
    is the bit that *must* differ per sub-proxy after the fix.
    """
    ext = tmp_path / "extension_modules"
    proxy_dir = ext / "proxy"
    proxy_dir.mkdir(parents=True)
    (ext / "__init__.py").write_text("")

    # The custom proxy module: returns ``serial_number = <id>`` so each
    # sub-proxy ends up with a grain that uniquely identifies its device.
    proxy_module = textwrap.dedent(
        '''
        """
        Test-only proxy module used by tests/pytests/functional/metaproxy.

        Returns a ``serial_number`` grain whose value is the sub-proxy id
        currently driving this proxymodule instance. This makes the per
        sub-proxy ``__grains__`` distinguishable so the deltaproxy fix
        for issue #68248 can be observed end-to-end.
        """

        __proxyenabled__ = ["serial_test_proxy"]


        def __virtual__():
            return True


        def init(opts):
            return True


        def initialized():
            return True


        def grains():
            # ``__opts__`` is injected by the loader; ``id`` is the
            # sub-proxy id for this proxymodule instance.
            return {"serial_number": __opts__["id"]}


        def grains_refresh():
            return grains()


        def shutdown(opts):
            return True


        def ping():
            return True
        '''
    ).lstrip()
    (proxy_dir / "serial_test_proxy.py").write_text(proxy_module)
    return ext
