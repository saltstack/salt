import pytest
import salt.config
import salt.fileserver.roots as roots
from salt.utils.odict import OrderedDict
from tests.support.mock import patch

pytestmark = [
    pytest.mark.windows_whitelisted,
]


@pytest.fixture(scope="function")
def configure_loader_modules(base_env_state_tree_root_dir, tmp_path):
    cachedir = tmp_path / "__salt_test_fileserver_roots_cache_dir"
    cachedir.mkdir(parents=True, exist_ok=True)
    opts = salt.config.DEFAULT_MINION_OPTS.copy()
    opts["cachedir"] = str(cachedir)
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
    ("base", "something-else", "cool_path_123", "__env__"),
)
def test_fileserver_roots_find_file_envs_path_substitution(
    env, temp_salt_minion, tmp_path
):
    """
    Test fileserver access to a dynamic path using __env__
    """
    fn = "test.txt"
    opts = temp_salt_minion.config.copy()

    if env == "__env__":
        # __env__ saltenv will pass "dynamic" as saltenv and
        # expect to be routed to the "dynamic" directory
        actual_env = "dynamic"
        leaf_dir = actual_env
    else:
        # any other saltenv will pass saltenv normally and
        # expect to be routed to a static "__env__" directory
        actual_env = env
        leaf_dir = "__env__"

    envpath = tmp_path / leaf_dir
    envpath.mkdir(parents=True, exist_ok=True)
    filepath = envpath / fn
    filepath.touch()

    # Stop using OrderedDict once we drop Py3.5 support
    expected = OrderedDict()
    expected["rel"] = fn
    expected["path"] = str(filepath)

    # Stop using OrderedDict once we drop Py3.5 support
    opts["file_roots"] = OrderedDict()
    opts["file_roots"][env] = [str(tmp_path / leaf_dir)]

    with patch("salt.fileserver.roots.__opts__", opts, create=True):
        ret = roots.find_file(fn, saltenv=actual_env)
    ret.pop("stat")
    assert ret == expected


@pytest.mark.parametrize(
    "saltenv", ("base", "something-else", "cool_path_123", "__env__")
)
def test_fileserver_roots__file_lists_envs_path_substitution(
    saltenv, temp_salt_minion, tmp_path
):
    """
    Test fileserver access to a dynamic path using __env__
    """

    # We need our saltenv directory as well as some other env directory.
    # It doesn't really matter what it is - expected saltenv and not expected
    # saltenv
    # The filenames should be different, because cache lists the filenames.
    opts = temp_salt_minion.config.copy()
    other_env = "something_completely_different"
    other_filename = "different.txt"
    expected_filename = "test.txt"
    expected = [expected_filename]
    expected_different_ret = [other_filename]

    # __env__ saltenv will pass "dynamic" as saltenv and
    # expect to be routed to the "dynamic" directory
    actual_env = "dynamic" if saltenv == "__env__" else saltenv

    # If `__env__` is in the path and is the file roots (see
    # doc/ref/configuration/master.rst) then `__env__` will be replaced in the
    # file path with the actual saltenv. So we need the file_roots path, as
    # well as both our expected saltenv and our not expected saltenv. We also
    # need some files in the directories.
    file_roots = tmp_path / "__env__" / "cool"
    envpath = tmp_path / actual_env / "cool"
    otherpath = tmp_path / other_env / "cool"
    envpath.mkdir(parents=True, exist_ok=True)
    otherpath.mkdir(parents=True, exist_ok=True)
    (envpath / expected_filename).touch()
    (otherpath / other_filename).touch()

    # Stop using OrderedDict once we drop Py3.5 support
    opts["file_roots"] = OrderedDict()
    opts["file_roots"]["__env__"] = [str(file_roots)]

    with patch("salt.fileserver.roots.__opts__", opts, create=True):
        # actual_env is our target. The other env doesn't really matter, but
        # it should be different than our expected one and also contain its
        # own file(s)
        ret = roots._file_lists({"saltenv": actual_env}, "files")
        different_ret = roots._file_lists({"saltenv": other_env}, "files")

    assert ret == expected
    assert different_ret != ret
    assert different_ret == expected_different_ret
