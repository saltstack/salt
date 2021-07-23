import pytest
import salt.config
import salt.fileserver.roots as roots

pytestmark = [
    pytest.mark.windows_whitelisted,
]


@pytest.fixture(scope="module")
def configure_loader_modules(base_env_state_tree_root_dir):
    opts = salt.config.DEFAULT_MINION_OPTS.copy()
    print(base_env_state_tree_root_dir)
    opts["file_roots"]["base"] = [str(base_env_state_tree_root_dir)]
    return {roots: {"__opts__": opts}}


# nox -e pytest-zeromq-3.8(coverage=False) -- -vvv --run-slow --run-destructive tests\pytests\functional\fileserver\test_roots.py
def test_symlink_list(base_env_state_tree_root_dir):
    with pytest.helpers.temp_file(
        "target", "data", base_env_state_tree_root_dir
    ) as target:
        link = base_env_state_tree_root_dir / "link"
        link.symlink_to(str(target))
        ret = roots.symlink_list({"saltenv": "base"})
        assert ret == {"link": str(target)}
