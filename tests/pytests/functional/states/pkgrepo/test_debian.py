import glob
import logging
import os
import pathlib
import shutil
import sys

import _pytest._version
import attr
import pytest
import salt.utils.files
from tests.conftest import CODE_DIR

try:
    from sysconfig import get_python_lib  # pylint: disable=no-name-in-module
except ImportError:
    from distutils.sysconfig import get_python_lib

PYTEST_GE_7 = getattr(_pytest._version, "version_tuple", (-1, -1)) >= (7, 0)


log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.destructive_test,
    pytest.mark.skip_if_not_root,
]


@pytest.fixture
def pkgrepo(states, grains):
    if grains["os_family"] != "Debian":
        exc_kwargs = {}
        if PYTEST_GE_7:
            exc_kwargs["_use_item_location"] = True
        raise pytest.skip.Exception(
            "Test only for debian based platforms", **exc_kwargs
        )
    return states.pkgrepo


@pytest.mark.requires_salt_states("pkgrepo.managed")
def test_adding_repo_file(pkgrepo, tmp_path):
    """
    test adding a repo file using pkgrepo.managed
    """
    repo_file = str(tmp_path / "stable-binary.list")
    repo_content = "deb http://www.deb-multimedia.org stable main"
    ret = pkgrepo.managed(name=repo_content, file=repo_file, clean_file=True)
    with salt.utils.files.fopen(repo_file, "r") as fp:
        file_content = fp.read()
    assert file_content.strip() == repo_content


@pytest.mark.requires_salt_states("pkgrepo.managed")
def test_adding_repo_file_arch(pkgrepo, tmp_path, subtests):
    """
    test adding a repo file using pkgrepo.managed
    and setting architecture
    """
    repo_file = str(tmp_path / "stable-binary.list")
    repo_content = "deb [arch=amd64  ] http://www.deb-multimedia.org stable main"
    pkgrepo.managed(name=repo_content, file=repo_file, clean_file=True)
    with salt.utils.files.fopen(repo_file, "r") as fp:
        file_content = fp.read()
        assert (
            file_content.strip()
            == "deb [arch=amd64] http://www.deb-multimedia.org stable main"
        )
    with subtests.test("With multiple archs"):
        repo_content = (
            "deb [arch=amd64,i386  ] http://www.deb-multimedia.org stable main"
        )
        pkgrepo.managed(name=repo_content, file=repo_file, clean_file=True)
        with salt.utils.files.fopen(repo_file, "r") as fp:
            file_content = fp.read()
            assert (
                file_content.strip()
                == "deb [arch=amd64,i386] http://www.deb-multimedia.org stable main"
            )


@pytest.mark.requires_salt_states("pkgrepo.managed")
def test_adding_repo_file_cdrom(pkgrepo, tmp_path):
    """
    test adding a repo file using pkgrepo.managed
    The issue is that CDROM installs often have [] in the line, and we
    should still add the repo even though it's not setting arch(for example)
    """
    repo_file = str(tmp_path / "cdrom.list")
    repo_content = "deb cdrom:[Debian GNU/Linux 11.4.0 _Bullseye_ - Official amd64 NETINST 20220709-10:31]/ stable main"
    pkgrepo.managed(name=repo_content, file=repo_file, clean_file=True)
    with salt.utils.files.fopen(repo_file, "r") as fp:
        file_content = fp.read()
        assert (
            file_content.strip()
            == "deb cdrom:[Debian GNU/Linux 11.4.0 _Bullseye_ - Official amd64 NETINST 20220709-10:31]/ stable main"
        )


def system_aptsources_ids(value):
    return "{}(aptsources.sourceslist)".format(value.title())


