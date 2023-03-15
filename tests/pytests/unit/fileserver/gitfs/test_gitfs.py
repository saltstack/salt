"""
These are where the tests go, so that they can be run using both GitPython
and pygit2.

NOTE: The gitfs.update() has to happen AFTER the setUp is called. This is
because running it inside the setUp will spawn a new singleton, which means
that tests which need to mock the __opts__ will be too late; the setUp will
have created a new singleton that will bypass our mocking. To ensure that
our tests are reliable and correct, we want to make sure that each test
uses a new gitfs object, allowing different manipulations of the opts to be
tested.

Therefore, keep the following in mind:

1. Each test needs to call gitfs.update() *after* any patching, and
    *before* calling the function being tested.
2. Do *NOT* move the gitfs.update() into the setUp.

    :codeauthor: Erik Johnson <erik@saltstack.com>
"""

import logging
import os
import pathlib

import pytest

import salt.ext.tornado.ioloop
import salt.fileserver.gitfs as gitfs
import salt.utils.files
import salt.utils.gitfs
import salt.utils.platform
import salt.utils.win_functions
import salt.utils.yaml
from tests.support.helpers import patched_environ
from tests.support.mock import patch

try:
    import pwd  # pylint: disable=unused-import
except ImportError:
    pass


try:
    import git

    # We still need to use GitPython here for temp repo setup, so we do need to
    # actually import it. But we don't need import pygit2 in this module, we
    # can just use the Version instances imported along with
    # salt.utils.gitfs to check if we have a compatible version.
    HAS_GITPYTHON = (
        salt.utils.gitfs.GITPYTHON_VERSION
        and salt.utils.gitfs.GITPYTHON_VERSION >= salt.utils.gitfs.GITPYTHON_MINVER
    )
except (ImportError, AttributeError):
    HAS_GITPYTHON = False

try:
    HAS_PYGIT2 = (
        salt.utils.gitfs.PYGIT2_VERSION
        and salt.utils.gitfs.PYGIT2_VERSION >= salt.utils.gitfs.PYGIT2_MINVER
        and salt.utils.gitfs.LIBGIT2_VERSION
        and salt.utils.gitfs.LIBGIT2_VERSION >= salt.utils.gitfs.LIBGIT2_MINVER
    )
except AttributeError:
    HAS_PYGIT2 = False

log = logging.getLogger(__name__)


@pytest.fixture(scope="module", params=["gitpython", "pygit2"], autouse=True)
def provider(request):
    if not HAS_GITPYTHON:
        pytest.skip(
            "GitPython >= {} required for temp repo setup".format(
                salt.utils.gitfs.GITPYTHON_MINVER
            )
        )
    if request.param == "pygit2":
        if not HAS_PYGIT2:
            pytest.skip(
                "pygit2 >= {} and libgit2 >= {} required".format(
                    salt.utils.gitfs.PYGIT2_MINVER, salt.utils.gitfs.LIBGIT2_MINVER
                )
            )
        if salt.utils.platform.is_windows():
            pytest.skip("Skip Pygit2 on windows, due to pygit2 access error on windows")

    return request.param


@pytest.fixture
def sock_dir(tmp_path):
    dirname = tmp_path / "sock_dir"
    dirname.mkdir(parents=True, exist_ok=True)
    return dirname


@pytest.fixture(scope="module")
def unicode_filename():
    return "питон.txt"


@pytest.fixture(scope="module")
def tag_name():
    return "mytag"


@pytest.fixture(scope="module")
def unicode_dirname():
    return "соль"


@pytest.fixture(scope="module")
def load():
    return {"saltenv": "base"}


@pytest.fixture(autouse=True)
def testfile(tmp_path):
    fp = tmp_path / "testfile"
    fp.write_text("This is a testfile")
    return fp


