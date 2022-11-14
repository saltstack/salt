import warnings

import pytest
from saltfactories.utils import random_string

import salt.config
import salt.loader
from salt.loader.lazy import LazyLoader


@pytest.fixture(scope="module")
def loaded_base_name():
    return random_string("{}.".format(__name__), digits=False, uppercase=False)


@pytest.fixture(scope="module")
def opts(loaded_base_name):
    return salt.config.minion_config(None)


def _loader_id(value):
    return value[0]


@pytest.fixture(
    params=(
        ("static_loader", ("modules", "test")),
        ("raw_mod", ("test", None)),
        ("minion_mods", ()),
        ("metaproxy", ()),
        ("matchers", ()),
        ("engines", (None, None, None)),
        ("proxy", ()),
        ("returners", (None,)),
        ("utils", ()),
        ("pillars", (None,)),
        ("tops", ()),
        ("wheels", ()),
        ("outputters", ()),
        ("serializers", ()),
        ("eauth_tokens", ()),
        ("auth", ()),
        ("fileserver", (None,)),
        ("roster", ()),
        ("thorium", (None, None)),
        ("states", (None, None, None)),
        ("beacons", (None,)),
        ("log_handlers", ()),
        ("ssh_wrapper", ()),
        ("render", (None,)),
        ("grain_funcs", ()),
        ("runner", ()),
        ("queues", ()),
        ("sdb", ()),
        ("pkgdb", ()),
        ("pkgfiles", ()),
        ("clouds", ()),
        ("netapi", ()),
        ("executors", ()),
        ("cache", ()),
    ),
    ids=_loader_id,
)
def loader(request, opts, loaded_base_name):
    loader_name, loader_args = request.param
    loader = getattr(salt.loader, loader_name)(
        opts, *loader_args, loaded_base_name=loaded_base_name
    )
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            # Force loading all functions
            list(loader)
            yield loader
    finally:
        if not isinstance(loader, LazyLoader):
            for loaded_func in loader.values():
                loader = loaded_func.loader
                break
        if isinstance(loader, LazyLoader):
            loader.clean_modules()


def test_loader(loader, loaded_base_name):
    if not isinstance(loader, LazyLoader):
        for loaded_func in loader.values():
            loader = loaded_func.loader
            loader_tag = loader.tag
            assert loader.loaded_base_name == loaded_base_name
            module_name = loaded_func.func.__module__
            try:
                assert module_name.startswith(loaded_base_name)
            except AssertionError:
                if loader_tag != "utils":
                    raise
    else:
        loader_tag = loader.tag
        assert loader.loaded_base_name == loaded_base_name
        for func_name in list(loader._dict):
            module_name = loader[func_name].__module__
            try:
                assert module_name.startswith(loaded_base_name)
            except AssertionError:
                if loader_tag != "utils":
                    raise
