"""
Tests for salt.loader.lazy
"""
import sys

import pytest
import salt.loader
import salt.loader.context
import salt.loader.lazy
import salt.utils.files


@pytest.fixture
def loader_dir(tmp_path):
    """
    Create a simple directory with a couple modules to load and run tests
    against.
    """
    mod_contents = """
    def __virtual__():
        return True

    def set_context(key, value):
        __context__[key] = value

    def get_context(key):
        return __context__[key]
    """
    with pytest.helpers.temp_file(
        "mod_a.py", directory=tmp_path, contents=mod_contents
    ), pytest.helpers.temp_file("mod_b.py", directory=tmp_path, contents=mod_contents):
        yield str(tmp_path)


def test_loaders_have_uniq_context(loader_dir):
    """
    Loaded functions run in the LazyLoader's context.
    """
    opts = {"optimization_order": [0, 1, 2]}
    loader_1 = salt.loader.lazy.LazyLoader([loader_dir], opts)
    loader_2 = salt.loader.lazy.LazyLoader([loader_dir], opts)
    loader_1._load_all()
    loader_2._load_all()
    assert loader_1.pack["__context__"] == {}
    assert loader_2.pack["__context__"] == {}
    loader_1["mod_a.set_context"]("foo", "bar")
    assert loader_1.pack["__context__"] == {"foo": "bar"}
    assert loader_1["mod_b.get_context"]("foo") == "bar"
    with pytest.raises(KeyError):
        loader_2["mod_a.get_context"]("foo")
    assert loader_2.pack["__context__"] == {}


def test_loaded_methods_are_loaded_func(loader_dir):
    """
    Functions loaded from LazyLoader's item lookups are LoadedFunc objects
    """
    opts = {"optimization_order": [0, 1, 2]}
    loader_1 = salt.loader.lazy.LazyLoader([loader_dir], opts)
    fun = loader_1["mod_a.get_context"]
    assert isinstance(fun, salt.loader.lazy.LoadedFunc)


def test_loaded_modules_are_loaded_mods(loader_dir):
    """
    Modules looked up as attributes of LazyLoaders are LoadedMod objects.
    """
    opts = {"optimization_order": [0, 1, 2]}
    loader_1 = salt.loader.lazy.LazyLoader([loader_dir], opts)
    mod = loader_1.mod_a
    assert isinstance(mod, salt.loader.lazy.LoadedMod)


def test_loaders_create_named_loader_contexts(loader_dir):
    """
    LazyLoader's create NamedLoaderContexts on the modules the load.
    """
    opts = {"optimization_order": [0, 1, 2]}
    loader_1 = salt.loader.lazy.LazyLoader([loader_dir], opts)
    mod = loader_1.mod_a
    assert isinstance(mod.mod, str)
    func = mod.set_context
    assert isinstance(func, salt.loader.lazy.LoadedFunc)
    module_name = func.func.__module__
    module = sys.modules[module_name]
    assert isinstance(module.__context__, salt.loader.context.NamedLoaderContext)
    wrapped_module_name = func.__module__
    wrapped_module = sys.modules[wrapped_module_name]
    assert isinstance(
        wrapped_module.__context__, salt.loader.context.NamedLoaderContext
    )
    assert module is wrapped_module


def test_loaders_convert_context_to_values(loader_dir):
    """
    LazyLoaders convert NamedLoaderContexts to values when instantiated.
    """
    loader_context = salt.loader.context.LoaderContext()
    grains_default = {
        "os": "linux",
    }
    grains = salt.loader.context.NamedLoaderContext(
        "grains", loader_context, grains_default
    )
    opts = {
        "optimization_order": [0, 1, 2],
        "grains": grains,
    }
    loader_1 = salt.loader.lazy.LazyLoader([loader_dir], opts)
    assert loader_1.opts["grains"] == grains_default
    # The loader's opts is a copy
    assert opts["grains"] == grains


def test_missing_loader_from_salt_internal_loaders():
    with pytest.raises(RuntimeError):
        salt.loader._module_dirs(
            {"extension_modules": "/tmp/foo"}, "missingmodules", "module"
        )
