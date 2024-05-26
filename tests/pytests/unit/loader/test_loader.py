"""
tests.pytests.unit.loader.test_loader
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for salt's loader
"""

import os
import shutil
import textwrap

import pytest

import salt.config
import salt.exceptions
import salt.loader
import salt.loader.lazy
from tests.support.mock import MagicMock, patch


@pytest.fixture
def grains_dir(tmp_path):
    """
    Create a simple directory with grain modules.
    """
    grain_with_annotation = textwrap.dedent(
        """
        from typing import Dict

        def example_grain() -> Dict[str, str]:
            return {"example": "42"}
        """
    )
    tmp_path = str(tmp_path)
    with salt.utils.files.fopen(os.path.join(tmp_path, "example.py"), "w") as fp:
        fp.write(grain_with_annotation)
    try:
        yield tmp_path
    finally:
        shutil.rmtree(tmp_path)


def test_grains(minion_opts):
    """
    Load grains.
    """
    grains = salt.loader.grains(minion_opts, force_refresh=True)
    assert "saltversion" in grains


def test_custom_grain_with_annotations(minion_opts, grains_dir):
    """
    Load custom grain with annotations.
    """
    minion_opts["grains_dirs"] = [grains_dir]
    grains = salt.loader.grains(minion_opts, force_refresh=True)
    assert grains.get("example") == "42"


def test_raw_mod_functions():
    "Ensure functions loaded by raw_mod are LoaderFunc instances"
    opts = {
        "extension_modules": "",
        "optimization_order": [0],
    }
    ret = salt.loader.raw_mod(opts, "grains", "get")
    for k, v in ret.items():
        assert isinstance(v, salt.loader.lazy.LoadedFunc)


def test_named_loader_context_name_not_packed(tmp_path):
    opts = {
        "optimization_order": [0],
    }
    contents = """
    from salt.loader.dunder import loader_context
    __not_packed__ = loader_context.named_context("__not_packed__")
    def foobar():
        return __not_packed__["not.packed"]()
    """
    with pytest.helpers.temp_file("mymod.py", contents, directory=tmp_path):
        loader = salt.loader.LazyLoader([tmp_path], opts)
        with pytest.raises(
            salt.exceptions.LoaderError,
            match="LazyLoader does not have a packed value for: __not_packed__",
        ):
            loader["mymod.foobar"]()


def test_render():
    opts = salt.config.DEFAULT_MINION_OPTS.copy()
    minion_mods = salt.loader.minion_mods(opts)
    for role in ["minion", "master"]:
        opts["__role"] = role
        for renderer in ["jinja|yaml", "some_custom_thing"]:
            opts["renderer"] = renderer
            ret = salt.loader.render(opts, minion_mods)
            assert isinstance(ret, salt.loader.lazy.FilterDictWrapper)
    with pytest.raises(salt.exceptions.LoaderError), patch(
        "salt.loader.check_render_pipe_str", MagicMock(side_effect=[False, False])
    ):
        salt.loader.render(opts, minion_mods)
