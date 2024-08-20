import logging

import pytest

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.destructive_test,
    pytest.mark.skip_if_not_root,
]

RPM_GPG_KEY_EPEL_8_SALTTEST = """\
-----BEGIN PGP PUBLIC KEY BLOCK-----

mQINBFz3zvsBEADJOIIWllGudxnpvJnkxQz2CtoWI7godVnoclrdl83kVjqSQp+2
dgxuG5mUiADUfYHaRQzxKw8efuQnwxzU9kZ70ngCxtmbQWGmUmfSThiapOz00018
+eo5MFabd2vdiGo1y+51m2sRDpN8qdCaqXko65cyMuLXrojJHIuvRA/x7iqOrRfy
a8x3OxC4PEgl5pgDnP8pVK0lLYncDEQCN76D9ubhZQWhISF/zJI+e806V71hzfyL
/Mt3mQm/li+lRKU25Usk9dWaf4NH/wZHMIPAkVJ4uD4H/uS49wqWnyiTYGT7hUbi
ecF7crhLCmlRzvJR8mkRP6/4T/F3tNDPWZeDNEDVFUkTFHNU6/h2+O398MNY/fOh
yKaNK3nnE0g6QJ1dOH31lXHARlpFOtWt3VmZU0JnWLeYdvap4Eff9qTWZJhI7Cq0
Wm8DgLUpXgNlkmquvE7P2W5EAr2E5AqKQoDbfw/GiWdRvHWKeNGMRLnGI3QuoX3U
pAlXD7v13VdZxNydvpeypbf/AfRyrHRKhkUj3cU1pYkM3DNZE77C5JUe6/0nxbt4
ETUZBTgLgYJGP8c7PbkVnO6I/KgL1jw+7MW6Az8Ox+RXZLyGMVmbW/TMc8haJfKL
MoUo3TVk8nPiUhoOC0/kI7j9ilFrBxBU5dUtF4ITAWc8xnG6jJs/IsvRpQARAQAB
tChGZWRvcmEgRVBFTCAoOCkgPGVwZWxAZmVkb3JhcHJvamVjdC5vcmc+iQI4BBMB
AgAiBQJc9877AhsPBgsJCAcDAgYVCAIJCgsEFgIDAQIeAQIXgAAKCRAh6kWrL4bW
oWagD/4xnLWws34GByVDQkjprk0fX7Iyhpm/U7BsIHKspHLL+Y46vAAGY/9vMvdE
0fcr9Ek2Zp7zE1RWmSCzzzUgTG6BFoTG1H4Fho/7Z8BXK/jybowXSZfqXnTOfhSF
alwDdwlSJvfYNV9MbyvbxN8qZRU1z7PEWZrIzFDDToFRk0R71zHpnPTNIJ5/YXTw
NqU9OxII8hMQj4ufF11040AJQZ7br3rzerlyBOB+Jd1zSPVrAPpeMyJppWFHSDAI
WK6x+am13VIInXtqB/Cz4GBHLFK5d2/IYspVw47Solj8jiFEtnAq6+1Aq5WH3iB4
bE2e6z00DSF93frwOyWN7WmPIoc2QsNRJhgfJC+isGQAwwq8xAbHEBeuyMG8GZjz
xohg0H4bOSEujVLTjH1xbAG4DnhWO/1VXLX+LXELycO8ZQTcjj/4AQKuo4wvMPrv
9A169oETG+VwQlNd74VBPGCvhnzwGXNbTK/KH1+WRH0YSb+41flB3NKhMSU6dGI0
SGtIxDSHhVVNmx2/6XiT9U/znrZsG5Kw8nIbbFz+9MGUUWgJMsd1Zl9R8gz7V9fp
n7L7y5LhJ8HOCMsY/Z7/7HUs+t/A1MI4g7Q5g5UuSZdgi0zxukiWuCkLeAiAP4y7
zKK4OjJ644NDcWCHa36znwVmkz3ixL8Q0auR15Oqq2BjR/fyog==
=84m8
-----END PGP PUBLIC KEY BLOCK-----
"""

