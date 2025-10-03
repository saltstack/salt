from pathlib import Path

import pytest

from tests.support.runtests import RUNTIME_VARS


@pytest.fixture(scope="module")
def minion_config_overrides():
    return {"master_tops": {"master_tops_test": True}}


@pytest.fixture(scope="module", autouse=True)
def _master_tops_test(state_tree, loaders):
    mod_contents = (
        Path(RUNTIME_VARS.FILES) / "extension_modules" / "tops" / "master_tops_test.py"
    ).read_text()
    try:
        with pytest.helpers.temp_file(
            "master_tops_test.py", mod_contents, state_tree / "_tops"
        ):
            res = loaders.modules.saltutil.sync_tops()
            assert "tops.master_tops_test" in res
            yield
    finally:
        loaders.modules.saltutil.sync_tops()


def test_masterless_master_tops(loaders):
    res = loaders.modules.state.show_top()
    assert res
    assert "base" in res
    assert "master_tops_test" in res["base"]