@pytest.fixture(
    params=("with", "without"), ids=system_aptsources_ids, scope="module", autouse=True
)
def system_aptsources(request, grains):
    sys_modules = list(sys.modules)
    copied_paths = []
    exc_kwargs = {}
    if PYTEST_GE_7:
        exc_kwargs["_use_item_location"] = True
    if grains["os_family"] != "Debian":
        raise pytest.skip.Exception(
            "Test only for debian based platforms", **exc_kwargs
        )
    try:
        try:
            from aptsources import sourceslist  # pylint: disable=unused-import

            if request.param == "without":
                raise pytest.skip.Exception(
                    "This test is meant to run without the system aptsources package, but it's "
                    "available from '{}'.".format(sourceslist.__file__),
                    **exc_kwargs
                )
            else:
                # Run the test
                yield request.param
        except ImportError:
            if request.param == "without":
                # Run the test
                yield
            else:
                copied_paths = []
                py_version_keys = [
                    "{}".format(*sys.version_info),
                    "{}.{}".format(*sys.version_info),
                ]
                session_site_packages_dir = get_python_lib()
                session_site_packages_dir = os.path.relpath(
                    session_site_packages_dir, str(CODE_DIR)
                )
                for py_version in py_version_keys:
                    dist_packages_path = "/usr/lib/python{}/dist-packages".format(
                        py_version
                    )
                    if not os.path.isdir(dist_packages_path):
                        continue
                    for aptpkg in glob.glob(os.path.join(dist_packages_path, "*apt*")):
                        src = os.path.realpath(aptpkg)
                        dst = os.path.join(
                            session_site_packages_dir, os.path.basename(src)
                        )
                        if os.path.exists(dst):
                            log.info(
                                "Not overwritting already existing %s with %s", dst, src
                            )
                            continue
                        log.info("Copying %s into %s", src, dst)
                        copied_paths.append(dst)
                        if os.path.isdir(src):
                            shutil.copytree(src, dst)
                        else:
                            shutil.copyfile(src, dst)
                if not copied_paths:
                    raise pytest.skip.Exception(
                        "aptsources.sourceslist python module not found", **exc_kwargs
                    )
                # Run the test
                yield request.param
    finally:
        for path in copied_paths:
            log.info("Deleting %r", path)
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
            else:
                os.unlink(path)
        for name in list(sys.modules):
            if name in sys_modules:
                continue
            if "apt" not in name:
                continue
            log.debug("Removing '%s' from 'sys.modules'", name)
            sys.modules.pop(name)


@pytest.fixture
def ubuntu_state_tree(system_aptsources, state_tree, grains):
    if grains["os"] != "Ubuntu":
        pytest.skip(
            "Test only applicable to Ubuntu, not '{}'".format(grains["osfinger"])
        )
    managed_sls_contents = """
    {% set codename = grains['oscodename'] %}
    {% set ubuntu_repos = [] %}
    {% set beta = grains['oscodename'] in ['xenial', 'bionic', 'eoan', 'focal', 'groovy'] %}
    {% set backports = grains['oscodename'] in ['xenial', 'bionic', 'eoan', 'focal'] %}

    {%- if beta %}{%- do ubuntu_repos.append('firefox-beta') %}
    firefox-beta:
      pkgrepo.managed:
        - name: deb http://ppa.launchpad.net/mozillateam/firefox-next/ubuntu {{ codename }} main
        - dist: {{ codename }}
        - file: /etc/apt/sources.list.d/firefox-beta.list
        - keyid: CE49EC21
        - keyserver: keyserver.ubuntu.com
    {%- endif %}

    {%- if backports %}{%- do ubuntu_repos.append('kubuntu-ppa') %}
    kubuntu-ppa:
      pkgrepo.managed:
        - ppa: kubuntu-ppa/backports
    {%- endif %}

    pkgrepo-deps:
      pkg.installed:
        - pkgs:
          - python3-apt
          - software-properties-common
    {%- for repo in ubuntu_repos -%}
    {% if loop.first %}
        - require_in:{%- endif %}
          - pkgrepo: {{ repo }}
    {%- endfor %}
    """
    absent_sls_contents = """
    firefox-beta:
      pkgrepo.absent:
        - name: deb http://ppa.launchpad.net/mozillateam/firefox-next/ubuntu {{ grains['oscodename'] }} main

    kubuntu-ppa:
      pkgrepo.absent:
        - ppa: kubuntu-ppa/backports
    """
    managed_state_file = pytest.helpers.temp_file(
        "pkgrepo/managed.sls", managed_sls_contents, state_tree
    )
    absent_state_file = pytest.helpers.temp_file(
        "pkgrepo/absent.sls", absent_sls_contents, state_tree
    )
    try:
        with managed_state_file, absent_state_file:
            yield
    finally:
        for pathstr in ("/etc/apt/sources.list.d/firefox-beta.list",):
            path = pathlib.Path(pathstr)
            if path.exists():
                path.unlink()