RPM_GPG_KEY_EPEL_7_SALTTEST = """\
-----BEGIN PGP PUBLIC KEY BLOCK-----
Version: GnuPG v1.4.11 (GNU/Linux)

mQINBFKuaIQBEAC1UphXwMqCAarPUH/ZsOFslabeTVO2pDk5YnO96f+rgZB7xArB
OSeQk7B90iqSJ85/c72OAn4OXYvT63gfCeXpJs5M7emXkPsNQWWSju99lW+AqSNm
jYWhmRlLRGl0OO7gIwj776dIXvcMNFlzSPj00N2xAqjMbjlnV2n2abAE5gq6VpqP
vFXVyfrVa/ualogDVmf6h2t4Rdpifq8qTHsHFU3xpCz+T6/dGWKGQ42ZQfTaLnDM
jToAsmY0AyevkIbX6iZVtzGvanYpPcWW4X0RDPcpqfFNZk643xI4lsZ+Y2Er9Yu5
S/8x0ly+tmmIokaE0wwbdUu740YTZjCesroYWiRg5zuQ2xfKxJoV5E+Eh+tYwGDJ
n6HfWhRgnudRRwvuJ45ztYVtKulKw8QQpd2STWrcQQDJaRWmnMooX/PATTjCBExB
9dkz38Druvk7IkHMtsIqlkAOQMdsX1d3Tov6BE2XDjIG0zFxLduJGbVwc/6rIc95
T055j36Ez0HrjxdpTGOOHxRqMK5m9flFbaxxtDnS7w77WqzW7HjFrD0VeTx2vnjj
GqchHEQpfDpFOzb8LTFhgYidyRNUflQY35WLOzLNV+pV3eQ3Jg11UFwelSNLqfQf
uFRGc+zcwkNjHh5yPvm9odR1BIfqJ6sKGPGbtPNXo7ERMRypWyRz0zi0twARAQAB
tChGZWRvcmEgRVBFTCAoNykgPGVwZWxAZmVkb3JhcHJvamVjdC5vcmc+iQI4BBMB
AgAiBQJSrmiEAhsPBgsJCAcDAgYVCAIJCgsEFgIDAQIeAQIXgAAKCRBqL66iNSxk
5cfGD/4spqpsTjtDM7qpytKLHKruZtvuWiqt5RfvT9ww9GUUFMZ4ZZGX4nUXg49q
ixDLayWR8ddG/s5kyOi3C0uX/6inzaYyRg+Bh70brqKUK14F1BrrPi29eaKfG+Gu
MFtXdBG2a7OtPmw3yuKmq9Epv6B0mP6E5KSdvSRSqJWtGcA6wRS/wDzXJENHp5re
9Ism3CYydpy0GLRA5wo4fPB5uLdUhLEUDvh2KK//fMjja3o0L+SNz8N0aDZyn5Ax
CU9RB3EHcTecFgoy5umRj99BZrebR1NO+4gBrivIfdvD4fJNfNBHXwhSH9ACGCNv
HnXVjHQF9iHWApKkRIeh8Fr2n5dtfJEF7SEX8GbX7FbsWo29kXMrVgNqHNyDnfAB
VoPubgQdtJZJkVZAkaHrMu8AytwT62Q4eNqmJI1aWbZQNI5jWYqc6RKuCK6/F99q
thFT9gJO17+yRuL6Uv2/vgzVR1RGdwVLKwlUjGPAjYflpCQwWMAASxiv9uPyYPHc
ErSrbRG0wjIfAR3vus1OSOx3xZHZpXFfmQTsDP7zVROLzV98R3JwFAxJ4/xqeON4
vCPFU6OsT3lWQ8w7il5ohY95wmujfr6lk89kEzJdOTzcn7DBbUru33CQMGKZ3Evt
RjsC7FDbL017qxS+ZVA/HGkyfiu4cpgV8VUnbql5eAZ+1Ll6Dw==
=hdPa
-----END PGP PUBLIC KEY BLOCK-----
"""


