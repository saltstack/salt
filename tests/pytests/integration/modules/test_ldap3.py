import pytest

pytest_plugins = [
    "tests.support.pytest.ldap",
]
pytestmark = [
    pytest.mark.destructive_test,
    pytest.mark.skip_if_binaries_missing("docker"),
    pytest.mark.slow_test,
]


def test_search(openldap_minion_run, subtree, u0dn):
    assert openldap_minion_run("ldap3.search", base=subtree) == {
        subtree: {
            "objectClass": ["dcObject", "organization"],
            "dc": ["test_search"],
            "o": ["test_search"],
        },
        u0dn: {
            "objectClass": ["person"],
            "cn": ["u0"],
            "sn": ["Lastname"],
            "description": ["desc", "another desc"],
        },
    }


def test_search_filter(openldap_minion_run, subtree, u0dn):
    assert openldap_minion_run(
        "ldap3.search", base=subtree, filterstr="(sn=Lastname)"
    ) == {
        u0dn: {
            "objectClass": ["person"],
            "cn": ["u0"],
            "sn": ["Lastname"],
            "description": ["desc", "another desc"],
        },
    }
