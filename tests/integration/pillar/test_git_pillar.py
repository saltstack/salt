"""
Integration tests for git_pillar

The base classes for all of these tests are in tests/support/gitfs.py.
Repositories for the tests are generated on the fly (look for the "make_repo"
function).

Where possible, a test case in this module should be reproduced in the
following ways:

1. GitPython over SSH (TestGitPythonSSH)
2. GitPython over HTTP (TestGitPythonHTTP)
3. GitPython over HTTP w/basic auth (TestGitPythonAuthenticatedHTTP)
4. pygit2 over SSH (TestPygit2SSH)
5. pygit2 over HTTP (TestPygit2HTTP)
6. pygit2 over HTTP w/basic auth (TestPygit2AuthenticatedHTTP)

For GitPython, this is easy, since it does not support the authentication
configuration parameters that pygit2 does. Therefore, this test module includes
a GitPythonMixin class which can be reused for all three GitPython test
classes. The only thing we vary for these tests is the URL that we use.

For pygit2 this is more complicated, since it supports A) both passphraseless
and passphrase-protected SSH keys, and B) both global and per-remote credential
parameters. So, for SSH tests we need to run each GitPython test case in 4
different ways to cover pygit2:

1. Passphraseless key, global credential options
2. Passphraseless key, per-repo credential options
3. Passphrase-protected key, global credential options
4. Passphrase-protected key, per-repo credential options

For HTTP tests, we need to run each GitPython test case in 2 different ways to
cover pygit2 with authentication:

1. Global credential options
2. Per-repo credential options

For unauthenticated HTTP, we can just run a single case just like for a
GitPython test function, with the only change being to the git_pillar_provider
config option.

The way we accomplish the extra test cases for pygit2 is not by writing more
test functions, but to keep the same test function names both in the GitPython
test classes and the pygit2 test classes, and just perform multiple pillar
compilations and asserts in each pygit2 test function.


For SSH tests, a system user is added and a temporary sshd instance is started
on a randomized port. The user and sshd server are torn down after the tests
are run.

For HTTP tests, nginx + uWSGI + git-http-backend handles serving the repo.
However, there was a change in git 2.4.4 which causes a fetch to hang when
using uWSGI.  This was worked around in uWSGI 2.0.13 by adding an additional
setting.  However, Ubuntu 16.04 LTS ships with uWSGI 2.0.12 in their official
repos, so to work around this we pip install a newer uWSGI (with CGI support
baked in) within a virtualenv the test suite creates, and then uses that uwsgi
binary to start the uWSGI daemon. More info on the git issue and the uWSGI
workaround can be found in the below two links:

https://github.com/git/git/commit/6bc0cb5
https://github.com/unbit/uwsgi/commit/ac1e354
"""

import random
import string

import pytest
import salt.utils.path
import salt.utils.platform
from salt.modules.virtualenv_mod import KNOWN_BINARY_NAMES as VIRTUALENV_NAMES
from salt.utils.gitfs import (
    GITPYTHON_MINVER,
    GITPYTHON_VERSION,
    LIBGIT2_MINVER,
    LIBGIT2_VERSION,
    PYGIT2_MINVER,
    PYGIT2_VERSION,
)
from tests.support.gitfs import (  # pylint: disable=unused-import
    PASSWORD,
    USERNAME,
    GitPillarHTTPTestBase,
    GitPillarSSHTestBase,
    ssh_pillar_tests_prep,
    webserver_pillar_tests_prep,
    webserver_pillar_tests_prep_authenticated,
)
from tests.support.helpers import destructiveTest, skip_if_not_root, slowTest
from tests.support.unit import skipIf

# Check for requisite components
try:
    HAS_GITPYTHON = GITPYTHON_VERSION >= GITPYTHON_MINVER
except Exception:  # pylint: disable=broad-except
    HAS_GITPYTHON = False

try:
    HAS_PYGIT2 = PYGIT2_VERSION >= PYGIT2_MINVER and LIBGIT2_VERSION >= LIBGIT2_MINVER
except Exception:  # pylint: disable=broad-except
    HAS_PYGIT2 = False

HAS_SSHD = bool(salt.utils.path.which("sshd"))
HAS_NGINX = bool(salt.utils.path.which("nginx"))
HAS_VIRTUALENV = bool(salt.utils.path.which_bin(VIRTUALENV_NAMES))


def _rand_key_name(length):
    return "id_rsa_{}".format(
        "".join(random.choice(string.ascii_letters) for _ in range(length))
    )


def _windows_or_mac():
    return salt.utils.platform.is_windows() or salt.utils.platform.is_darwin()


