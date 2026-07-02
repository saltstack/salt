"""
Tests for salt.loader.context
"""

import copy

import pytest

import salt.loader.context
import salt.loader.lazy
import salt.payload


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


def test_named_loader_context_none_value_container_protocol():
    """
    Regression test for #65504.

    When ``NamedLoaderContext.value()`` returns ``None`` (no loader in the
    current context and ``default`` is ``None``), the container-protocol
    dunder methods must not raise ``AttributeError``. They should return
    sensible empty-container defaults so that consumers such as
    ``salt.payload.dumps`` (which msgpack-encodes a
    ``collections.abc.MutableMapping`` by calling ``dict(obj)``) do not
    crash when a ``NamedLoaderContext`` slips into a returned payload.
    """
    loader_context = salt.loader.context.LoaderContext()
    named_context = salt.loader.context.NamedLoaderContext(
        "__some_dunder__", loader_context, default=None
    )
    # Sanity: value() really is None here.
    assert named_context.value() is None

    # Iteration protocol yields nothing.
    assert list(iter(named_context)) == []

    # Length is zero.
    assert len(named_context) == 0

    # Membership tests are False.
    assert "anything" not in named_context

    # Truthiness is False (empty container semantics).
    assert bool(named_context) is False

    # get() returns the requested default rather than crashing.
    assert named_context.get("missing") is None
    assert named_context.get("missing", "fallback") == "fallback"

    # Indexed access raises KeyError, not AttributeError.
    with pytest.raises(KeyError):
        _ = named_context["missing"]

    # Deletion raises KeyError, not AttributeError.
    with pytest.raises(KeyError):
        del named_context["missing"]

    # Assignment raises TypeError (no underlying mapping to mutate),
    # not AttributeError.
    with pytest.raises(TypeError):
        named_context["missing"] = "value"

    # The load-bearing case from the issue: msgpack must be able to
    # encode a payload that contains a NamedLoaderContext whose value
    # is None without crashing on ``dict(obj)``.
    packed = salt.payload.dumps({"foo": named_context}, use_bin_type=True)
    assert salt.payload.loads(packed) == {"foo": {}}
