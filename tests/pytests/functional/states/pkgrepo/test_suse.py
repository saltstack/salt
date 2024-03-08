import pytest

pytestmark = [
    pytest.mark.destructive_test,
    pytest.mark.skip_if_not_root,
]


@pytest.fixture
def pkgrepo(states, grains):
    if grains["os_family"] != "Suse":
        raise pytest.skip.Exception(
            "Test is only applicable to SUSE based operating systems",
            _use_item_location=True,
        )
    return states.pkgrepo


@pytest.fixture
def suse_state_tree(grains, pkgrepo, state_tree):
    managed_sls_contents = """
    salttest:
      pkgrepo.managed:
        - enabled: 1
        - gpgcheck: 1
        - comments:
          - '# Salt Test'
        - refresh: 1
    {% if grains['osmajorrelease'] == 15 %}
        - baseurl: https://download.opensuse.org/repositories/openSUSE:/Backports:/SLE-15-SP4/standard/
        - humanname: openSUSE Backports for SLE 15 SP4
        - gpgkey: https://download.opensuse.org/repositories/openSUSE:/Backports:/SLE-15-SP4/standard/repodata/repomd.xml.key
    {% elif grains['osfullname'] == 'openSUSE Tumbleweed' %}
        - baseurl: http://download.opensuse.org/tumbleweed/repo/oss/
        - humanname: openSUSE Tumbleweed OSS
        - gpgkey: https://download.opensuse.org/tumbleweed/repo/oss/repodata/repomd.xml.key
    {% endif %}
    """

    absent_sls_contents = """
    salttest:
      pkgrepo:
        - absent
    """

    modified_sls_contents = """
    salttest:
      pkgrepo.managed:
        - enabled: 1
        - gpgcheck: 1
        - comments:
          - '# Salt Test (modified)'
        - refresh: 1
    {% if grains['osmajorrelease'] == 15 %}
        - baseurl: https://download.opensuse.org/repositories/openSUSE:/Backports:/SLE-15-SP4/standard/
        - humanname: Salt modified Backports
        - gpgkey: https://download.opensuse.org/repositories/openSUSE:/Backports:/SLE-15-SP4/standard/repodata/repomd.xml.key
    {% elif grains['osfullname'] == 'openSUSE Tumbleweed' %}
        - baseurl: http://download.opensuse.org/tumbleweed/repo/oss/
        - humanname: Salt modified OSS
        - gpgkey: https://download.opensuse.org/tumbleweed/repo/oss/repodata/repomd.xml.key
    {% endif %}
    """

    managed_state_file = pytest.helpers.temp_file(
        "pkgrepo/managed.sls", managed_sls_contents, state_tree
    )
    absent_state_file = pytest.helpers.temp_file(
        "pkgrepo/absent.sls", absent_sls_contents, state_tree
    )
    modified_state_file = pytest.helpers.temp_file(
        "pkgrepo/modified.sls", modified_sls_contents, state_tree
    )

    try:
        with managed_state_file, absent_state_file, modified_state_file:
            yield
    finally:
        pass


@pytest.mark.requires_salt_states("pkgrepo.managed", "pkgrepo.absent")
def test_pkgrepo_managed_absent(grains, modules, subtests, suse_state_tree):
    """
    Test adding and removing a repository
    """
    add_repo_test_passed = False

    def _run(name, test=False):
        return modules.state.sls(
            mods=name,
            test=test,
        )

    with subtests.test("Add repository"):
        ret = _run("pkgrepo.managed")
        assert ret.failed is False
        for state in ret:
            assert state.result is True
        add_repo_test_passed = True

    if add_repo_test_passed is False:
        pytest.skip("Adding the repository failed, skipping removal tests.")

    with subtests.test("Remove repository, test"):
        ret = _run("pkgrepo.absent", test=True)
        assert ret.failed is False
        for state in ret:
            assert state.changes == {}
            assert state.comment.startswith("Package repo 'salttest' will be removed.")
            assert state.result is None

    with subtests.test("Remove repository"):
        ret = _run("pkgrepo.absent")
        assert ret.failed is False
        for state in ret:
            assert state.result is True

    with subtests.test("Remove repository again, test"):
        ret = _run("pkgrepo.absent", test=True)
        assert ret.failed is False
        for state in ret:
            assert state.changes == {}
            assert state.comment == "Package repo salttest is absent"
            assert state.result is True

    with subtests.test("Remove repository again"):
        ret = _run("pkgrepo.absent")
        assert ret.failed is False
        for state in ret:
            assert state.changes == {}
            assert state.comment == "Package repo salttest is absent"
            assert state.result is True


@pytest.mark.requires_salt_states("pkgrepo.managed")
def test_pkgrepo_managed_modify(grains, modules, subtests, suse_state_tree):
    """
    Test adding and modifying a repository
    """
    add_repo_test_passed = False

    def _run(name, test=False):
        return modules.state.sls(
            mods=name,
            test=test,
        )

    with subtests.test("Add repository, test"):
        ret = _run("pkgrepo.managed", test=True)
        assert ret.failed is False
        for state in ret:
            assert state.changes == {"repo": "salttest"}
            assert state.comment.startswith(
                "Package repo 'salttest' would be configured."
            )
            assert state.result is None

    with subtests.test("Add repository"):
        ret = _run("pkgrepo.managed")
        assert ret.failed is False
        for state in ret:
            assert state.changes == {"repo": "salttest"}
            assert state.comment == "Configured package repo 'salttest'"
            assert state.result is True
        add_repo_test_passed = True

    if add_repo_test_passed is False:
        pytest.skip("Adding the repository failed, skipping modification tests.")

    with subtests.test("Add repository again, test"):
        ret = _run("pkgrepo.managed", test=True)
        assert ret.failed is False
        for state in ret:
            assert state.changes == {}
            assert state.comment == "Package repo 'salttest' already configured"
            assert state.result is True

    with subtests.test("Add repository again"):
        ret = _run("pkgrepo.managed")
        assert ret.failed is False
        for state in ret:
            assert state.result is True
            assert state.changes == {}
            assert state.comment == "Package repo 'salttest' already configured"

    with subtests.test("Modify repository, test"):
        ret = _run("pkgrepo.modified", test=True)
        assert ret.failed is False
        for state in ret:
            assert state.changes == {
                "comments": {"new": ["# Salt Test (modified)"], "old": None},
                "refresh": {"new": 1, "old": None},
                "gpgkey": {
                    "new": "https://download.opensuse.org/repositories/openSUSE:/Backports:/SLE-15-SP4/standard/repodata/repomd.xml.key",
                    "old": None,
                },
                "name": {
                    "new": "Salt modified Backports",
                    "old": "openSUSE Backports for SLE 15 SP4",
                },
            }
            assert state.comment.startswith(
                "Package repo 'salttest' would be configured."
            )
            assert state.result is None

    with subtests.test("Modify repository"):
        ret = _run("pkgrepo.modified")
        assert ret.failed is False
        for state in ret:
            assert state.result is True
            assert state.changes == {
                "name": {
                    "new": "Salt modified Backports",
                    "old": "openSUSE Backports for SLE 15 SP4",
                }
            }
            assert state.comment == "Configured package repo 'salttest'"
