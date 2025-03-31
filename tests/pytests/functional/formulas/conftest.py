import shutil
import zipfile

import pytest


@pytest.fixture(scope="module")
def formula():
    pytest.fail("The module scoped 'formula' fixture should have been overridden.")


@pytest.fixture(scope="module")
def modules(loaders, formula, tmp_path_factory, base_env_state_tree_root_dir):
    url = f"https://github.com/saltstack-formulas/{formula.name}/archive/refs/tags/v{formula.tag}.zip"
    zipfiles_dir = tmp_path_factory.mktemp(f"unzipped-{formula.name}-{formula.tag}")
    try:
        target_path = base_env_state_tree_root_dir / f"{formula.name}-{formula.tag}"
        zipfile_path = pytest.helpers.download_file(
            url, zipfiles_dir / url.split("/")[-1]
        )
        with zipfile.ZipFile(zipfile_path) as zip_obj:
            zip_obj.extractall(zipfiles_dir)
        shutil.move(zipfiles_dir / f"{formula.name}-{formula.tag}", target_path)

        loaders.opts["file_roots"]["base"].append(str(target_path))
        yield loaders.modules
    finally:
        shutil.rmtree(zipfiles_dir, ignore_errors=True)
