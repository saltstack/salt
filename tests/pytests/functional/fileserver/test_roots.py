import pytest
import salt.config
import salt.fileserver.roots as roots
from salt.utils.odict import OrderedDict
from tests.support.mock import patch

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


@pytest.mark.parametrize(
    "env",
    ("base", "something-else", "cool_path_123"),
)
def test_fileserver_roots_find_file_envs_path_substitution(
    env, temp_salt_minion, tmp_path
):
    """
    Test fileserver access to a dynamic path using __env__
    """
    fn = "test.txt"
    opts = temp_salt_minion.config.copy()

    envpath = tmp_path / env
    envpath.mkdir(parents=True, exist_ok=True)
    filepath = envpath / fn
    filepath.touch()

    # Stop using OrderedDict once we drop Py3.5 support
    expected = OrderedDict()
    expected["rel"] = fn
    expected["path"] = str(filepath)

    # Stop using OrderedDict once we drop Py3.5 support
    opts["file_roots"] = OrderedDict()
    opts["file_roots"][env] = [str(tmp_path / "__env__")]

    with patch("salt.fileserver.roots.__opts__", opts, create=True):
        ret = roots.find_file(fn, saltenv=env)
    ret.pop("stat")
    assert ret == expected


@pytest.mark.parametrize(
    "env",
    ("base", "something-else", "cool_path_123"),
)
def test_fileserver_roots__file_lists_envs_path_substitution(
    env, temp_salt_minion, tmp_path
):
    """
    Test fileserver access to a dynamic path using __env__
    """
    fn = "test.txt"
    opts = temp_salt_minion.config.copy()

    envpath = tmp_path / env
    envpath.mkdir(parents=True, exist_ok=True)
    filepath = envpath / fn
    filepath.touch()

    expected = [fn]

    # Stop using OrderedDict once we drop Py3.5 support
    opts["file_roots"] = OrderedDict()
    opts["file_roots"][env] = [str(tmp_path / "__env__")]

    with patch("salt.fileserver.roots.__opts__", opts, create=True):
        ret = roots._file_lists({"saltenv": env}, "files")

    assert ret == expected
