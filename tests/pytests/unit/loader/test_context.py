"""
Tests for salt.loader.context
"""

import contextvars
import copy
import threading

import salt.loader
import salt.loader.context
import salt.loader.lazy
from tests.support.mock import patch


def test_named_loader_context():
    loader_context = salt.loader.context.LoaderContext()
    named_context = salt.loader.context.NamedLoaderContext("__test__", loader_context)
    test_dunder = {"foo": "bar"}
    lazy_loader = salt.loader.lazy.LazyLoader(["/foo"], pack={"__test__": test_dunder})
    assert named_context.loader() is None
    token = salt.loader.context.loader_ctxvar.set(lazy_loader)
    try:
        assert named_context.loader() == lazy_loader
        # The loader's value is the same object as test_dunder
        assert named_context.value() is test_dunder
        assert named_context["foo"] == "bar"
    finally:
        salt.loader.context.loader_ctxvar.reset(token)


def test_named_loader_default():
    loader_context = salt.loader.context.LoaderContext()
    default = {"foo": "bar"}
    named_context = salt.loader.context.NamedLoaderContext(
        "__test__", loader_context, default=default
    )
    assert named_context.loader() is None
    # The loader's value is the same object as default
    assert named_context.value() is default
    assert named_context["foo"] == "bar"


def test_named_loader_context_deepcopy():
    loader_context = salt.loader.context.LoaderContext()
    default_data = {"foo": "bar"}
    named_context = salt.loader.context.NamedLoaderContext(
        "__test__", loader_context, default_data
    )
    coppied = copy.deepcopy(named_context)
    assert coppied.name == named_context.name
    assert id(coppied.loader_context) == id(named_context.loader_context)
    assert id(coppied.default) != id(named_context.default)


def test_named_loader_context_opts():
    loader_context = salt.loader.context.LoaderContext()
    opts = loader_context.named_context("__opts__")
    loader = salt.loader.lazy.LazyLoader(["/foo"], opts={"foo": "bar"})
    with salt.loader.context.loader_context(loader):
        assert "foo" in opts
        assert opts["foo"] == "bar"


# ---------------------------------------------------------------------------
# resource_ctxvar tests
# ---------------------------------------------------------------------------


def test_resource_ctxvar_default_is_empty_dict():
    """resource_ctxvar returns {} when nothing has been set in this context."""
    assert salt.loader.context.resource_ctxvar.get() == {}


def test_resource_ctxvar_set_and_get():
    """Setting resource_ctxvar is visible within the same thread."""
    target = {"id": "dummy-01", "type": "dummy"}
    tok = salt.loader.context.resource_ctxvar.set(target)
    try:
        assert salt.loader.context.resource_ctxvar.get() is target
    finally:
        salt.loader.context.resource_ctxvar.reset(tok)
    # After reset the default is restored.
    assert salt.loader.context.resource_ctxvar.get() == {}


def test_resource_ctxvar_thread_isolation():
    """
    Each thread gets an independent copy of resource_ctxvar.

    This is the core property that fixes Race 1: Thread A setting
    resource_ctxvar to target_A must be invisible to Thread B, which sets it
    to target_B, even when both threads share the same LazyLoader object.
    """
    target_a = {"id": "dummy-01", "type": "dummy"}
    target_b = {"id": "dummy-02", "type": "dummy"}
    results = {}

    def worker(name, target, barrier):
        salt.loader.context.resource_ctxvar.set(target)
        # Both threads arrive here before either reads, maximising the
        # chance of interference if isolation is broken.
        barrier.wait()
        results[name] = salt.loader.context.resource_ctxvar.get()

    barrier = threading.Barrier(2)
    t1 = threading.Thread(target=worker, args=("a", target_a, barrier))
    t2 = threading.Thread(target=worker, args=("b", target_b, barrier))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert results["a"] is target_a
    assert results["b"] is target_b


def test_resource_ctxvar_captured_by_copy_context():
    """
    copy_context() snapshots the current resource_ctxvar value.

    LazyLoader.run() calls copy_context() on every invocation, which is why
    setting resource_ctxvar in _thread_return before the function executes is
    sufficient for the value to be visible inside _run_as without any pack
    mutation.
    """
    target = {"id": "node1", "type": "ssh"}
    tok = salt.loader.context.resource_ctxvar.set(target)
    try:
        ctx = contextvars.copy_context()
    finally:
        salt.loader.context.resource_ctxvar.reset(tok)

    # Outside the token the default is restored in *this* context.
    assert salt.loader.context.resource_ctxvar.get() == {}

    # But the snapshot captured the value that was current at copy time.
    seen = {}
    ctx.run(lambda: seen.update({"val": salt.loader.context.resource_ctxvar.get()}))
    assert seen["val"] is target


def test_named_loader_context_resource_bypasses_pack():
    """
    NamedLoaderContext.value() for __resource__ reads from resource_ctxvar,
    not from the loader pack.

    This guarantees that concurrent threads using the same loader object each
    see their own resource target regardless of what the shared pack contains.
    """
    loader_context = salt.loader.context.LoaderContext()
    named = loader_context.named_context("__resource__")

    # With no ctxvar set the default {} is returned even if there is no loader.
    assert named.value() == {}

    # Set a target in the current context; the named context must reflect it.
    target = {"id": "dummy-03", "type": "dummy"}
    tok = salt.loader.context.resource_ctxvar.set(target)
    try:
        assert named.value() is target
        assert named["id"] == "dummy-03"
    finally:
        salt.loader.context.resource_ctxvar.reset(tok)

    # After reset the default is restored.
    assert named.value() == {}


def test_resource_modules_packs_resource_dunder():
    """
    salt.loader.resource_modules must include ``"__resource__"`` in its pack
    so that LazyLoader creates a NamedLoaderContext for it on every loaded
    module.  Without this, ``sshresource_state._resource_id()`` raises
    ``NameError: name '__resource__' is not defined``.
    """
    opts = {
        "optimization_order": [0, 1, 2],
        "extension_modules": "",
        "fileserver_backend": ["roots"],
    }
    with (
        patch("salt.loader._module_dirs", return_value=[]),
        patch("salt.loader.lazy.LazyLoader.__init__", return_value=None) as patched,
    ):
        salt.loader.resource_modules(opts, "ssh")
    assert patched.called, "LazyLoader.__init__ was never called"
    _, call_kwargs = patched.call_args
    pack = call_kwargs.get("pack", {})
    assert "__resource__" in pack, (
        "resource_modules pack is missing '__resource__'; "
        "sshresource_state will raise NameError at runtime"
    )
