"""
Tests for salt.loader
"""
import os
import shutil
import sys

import pytest
import salt.loader
import salt.loader_context
import salt.utils.files
from tests.support.helpers import dedent


@pytest.fixture
def loader_dir(tmp_path):
    """
    Create a simple directory with a couple modules to load and run tests
    against.
    """
    mod_content = dedent(
        """
    def __virtual__():
        return True

    def set_context(key, value):
        __context__[key] = value

    def get_context(key):
        return __context__[key]
    """
    )
    tmp_path = str(tmp_path)
    with salt.utils.files.fopen(os.path.join(tmp_path, "mod_a.py"), "w") as fp:
        fp.write(mod_content)
    with salt.utils.files.fopen(os.path.join(tmp_path, "mod_b.py"), "w") as fp:
        fp.write(mod_content)
    try:
        yield tmp_path
    finally:
        shutil.rmtree(tmp_path)


def test_loaders_have_uniq_context(loader_dir):
    """
    Loaded functions run in the LazyLoader's context.
    """
    opts = {"optimization_order": [0, 1, 2]}
    loader_1 = salt.loader.LazyLoader([loader_dir], opts,)
    loader_2 = salt.loader.LazyLoader([loader_dir], opts,)
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
    loader_1 = salt.loader.LazyLoader([loader_dir], opts,)
    fun = loader_1["mod_a.get_context"]
    assert isinstance(fun, salt.loader.LoadedFunc)


def test_loaded_modules_are_loaded_mods(loader_dir):
    """
    Modules looked up as attributes of LazyLoaders are LoadedMod objects.
    """
    opts = {"optimization_order": [0, 1, 2]}
    loader_1 = salt.loader.LazyLoader([loader_dir], opts,)
    mod = loader_1.mod_a
    assert isinstance(mod, salt.loader.LoadedMod)


def test_loaders_create_named_loader_contexts(loader_dir):
    """
    LazyLoader's create NamedLoaderContexts on the modules the load.
    """
    opts = {"optimization_order": [0, 1, 2]}
    loader_1 = salt.loader.LazyLoader([loader_dir], opts,)
    mod = loader_1.mod_a
    assert isinstance(mod.mod, dict)
    func = mod.set_context
    assert isinstance(func, salt.loader.LoadedFunc)
    module_name = func.func.__module__
    module = sys.modules[module_name]
    assert isinstance(module.__context__, salt.loader_context.NamedLoaderContext)


def test_loaders_convert_context_to_values(loader_dir):
    """
    LazyLoaders convert NamedLoaderContexts to values when instantiated.
    """
    loader_context = salt.loader_context.LoaderContext()
    grains_default = {
        "os": "linux",
    }
    grains = salt.loader_context.NamedLoaderContext(
        "grains", loader_context, grains_default
    )
    opts = {
        "optimization_order": [0, 1, 2],
        "grains": grains,
    }
    loader_1 = salt.loader.LazyLoader([loader_dir], opts,)
    assert loader_1.opts["grains"] == grains_default
    # The loader's opts is a copy
    assert opts["grains"] == grains
