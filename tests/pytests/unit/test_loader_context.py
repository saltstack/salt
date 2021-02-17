"""
Tests for salt.loader_context
"""
import salt.loader
import salt.loader_context


def test_named_loader_context():
    loader_context = salt.loader_context.LoaderContext()
    named_context = salt.loader_context.NamedLoaderContext("__test__", loader_context)
    test_dunder = {"foo": "bar"}
    lazy_loader = salt.loader.LazyLoader(["/foo"], pack={"__test__": test_dunder})
    assert named_context.loader() is None
    token = salt.loader_context.loader_ctxvar.set(lazy_loader)
    try:
        assert named_context.loader() == lazy_loader
        # The loader's value is the same object as test_dunder
        assert named_context.value() is test_dunder
        assert named_context["foo"] == "bar"
    finally:
        salt.loader_context.loader_ctxvar.reset(token)


def test_named_loader_default():
    loader_context = salt.loader_context.LoaderContext()
    default = {"foo": "bar"}
    named_context = salt.loader_context.NamedLoaderContext(
        "__test__", loader_context, default=default
    )
    assert named_context.loader() is None
    # The loader's value is the same object as default
    assert named_context.value() is default
    assert named_context["foo"] == "bar"