@pytest.fixture
def repo_dir(tmp_path, unicode_dirname, tag_name, unicode_filename):
    try:
        del salt.utils.gitfs.GitFS.instance_map[
            salt.ext.tornado.ioloop.IOLoop.current()
        ]
    except KeyError:
        pass

    dirname = str(tmp_path / "repo_dir")
    if salt.utils.platform.is_windows():
        dirname = dirname.replace("\\", "/")

    # Populate repo
    root = pathlib.Path(dirname)
    grail_dir = root / "grail"
    grail_dir.mkdir(parents=True, exist_ok=True)
    (grail_dir / "random_file").touch()
    testfile = root / "testfile"
    testfile.write_text("this is a testfile in a git repo\n")
    unicode_file = root / unicode_filename
    unicode_file.write_text("\nThis is a file with a unicode name\n")
    unicode_dir = root / unicode_dirname
    unicode_dir.mkdir(parents=True, exist_ok=True)
    (unicode_dir / "foo.txt").touch()

    # Generate git data
    repo = git.Repo.init(dirname)
    try:
        if salt.utils.platform.is_windows():
            username = salt.utils.win_functions.get_current_user()
        else:
            username = pwd.getpwuid(os.geteuid()).pw_name
    except AttributeError:
        log.error("Unable to get effective username, falling back to 'root'.")
        username = "root"

    with patched_environ(USERNAME=username):
        repo.index.add([x for x in os.listdir(dirname) if x != ".git"])
        repo.index.commit("Test")

        # Add another branch with unicode characters in the name
        repo.create_head(unicode_dirname, "HEAD")

        # Add a tag
        repo.create_tag(tag_name, "HEAD")
        # Older GitPython versions do not have a close method.
        if hasattr(repo, "close"):
            repo.close()

    return dirname


@pytest.fixture
def cache_dir(tmp_path):
    dirname = tmp_path / "cache_dir"
    dirname.mkdir(parents=True, exist_ok=True)
    return dirname


@pytest.fixture
def configure_loader_modules(provider, sock_dir, repo_dir, cache_dir):
    opts = {
        "sock_dir": str(sock_dir),
        "gitfs_remotes": ["file://" + str(repo_dir)],
        "cachedir": str(cache_dir),
        "gitfs_root": "",
        "fileserver_backend": ["gitfs"],
        "gitfs_base": "master",
        "gitfs_fallback": "",
        "fileserver_events": True,
        "transport": "zeromq",
        "gitfs_mountpoint": "",
        "gitfs_saltenv": [],
        "gitfs_saltenv_whitelist": [],
        "gitfs_saltenv_blacklist": [],
        "gitfs_user": "",
        "gitfs_password": "",
        "gitfs_insecure_auth": False,
        "gitfs_privkey": "",
        "gitfs_pubkey": "",
        "gitfs_passphrase": "",
        "gitfs_refspecs": [
            "+refs/heads/*:refs/remotes/origin/*",
            "+refs/tags/*:refs/tags/*",
        ],
        "gitfs_ssl_verify": True,
        "gitfs_disable_saltenv_mapping": False,
        "gitfs_ref_types": ["branch", "tag", "sha"],
        "gitfs_update_interval": 60,
        "__role": "master",
        "gitfs_provider": provider,
    }

    return {gitfs: {"__opts__": opts}}


@pytest.fixture(autouse=True)
def skip_on_no_virtual(configure_loader_modules):
    if not gitfs.__virtual__():
        pytest.skip("GitFS could not be loaded. Skipping GitFS tests!")


@pytest.mark.slow_test
def test_file_list(load, unicode_filename, unicode_dirname):
    gitfs.update()
    ret = gitfs.file_list(load)
    assert "testfile" in ret
    assert unicode_filename in ret
    # This function does not use os.sep, the Salt fileserver uses the
    # forward slash, hence it being explicitly used to join here.
    assert "/".join((unicode_dirname, "foo.txt")) in ret


@pytest.mark.slow_test
def test_dir_list(load, unicode_dirname):
    gitfs.update()
    ret = gitfs.dir_list(load)
    assert "grail" in ret
    assert unicode_dirname in ret


