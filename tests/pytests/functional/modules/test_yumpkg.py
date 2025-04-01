import shutil

import pytest

import salt.modules.cmdmod
import salt.modules.config
import salt.modules.pkg_resource
import salt.modules.yumpkg
import salt.utils.files
import salt.utils.pkg.rpm
from salt.exceptions import SaltInvocationError

pytestmark = [
    pytest.mark.skip_if_binaries_missing("rpm", "yum"),
]


@pytest.fixture
def configure_loader_modules(minion_opts, grains):
    grains.update({"osarch": salt.utils.pkg.rpm.get_osarch()})
    return {
        salt.modules.config: {
            "__grains__": grains,
        },
        salt.modules.pkg_resource: {
            "__grains__": grains,
        },
        salt.modules.yumpkg: {
            "__salt__": {
                "cmd.run": salt.modules.cmdmod.run,
                "cmd.run_all": salt.modules.cmdmod.run_all,
                "cmd.run_stdout": salt.modules.cmdmod.run_stdout,
                "config.get": salt.modules.config.get,
                "pkg_resource.add_pkg": salt.modules.pkg_resource.add_pkg,
                "pkg_resource.format_pkg_list": salt.modules.pkg_resource.format_pkg_list,
                "pkg_resource.parse_targets": salt.modules.pkg_resource.parse_targets,
                "pkg_resource.sort_pkglist": salt.modules.pkg_resource.sort_pkglist,
            },
            "__opts__": minion_opts,
            "__grains__": grains,
        },
    }


@pytest.fixture
def repo_basedir(tmp_path):
    basedir = tmp_path / "test_yum"
    basedir.mkdir(exist_ok=True, parents=True)
    repo_file = basedir / "salt-test-repo.repo"
    file_contents = [
        "[salt-repo]",
        "name=Salt repo for RHEL/CentOS 8 PY3",
        "baseurl=https://repo.saltproject.io/salt/py3/redhat/8/x86_64/latest",
        "skip_if_unavailable=True",
        "priority=10",
        "enabled_metadata=1",
        "gcheck=1",
        "gkey=https://repo.saltproject.io/salt/py3/redhat/8/x86_64/latest/SALT-PROJECT-GPG-PUBKEY-2023.pub",
    ]
    with salt.utils.files.fopen(str(repo_file), "w") as fd:
        for line in file_contents:
            fd.write(f"{line}\n")
    try:
        yield basedir
    finally:
        shutil.rmtree(str(basedir))


@pytest.mark.slow_test
def test_yum_list_pkgs(grains):
    """
    compare the output of rpm -qa vs the return of yumpkg.list_pkgs,
    make sure that any changes to ympkg.list_pkgs still returns.
    """
    cmd = [
        "rpm",
        "-qa",
        "--queryformat",
        "%{NAME}\n",
    ]
    known_pkgs = salt.modules.cmdmod.run(cmd, python_shell=False)
    listed_pkgs = salt.modules.yumpkg.list_pkgs()
    for line in known_pkgs.splitlines():
        assert any(line in d for d in listed_pkgs)


@pytest.mark.destructive_test
@pytest.mark.skip_if_not_root
@pytest.mark.slow_test
def test_yumpkg_remove_wildcard():
    salt.modules.yumpkg.install(pkgs=["httpd-devel", "httpd-tools"])
    ret = salt.modules.yumpkg.remove(name="httpd-*")
    assert not ret["httpd-devel"]["new"]
    assert ret["httpd-devel"]["old"]
    assert not ret["httpd-tools"]["new"]
    assert ret["httpd-tools"]["old"]