@pytest.fixture
def pkgrepo(states, grains):
    if grains["os_family"] != "RedHat":
        raise pytest.skip.Exception(
            "Test only for CentOS platforms, not '{}' based distributions.".format(
                grains["os_family"]
            ),
            _use_item_location=True,
        )
    return states.pkgrepo


@pytest.fixture
def centos_state_tree(grains, pkgrepo, state_tree):
    if grains["os"] not in ("CentOS", "CentOS Stream"):
        pytest.skip("Test only applicable to CentOS, not '{}'.".format(grains["os"]))

    managed_sls_contents = """
    {% if grains['osmajorrelease'] == 8 %}
    epel-salttest:
      pkgrepo.managed:
        - humanname: Extra Packages for Enterprise Linux 8 - $basearch (salttest)
        - comments:
          - '#baseurl=http://download.fedoraproject.org/pub/epel/8/$basearch'
        - mirrorlist: https://mirrors.fedoraproject.org/metalink?repo=epel-8&arch=$basearch
        - failovermethod: priority
        - enabled: 1
        - gpgcheck: 1
        - gpgkey: file:///etc/pki/rpm-gpg/RPM-GPG-KEY-EPEL-8-salttest
        - require:
          - file: /etc/pki/rpm-gpg/RPM-GPG-KEY-EPEL-8-salttest

    /etc/pki/rpm-gpg/RPM-GPG-KEY-EPEL-8-salttest:
      file.managed:
        - source: salt://pkgrepo/files/RPM-GPG-KEY-EPEL-8-salttest
        - user: root
        - group: root
        - mode: 644
    {% elif grains['osmajorrelease'] == 7 %}
    epel-salttest:
      pkgrepo.managed:
        - humanname: Extra Packages for Enterprise Linux 7 - $basearch (salttest)
        - comments:
          - '#baseurl=http://download.fedoraproject.org/pub/epel/7/$basearch'
        - mirrorlist: https://mirrors.fedoraproject.org/metalink?repo=epel-7&arch=$basearch
        - failovermethod: priority
        - enabled: 1
        - gpgcheck: 1
        - gpgkey: file:///etc/pki/rpm-gpg/RPM-GPG-KEY-EPEL-7-salttest
        - require:
          - file: /etc/pki/rpm-gpg/RPM-GPG-KEY-EPEL-7-salttest

    /etc/pki/rpm-gpg/RPM-GPG-KEY-EPEL-7-salttest:
      file.managed:
        - source: salt://pkgrepo/files/RPM-GPG-KEY-EPEL-7-salttest
        - user: root
        - group: root
        - mode: 644
    {% endif %}
    """
    absend_sls_contents = """
    epel-salttest:
      pkgrepo:
        - absent
    """
    centos_7_gpg_key = pytest.helpers.temp_file(
        "pkgrepo/files/RPM-GPG-KEY-EPEL-7-salttest",
        RPM_GPG_KEY_EPEL_7_SALTTEST,
        state_tree,
    )
    centos_8_gpg_key = pytest.helpers.temp_file(
        "pkgrepo/files/RPM-GPG-KEY-EPEL-8-salttest",
        RPM_GPG_KEY_EPEL_8_SALTTEST,
        state_tree,
    )
    managed_state_file = pytest.helpers.temp_file(
        "pkgrepo/managed.sls", managed_sls_contents, state_tree
    )
    absent_state_file = pytest.helpers.temp_file(
        "pkgrepo/absent.sls", absend_sls_contents, state_tree
    )

    try:
        with centos_7_gpg_key, centos_8_gpg_key, managed_state_file, absent_state_file:
            yield
    finally:
        pass


