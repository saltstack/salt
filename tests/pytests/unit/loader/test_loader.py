"""
tests.pytests.unit.loader.test_loader
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for salt's loader
"""
import os
import shutil
import textwrap

import pytest

import salt.loader
import salt.loader.lazy


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