def test_find_and_serve_file(repo_dir):
    with patch.dict(gitfs.__opts__, {"file_buffer_size": 262144}):
        gitfs.update()

        # find_file
        ret = gitfs.find_file("testfile")
        assert "testfile" == ret["rel"]

        full_path_to_file = salt.utils.path.join(
            gitfs.__opts__["cachedir"], "gitfs", "refs", "base", "testfile"
        )
        assert full_path_to_file == ret["path"]

        # serve_file
        load = {"saltenv": "base", "path": full_path_to_file, "loc": 0}
        fnd = {"path": full_path_to_file, "rel": "testfile"}
        ret = gitfs.serve_file(load, fnd)

        with salt.utils.files.fopen(
            os.path.join(repo_dir, "testfile"), "r"
        ) as fp_:  # NB: Why not 'rb'?
            data = fp_.read()

        assert ret == {"data": data, "dest": "testfile"}


def test_file_list_fallback(unicode_filename, unicode_dirname):
    with patch.dict(gitfs.__opts__, {"gitfs_fallback": "master"}):
        gitfs.update()
        ret = gitfs.file_list({"saltenv": "notexisting"})
        assert "testfile" in ret
        assert unicode_filename in ret
        # This function does not use os.sep, the Salt fileserver uses the
        # forward slash, hence it being explicitly used to join here.
        assert "/".join((unicode_dirname, "foo.txt")) in ret


def test_dir_list_fallback(unicode_dirname):
    with patch.dict(gitfs.__opts__, {"gitfs_fallback": "master"}):
        gitfs.update()
        ret = gitfs.dir_list({"saltenv": "notexisting"})
        assert "grail" in ret
        assert unicode_dirname in ret


def test_find_and_serve_file_fallback(repo_dir):
    with patch.dict(
        gitfs.__opts__, {"file_buffer_size": 262144, "gitfs_fallback": "master"}
    ):
        gitfs.update()

        # find_file
        ret = gitfs.find_file("testfile", tgt_env="notexisting")
        assert "testfile" == ret["rel"]

        full_path_to_file = salt.utils.path.join(
            gitfs.__opts__["cachedir"], "gitfs", "refs", "notexisting", "testfile"
        )
        assert full_path_to_file == ret["path"]

        # serve_file
        load = {"saltenv": "notexisting", "path": full_path_to_file, "loc": 0}
        fnd = {"path": full_path_to_file, "rel": "testfile"}
        ret = gitfs.serve_file(load, fnd)

        with salt.utils.files.fopen(
            os.path.join(repo_dir, "testfile"), "r"
        ) as fp_:  # NB: Why not 'rb'?
            data = fp_.read()

        assert ret == {"data": data, "dest": "testfile"}


@pytest.mark.slow_test
def test_envs(unicode_dirname, tag_name):
    gitfs.update()
    ret = gitfs.envs(ignore_cache=True)
    assert "base" in ret
    assert unicode_dirname in ret
    assert tag_name in ret


@pytest.mark.slow_test
def test_ref_types_global(unicode_dirname, tag_name):
    """
    Test the global gitfs_ref_types config option
    """
    with patch.dict(gitfs.__opts__, {"gitfs_ref_types": ["branch"]}):
        gitfs.update()
        ret = gitfs.envs(ignore_cache=True)
        # Since we are restricting to branches only, the tag should not
        # appear in the envs list.
        assert "base" in ret
        assert unicode_dirname in ret
        assert tag_name not in ret


@pytest.mark.slow_test
def test_ref_types_per_remote(repo_dir, unicode_dirname, tag_name):
    """
    Test the per_remote ref_types config option, using a different
    ref_types setting than the global test.
    """
    remotes = [{"file://" + repo_dir: [{"ref_types": ["tag"]}]}]
    with patch.dict(gitfs.__opts__, {"gitfs_remotes": remotes}):
        gitfs.update()
        ret = gitfs.envs(ignore_cache=True)
        # Since we are restricting to tags only, the tag should appear in
        # the envs list, but the branches should not.
        assert "base" not in ret
        assert unicode_dirname not in ret
        assert tag_name in ret


@pytest.mark.slow_test
def test_disable_saltenv_mapping_global_with_mapping_defined_globally():
    """
    Test the global gitfs_disable_saltenv_mapping config option, combined
    with the per-saltenv mapping being defined in the global gitfs_saltenv
    option.
    """
    opts = {
        "gitfs_disable_saltenv_mapping": True,
        "gitfs_saltenv": [{"foo": [{"ref": "somebranch"}]}],
    }
    with patch.dict(gitfs.__opts__, opts):
        gitfs.update()
        ret = gitfs.envs(ignore_cache=True)
        # Since we are restricting to tags only, the tag should appear in
        # the envs list, but the branches should not.
        assert ret == ["base", "foo"]