def test_yumpkg_mod_repo_fails(repo_basedir):
    with pytest.raises(SaltInvocationError) as excinfo:
        salt.modules.yumpkg.mod_repo(
            repo="basedir-fail-test", basedir="/fake/directory"
        )
    assert (
        str(excinfo.value)
        == "The repo does not exist and needs to be created, but none of the following basedir directories exist: ['/fake/directory']"
    )

    with pytest.raises(SaltInvocationError) as excinfo:
        salt.modules.yumpkg.mod_repo(
            repo="missing-name-fail", basedir=str(repo_basedir)
        )
    assert (
        str(excinfo.value)
        == "The repo does not exist and needs to be created, but a name was not given"
    )

    with pytest.raises(SaltInvocationError) as excinfo:
        salt.modules.yumpkg.mod_repo(
            repo="missing-url-fail", basedir=str(repo_basedir), name="missing_url"
        )
    assert (
        str(excinfo.value)
        == "The repo does not exist and needs to be created, but none of baseurl, mirrorlist, metalink was given"
    )

    with pytest.raises(SaltInvocationError) as excinfo:
        salt.modules.yumpkg.mod_repo(
            repo="too-many-url-fail",
            basedir=str(repo_basedir),
            name="toomanyurls",
            baseurl="https://example.com",
            mirrorlist="https://example.com",
            metalink="https://example.com",
        )
    assert (
        str(excinfo.value)
        == "One and only one of baseurl, mirrorlist, metalink can be used"
    )

    with pytest.raises(SaltInvocationError) as excinfo:
        salt.modules.yumpkg.mod_repo(
            repo="too-many-url-fail",
            basedir=str(repo_basedir),
            name="toomanyurls",
            baseurl="https://example.com",
            metalink="https://example.com",
        )
    assert (
        str(excinfo.value)
        == "One and only one of baseurl, mirrorlist, metalink can be used"
    )

    with pytest.raises(SaltInvocationError) as excinfo:
        salt.modules.yumpkg.mod_repo(
            repo="too-many-url-fail",
            basedir=str(repo_basedir),
            name="toomanyurls",
            baseurl="https://example.com",
            mirrorlist="https://example.com",
        )
    assert (
        str(excinfo.value)
        == "One and only one of baseurl, mirrorlist, metalink can be used"
    )

    with pytest.raises(SaltInvocationError) as excinfo:
        salt.modules.yumpkg.mod_repo(
            repo="too-many-url-fail",
            basedir=str(repo_basedir),
            name="toomanyurls",
            mirrorlist="https://example.com",
            metalink="https://example.com",
        )
    assert (
        str(excinfo.value)
        == "One and only one of baseurl, mirrorlist, metalink can be used"
    )

    with pytest.raises(SaltInvocationError) as excinfo:
        salt.modules.yumpkg.mod_repo(
            repo="salt-repo",
            basedir=str(repo_basedir),
            name="",
        )
    assert str(excinfo.value) == "The repo name cannot be deleted"

    with pytest.raises(SaltInvocationError) as excinfo:
        salt.modules.yumpkg.mod_repo(
            repo="salt-repo",
            basedir=str(repo_basedir),
            name="Salt repo for RHEL/CentOS 8 PY3",
            baseurl="",
        )
    assert str(excinfo.value).startswith("Cannot delete baseurl without specifying")
    assert "metalink" in str(excinfo.value)
    assert "mirrorlist" in str(excinfo.value)


def test_yumpkg_mod_repo_nochange(repo_basedir):
    repo_file = repo_basedir / "salt-test-repo.repo"
    test_enable = salt.modules.yumpkg.mod_repo(
        repo="salt-repo",
        basedir=str(repo_basedir),
        name="Salt repo for RHEL/CentOS 8 PY3",
        enable=True,
    )
    # check return on thing that we included in command
    assert test_enable[str(repo_file)]["salt-repo"]["enable"] is True
    # check return on thing that we did not include in command
    assert (
        test_enable[str(repo_file)]["salt-repo"]["gkey"]
        == "https://repo.saltproject.io/salt/py3/redhat/8/x86_64/latest/SALT-PROJECT-GPG-PUBKEY-2023.pub"
    )


def test_yumpkg_mod_repo_baseurl_to_metalink(repo_basedir):
    repo_file = repo_basedir / "salt-test-repo.repo"
    test_metalink = salt.modules.yumpkg.mod_repo(
        repo="salt-repo",
        basedir=str(repo_basedir),
        name="Salt repo for RHEL/CentOS 8 PY3",
        metalink="https://example.com",
    )
    # new metalink item?
    assert (
        test_metalink[str(repo_file)]["salt-repo"]["metalink"] == "https://example.com"
    )
    # make sure baseurl is not in the result
    assert "baseurl" not in test_metalink[str(repo_file)]["salt-repo"]


def test_yumpkg_mod_repo_baseurl_to_mirrorlist(repo_basedir):
    repo_file = repo_basedir / "salt-test-repo.repo"
    test_mirrorlist = salt.modules.yumpkg.mod_repo(
        repo="salt-repo",
        basedir=str(repo_basedir),
        name="Salt repo for RHEL/CentOS 8 PY3",
        mirrorlist="https://example.com",
    )
    # new metalink item?
    assert (
        test_mirrorlist[str(repo_file)]["salt-repo"]["mirrorlist"]
        == "https://example.com"
    )
    # make sure baseurl is not in the result
    assert "baseurl" not in test_mirrorlist[str(repo_file)]["salt-repo"]


def test_yumpkg_mod_repo_create_repo(repo_basedir):
    repo_file = repo_basedir / "test.repo"
    test_repo = salt.modules.yumpkg.mod_repo(
        repo="test",
        basedir=str(repo_basedir),
        name="test repo",
        baseurl="https://example.com",
    )
    # new metalink item?
    assert test_repo[str(repo_file)]["test"]["baseurl"] == "https://example.com"
    assert test_repo[str(repo_file)]["test"]["name"] == "test repo"
