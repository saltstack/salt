import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.slow_test,
]


@pytest.fixture(scope="module")
def pkg_def_contents(state_tree):
    return r"""
    my-software:
      '1.0.1':
        full_name: 'My Software'
        installer: 'C:\files\mysoftware101.msi'
        install_flags: '/qn /norestart'
        uninstaller: 'C:\files\mysoftware101.msi'
        uninstall_flags: '/qn /norestart'
        msiexec: True
        reboot: False
      '1.0.2':
        full_name: 'My Software'
        installer: 'C:\files\mysoftware102.msi'
        install_flags: '/qn /norestart'
        uninstaller: 'C:\files\mysoftware102.msi'
        uninstall_flags: '/qn /norestart'
        msiexec: True
        reboot: False
    your-software:
      '1.0.0':
        full_name: 'Your Software'
        installer: 'C:\files\yoursoftware101.msi'
        install_flags: '/qn /norestart'
        uninstaller: 'C:\files\yoursoftware101.msi'
        uninstall_flags: '/qn /norestart'
        msiexec: True
        reboot: False
    """


@pytest.fixture(scope="module")
def pkg(modules):
    yield modules.pkg


@pytest.fixture(scope="function")
def repo(pkg, state_tree, pkg_def_contents):
    assert len(pkg.get_package_info("my-software")) == 0
    repo_dir = state_tree / "winrepo_ng"
    with pytest.helpers.temp_file("my-software.sls", pkg_def_contents, repo_dir):
        pkg.refresh_db()


def test_refresh_db(pkg, repo):
    assert len(pkg.get_package_info("my-software")) == 2
    assert len(pkg.get_package_info("your-software")) == 1


@pytest.mark.parametrize(
    "as_dict, reverse, expected",
    [
        (False, False, ["1.0.1", "1.0.2"]),
        (False, True, ["1.0.2", "1.0.1"]),
        (True, False, {"my-software": ["1.0.1", "1.0.2"]}),
        (True, True, {"my-software": ["1.0.2", "1.0.1"]}),
    ],
)
def test_list_available(pkg, repo, as_dict, reverse, expected):
    result = pkg.list_available(
        "my-software", return_dict_always=as_dict, reverse_sort=reverse
    )
    assert result == expected


@pytest.mark.parametrize(
    "pkg_name, expected",
    [
        ("my-software", {"my-software": ["1.0.2", "1.0.1"]}),
        ("my-software=1.0.1", {"my-software": ["1.0.1"]}),
        ("my-soft*", {"my-software": ["1.0.2", "1.0.1"]}),
        ("your-software", {"your-software": ["1.0.0"]}),
        (None, {"my-software": ["1.0.2", "1.0.1"], "your-software": ["1.0.0"]}),
    ],
)
def test_list_repo_pkgs(pkg, repo, pkg_name, expected):
    if pkg_name is None:
        result = pkg.list_repo_pkgs()
    else:
        result = pkg.list_repo_pkgs(pkg_name)
    assert result == expected
