import pytest
import salt.config
import salt.fileserver.roots as roots

pytestmark = [
    pytest.mark.windows_whitelisted,
]


@pytest.fixture(scope="module")
def configure_loader_modules(state_tree):
    opts = salt.config.DEFAULT_MINION_OPTS.copy()
    opts["file_roots"]["base"] = [str(state_tree.base.write_path)]
    return {roots: {"__opts__": opts}}


def test_symlink_list(state_tree):
    with state_tree.base.temp_file("target", "data") as target:
        link = state_tree.base.write_path / "link"
        link.symlink_to(str(target))
        ret = roots.symlink_list({"saltenv": "base"})
        assert ret == {"link": str(target)}
