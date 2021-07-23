"""
Tests for the SVN state
"""
import logging

import pytest
import salt.utils.platform

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.requires_network,
    pytest.mark.skip_if_binaries_missing("svn"),
]


@pytest.fixture
def repo_target(tmp_path):
    return tmp_path / "svn-repo-checkout"


@pytest.fixture
def repo_revision():
    return "1456987"


@pytest.fixture
def repo_url():
    return "http://svn.apache.org/repos/asf/httpd/httpd/trunk/test/"


@pytest.fixture(scope="module")
def svn(states):
    return states.svn


@pytest.fixture(scope="module")
def svn_mod(modules):
    return modules.svn


@pytest.fixture(scope="module")
def account():
    with pytest.helpers.create_account(create_group=True) as _account:
        yield _account


@pytest.mark.slow_test
def test_latest(svn, repo_url, repo_revision, repo_target):
    """
    svn.latest
    """
    ret = svn.latest(name=repo_url, rev=repo_revision, target=str(repo_target))
    assert ret.result is True
    assert repo_target.joinpath(".svn").is_dir()
    assert ret.changes
    assert "new" in ret.changes
    assert ret.changes["new"] == repo_url
    assert "revision" in ret.changes
    assert ret.changes["revision"] == repo_revision


@pytest.mark.slow_test
def test_latest_failure(svn, repo_revision, repo_target):
    """
    svn.latest
    """
    ret = svn.latest(
        name="https://youSpelledApacheWrong.com/repo/asf/httpd/trunk/",
        rev=repo_revision,
        target=str(repo_target),
    )
    assert ret.result is False
    assert not repo_target.joinpath(".svn").is_dir()


@pytest.mark.slow_test
@pytest.mark.destructive_test
@pytest.mark.skip_if_not_root
def test_latest_user(svn, repo_url, repo_revision, repo_target, account):
    """
    svn.latest
    """
    # Make sure the repo_target parent directory is writable by anyone
    repo_target.parent.chmod(0o777)
    ret = svn.latest(
        name=repo_url, rev=repo_revision, target=str(repo_target), user=account.username
    )
    assert ret.result is True
    assert repo_target.joinpath(".svn").is_dir()
    assert ret.changes
    assert "new" in ret.changes
    assert ret.changes["new"] == repo_url
    assert "revision" in ret.changes
    assert ret.changes["revision"] == repo_revision

    # Make sure that the files in the cloned repo are owned by the account that did the checkout
    for entry in repo_target.iterdir():
        entry_stat = entry.stat()
        assert entry_stat.st_uid == account.info.uid
        try:
            assert entry_stat.st_gid == account.info.gid
        except AssertionError:
            if not salt.utils.platform.is_darwin():
                raise
            pytest.xfail("The 'cmd' module does not change to the user group on Darwin")


@pytest.mark.slow_test
def test_latest_empty_dir(svn, repo_url, repo_revision, repo_target):
    """
    svn.latest
    """
    repo_target.mkdir()
    ret = svn.latest(name=repo_url, rev=repo_revision, target=str(repo_target))
    assert ret.result is True
    assert repo_target.joinpath(".svn").is_dir()


def no_test_latest_existing_repo(svn, svn_mod, repo_url, repo_revision, repo_target):
    """
    svn.latest against existing repository
    """
    current_rev = "1442865"
    cwd = str(repo_target.parent)
    basename = repo_target.name
    opts = ("-r", current_rev)

    assert svn_mod.checkout(cwd, repo_url, basename, None, None, opts)

    ret = svn.latest(name=repo_url, rev=repo_revision, target=str(repo_target))
    assert ret.result is True
    assert ret.changes
    assert "revision" in ret.changes
    assert ret.changes["revision"] == "{} => {}".format(current_rev, repo_revision)
    assert repo_target.joinpath(".svn").is_dir()


def no_test_latest_existing_repo_no_rev_change(
    svn, svn_mod, repo_url, repo_revision, repo_target
):
    """
    svn.latest against existing repository
    """
    current_rev = repo_revision
    cwd = str(repo_target.parent)
    basename = repo_target.name
    opts = ("-r", current_rev)
    assert svn_mod.checkout(cwd, repo_url, basename, None, None, opts)

    ret = svn.latest(name=repo_url, rev=repo_revision, target=str(repo_target))
    assert ret.result is True
    assert not ret.changes
    assert isinstance(ret.changes, dict)
    assert repo_target.joinpath(".svn").is_dir()