class GitPythonMixin:
    """
    GitPython doesn't support anything fancy in terms of authentication
    options, so all of the tests for GitPython can be re-used via this mixin.
    """

    @slowTest
    def test_single_source(self):
        """
        Test using a single ext_pillar repo
        """
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: gitpython
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}
            """
        )
        self.assertEqual(
            ret,
            {
                "branch": "master",
                "mylist": ["master"],
                "mydict": {
                    "master": True,
                    "nested_list": ["master"],
                    "nested_dict": {"master": True},
                },
            },
        )

    @slowTest
    def test_multiple_sources_master_dev_no_merge_lists(self):
        """
        Test using two ext_pillar dirs. Since all git_pillar repos are merged
        into a single dictionary, ordering matters.

        This tests with the master branch followed by dev, and with
        pillar_merge_lists disabled.
        """
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: gitpython
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: False
            ext_pillar:
              - git:
                - master {url}
                - dev {url}
            """
        )
        self.assertEqual(
            ret,
            {
                "branch": "dev",
                "mylist": ["dev"],
                "mydict": {
                    "master": True,
                    "dev": True,
                    "nested_list": ["dev"],
                    "nested_dict": {"master": True, "dev": True},
                },
            },
        )

    @slowTest
    def test_multiple_sources_dev_master_no_merge_lists(self):
        """
        Test using two ext_pillar dirs. Since all git_pillar repos are merged
        into a single dictionary, ordering matters.

        This tests with the dev branch followed by master, and with
        pillar_merge_lists disabled.
        """
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: gitpython
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: False
            ext_pillar:
              - git:
                - dev {url}
                - master {url}
            """
        )
        self.assertEqual(
            ret,
            {
                "branch": "master",
                "mylist": ["master"],
                "mydict": {
                    "master": True,
                    "dev": True,
                    "nested_list": ["master"],
                    "nested_dict": {"master": True, "dev": True},
                },
            },
        )

    @slowTest
    def test_multiple_sources_master_dev_merge_lists(self):
        """
        Test using two ext_pillar dirs. Since all git_pillar repos are merged
        into a single dictionary, ordering matters.

        This tests with the master branch followed by dev, and with
        pillar_merge_lists enabled.
        """
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: gitpython
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: True
            ext_pillar:
              - git:
                - master {url}
                - dev {url}
            """
        )
        self.assertEqual(
            ret,
            {
                "branch": "dev",
                "mylist": ["master", "dev"],
                "mydict": {
                    "master": True,
                    "dev": True,
                    "nested_list": ["master", "dev"],
                    "nested_dict": {"master": True, "dev": True},
                },
            },
        )

    @slowTest
    def test_multiple_sources_dev_master_merge_lists(self):
        """
        Test using two ext_pillar dirs. Since all git_pillar repos are merged
        into a single dictionary, ordering matters.

        This tests with the dev branch followed by master, and with
        pillar_merge_lists enabled.
        """
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: gitpython
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: True
            ext_pillar:
              - git:
                - dev {url}
                - master {url}
            """
        )
        self.assertEqual(
            ret,
            {
                "branch": "master",
                "mylist": ["dev", "master"],
                "mydict": {
                    "master": True,
                    "dev": True,
                    "nested_list": ["dev", "master"],
                    "nested_dict": {"master": True, "dev": True},
                },
            },
        )

    @slowTest
    def test_multiple_sources_with_pillarenv(self):
        """
        Test using pillarenv to restrict results to those from a single branch
        """
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: gitpython
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillarenv: base
            ext_pillar:
              - git:
                - master {url}
                - dev {url}
            """
        )
        self.assertEqual(
            ret,
            {
                "branch": "master",
                "mylist": ["master"],
                "mydict": {
                    "master": True,
                    "nested_list": ["master"],
                    "nested_dict": {"master": True},
                },
            },
        )

    @slowTest
    def test_includes_enabled(self):
        """
        Test with git_pillar_includes enabled. The top_only branch references
        an SLS file from the master branch, so we should see the key from that
        SLS file (included_pillar) in the compiled pillar data.
        """
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: gitpython
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}
                - top_only {url}:
                  - env: base
            """
        )
        self.assertEqual(
            ret,
            {
                "branch": "master",
                "mylist": ["master"],
                "mydict": {
                    "master": True,
                    "nested_list": ["master"],
                    "nested_dict": {"master": True},
                },
                "included_pillar": True,
            },
        )

    @slowTest
    def test_includes_disabled(self):
        """
        Test with git_pillar_includes enabled. The top_only branch references
        an SLS file from the master branch, but since includes are disabled it
        will not find the SLS file and the "included_pillar" key should not be
        present in the compiled pillar data. We should instead see an error
        message in the compiled data.
        """
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: gitpython
            git_pillar_includes: False
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}
                - top_only {url}:
                  - env: base
            """
        )
        self.assertEqual(
            ret,
            {
                "branch": "master",
                "mylist": ["master"],
                "mydict": {
                    "master": True,
                    "nested_list": ["master"],
                    "nested_dict": {"master": True},
                },
                "_errors": [
                    "Specified SLS 'bar' in environment 'base' is not "
                    "available on the salt master"
                ],
            },
        )

    @slowTest
    def test_includes_enabled_solves___env___with_mountpoint(self):
        """
        Test with git_pillar_includes enabled and using "__env__" as the branch
        name for the configured repositories.
        The "gitinfo" repository contains top.sls file with a local reference
        and also referencing external "nowhere.foo" which is provided by "webinfo"
        repository mounted as "nowhere".
        """
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: gitpython
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - __env__ {url_extra_repo}:
                  - name: gitinfo
                - __env__ {url}:
                  - name: webinfo
                  - mountpoint: nowhere
            """
        )
        self.assertEqual(
            ret,
            {
                "branch": "master",
                "motd": "The force will be with you. Always.",
                "mylist": ["master"],
                "mydict": {
                    "master": True,
                    "nested_list": ["master"],
                    "nested_dict": {"master": True},
                },
            },
        )

    @slowTest
    def test_root_parameter(self):
        """
        Test root parameter
        """
        expected = {"from_subdir": True}

        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: gitpython
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - root: subdir
                - top_only {url}:
                  - env: base
            """
        )
        self.assertEqual(ret, expected)

    @slowTest
    def test_mountpoint_parameter(self):
        """
        Test mountpoint parameter
        """
        expected = {"included_pillar": True}

        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: gitpython
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - mountpoint: mounted
                - top_mounted {url}:
                  - env: base
            """
        )
        self.assertEqual(ret, expected)

    @slowTest
    def test_root_and_mountpoint_parameters(self):
        """
        Test root and mountpoint parameters
        """
        expected = {"from_subdir": True}

        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: gitpython
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - mountpoint: mounted
                  - root: subdir
                - top_mounted {url}:
                  - env: base
            """
        )
        self.assertEqual(ret, expected)

    @slowTest
    def test_all_saltenvs(self):
        """
        Test all_saltenvs parameter.
        """
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: gitpython
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillarenv: dev
            ext_pillar:
              - git:
                - __env__ {url_extra_repo}:
                  - all_saltenvs: master
                - __env__ {url}:
                  - mountpoint: nowhere
            """
        )
        self.assertEqual(
            ret,
            {
                "branch": "dev",
                "motd": "The force will be with you. Always.",
                "mylist": ["dev"],
                "mydict": {
                    "dev": True,
                    "nested_list": ["dev"],
                    "nested_dict": {"dev": True},
                },
            },
        )

    @slowTest
    def test_all_saltenvs_base(self):
        """
        Test all_saltenvs parameter with base pillarenv.
        """
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: gitpython
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - __env__ {url_extra_repo}:
                  - all_saltenvs: master
                - __env__ {url}:
                  - mountpoint: nowhere
            """
        )
        self.assertEqual(
            ret,
            {
                "branch": "master",
                "motd": "The force will be with you. Always.",
                "mylist": ["master"],
                "mydict": {
                    "master": True,
                    "nested_list": ["master"],
                    "nested_dict": {"master": True},
                },
            },
        )

    @slowTest
    def test_fallback(self):
        """
        Test fallback parameter.
        """
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: gitpython
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillarenv: nonexisting
            ext_pillar:
              - git:
                - __env__ {url_extra_repo}:
                  - fallback: master
                - __env__ {url}:
                  - mountpoint: nowhere
                  - fallback: dev
            """
        )
        self.assertEqual(
            ret,
            {
                "branch": "dev",
                "motd": "The force will be with you. Always.",
                "mylist": ["dev"],
                "mydict": {
                    "dev": True,
                    "nested_list": ["dev"],
                    "nested_dict": {"dev": True},
                },
            },
        )


@destructiveTest
@skipIf(_windows_or_mac(), "minion is windows or mac")
@skip_if_not_root
@skipIf(not HAS_GITPYTHON, "GitPython >= {} required".format(GITPYTHON_MINVER))
@skipIf(not HAS_SSHD, "sshd not present")
@pytest.mark.usefixtures("ssh_pillar_tests_prep")
class TestGitPythonSSH(GitPillarSSHTestBase, GitPythonMixin):
    """
    Test git_pillar with GitPython using SSH authentication
    """

    id_rsa_nopass = _rand_key_name(8)
    id_rsa_withpass = _rand_key_name(8)
    username = USERNAME
    passphrase = PASSWORD


@skipIf(_windows_or_mac(), "minion is windows or mac")
@skip_if_not_root
@skipIf(not HAS_GITPYTHON, "GitPython >= {} required".format(GITPYTHON_MINVER))
@skipIf(not HAS_NGINX, "nginx not present")
@skipIf(not HAS_VIRTUALENV, "virtualenv not present")
@pytest.mark.usefixtures("webserver_pillar_tests_prep")
class TestGitPythonHTTP(GitPillarHTTPTestBase, GitPythonMixin):
    """
    Test git_pillar with GitPython using unauthenticated HTTP
    """


@skipIf(_windows_or_mac(), "minion is windows or mac")
@skip_if_not_root
@skipIf(not HAS_GITPYTHON, "GitPython >= {} required".format(GITPYTHON_MINVER))
@skipIf(not HAS_NGINX, "nginx not present")
@skipIf(not HAS_VIRTUALENV, "virtualenv not present")
@pytest.mark.usefixtures("webserver_pillar_tests_prep_authenticated")
class TestGitPythonAuthenticatedHTTP(TestGitPythonHTTP, GitPythonMixin):
    """
    Test git_pillar with GitPython using authenticated HTTP
    """

    username = USERNAME
    password = PASSWORD


@destructiveTest
@skipIf(_windows_or_mac(), "minion is windows or mac")
@skip_if_not_root
@skipIf(
    not HAS_PYGIT2,
    "pygit2 >= {} and libgit2 >= {} required".format(PYGIT2_MINVER, LIBGIT2_MINVER),
)
@skipIf(not HAS_SSHD, "sshd not present")
@pytest.mark.usefixtures("ssh_pillar_tests_prep")
class TestPygit2SSH(GitPillarSSHTestBase):
    """
    Test git_pillar with pygit2 using SSH authentication

    NOTE: Any tests added to this test class should have equivalent tests (if
    possible) in the TestGitPythonSSH class.
    """

    id_rsa_nopass = _rand_key_name(8)
    id_rsa_withpass = _rand_key_name(8)
    username = USERNAME
    passphrase = PASSWORD

    @slowTest
    def test_single_source(self):
        """
        Test using a single ext_pillar repo
        """
        expected = {
            "branch": "master",
            "mylist": ["master"],
            "mydict": {
                "master": True,
                "nested_list": ["master"],
                "nested_dict": {"master": True},
            },
        }

        # Test with passphraseless key and global credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_nopass}
            git_pillar_privkey: {privkey_nopass}
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphraseless key and per-repo credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphrase-protected key and global credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_withpass}
            git_pillar_privkey: {privkey_withpass}
            git_pillar_passphrase: {passphrase}
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphrase-protected key and per-repo credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
            """
        )
        self.assertEqual(ret, expected)

    @slowTest
    def test_multiple_sources_master_dev_no_merge_lists(self):
        """
        Test using two ext_pillar dirs. Since all git_pillar repos are merged
        into a single dictionary, ordering matters.

        This tests with the master branch followed by dev, and with
        pillar_merge_lists disabled.
        """
        expected = {
            "branch": "dev",
            "mylist": ["dev"],
            "mydict": {
                "master": True,
                "dev": True,
                "nested_list": ["dev"],
                "nested_dict": {"master": True, "dev": True},
            },
        }

        # Test with passphraseless key and global credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_nopass}
            git_pillar_privkey: {privkey_nopass}
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: False
            ext_pillar:
              - git:
                - master {url}
                - dev {url}
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphraseless key and per-repo credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: False
            ext_pillar:
              - git:
                - master {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                - dev {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphrase-protected key and global credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_withpass}
            git_pillar_privkey: {privkey_withpass}
            git_pillar_passphrase: {passphrase}
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: False
            ext_pillar:
              - git:
                - master {url}
                - dev {url}
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphrase-protected key and per-repo credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: False
            ext_pillar:
              - git:
                - master {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
                - dev {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
            """
        )
        self.assertEqual(ret, expected)

    @slowTest
    def test_multiple_sources_dev_master_no_merge_lists(self):
        """
        Test using two ext_pillar dirs. Since all git_pillar repos are merged
        into a single dictionary, ordering matters.

        This tests with the dev branch followed by master, and with
        pillar_merge_lists disabled.
        """
        expected = {
            "branch": "master",
            "mylist": ["master"],
            "mydict": {
                "master": True,
                "dev": True,
                "nested_list": ["master"],
                "nested_dict": {"master": True, "dev": True},
            },
        }

        # Test with passphraseless key and global credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_nopass}
            git_pillar_privkey: {privkey_nopass}
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: False
            ext_pillar:
              - git:
                - dev {url}
                - master {url}
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphraseless key and per-repo credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: False
            ext_pillar:
              - git:
                - dev {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                - master {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphrase-protected key and global credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_withpass}
            git_pillar_privkey: {privkey_withpass}
            git_pillar_passphrase: {passphrase}
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: False
            ext_pillar:
              - git:
                - dev {url}
                - master {url}
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphrase-protected key and per-repo credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: False
            ext_pillar:
              - git:
                - dev {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
                - master {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
            """
        )
        self.assertEqual(ret, expected)

    @slowTest
    def test_multiple_sources_master_dev_merge_lists(self):
        """
        Test using two ext_pillar dirs. Since all git_pillar repos are merged
        into a single dictionary, ordering matters.

        This tests with the master branch followed by dev, and with
        pillar_merge_lists enabled.
        """
        expected = {
            "branch": "dev",
            "mylist": ["master", "dev"],
            "mydict": {
                "master": True,
                "dev": True,
                "nested_list": ["master", "dev"],
                "nested_dict": {"master": True, "dev": True},
            },
        }

        # Test with passphraseless key and global credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_nopass}
            git_pillar_privkey: {privkey_nopass}
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: True
            ext_pillar:
              - git:
                - master {url}
                - dev {url}
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphraseless key and per-repo credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: True
            ext_pillar:
              - git:
                - master {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                - dev {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphrase-protected key and global credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_withpass}
            git_pillar_privkey: {privkey_withpass}
            git_pillar_passphrase: {passphrase}
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: True
            ext_pillar:
              - git:
                - master {url}
                - dev {url}
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphrase-protected key and per-repo credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: True
            ext_pillar:
              - git:
                - master {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
                - dev {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
            """
        )
        self.assertEqual(ret, expected)

    @slowTest
    def test_multiple_sources_dev_master_merge_lists(self):
        """
        Test using two ext_pillar dirs. Since all git_pillar repos are merged
        into a single dictionary, ordering matters.

        This tests with the dev branch followed by master, and with
        pillar_merge_lists enabled.
        """
        expected = {
            "branch": "master",
            "mylist": ["dev", "master"],
            "mydict": {
                "master": True,
                "dev": True,
                "nested_list": ["dev", "master"],
                "nested_dict": {"master": True, "dev": True},
            },
        }

        # Test with passphraseless key and global credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_nopass}
            git_pillar_privkey: {privkey_nopass}
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: True
            ext_pillar:
              - git:
                - dev {url}
                - master {url}
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphraseless key and per-repo credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: True
            ext_pillar:
              - git:
                - dev {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                - master {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphrase-protected key and global credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_withpass}
            git_pillar_privkey: {privkey_withpass}
            git_pillar_passphrase: {passphrase}
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: True
            ext_pillar:
              - git:
                - dev {url}
                - master {url}
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphrase-protected key and per-repo credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: True
            ext_pillar:
              - git:
                - dev {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
                - master {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
            """
        )
        self.assertEqual(ret, expected)

    @slowTest
    def test_multiple_sources_with_pillarenv(self):
        """
        Test using pillarenv to restrict results to those from a single branch
        """
        expected = {
            "branch": "master",
            "mylist": ["master"],
            "mydict": {
                "master": True,
                "nested_list": ["master"],
                "nested_dict": {"master": True},
            },
        }

        # Test with passphraseless key and global credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_nopass}
            git_pillar_privkey: {privkey_nopass}
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillarenv: base
            ext_pillar:
              - git:
                - master {url}
                - dev {url}
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphraseless key and per-repo credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillarenv: base
            ext_pillar:
              - git:
                - master {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                - dev {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphrase-protected key and global credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_withpass}
            git_pillar_privkey: {privkey_withpass}
            git_pillar_passphrase: {passphrase}
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillarenv: base
            ext_pillar:
              - git:
                - master {url}
                - dev {url}
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphrase-protected key and per-repo credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillarenv: base
            ext_pillar:
              - git:
                - master {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
                - dev {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                  - passphrase: {passphrase}
            """
        )
        self.assertEqual(ret, expected)

    @slowTest
    def test_includes_enabled(self):
        """
        Test with git_pillar_includes enabled. The top_only branch references
        an SLS file from the master branch, so we should see the
        "included_pillar" key from that SLS file in the compiled pillar data.
        """
        expected = {
            "branch": "master",
            "mylist": ["master"],
            "mydict": {
                "master": True,
                "nested_list": ["master"],
                "nested_dict": {"master": True},
            },
            "included_pillar": True,
        }

        # Test with passphraseless key and global credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_nopass}
            git_pillar_privkey: {privkey_nopass}
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}
                - top_only {url}:
                  - env: base
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphraseless key and per-repo credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                - top_only {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                  - env: base
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphrase-protected key and global credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_withpass}
            git_pillar_privkey: {privkey_withpass}
            git_pillar_passphrase: {passphrase}
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}
                - top_only {url}:
                  - env: base
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphrase-protected key and per-repo credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
                - top_only {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
                  - env: base
            """
        )
        self.assertEqual(ret, expected)

    @slowTest
    def test_includes_disabled(self):
        """
        Test with git_pillar_includes enabled. The top_only branch references
        an SLS file from the master branch, but since includes are disabled it
        will not find the SLS file and the "included_pillar" key should not be
        present in the compiled pillar data. We should instead see an error
        message in the compiled data.
        """
        expected = {
            "branch": "master",
            "mylist": ["master"],
            "mydict": {
                "master": True,
                "nested_list": ["master"],
                "nested_dict": {"master": True},
            },
            "_errors": [
                "Specified SLS 'bar' in environment 'base' is not "
                "available on the salt master"
            ],
        }

        # Test with passphraseless key and global credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_includes: False
            git_pillar_pubkey: {pubkey_nopass}
            git_pillar_privkey: {privkey_nopass}
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}
                - top_only {url}:
                  - env: base
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphraseless key and per-repo credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_includes: False
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                - top_only {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                  - env: base
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphrase-protected key and global credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_includes: False
            git_pillar_pubkey: {pubkey_withpass}
            git_pillar_privkey: {privkey_withpass}
            git_pillar_passphrase: {passphrase}
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}
                - top_only {url}:
                  - env: base
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphrase-protected key and per-repo credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_includes: False
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
                - top_only {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
                  - env: base
            """
        )
        self.assertEqual(ret, expected)

    @slowTest
    def test_includes_enabled_solves___env___with_mountpoint(self):
        """
        Test with git_pillar_includes enabled and using "__env__" as the branch
        name for the configured repositories.
        The "gitinfo" repository contains top.sls file with a local reference
        and also referencing external "nowhere.foo" which is provided by "webinfo"
        repository mounted as "nowhere".
        """
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_nopass}
            git_pillar_privkey: {privkey_nopass}
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - __env__ {url_extra_repo}:
                  - name: gitinfo
                - __env__ {url}:
                  - name: webinfo
                  - mountpoint: nowhere
            """
        )
        self.assertEqual(
            ret,
            {
                "branch": "master",
                "motd": "The force will be with you. Always.",
                "mylist": ["master"],
                "mydict": {
                    "master": True,
                    "nested_list": ["master"],
                    "nested_dict": {"master": True},
                },
            },
        )

    @slowTest
    def test_root_parameter(self):
        """
        Test root parameter
        """
        expected = {"from_subdir": True}

        # Test with passphraseless key and global credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_nopass}
            git_pillar_privkey: {privkey_nopass}
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - root: subdir
                - top_only {url}:
                  - env: base
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphraseless key and per-repo credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - root: subdir
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                - top_only {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                  - env: base
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphrase-protected key and global credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_withpass}
            git_pillar_privkey: {privkey_withpass}
            git_pillar_passphrase: {passphrase}
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - root: subdir
                - top_only {url}:
                  - env: base
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphrase-protected key and per-repo credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - root: subdir
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
                - top_only {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
                  - env: base
            """
        )
        self.assertEqual(ret, expected)

    @slowTest
    def test_mountpoint_parameter(self):
        """
        Test mountpoint parameter
        """
        expected = {"included_pillar": True}

        # Test with passphraseless key and global credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_nopass}
            git_pillar_privkey: {privkey_nopass}
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - mountpoint: mounted
                - top_mounted {url}:
                  - env: base
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphraseless key and per-repo credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - mountpoint: mounted
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                - top_mounted {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                  - env: base
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphrase-protected key and global credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_withpass}
            git_pillar_privkey: {privkey_withpass}
            git_pillar_passphrase: {passphrase}
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - mountpoint: mounted
                - top_mounted {url}:
                  - env: base
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphrase-protected key and per-repo credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - mountpoint: mounted
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
                - top_mounted {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
                  - env: base
            """
        )
        self.assertEqual(ret, expected)

    @slowTest
    def test_root_and_mountpoint_parameters(self):
        """
        Test root and mountpoint parameters
        """
        expected = {"from_subdir": True}

        # Test with passphraseless key and global credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_nopass}
            git_pillar_privkey: {privkey_nopass}
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - mountpoint: mounted
                  - root: subdir
                - top_mounted {url}:
                  - env: base
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphraseless key and per-repo credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - mountpoint: mounted
                  - root: subdir
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                - top_mounted {url}:
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                  - env: base
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphrase-protected key and global credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_withpass}
            git_pillar_privkey: {privkey_withpass}
            git_pillar_passphrase: {passphrase}
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - mountpoint: mounted
                  - root: subdir
                - top_mounted {url}:
                  - env: base
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphrase-protected key and per-repo credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - mountpoint: mounted
                  - root: subdir
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
                - top_mounted {url}:
                  - pubkey: {pubkey_withpass}
                  - privkey: {privkey_withpass}
                  - passphrase: {passphrase}
                  - env: base
            """
        )
        self.assertEqual(ret, expected)

    @slowTest
    def test_all_saltenvs(self):
        """
        Test all_saltenvs parameter.
        """
        expected = {
            "branch": "dev",
            "motd": "The force will be with you. Always.",
            "mylist": ["dev"],
            "mydict": {
                "dev": True,
                "nested_list": ["dev"],
                "nested_dict": {"dev": True},
            },
        }

        # Test with passphraseless key and global credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_nopass}
            git_pillar_privkey: {privkey_nopass}
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillarenv: dev
            ext_pillar:
              - git:
                - __env__ {url_extra_repo}:
                  - all_saltenvs: master
                - __env__ {url}:
                  - mountpoint: nowhere
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphraseless key and per-repo credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillarenv: dev
            ext_pillar:
              - git:
                - __env__ {url_extra_repo}:
                  - all_saltenvs: master
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                - __env__ {url}:
                  - mountpoint: nowhere
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphrase-protected key and global credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_withpass}
            git_pillar_privkey: {privkey_withpass}
            git_pillar_passphrase: {passphrase}
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillarenv: dev
            ext_pillar:
              - git:
                - __env__ {url_extra_repo}:
                  - all_saltenvs: master
                - __env__ {url}:
                  - mountpoint: nowhere
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphrase-protected key and per-repo credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillarenv: dev
            ext_pillar:
              - git:
                - __env__ {url_extra_repo}:
                  - all_saltenvs: master
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                  - passphrase: {passphrase}
                - __env__ {url}:
                  - mountpoint: nowhere
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                  - passphrase: {passphrase}
            """
        )
        self.assertEqual(ret, expected)

    @slowTest
    def test_all_saltenvs_base(self):
        """
        Test all_saltenvs parameter.
        """
        expected = {
            "branch": "master",
            "motd": "The force will be with you. Always.",
            "mylist": ["master"],
            "mydict": {
                "master": True,
                "nested_list": ["master"],
                "nested_dict": {"master": True},
            },
        }

        # Test with passphraseless key and global credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_nopass}
            git_pillar_privkey: {privkey_nopass}
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - __env__ {url_extra_repo}:
                  - all_saltenvs: master
                - __env__ {url}:
                  - mountpoint: nowhere
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphraseless key and per-repo credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - __env__ {url_extra_repo}:
                  - all_saltenvs: master
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                - __env__ {url}:
                  - mountpoint: nowhere
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphrase-protected key and global credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_withpass}
            git_pillar_privkey: {privkey_withpass}
            git_pillar_passphrase: {passphrase}
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - __env__ {url_extra_repo}:
                  - all_saltenvs: master
                - __env__ {url}:
                  - mountpoint: nowhere
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphrase-protected key and per-repo credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - __env__ {url_extra_repo}:
                  - all_saltenvs: master
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                  - passphrase: {passphrase}
                - __env__ {url}:
                  - mountpoint: nowhere
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                  - passphrase: {passphrase}
            """
        )
        self.assertEqual(ret, expected)

    @slowTest
    def test_fallback(self):
        """
        Test fallback parameter.
        """
        expected = {
            "branch": "dev",
            "motd": "The force will be with you. Always.",
            "mylist": ["dev"],
            "mydict": {
                "dev": True,
                "nested_list": ["dev"],
                "nested_dict": {"dev": True},
            },
        }

        # Test with passphraseless key and global credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_nopass}
            git_pillar_privkey: {privkey_nopass}
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillarenv: nonexisting
            ext_pillar:
              - git:
                - __env__ {url_extra_repo}:
                  - fallback: master
                - __env__ {url}:
                  - mountpoint: nowhere
                  - fallback: dev
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphraseless key and per-repo credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillarenv: nonexisting
            ext_pillar:
              - git:
                - __env__ {url_extra_repo}:
                  - fallback: master
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                - __env__ {url}:
                  - mountpoint: nowhere
                  - fallback: dev
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphrase-protected key and global credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_pubkey: {pubkey_withpass}
            git_pillar_privkey: {privkey_withpass}
            git_pillar_passphrase: {passphrase}
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillarenv: nonexisting
            ext_pillar:
              - git:
                - __env__ {url_extra_repo}:
                  - fallback: master
                - __env__ {url}:
                  - mountpoint: nowhere
                  - fallback: dev
            """
        )
        self.assertEqual(ret, expected)

        # Test with passphrase-protected key and per-repo credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillarenv: nonexisting
            ext_pillar:
              - git:
                - __env__ {url_extra_repo}:
                  - fallback: master
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                  - passphrase: {passphrase}
                - __env__ {url}:
                  - mountpoint: nowhere
                  - fallback: dev
                  - pubkey: {pubkey_nopass}
                  - privkey: {privkey_nopass}
                  - passphrase: {passphrase}
            """
        )
        self.assertEqual(ret, expected)


@skipIf(_windows_or_mac(), "minion is windows or mac")
@skip_if_not_root
@skipIf(
    not HAS_PYGIT2,
    "pygit2 >= {} and libgit2 >= {} required".format(PYGIT2_MINVER, LIBGIT2_MINVER),
)
@skipIf(not HAS_NGINX, "nginx not present")
@skipIf(not HAS_VIRTUALENV, "virtualenv not present")
@pytest.mark.usefixtures("webserver_pillar_tests_prep")
class TestPygit2HTTP(GitPillarHTTPTestBase):
    """
    Test git_pillar with pygit2 using SSH authentication
    """

    @slowTest
    def test_single_source(self):
        """
        Test using a single ext_pillar repo
        """
        expected = {
            "branch": "master",
            "mylist": ["master"],
            "mydict": {
                "master": True,
                "nested_list": ["master"],
                "nested_dict": {"master": True},
            },
        }

        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}
            """
        )
        self.assertEqual(ret, expected)

    @slowTest
    def test_multiple_sources_master_dev_no_merge_lists(self):
        """
        Test using two ext_pillar dirs. Since all git_pillar repos are merged
        into a single dictionary, ordering matters.

        This tests with the master branch followed by dev, and with
        pillar_merge_lists disabled.
        """
        expected = {
            "branch": "dev",
            "mylist": ["dev"],
            "mydict": {
                "master": True,
                "dev": True,
                "nested_list": ["dev"],
                "nested_dict": {"master": True, "dev": True},
            },
        }

        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: False
            ext_pillar:
              - git:
                - master {url}
                - dev {url}
            """
        )
        self.assertEqual(ret, expected)

    @slowTest
    def test_multiple_sources_dev_master_no_merge_lists(self):
        """
        Test using two ext_pillar dirs. Since all git_pillar repos are merged
        into a single dictionary, ordering matters.

        This tests with the dev branch followed by master, and with
        pillar_merge_lists disabled.
        """
        expected = {
            "branch": "master",
            "mylist": ["master"],
            "mydict": {
                "master": True,
                "dev": True,
                "nested_list": ["master"],
                "nested_dict": {"master": True, "dev": True},
            },
        }

        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: False
            ext_pillar:
              - git:
                - dev {url}
                - master {url}
            """
        )
        self.assertEqual(ret, expected)

    @slowTest
    def test_multiple_sources_master_dev_merge_lists(self):
        """
        Test using two ext_pillar dirs. Since all git_pillar repos are merged
        into a single dictionary, ordering matters.

        This tests with the master branch followed by dev, and with
        pillar_merge_lists enabled.
        """
        expected = {
            "branch": "dev",
            "mylist": ["master", "dev"],
            "mydict": {
                "master": True,
                "dev": True,
                "nested_list": ["master", "dev"],
                "nested_dict": {"master": True, "dev": True},
            },
        }

        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: True
            ext_pillar:
              - git:
                - master {url}
                - dev {url}
            """
        )
        self.assertEqual(ret, expected)

    @slowTest
    def test_multiple_sources_dev_master_merge_lists(self):
        """
        Test using two ext_pillar dirs. Since all git_pillar repos are merged
        into a single dictionary, ordering matters.

        This tests with the dev branch followed by master, and with
        pillar_merge_lists enabled.
        """
        expected = {
            "branch": "master",
            "mylist": ["dev", "master"],
            "mydict": {
                "master": True,
                "dev": True,
                "nested_list": ["dev", "master"],
                "nested_dict": {"master": True, "dev": True},
            },
        }

        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: True
            ext_pillar:
              - git:
                - dev {url}
                - master {url}
            """
        )
        self.assertEqual(ret, expected)

    @slowTest
    def test_multiple_sources_with_pillarenv(self):
        """
        Test using pillarenv to restrict results to those from a single branch
        """
        expected = {
            "branch": "master",
            "mylist": ["master"],
            "mydict": {
                "master": True,
                "nested_list": ["master"],
                "nested_dict": {"master": True},
            },
        }

        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillarenv: base
            ext_pillar:
              - git:
                - master {url}
                - dev {url}
            """
        )
        self.assertEqual(ret, expected)

    @slowTest
    def test_includes_enabled(self):
        """
        Test with git_pillar_includes enabled. The top_only branch references
        an SLS file from the master branch, so we should see the
        "included_pillar" key from that SLS file in the compiled pillar data.
        """
        expected = {
            "branch": "master",
            "mylist": ["master"],
            "mydict": {
                "master": True,
                "nested_list": ["master"],
                "nested_dict": {"master": True},
            },
            "included_pillar": True,
        }

        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}
                - top_only {url}:
                  - env: base
            """
        )
        self.assertEqual(ret, expected)

    @slowTest
    def test_includes_disabled(self):
        """
        Test with git_pillar_includes enabled. The top_only branch references
        an SLS file from the master branch, but since includes are disabled it
        will not find the SLS file and the "included_pillar" key should not be
        present in the compiled pillar data. We should instead see an error
        message in the compiled data.
        """
        expected = {
            "branch": "master",
            "mylist": ["master"],
            "mydict": {
                "master": True,
                "nested_list": ["master"],
                "nested_dict": {"master": True},
            },
            "_errors": [
                "Specified SLS 'bar' in environment 'base' is not "
                "available on the salt master"
            ],
        }

        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_includes: False
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}
                - top_only {url}:
                  - env: base
            """
        )
        self.assertEqual(ret, expected)

    @slowTest
    def test_includes_enabled_solves___env___with_mountpoint(self):
        """
        Test with git_pillar_includes enabled and using "__env__" as the branch
        name for the configured repositories.
        The "gitinfo" repository contains top.sls file with a local reference
        and also referencing external "nowhere.foo" which is provided by "webinfo"
        repository mounted as "nowhere".
        """
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - __env__ {url_extra_repo}:
                  - name: gitinfo
                - __env__ {url}:
                  - name: webinfo
                  - mountpoint: nowhere
            """
        )
        self.assertEqual(
            ret,
            {
                "branch": "master",
                "motd": "The force will be with you. Always.",
                "mylist": ["master"],
                "mydict": {
                    "master": True,
                    "nested_list": ["master"],
                    "nested_dict": {"master": True},
                },
            },
        )

    @slowTest
    def test_root_parameter(self):
        """
        Test root parameter
        """
        expected = {"from_subdir": True}

        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - root: subdir
                - top_only {url}:
                  - env: base
            """
        )
        self.assertEqual(ret, expected)

    @slowTest
    def test_mountpoint_parameter(self):
        """
        Test mountpoint parameter
        """
        expected = {"included_pillar": True}

        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - mountpoint: mounted
                - top_mounted {url}:
                  - env: base
            """
        )
        self.assertEqual(ret, expected)

    @slowTest
    def test_root_and_mountpoint_parameters(self):
        """
        Test root and mountpoint parameters
        """
        expected = {"from_subdir": True}

        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - mountpoint: mounted
                  - root: subdir
                - top_mounted {url}:
                  - env: base
            """
        )
        self.assertEqual(ret, expected)

    @slowTest
    def test_all_saltenvs(self):
        """
        Test all_saltenvs parameter.
        """
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillarenv: dev
            ext_pillar:
              - git:
                - __env__ {url_extra_repo}:
                  - all_saltenvs: master
                - __env__ {url}:
                  - mountpoint: nowhere
            """
        )
        self.assertEqual(
            ret,
            {
                "branch": "dev",
                "motd": "The force will be with you. Always.",
                "mylist": ["dev"],
                "mydict": {
                    "dev": True,
                    "nested_list": ["dev"],
                    "nested_dict": {"dev": True},
                },
            },
        )

    @slowTest
    def test_all_saltenvs_base(self):
        """
        Test all_saltenvs parameter with base pillarenv.
        """
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - __env__ {url_extra_repo}:
                  - all_saltenvs: master
                - __env__ {url}:
                  - mountpoint: nowhere
            """
        )
        self.assertEqual(
            ret,
            {
                "branch": "master",
                "motd": "The force will be with you. Always.",
                "mylist": ["master"],
                "mydict": {
                    "master": True,
                    "nested_list": ["master"],
                    "nested_dict": {"master": True},
                },
            },
        )

    @slowTest
    def test_fallback(self):
        """
        Test fallback parameter.
        """
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillarenv: nonexisting
            ext_pillar:
              - git:
                - __env__ {url_extra_repo}:
                  - fallback: master
                - __env__ {url}:
                  - mountpoint: nowhere
                  - fallback: dev
            """
        )
        self.assertEqual(
            ret,
            {
                "branch": "dev",
                "motd": "The force will be with you. Always.",
                "mylist": ["dev"],
                "mydict": {
                    "dev": True,
                    "nested_list": ["dev"],
                    "nested_dict": {"dev": True},
                },
            },
        )