@pytest.mark.requires_salt_states("pkgrepo.managed", "pkgrepo.absent")
def test_pkgrepo_managed_absent(grains, modules, subtests, centos_state_tree):
    """
    Test adding/removing a repo
    """
    add_repo_test_passed = False

    with subtests.test("Add Repo"):
        ret = modules.state.sls("pkgrepo.managed")
        assert ret.failed is False
        for state in ret:
            assert state.result is True
        add_repo_test_passed = True

    with subtests.test("Remove Repo"):
        if add_repo_test_passed is False:
            pytest.skip("Adding the repo failed. Skipping.")
        ret = modules.state.sls("pkgrepo.absent")
        assert ret.failed is False
        for state in ret:
            assert state.result is True


@pytest.fixture
def pkgrepo_with_comments_name(pkgrepo):
    pkgrepo_name = "examplerepo"
    try:
        yield pkgrepo_name
    finally:
        try:
            pkgrepo.absent(pkgrepo_name)
        except Exception:  # pylint: disable=broad-except
            pass


def test_pkgrepo_with_comments(pkgrepo, pkgrepo_with_comments_name, subtests):
    """
    Test adding a repo with comments
    """
    kwargs = {
        "name": pkgrepo_with_comments_name,
        "baseurl": "http://example.com/repo",
        "enabled": False,
        "comments": ["This is a comment"],
    }

    with subtests.test("Add repo"):
        # Run the state to add the repo
        ret = pkgrepo.managed(**kwargs.copy())
        assert ret.result is True

    with subtests.test("Modify comments"):
        # Run again with modified comments
        kwargs["comments"].append("This is another comment")
        ret = pkgrepo.managed(**kwargs.copy())
        assert ret.result is True
        assert ret.changes == {
            "comments": {
                "old": ["This is a comment"],
                "new": ["This is a comment", "This is another comment"],
            }
        }

    with subtests.test("Repeat last call"):
        # Run a third time, no changes should be made
        ret = pkgrepo.managed(**kwargs.copy())
        assert ret.result is True
        assert not ret.changes
        assert ret.comment == "Package repo '{}' already configured".format(
            pkgrepo_with_comments_name
        )


@pytest.fixture
def copr_pkgrepo_with_comments_name(pkgrepo, grains):
    if (
        grains["osfinger"] in ("CentOS Linux-7", "Amazon Linux-2")
        or grains["os"] == "VMware Photon OS"
    ):
        pytest.skip("copr plugin not installed on {} CI".format(grains["osfinger"]))
    if (
        grains["os"] in ("CentOS Stream", "AlmaLinux", "Rocky")
        and grains["osmajorrelease"] == 9
        or grains["osfinger"] == "Amazon Linux-2023"
    ):
        pytest.skip("No repo for {} in test COPR yet".format(grains["osfinger"]))
    pkgrepo_name = "hello-copr"
    try:
        yield pkgrepo_name
    finally:
        try:
            pkgrepo.absent(copr="mymindstorm/hello")
        except Exception:  # pylint: disable=broad-except
            pass


def test_copr_pkgrepo_with_comments(pkgrepo, copr_pkgrepo_with_comments_name, subtests):
    """
    Test adding a repo with comments
    """
    kwargs = {
        "name": copr_pkgrepo_with_comments_name,
        "copr": "mymindstorm/hello",
        "enabled": False,
        "comments": ["This is a comment"],
    }

    with subtests.test("Add repo"):
        # Run the state to add the repo
        ret = pkgrepo.managed(**kwargs.copy())
        assert ret.result is True

    with subtests.test("Modify comments"):
        # Run again with modified comments
        kwargs["comments"].append("This is another comment")
        ret = pkgrepo.managed(**kwargs.copy())
        assert ret.result is True
        assert ret.changes == {
            "comments": {
                "old": ["This is a comment"],
                "new": ["This is a comment", "This is another comment"],
            }
        }

    with subtests.test("Repeat last call"):
        # Run a third time, no changes should be made
        ret = pkgrepo.managed(**kwargs.copy())
        assert ret.result is True
        assert not ret.changes
        assert ret.comment == "Package repo '{}' already configured".format(
            copr_pkgrepo_with_comments_name
        )
