import shutil

import pytest

from tests.support.pytest.formulas import SaltStackFormula


@pytest.fixture(scope="module")
def saltstack_formula(tmp_path_factory, base_env_state_tree_root_dir):
    zipfiles_dir = tmp_path_factory.mktemp("fomulas-zips")
    try:
        yield SaltStackFormula.with_default_paths(
            zipfiles_dir, base_env_state_tree_root_dir
        )
    finally:
        shutil.rmtree(zipfiles_dir, ignore_errors=True)