@pytest.mark.slow_test
def test_saltenv_blacklist(unicode_dirname):
    """
    test saltenv_blacklist
    """
    opts = {"gitfs_saltenv_blacklist": "base"}
    with patch.dict(gitfs.__opts__, opts):
        gitfs.update()
        ret = gitfs.envs(ignore_cache=True)
        assert "base" not in ret
        assert unicode_dirname in ret
        assert "mytag" in ret


@pytest.mark.slow_test
def test_saltenv_whitelist(unicode_dirname):
    """
    test saltenv_whitelist
    """
    opts = {"gitfs_saltenv_whitelist": "base"}
    with patch.dict(gitfs.__opts__, opts):
        gitfs.update()
        ret = gitfs.envs(ignore_cache=True)
        assert "base" in ret
        assert unicode_dirname not in ret
        assert "mytag" not in ret


@pytest.mark.slow_test
def test_env_deprecated_opts(unicode_dirname):
    """
    ensure deprecated options gitfs_env_whitelist
    and gitfs_env_blacklist do not cause gitfs to
    not load.
    """
    opts = {
        "gitfs_env_whitelist": "base",
        "gitfs_env_blacklist": "",
    }
    with patch.dict(gitfs.__opts__, opts):
        gitfs.update()
        ret = gitfs.envs(ignore_cache=True)
        assert "base" in ret
        assert unicode_dirname in ret
        assert "mytag" in ret


@pytest.mark.slow_test
def test_disable_saltenv_mapping_global_with_mapping_defined_per_remote(repo_dir):
    """
    Test the global gitfs_disable_saltenv_mapping config option, combined
    with the per-saltenv mapping being defined in the remote itself via the
    "saltenv" per-remote option.
    """
    opts = {
        "gitfs_disable_saltenv_mapping": True,
        "gitfs_remotes": [
            {repo_dir: [{"saltenv": [{"bar": [{"ref": "somebranch"}]}]}]}
        ],
    }
    with patch.dict(gitfs.__opts__, opts):
        gitfs.update()
        ret = gitfs.envs(ignore_cache=True)
        # Since we are restricting to tags only, the tag should appear in
        # the envs list, but the branches should not.
        assert ret == ["bar", "base"]


@pytest.mark.slow_test
def test_disable_saltenv_mapping_per_remote_with_mapping_defined_globally(repo_dir):
    """
    Test the per-remote disable_saltenv_mapping config option, combined
    with the per-saltenv mapping being defined in the global gitfs_saltenv
    option.
    """
    opts = {
        "gitfs_remotes": [{repo_dir: [{"disable_saltenv_mapping": True}]}],
        "gitfs_saltenv": [{"hello": [{"ref": "somebranch"}]}],
    }

    with patch.dict(gitfs.__opts__, opts):
        gitfs.update()
        ret = gitfs.envs(ignore_cache=True)
        # Since we are restricting to tags only, the tag should appear in
        # the envs list, but the branches should not.
        assert ret == ["base", "hello"]


@pytest.mark.slow_test
def test_disable_saltenv_mapping_per_remote_with_mapping_defined_per_remote(repo_dir):
    """
    Test the per-remote disable_saltenv_mapping config option, combined
    with the per-saltenv mapping being defined in the remote itself via the
    "saltenv" per-remote option.
    """
    opts = {
        "gitfs_remotes": [
            {
                repo_dir: [
                    {"disable_saltenv_mapping": True},
                    {"saltenv": [{"world": [{"ref": "somebranch"}]}]},
                ]
            }
        ]
    }
    with patch.dict(gitfs.__opts__, opts):
        gitfs.update()
        ret = gitfs.envs(ignore_cache=True)
        # Since we are restricting to tags only, the tag should appear in
        # the envs list, but the branches should not.
        assert ret == ["base", "world"]