@skipIf(_windows_or_mac(), "minion is windows or mac")
@skip_if_not_root
@skipIf(
    not HAS_PYGIT2,
    "pygit2 >= {} and libgit2 >= {} required".format(PYGIT2_MINVER, LIBGIT2_MINVER),
)
@skipIf(not HAS_NGINX, "nginx not present")
@skipIf(not HAS_VIRTUALENV, "virtualenv not present")
@pytest.mark.usefixtures("webserver_pillar_tests_prep_authenticated")
class TestPygit2AuthenticatedHTTP(GitPillarHTTPTestBase):
    """
    Test git_pillar with pygit2 using SSH authentication

    NOTE: Any tests added to this test class should have equivalent tests (if
    possible) in the TestGitPythonSSH class.
    """

    username = USERNAME
    password = PASSWORD

    @slowTest
    def test_single_source(self):
        """
        Test using a single ext_pillar repo
        """
        expected = {
            "branch": "master",
            "mylist": ["master"],
            "mydict": {
                "master": True,
                "nested_list": ["master"],
                "nested_dict": {"master": True},
            },
        }

        # Test with global credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_user: {username}
            git_pillar_password: {password}
            git_pillar_insecure_auth: True
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}
            """
        )
        self.assertEqual(ret, expected)

        # Test with per-repo credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - user: {username}
                  - password: {password}
                  - insecure_auth: True
            """
        )
        self.assertEqual(ret, expected)

    @slowTest
    def test_multiple_sources_master_dev_no_merge_lists(self):
        """
        Test using two ext_pillar dirs. Since all git_pillar repos are merged
        into a single dictionary, ordering matters.

        This tests with the master branch followed by dev, and with
        pillar_merge_lists disabled.
        """
        expected = {
            "branch": "dev",
            "mylist": ["dev"],
            "mydict": {
                "master": True,
                "dev": True,
                "nested_list": ["dev"],
                "nested_dict": {"master": True, "dev": True},
            },
        }

        # Test with global credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_user: {username}
            git_pillar_password: {password}
            git_pillar_insecure_auth: True
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: False
            ext_pillar:
              - git:
                - master {url}
                - dev {url}
            """
        )
        self.assertEqual(ret, expected)

        # Test with per-repo credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: False
            ext_pillar:
              - git:
                - master {url}:
                  - user: {username}
                  - password: {password}
                  - insecure_auth: True
                - dev {url}:
                  - user: {username}
                  - password: {password}
                  - insecure_auth: True
            """
        )
        self.assertEqual(ret, expected)

    @slowTest
    def test_multiple_sources_dev_master_no_merge_lists(self):
        """
        Test using two ext_pillar dirs. Since all git_pillar repos are merged
        into a single dictionary, ordering matters.

        This tests with the dev branch followed by master, and with
        pillar_merge_lists disabled.
        """
        expected = {
            "branch": "master",
            "mylist": ["master"],
            "mydict": {
                "master": True,
                "dev": True,
                "nested_list": ["master"],
                "nested_dict": {"master": True, "dev": True},
            },
        }

        # Test with global credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_user: {username}
            git_pillar_password: {password}
            git_pillar_insecure_auth: True
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: False
            ext_pillar:
              - git:
                - dev {url}
                - master {url}
            """
        )
        self.assertEqual(ret, expected)

        # Test with per-repo credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: False
            ext_pillar:
              - git:
                - dev {url}:
                  - user: {username}
                  - password: {password}
                  - insecure_auth: True
                - master {url}:
                  - user: {username}
                  - password: {password}
                  - insecure_auth: True
            """
        )
        self.assertEqual(ret, expected)

    @slowTest
    def test_multiple_sources_master_dev_merge_lists(self):
        """
        Test using two ext_pillar dirs. Since all git_pillar repos are merged
        into a single dictionary, ordering matters.

        This tests with the master branch followed by dev, and with
        pillar_merge_lists enabled.
        """
        expected = {
            "branch": "dev",
            "mylist": ["master", "dev"],
            "mydict": {
                "master": True,
                "dev": True,
                "nested_list": ["master", "dev"],
                "nested_dict": {"master": True, "dev": True},
            },
        }

        # Test with global credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_user: {username}
            git_pillar_password: {password}
            git_pillar_insecure_auth: True
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: True
            ext_pillar:
              - git:
                - master {url}
                - dev {url}
            """
        )
        self.assertEqual(ret, expected)

        # Test with per-repo credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: True
            ext_pillar:
              - git:
                - master {url}:
                  - user: {username}
                  - password: {password}
                  - insecure_auth: True
                - dev {url}:
                  - user: {username}
                  - password: {password}
                  - insecure_auth: True
            """
        )
        self.assertEqual(ret, expected)

    @slowTest
    def test_multiple_sources_dev_master_merge_lists(self):
        """
        Test using two ext_pillar dirs. Since all git_pillar repos are merged
        into a single dictionary, ordering matters.

        This tests with the dev branch followed by master, and with
        pillar_merge_lists enabled.
        """
        expected = {
            "branch": "master",
            "mylist": ["dev", "master"],
            "mydict": {
                "master": True,
                "dev": True,
                "nested_list": ["dev", "master"],
                "nested_dict": {"master": True, "dev": True},
            },
        }

        # Test with global credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_user: {username}
            git_pillar_password: {password}
            git_pillar_insecure_auth: True
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: True
            ext_pillar:
              - git:
                - dev {url}
                - master {url}
            """
        )
        self.assertEqual(ret, expected)

        # Test with per-repo credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillar_merge_lists: True
            ext_pillar:
              - git:
                - dev {url}:
                  - user: {username}
                  - password: {password}
                  - insecure_auth: True
                - master {url}:
                  - user: {username}
                  - password: {password}
                  - insecure_auth: True
            """
        )
        self.assertEqual(ret, expected)

    @slowTest
    def test_multiple_sources_with_pillarenv(self):
        """
        Test using pillarenv to restrict results to those from a single branch
        """
        expected = {
            "branch": "master",
            "mylist": ["master"],
            "mydict": {
                "master": True,
                "nested_list": ["master"],
                "nested_dict": {"master": True},
            },
        }

        # Test with global credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_user: {username}
            git_pillar_password: {password}
            git_pillar_insecure_auth: True
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillarenv: base
            ext_pillar:
              - git:
                - master {url}
                - dev {url}
            """
        )
        self.assertEqual(ret, expected)

        # Test with per-repo credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillarenv: base
            ext_pillar:
              - git:
                - master {url}:
                  - user: {username}
                  - password: {password}
                  - insecure_auth: True
                - dev {url}:
                  - user: {username}
                  - password: {password}
                  - insecure_auth: True
            """
        )
        self.assertEqual(ret, expected)

    @slowTest
    def test_includes_enabled(self):
        """
        Test with git_pillar_includes enabled. The top_only branch references
        an SLS file from the master branch, so we should see the
        "included_pillar" key from that SLS file in the compiled pillar data.
        """
        expected = {
            "branch": "master",
            "mylist": ["master"],
            "mydict": {
                "master": True,
                "nested_list": ["master"],
                "nested_dict": {"master": True},
            },
            "included_pillar": True,
        }

        # Test with global credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_user: {username}
            git_pillar_password: {password}
            git_pillar_insecure_auth: True
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}
                - top_only {url}:
                  - env: base
            """
        )
        self.assertEqual(ret, expected)

    @slowTest
    def test_mountpoint_parameter(self):
        """
        Test mountpoint parameter
        """
        expected = {"included_pillar": True}

        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_user: {username}
            git_pillar_password: {password}
            git_pillar_insecure_auth: True
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - mountpoint: mounted
                - top_mounted {url}:
                  - env: base
            """
        )
        self.assertEqual(ret, expected)

    @slowTest
    def test_root_parameter(self):
        """
        Test root parameter
        """
        expected = {"from_subdir": True}

        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_user: {username}
            git_pillar_password: {password}
            git_pillar_insecure_auth: True
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - root: subdir
                - top_only {url}:
                  - env: base
            """
        )
        self.assertEqual(ret, expected)

        # Test with per-repo credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - root: subdir
                  - user: {username}
                  - password: {password}
                  - insecure_auth: True
                - top_only {url}:
                  - user: {username}
                  - password: {password}
                  - insecure_auth: True
                  - env: base
            """
        )
        self.assertEqual(ret, expected)

    @slowTest
    def test_includes_disabled(self):
        """
        Test with git_pillar_includes enabled. The top_only branch references
        an SLS file from the master branch, but since includes are disabled it
        will not find the SLS file and the "included_pillar" key should not be
        present in the compiled pillar data. We should instead see an error
        message in the compiled data.
        """
        expected = {
            "branch": "master",
            "mylist": ["master"],
            "mydict": {
                "master": True,
                "nested_list": ["master"],
                "nested_dict": {"master": True},
            },
            "_errors": [
                "Specified SLS 'bar' in environment 'base' is not "
                "available on the salt master"
            ],
        }

        # Test with global credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_includes: False
            git_pillar_user: {username}
            git_pillar_password: {password}
            git_pillar_insecure_auth: True
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}
                - top_only {url}:
                  - env: base
            """
        )
        self.assertEqual(ret, expected)

        # Test with per-repo credential options
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_includes: False
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - user: {username}
                  - password: {password}
                  - insecure_auth: True
                - top_only {url}:
                  - user: {username}
                  - password: {password}
                  - insecure_auth: True
                  - env: base
            """
        )
        self.assertEqual(ret, expected)

    @slowTest
    def test_includes_enabled_solves___env___with_mountpoint(self):
        """
        Test with git_pillar_includes enabled and using "__env__" as the branch
        name for the configured repositories.
        The "gitinfo" repository contains top.sls file with a local reference
        and also referencing external "nowhere.foo" which is provided by "webinfo"
        repository mounted as "nowhere".
        """
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_user: {username}
            git_pillar_password: {password}
            git_pillar_insecure_auth: True
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - __env__ {url_extra_repo}:
                  - name: gitinfo
                  - user: {username}
                  - password: {password}
                  - insecure_auth: True
                - __env__ {url}:
                  - name: webinfo
                  - mountpoint: nowhere
                  - user: {username}
                  - password: {password}
                  - insecure_auth: True
            """
        )
        self.assertEqual(
            ret,
            {
                "branch": "master",
                "motd": "The force will be with you. Always.",
                "mylist": ["master"],
                "mydict": {
                    "master": True,
                    "nested_list": ["master"],
                    "nested_dict": {"master": True},
                },
            },
        )

    @slowTest
    def test_root_and_mountpoint_parameters(self):
        """
        Test root and mountpoint parameters
        """
        expected = {"from_subdir": True}

        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_user: {username}
            git_pillar_password: {password}
            git_pillar_insecure_auth: True
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - master {url}:
                  - mountpoint: mounted
                  - root: subdir
                - top_mounted {url}:
                  - env: base
            """
        )
        self.assertEqual(ret, expected)

    @slowTest
    def test_all_saltenvs(self):
        """
        Test all_saltenvs parameter.
        """
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_user: {username}
            git_pillar_password: {password}
            git_pillar_insecure_auth: True
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillarenv: dev
            ext_pillar:
              - git:
                - __env__ {url_extra_repo}:
                  - all_saltenvs: master
                - __env__ {url}:
                  - mountpoint: nowhere
            """
        )
        self.assertEqual(
            ret,
            {
                "branch": "dev",
                "motd": "The force will be with you. Always.",
                "mylist": ["dev"],
                "mydict": {
                    "dev": True,
                    "nested_list": ["dev"],
                    "nested_dict": {"dev": True},
                },
            },
        )

    @slowTest
    def test_all_saltenvs_base(self):
        """
        Test all_saltenvs parameter with base pillarenv.
        """
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_user: {username}
            git_pillar_password: {password}
            git_pillar_insecure_auth: True
            cachedir: {cachedir}
            extension_modules: {extmods}
            ext_pillar:
              - git:
                - __env__ {url_extra_repo}:
                  - all_saltenvs: master
                - __env__ {url}:
                  - mountpoint: nowhere
            """
        )
        self.assertEqual(
            ret,
            {
                "branch": "master",
                "motd": "The force will be with you. Always.",
                "mylist": ["master"],
                "mydict": {
                    "master": True,
                    "nested_list": ["master"],
                    "nested_dict": {"master": True},
                },
            },
        )

    @slowTest
    def test_fallback(self):
        """
        Test fallback parameter.
        """
        ret = self.get_pillar(
            """\
            file_ignore_regex: []
            file_ignore_glob: []
            git_pillar_provider: pygit2
            git_pillar_user: {username}
            git_pillar_password: {password}
            git_pillar_insecure_auth: True
            cachedir: {cachedir}
            extension_modules: {extmods}
            pillarenv: nonexisting
            ext_pillar:
              - git:
                - __env__ {url_extra_repo}:
                  - fallback: master
                - __env__ {url}:
                  - mountpoint: nowhere
                  - fallback: dev
            """
        )
        self.assertEqual(
            ret,
            {
                "branch": "dev",
                "motd": "The force will be with you. Always.",
                "mylist": ["dev"],
                "mydict": {
                    "dev": True,
                    "nested_list": ["dev"],
                    "nested_dict": {"dev": True},
                },
            },
        )