@pytest.mark.requires_salt_states("pkgrepo.managed", "pkgrepo.absent")
def test_pkgrepo_managed_absent(modules, ubuntu_state_tree, subtests):
    """
    Test adding a repo with the system aptsources package
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
def multiple_comps_repo_file_caconical(grains):
    if grains["os"] != "Ubuntu":
        pytest.skip(
            "Test only applicable to Ubuntu, not '{}'".format(grains["osfinger"])
        )
    repo_file_path = "/etc/apt/sources.list.d/99-salt-canonical-ubuntu.list"
    try:
        yield repo_file_path
    finally:
        try:
            os.unlink(repo_file_path)
        except OSError:
            pass


@pytest.fixture
def multiple_comps_repo_file_backports(grains):
    if grains["os"] != "Ubuntu":
        pytest.skip(
            "Test only applicable to Ubuntu, not '{}'".format(grains["osfinger"])
        )
    repo_file_path = (
        "/etc/apt/sources.list.d/99-salt-archive-ubuntu-focal-backports.list"
    )
    try:
        yield repo_file_path
    finally:
        try:
            os.unlink(repo_file_path)
        except OSError:
            pass


@pytest.fixture
def multiple_comps_state_tree(
    multiple_comps_repo_file_caconical, multiple_comps_repo_file_backports, state_tree
):
    sls_contents = """
    ubuntu-backports:
      pkgrepo.managed:
        - name: 'deb http://fi.archive.ubuntu.com/ubuntu focal-backports'
        - comps: main, restricted, universe, multiverse
        - refresh: false
        - disabled: false
        - clean_file: true
        - file: {}
        - require_in:
          - pkgrepo: canonical-ubuntu

    canonical-ubuntu:
      pkgrepo.managed:
        - name: 'deb http://archive.canonical.com/ubuntu {{{{ salt['grains.get']('oscodename') }}}}'
        - comps: partner
        - refresh: false
        - disabled: false
        - clean_file: true
        - file: {}
    """.format(
        multiple_comps_repo_file_backports,
        multiple_comps_repo_file_caconical,
    )
    with pytest.helpers.temp_file("multiple-comps-repos.sls", sls_contents, state_tree):
        yield


def test_managed_multiple_comps(modules, multiple_comps_state_tree):
    # On the first run, we must have changes
    ret = modules.state.sls("multiple-comps-repos")
    assert ret.failed is False
    for state in ret:
        assert state.result is True
        assert state.changes

    # On the second run though, we shouldn't have changes made
    ret = modules.state.sls("multiple-comps-repos")
    assert ret.failed is False
    for state in ret:
        assert state.result is True
        assert not state.changes


@pytest.fixture
def sources_list_file():
    fn_ = salt.utils.files.mkstemp(dir="/etc/apt/sources.list.d", suffix=".list")
    try:
        yield fn_
    finally:
        try:
            os.remove(fn_)
        except OSError:
            pass


def test_pkgrepo_with_architectures(pkgrepo, grains, sources_list_file, subtests):
    """
    Test managing a repo with architectures specified
    """
    name = "deb {{arch}}http://foo.com/bar/latest {oscodename} main".format(
        oscodename=grains["oscodename"]
    )

    def _get_arch(arch):
        return "[arch={}] ".format(arch) if arch else ""

    def _run(arch=None, test=False):
        return pkgrepo.managed(
            name=name.format(arch=_get_arch(arch)),
            file=sources_list_file,
            refresh=False,
            test=test,
        )

    with subtests.test("test=True"):
        # Run with test=True
        ret = _run(test=True)
        assert ret.changes == {"repo": name.format(arch="")}
        assert "would be" in ret.comment
        assert ret.result is None

    with subtests.test("test=False"):
        # Run for real
        ret = _run()
        assert ret.changes == {"repo": name.format(arch="")}
        assert ret.comment.startswith("Configured")
        assert ret.result is True

    with subtests.test("test=True repeat"):
        # Run again with test=True, should exit with no changes and a True
        # result.
        ret = _run(test=True)
        assert not ret.changes
        assert "already" in ret.comment
        assert ret.result is True

    with subtests.test("test=False repeat"):
        # Run for real again, results should be the same as above (i.e. we
        # should never get to the point where we exit with a None result).
        ret = _run()
        assert not ret.changes
        assert "already" in ret.comment
        assert ret.result is True

    expected_changes = {
        "line": {
            "new": name.format(arch=_get_arch("amd64")),
            "old": name.format(arch=""),
        },
        "architectures": {"new": ["amd64"], "old": []},
    }
    with subtests.test("test=True arch=amd64"):
        # Run with test=True and the architecture set. We should get a None
        # result with some expected changes.
        ret = _run(arch="amd64", test=True)
        assert ret.changes == expected_changes
        assert "would be" in ret.comment
        assert ret.result is None

    with subtests.test("test=False arch=amd64"):
        # Run for real, with the architecture set. We should get a True
        # result with the same changes.
        ret = _run(arch="amd64")
        assert ret.changes == expected_changes
        assert ret.comment.startswith("Configured")
        assert ret.result is True

    with subtests.test("test=True arch=amd64 repeat"):
        # Run again with test=True, should exit with no changes and a True
        # result.
        ret = _run(arch="amd64", test=True)
        assert not ret.changes
        assert "already" in ret.comment
        assert ret.result is True

    with subtests.test("test=False arch=amd64 repeat"):
        # Run for real again, results should be the same as above (i.e. we
        # should never get to the point where we exit with a None result).
        ret = _run(arch="amd64")
        assert not ret.changes
        assert "already" in ret.comment
        assert ret.result is True

    expected_changes = {
        "line": {
            "new": name.format(arch=""),
            "old": name.format(arch=_get_arch("amd64")),
        },
        "architectures": {"new": [], "old": ["amd64"]},
    }

    with subtests.test("test=True arch=None"):
        # Run with test=True and the architecture set back to the original
        # value. We should get a None result with some expected changes.
        ret = _run(test=True)
        assert ret.changes == expected_changes
        assert "would be" in ret.comment
        assert ret.result is None

    with subtests.test("test=False arch=None"):
        # Run for real, with the architecture set. We should get a True
        # result with the same changes.
        ret = _run()
        assert ret.changes == expected_changes
        assert ret.comment.startswith("Configured")
        assert ret.result is True

    with subtests.test("test=True arch=None repeat"):
        # Run again with test=True, should exit with no changes and a True
        # result.
        ret = _run(test=True)
        assert not ret.changes
        assert "already" in ret.comment
        assert ret.result is True

    with subtests.test("test=False arch=None repeat"):
        # Run for real again, results should be the same as above (i.e. we
        # should never get to the point where we exit with a None result).
        ret = _run()
        assert not ret.changes
        assert "already" in ret.comment
        assert ret.result is True


@pytest.fixture
def trailing_slash_repo_file(grains):
    if grains["os_family"] != "Debian":
        pytest.skip(
            "Test only applicable to Debian flavors, not '{}'".format(
                grains["osfinger"]
            )
        )
    repo_file_path = "/etc/apt/sources.list.d/trailing-slash.list"
    try:
        yield repo_file_path
    finally:
        try:
            os.unlink(repo_file_path)
        except OSError:
            pass


@pytest.mark.requires_salt_states("pkgrepo.managed", "pkgrepo.absent")
def test_repo_present_absent_trailing_slash_uri(pkgrepo, trailing_slash_repo_file):
    """
    test adding a repo with a trailing slash in the uri
    """
    # with the trailing slash
    repo_content = "deb http://www.deb-multimedia.org/ stable main"
    # initial creation
    ret = pkgrepo.managed(
        name=repo_content, file=trailing_slash_repo_file, refresh=False, clean_file=True
    )
    with salt.utils.files.fopen(trailing_slash_repo_file, "r") as fp:
        file_content = fp.read()
    assert file_content.strip() == "deb http://www.deb-multimedia.org/ stable main"
    assert ret.changes
    # no changes
    ret = pkgrepo.managed(
        name=repo_content, file=trailing_slash_repo_file, refresh=False
    )
    assert not ret.changes
    # absent
    ret = pkgrepo.absent(name=repo_content)
    assert ret.result


@pytest.mark.requires_salt_states("pkgrepo.managed", "pkgrepo.absent")
def test_repo_present_absent_no_trailing_slash_uri(pkgrepo, trailing_slash_repo_file):
    """
    test adding a repo with a trailing slash in the uri
    """
    # without the trailing slash
    repo_content = "deb http://www.deb-multimedia.org stable main"
    # initial creation
    ret = pkgrepo.managed(
        name=repo_content, file=trailing_slash_repo_file, refresh=False, clean_file=True
    )
    with salt.utils.files.fopen(trailing_slash_repo_file, "r") as fp:
        file_content = fp.read()
    assert file_content.strip() == "deb http://www.deb-multimedia.org stable main"
    assert ret.changes
    # no changes
    ret = pkgrepo.managed(
        name=repo_content, file=trailing_slash_repo_file, refresh=False
    )
    assert not ret.changes
    # absent
    ret = pkgrepo.absent(name=repo_content)
    assert ret.result


@pytest.mark.requires_salt_states("pkgrepo.managed", "pkgrepo.absent")
def test_repo_present_absent_no_trailing_slash_uri_add_slash(
    pkgrepo, trailing_slash_repo_file
):
    """
    test adding a repo without a trailing slash, and then running it
    again with a trailing slash.
    """
    # without the trailing slash
    repo_content = "deb http://www.deb-multimedia.org stable main"
    # initial creation
    ret = pkgrepo.managed(
        name=repo_content, file=trailing_slash_repo_file, refresh=False, clean_file=True
    )
    with salt.utils.files.fopen(trailing_slash_repo_file, "r") as fp:
        file_content = fp.read()
    assert file_content.strip() == "deb http://www.deb-multimedia.org stable main"
    assert ret.changes
    # now add a trailing slash in the name
    repo_content = "deb http://www.deb-multimedia.org/ stable main"
    ret = pkgrepo.managed(
        name=repo_content, file=trailing_slash_repo_file, refresh=False
    )
    with salt.utils.files.fopen(trailing_slash_repo_file, "r") as fp:
        file_content = fp.read()
    assert file_content.strip() == "deb http://www.deb-multimedia.org/ stable main"
    # absent
    ret = pkgrepo.absent(name=repo_content)
    assert ret.result


@attr.s(kw_only=True)
class Repo:
    key_root = attr.ib(default=pathlib.Path("/usr", "share", "keyrings"))
    signedby = attr.ib(default=False)
    grains = attr.ib()
    fullname = attr.ib()
    alt_repo = attr.ib(init=False)
    key_file = attr.ib()
    sources_list_file = attr.ib()
    repo_file = attr.ib()
    repo_content = attr.ib()
    key_url = attr.ib()

    @fullname.default
    def _default_fullname(self):
        return self.grains["osfullname"].lower().split()[0]

    @alt_repo.default
    def _default_alt_repo(self):
        """
        Use an alternative repo, packages do not
        exist for the OS on repo.saltproject.io
        """
        if (
            self.grains["osfullname"] == "Ubuntu"
            and self.grains["lsb_distrib_release"] == "22.04"
        ):
            return True
        return False

    @key_file.default
    def _default_key_file(self):
        key_file = self.key_root / "salt-archive-keyring.gpg"
        if self.alt_repo:
            key_file = self.key_root / "elasticsearch-keyring.gpg"
        key_file.parent.mkdir(exist_ok=True)
        assert not key_file.is_file()
        return key_file

    @repo_file.default
    def _default_repo_file(self):
        return self.sources_list_file

    @repo_content.default
    def _default_repo_content(self):
        if self.alt_repo:
            opts = " "
            if self.signedby:
                opts = " [signed-by=/usr/share/keyrings/elasticsearch-keyring.gpg] "
            repo_content = (
                "deb{}https://artifacts.elastic.co/packages/8.x/apt stable main".format(
                    opts
                )
            )
        else:
            opts = "[arch={arch}]".format(arch=self.grains["osarch"])
            if self.signedby:
                opts = "[arch={arch} signed-by=/usr/share/keyrings/salt-archive-keyring.gpg]".format(
                    arch=self.grains["osarch"]
                )
            repo_content = "deb {opts} https://repo.saltproject.io/py3/{}/{}/{arch}/latest {} main".format(
                self.fullname,
                self.grains["lsb_distrib_release"],
                self.grains["oscodename"],
                arch=self.grains["osarch"],
                opts=opts,
            )
        return repo_content

    @key_url.default
    def _default_key_url(self):
        key_url = "https://repo.saltproject.io/py3/{}/{}/{}/latest/salt-archive-keyring.gpg".format(
            self.fullname, self.grains["lsb_distrib_release"], self.grains["osarch"]
        )

        if self.alt_repo:
            key_url = "https://artifacts.elastic.co/GPG-KEY-elasticsearch"
        return key_url


@pytest.fixture
def repo(request, grains, sources_list_file):
    signedby = False
    if "signedby" in request.node.name:
        signedby = True
    repo = Repo(grains=grains, sources_list_file=sources_list_file, signedby=signedby)
    yield repo
    for key in [repo.key_file, repo.key_file.parent / "salt-alt-key.gpg"]:
        if key.is_file():
            key.unlink()


def test_adding_repo_file_signedby(pkgrepo, states, repo, subtests):
    """
    Test adding a repo file using pkgrepo.managed
    and setting signedby
    """

    def _run(test=False):
        return states.pkgrepo.managed(
            name=repo.repo_content,
            file=str(repo.repo_file),
            clean_file=True,
            signedby=str(repo.key_file),
            key_url=repo.key_url,
            aptkey=False,
            test=test,
        )

    ret = _run()
    with salt.utils.files.fopen(str(repo.repo_file), "r") as fp:
        file_content = fp.read()
        assert file_content.strip() == repo.repo_content
    assert repo.key_file.is_file()
    assert repo.repo_content in ret.comment
    with subtests.test("test=True"):
        ret = _run(test=True)
        assert ret.changes == {}


def test_adding_repo_file_signedby_keyserver(pkgrepo, states, repo):
    """
    Test adding a repo file using pkgrepo.managed
    and setting signedby with a keyserver
    """
    ret = states.pkgrepo.managed(
        name=repo.repo_content,
        file=str(repo.repo_file),
        clean_file=True,
        signedby=str(repo.key_file),
        keyserver="keyserver.ubuntu.com",
        keyid="0E08A149DE57BFBE",
        aptkey=False,
    )
    with salt.utils.files.fopen(str(repo.repo_file), "r") as fp:
        file_content = fp.read()
        assert file_content.strip() == repo.repo_content
    assert repo.key_file.is_file()


def test_adding_repo_file_keyserver_key_url(pkgrepo, states, repo):
    """
    Test adding a repo file using pkgrepo.managed
    and a key_url.
    """
    ret = states.pkgrepo.managed(
        name=repo.repo_content,
        file=str(repo.repo_file),
        clean_file=True,
        keyserver="keyserver.ubuntu.com",
        key_url=repo.key_url,
    )
    with salt.utils.files.fopen(str(repo.repo_file), "r") as fp:
        file_content = fp.read()
        assert file_content.strip() == repo.repo_content


def test_adding_repo_file_signedby_alt_file(pkgrepo, states, repo):
    """
    Test adding a repo file using pkgrepo.managed
    and setting signedby and then running again with
    different key path.
    """
    ret = states.pkgrepo.managed(
        name=repo.repo_content,
        file=str(repo.repo_file),
        clean_file=True,
        key_url=repo.key_url,
        aptkey=False,
    )
    with salt.utils.files.fopen(str(repo.repo_file), "r") as fp:
        file_content = fp.read()
        assert file_content.strip() == repo.repo_content
    assert repo.key_file.is_file()
    assert repo.repo_content in ret.comment

    key_file = repo.key_file.parent / "salt-alt-key.gpg"
    repo_content = "deb [arch=amd64 signed-by={}] https://repo.saltproject.io/py3/debian/10/amd64/latest buster main".format(
        str(key_file)
    )
    ret = states.pkgrepo.managed(
        name=repo_content,
        file=str(repo.repo_file),
        clean_file=True,
        key_url=repo.key_url,
        aptkey=False,
    )
    with salt.utils.files.fopen(str(repo.repo_file), "r") as fp:
        file_content = fp.read()
        assert file_content.strip() == repo_content
        assert file_content.endswith("\n")
    assert key_file.is_file()
    assert repo_content in ret.comment
