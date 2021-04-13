"""
Base classes for gitfs/git_pillar integration tests
"""

import errno
import logging
import os
import shutil
import tempfile
import textwrap

import attr
import pytest
import salt.utils.files
import salt.utils.path
import salt.utils.platform
import salt.utils.yaml
from salt.fileserver import gitfs
from salt.pillar import git_pillar
from salt.utils.immutabletypes import freeze
from saltfactories.factories.base import DaemonFactory
from saltfactories.factories.daemons.sshd import SshdDaemonFactory as _SshdDaemonFactory
from saltfactories.utils.ports import get_unused_localhost_port
from tests.support.case import ModuleCase
from tests.support.helpers import patched_environ, requires_system_grains
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import patch
from tests.support.runtests import RUNTIME_VARS

log = logging.getLogger(__name__)

USERNAME = "gitpillaruser"
PASSWORD = "saltrules"

_OPTS = freeze(
    {
        "__role": "minion",
        "environment": None,
        "pillarenv": None,
        "hash_type": "sha256",
        "file_roots": {},
        "state_top": "top.sls",
        "state_top_saltenv": None,
        "renderer": "yaml_jinja",
        "renderer_whitelist": [],
        "renderer_blacklist": [],
        "pillar_merge_lists": False,
        "git_pillar_base": "master",
        "git_pillar_branch": "master",
        "git_pillar_env": "",
        "git_pillar_fallback": "",
        "git_pillar_root": "",
        "git_pillar_ssl_verify": True,
        "git_pillar_global_lock": True,
        "git_pillar_user": "",
        "git_pillar_password": "",
        "git_pillar_insecure_auth": False,
        "git_pillar_privkey": "",
        "git_pillar_pubkey": "",
        "git_pillar_passphrase": "",
        "git_pillar_refspecs": [
            "+refs/heads/*:refs/remotes/origin/*",
            "+refs/tags/*:refs/tags/*",
        ],
        "git_pillar_includes": True,
    }
)


class SshdDaemonFactory(_SshdDaemonFactory):
    def apply_pre_start_states(self, salt_call_cli, testclass, username):
        if self.listen_port in self.check_ports:
            self.check_ports.remove(self.listen_port)
        if self.listen_port in self.listen_ports:
            self.listen_ports.remove(self.listen_port)
        self.listen_port = get_unused_localhost_port()
        self.check_ports.append(self.listen_port)
        self.listen_ports.append(self.listen_port)
        url = "ssh://{username}@127.0.0.1:{port}/~/repo.git".format(
            username=testclass.username, port=self.listen_port
        )
        url_extra_repo = "ssh://{username}@127.0.0.1:{port}/~/extra_repo.git".format(
            username=testclass.username, port=self.listen_port
        )
        home = "/root/.ssh"
        testclass.ext_opts = {
            "url": url,
            "url_extra_repo": url_extra_repo,
            "privkey_nopass": os.path.join(home, testclass.id_rsa_nopass),
            "pubkey_nopass": os.path.join(home, testclass.id_rsa_nopass + ".pub"),
            "privkey_withpass": os.path.join(home, testclass.id_rsa_withpass),
            "pubkey_withpass": os.path.join(home, testclass.id_rsa_withpass + ".pub"),
            "passphrase": testclass.passphrase,
        }
        ret = salt_call_cli.run(
            "state.apply",
            mods="git_pillar.ssh",
            pillar={
                "git_pillar": {
                    "git_ssh": testclass.git_ssh,
                    "id_rsa_nopass": testclass.id_rsa_nopass,
                    "id_rsa_withpass": testclass.id_rsa_withpass,
                    "sshd_bin": self.get_script_path(),
                    "sshd_port": self.listen_port,
                    "sshd_config_dir": str(self.config_dir),
                    "master_user": username,
                    "user": testclass.username,
                }
            },
            _timeout=240,
        )
        if ret.exitcode != 0:
            pytest.fail("Failed to apply the 'git_pillar.ssh' state")
        if next(iter(ret.json.values()))["result"] is not True:
            pytest.fail("Failed to apply the 'git_pillar.ssh' state")

    def set_known_host(self, salt_call_cli, username):
        ret = salt_call_cli.run(
            "ssh.set_known_host",
            user=username,
            hostname="127.0.0.1",
            port=self.listen_port,
            enc="ssh-rsa",
            fingerprint="fd:6f:7f:5d:06:6b:f2:06:0d:26:93:9e:5a:b5:19:46",
            hash_known_hosts=False,
            fingerprint_hash_type="md5",
        )
        if ret.exitcode != 0:
            pytest.fail("Failed to run 'ssh.set_known_host'")
        if "error" in ret.json:
            pytest.fail("Failed to run 'ssh.set_known_host'")


@attr.s(kw_only=True, slots=True)
class UwsgiDaemon(DaemonFactory):

    config_dir = attr.ib()
    listen_port = attr.ib(default=attr.Factory(get_unused_localhost_port))

    def __attrs_post_init__(self):
        if self.check_ports is None:
            self.check_ports = []
        self.check_ports.append(self.listen_port)
        super().__attrs_post_init__()

    def get_base_script_args(self):
        """
        Returns any additional arguments to pass to the CLI script
        """
        return ["--yaml", os.path.join(self.config_dir, "uwsgi.yml")]

    def apply_pre_start_states(self, salt_call_cli, testclass, root_dir):
        if self.listen_port in self.check_ports:
            self.check_ports.remove(self.listen_port)
        if self.listen_port in self.listen_ports:
            self.listen_ports.remove(self.listen_port)
        self.listen_port = get_unused_localhost_port()
        self.check_ports.append(self.listen_port)
        self.listen_ports.append(self.listen_port)

        config_dir = os.path.join(root_dir, "config")
        git_dir = os.path.join(root_dir, "git")
        testclass.repo_dir = repo_dir = os.path.join(git_dir, "repos")
        venv_dir = os.path.join(root_dir, "venv")
        uwsgi_bin = os.path.join(venv_dir, "bin", "uwsgi")

        pillar = {
            "git_pillar": {
                "config_dir": config_dir,
                "git_dir": git_dir,
                "venv_dir": venv_dir,
                "root_dir": root_dir,
                "uwsgi_port": self.listen_port,
            }
        }

        # Different libexec dir for git backend on Debian and FreeBSD-based systems
        if salt.utils.platform.is_freebsd():
            git_core = "/usr/local/libexec/git-core"
        else:
            git_core = "/usr/libexec/git-core"
        if not os.path.exists(git_core):
            git_core = "/usr/lib/git-core"

        if not os.path.exists(git_core):
            pytest.fail(
                "{} not found. Either git is not installed, or the test "
                "class needs to be updated.".format(git_core)
            )

        pillar["git_pillar"]["git-http-backend"] = os.path.join(
            git_core, "git-http-backend"
        )

        ret = salt_call_cli.run(
            "state.apply", mods="git_pillar.http.uwsgi", pillar=pillar, _timeout=120
        )
        if ret.exitcode != 0:
            pytest.fail("Failed to apply the 'git_pillar.http.uwsgi' state")
        if next(iter(ret.json.values()))["result"] is not True:
            pytest.fail("Failed to apply the 'git_pillar.http.uwsgi' state")


@attr.s(kw_only=True, slots=True)
class NginxDaemon(DaemonFactory):

    config_dir = attr.ib()
    uwsgi_port = attr.ib()
    listen_port = attr.ib(default=attr.Factory(get_unused_localhost_port))

    def __attrs_post_init__(self):
        if self.check_ports is None:
            self.check_ports = []
        self.check_ports.append(self.listen_port)
        super().__attrs_post_init__()

    def get_base_script_args(self):
        """
        Returns any additional arguments to pass to the CLI script
        """
        return ["-c", os.path.join(self.config_dir, "nginx.conf")]

    def apply_pre_start_states(self, salt_call_cli, testclass, root_dir):
        if self.listen_port in self.check_ports:
            self.check_ports.remove(self.listen_port)
        if self.listen_port in self.listen_ports:
            self.listen_ports.remove(self.listen_port)
        self.listen_port = get_unused_localhost_port()
        self.check_ports.append(self.listen_port)
        self.listen_ports.append(self.listen_port)

        config_dir = os.path.join(root_dir, "config")
        git_dir = os.path.join(root_dir, "git")
        url = "http://127.0.0.1:{port}/repo.git".format(port=self.listen_port)
        url_extra_repo = "http://127.0.0.1:{port}/extra_repo.git".format(
            port=self.listen_port
        )
        ext_opts = {"url": url, "url_extra_repo": url_extra_repo}
        # Add auth params if present (if so this will trigger the spawned
        # server to turn on HTTP basic auth).
        for credential_param in ("user", "password"):
            if hasattr(testclass, credential_param):
                ext_opts[credential_param] = getattr(testclass, credential_param)
        testclass.ext_opts = ext_opts
        testclass.nginx_port = self.listen_port

        auth_enabled = hasattr(testclass, "username") and hasattr(testclass, "password")
        pillar = {
            "git_pillar": {
                "config_dir": config_dir,
                "git_dir": git_dir,
                "uwsgi_port": self.uwsgi_port,
                "nginx_port": self.listen_port,
                "auth_enabled": auth_enabled,
            }
        }

        ret = salt_call_cli.run(
            "state.apply", mods="git_pillar.http.nginx", pillar=pillar
        )
        if ret.exitcode != 0:
            pytest.fail("Failed to apply the 'git_pillar.http.nginx' state")
        if next(iter(ret.json.values()))["result"] is not True:
            pytest.fail("Failed to apply the 'git_pillar.http.nginx' state")


@pytest.fixture(scope="class")
def ssh_pillar_tests_prep(request, salt_master, salt_minion):
    """
    Stand up an SSHD server to serve up git repos for tests.
    """
    salt_call_cli = salt_minion.get_salt_call_cli()

    sshd_bin = salt.utils.path.which("sshd")
    sshd_config_dir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)

    sshd_proc = SshdDaemonFactory(
        cli_script_name=sshd_bin,
        config_dir=sshd_config_dir,
        start_timeout=120,
        display_name=request.cls.__name__,
    )
    sshd_proc.register_before_start_callback(
        sshd_proc.apply_pre_start_states,
        salt_call_cli=salt_call_cli,
        testclass=request.cls,
        username=salt_master.config["user"],
    )
    sshd_proc.register_after_start_callback(
        sshd_proc.set_known_host,
        salt_call_cli=salt_call_cli,
        username=salt_master.config["user"],
    )
    try:
        sshd_proc.start()
        yield
    finally:
        request.cls.ext_opts = None
        salt_call_cli.run(
            "state.single", "user.absent", name=request.cls.username, purge=True
        )
        shutil.rmtree(sshd_config_dir, ignore_errors=True)
        ssh_dir = os.path.expanduser("~/.ssh")
        for filename in (
            request.cls.id_rsa_nopass,
            request.cls.id_rsa_nopass + ".pub",
            request.cls.id_rsa_withpass,
            request.cls.id_rsa_withpass + ".pub",
            request.cls.git_ssh,
        ):
            try:
                os.remove(os.path.join(ssh_dir, filename))
            except OSError as exc:
                if exc.errno != errno.ENOENT:
                    raise
        sshd_proc.terminate()


@pytest.fixture(scope="class")
def webserver_pillar_tests_prep(request, salt_master, salt_minion):
    """
    Stand up an nginx + uWSGI + git-http-backend webserver to
    serve up git repos for tests.
    """
    salt_call_cli = salt_minion.get_salt_call_cli()

    root_dir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
    config_dir = os.path.join(root_dir, "config")
    venv_dir = os.path.join(root_dir, "venv")
    uwsgi_bin = os.path.join(venv_dir, "bin", "uwsgi")

    uwsgi_proc = nginx_proc = None
    try:
        uwsgi_proc = UwsgiDaemon(
            cli_script_name=uwsgi_bin,
            config_dir=config_dir,
            start_timeout=120,
            display_name=request.cls.__name__,
        )
        uwsgi_proc.register_before_start_callback(
            uwsgi_proc.apply_pre_start_states,
            salt_call_cli=salt_call_cli,
            testclass=request.cls,
            root_dir=root_dir,
        )
        uwsgi_proc.start()
        nginx_proc = NginxDaemon(
            cli_script_name="nginx",
            config_dir=config_dir,
            start_timeout=120,
            uwsgi_port=uwsgi_proc.listen_port,
            display_name=request.cls.__name__,
        )
        nginx_proc.register_before_start_callback(
            nginx_proc.apply_pre_start_states,
            salt_call_cli=salt_call_cli,
            testclass=request.cls,
            root_dir=root_dir,
        )
        nginx_proc.start()
        yield
    finally:
        request.cls.repo_dir = request.cls.ext_opts = request.cls.nginx_port = None
        if uwsgi_proc:
            uwsgi_proc.terminate()
        if nginx_proc:
            nginx_proc.terminate()
        shutil.rmtree(root_dir, ignore_errors=True)


@pytest.fixture(scope="class")
def webserver_pillar_tests_prep_authenticated(request, webserver_pillar_tests_prep):
    url = "http://{username}:{password}@127.0.0.1:{port}/repo.git".format(
        username=request.cls.username,
        password=request.cls.password,
        port=request.cls.nginx_port,
    )
    url_extra_repo = "http://{username}:{password}@127.0.0.1:{port}/extra_repo.git".format(
        username=request.cls.username,
        password=request.cls.password,
        port=request.cls.nginx_port,
    )
    request.cls.ext_opts["url"] = url
    request.cls.ext_opts["url_extra_repo"] = url_extra_repo
    request.cls.ext_opts["username"] = request.cls.username
    request.cls.ext_opts["password"] = request.cls.password


class GitTestBase(ModuleCase):
    """
    Base class for all gitfs/git_pillar tests.
    """

    maxDiff = None
    git_opts = '-c user.name="Foo Bar" -c user.email=foo@bar.com'

    def make_repo(self, root_dir, user="root"):
        raise NotImplementedError()


class GitFSTestBase(GitTestBase, LoaderModuleMockMixin):
    """
    Base class for all gitfs tests
    """

    @requires_system_grains
    def setup_loader_modules(self, grains):  # pylint: disable=W0221
        return {gitfs: {"__opts__": _OPTS.copy(), "__grains__": grains}}

    def make_repo(self, root_dir, user="root"):
        raise NotImplementedError()


class GitPillarTestBase(GitTestBase, LoaderModuleMockMixin):
    """
    Base class for all git_pillar tests
    """

    bare_repo = bare_repo_backup = bare_extra_repo = bare_extra_repo_backup = None
    admin_repo = admin_repo_backup = admin_extra_repo = admin_extra_repo_backup = None

    @requires_system_grains
    def setup_loader_modules(self, grains):  # pylint: disable=W0221
        return {git_pillar: {"__opts__": _OPTS.copy(), "__grains__": grains}}

    def get_pillar(self, ext_pillar_conf):
        """
        Run git_pillar with the specified configuration
        """
        cachedir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        self.addCleanup(shutil.rmtree, cachedir, ignore_errors=True)
        ext_pillar_opts = {"optimization_order": [0, 1, 2]}
        ext_pillar_opts.update(
            salt.utils.yaml.safe_load(
                ext_pillar_conf.format(
                    cachedir=cachedir,
                    extmods=os.path.join(cachedir, "extmods"),
                    **self.ext_opts
                )
            )
        )
        with patch.dict(git_pillar.__opts__, ext_pillar_opts):
            return git_pillar.ext_pillar(
                "minion", {}, *ext_pillar_opts["ext_pillar"][0]["git"]
            )

    def make_repo(self, root_dir, user="root"):
        log.info("Creating test Git repo....")
        self.bare_repo = os.path.join(root_dir, "repo.git")
        self.bare_repo_backup = "{}.backup".format(self.bare_repo)
        self.admin_repo = os.path.join(root_dir, "admin")
        self.admin_repo_backup = "{}.backup".format(self.admin_repo)

        for dirname in (self.bare_repo, self.admin_repo):
            shutil.rmtree(dirname, ignore_errors=True)

        if os.path.exists(self.bare_repo_backup) and os.path.exists(
            self.admin_repo_backup
        ):
            shutil.copytree(self.bare_repo_backup, self.bare_repo)
            shutil.copytree(self.admin_repo_backup, self.admin_repo)
            return

        # Create bare repo
        self.run_function("git.init", [self.bare_repo], user=user, bare=True)

        # Clone bare repo
        self.run_function("git.clone", [self.admin_repo], url=self.bare_repo, user=user)

        def _push(branch, message):
            self.run_function("git.add", [self.admin_repo, "."], user=user)
            self.run_function(
                "git.commit",
                [self.admin_repo, message],
                user=user,
                git_opts=self.git_opts,
            )
            self.run_function(
                "git.push", [self.admin_repo], remote="origin", ref=branch, user=user,
            )

        with salt.utils.files.fopen(
            os.path.join(self.admin_repo, "top.sls"), "w"
        ) as fp_:
            fp_.write(
                textwrap.dedent(
                    """\
            base:
              '*':
                - foo
            """
                )
            )
        with salt.utils.files.fopen(
            os.path.join(self.admin_repo, "foo.sls"), "w"
        ) as fp_:
            fp_.write(
                textwrap.dedent(
                    """\
            branch: master
            mylist:
              - master
            mydict:
              master: True
              nested_list:
                - master
              nested_dict:
                master: True
            """
                )
            )
        # Add another file to be referenced using git_pillar_includes
        with salt.utils.files.fopen(
            os.path.join(self.admin_repo, "bar.sls"), "w"
        ) as fp_:
            fp_.write("included_pillar: True\n")
        # Add another file in subdir
        os.mkdir(os.path.join(self.admin_repo, "subdir"))
        with salt.utils.files.fopen(
            os.path.join(self.admin_repo, "subdir", "bar.sls"), "w"
        ) as fp_:
            fp_.write("from_subdir: True\n")
        _push("master", "initial commit")

        # Do the same with different values for "dev" branch
        self.run_function("git.checkout", [self.admin_repo], user=user, opts="-b dev")
        # The bar.sls shouldn't be in any branch but master
        self.run_function("git.rm", [self.admin_repo, "bar.sls"], user=user)
        with salt.utils.files.fopen(
            os.path.join(self.admin_repo, "top.sls"), "w"
        ) as fp_:
            fp_.write(
                textwrap.dedent(
                    """\
            dev:
              '*':
                - foo
            """
                )
            )
        with salt.utils.files.fopen(
            os.path.join(self.admin_repo, "foo.sls"), "w"
        ) as fp_:
            fp_.write(
                textwrap.dedent(
                    """\
            branch: dev
            mylist:
              - dev
            mydict:
              dev: True
              nested_list:
                - dev
              nested_dict:
                dev: True
            """
                )
            )
        _push("dev", "add dev branch")

        # Create just a top file in a separate repo, to be mapped to the base
        # env and referenced using git_pillar_includes
        self.run_function(
            "git.checkout", [self.admin_repo], user=user, opts="-b top_only"
        )
        # The top.sls should be the only file in this branch
        self.run_function(
            "git.rm",
            [self.admin_repo, "foo.sls", os.path.join("subdir", "bar.sls")],
            user=user,
        )
        with salt.utils.files.fopen(
            os.path.join(self.admin_repo, "top.sls"), "w"
        ) as fp_:
            fp_.write(
                textwrap.dedent(
                    """\
            base:
              '*':
                - bar
            """
                )
            )
        _push("top_only", "add top_only branch")

        # Create just another top file in a separate repo, to be mapped to the base
        # env and including mounted.bar
        self.run_function(
            "git.checkout", [self.admin_repo], user=user, opts="-b top_mounted"
        )
        # The top.sls should be the only file in this branch
        with salt.utils.files.fopen(
            os.path.join(self.admin_repo, "top.sls"), "w"
        ) as fp_:
            fp_.write(
                textwrap.dedent(
                    """\
            base:
              '*':
                - mounted.bar
            """
                )
            )
        _push("top_mounted", "add top_mounted branch")
        shutil.copytree(self.bare_repo, self.bare_repo_backup)
        shutil.copytree(self.admin_repo, self.admin_repo_backup)
        log.info("Test Git repo created.")

    def make_extra_repo(self, root_dir, user="root"):
        log.info("Creating extra test Git repo....")
        self.bare_extra_repo = os.path.join(root_dir, "extra_repo.git")
        self.bare_extra_repo_backup = "{}.backup".format(self.bare_extra_repo)
        self.admin_extra_repo = os.path.join(root_dir, "admin_extra")
        self.admin_extra_repo_backup = "{}.backup".format(self.admin_extra_repo)

        for dirname in (self.bare_extra_repo, self.admin_extra_repo):
            shutil.rmtree(dirname, ignore_errors=True)

        if os.path.exists(self.bare_extra_repo_backup) and os.path.exists(
            self.admin_extra_repo_backup
        ):
            shutil.copytree(self.bare_extra_repo_backup, self.bare_extra_repo)
            shutil.copytree(self.admin_extra_repo_backup, self.admin_extra_repo)
            return

        # Create bare extra repo
        self.run_function("git.init", [self.bare_extra_repo], user=user, bare=True)

        # Clone bare repo
        self.run_function(
            "git.clone", [self.admin_extra_repo], url=self.bare_extra_repo, user=user
        )

        def _push(branch, message):
            self.run_function("git.add", [self.admin_extra_repo, "."], user=user)
            self.run_function(
                "git.commit",
                [self.admin_extra_repo, message],
                user=user,
                git_opts=self.git_opts,
            )
            self.run_function(
                "git.push",
                [self.admin_extra_repo],
                remote="origin",
                ref=branch,
                user=user,
            )

        with salt.utils.files.fopen(
            os.path.join(self.admin_extra_repo, "top.sls"), "w"
        ) as fp_:
            fp_.write(
                textwrap.dedent(
                    """\
            "{{saltenv}}":
              '*':
                - motd
                - nowhere.foo
            """
                )
            )
        with salt.utils.files.fopen(
            os.path.join(self.admin_extra_repo, "motd.sls"), "w"
        ) as fp_:
            fp_.write(
                textwrap.dedent(
                    """\
            motd: The force will be with you. Always.
            """
                )
            )
        _push("master", "initial commit")
        shutil.copytree(self.bare_extra_repo, self.bare_extra_repo_backup)
        shutil.copytree(self.admin_extra_repo, self.admin_extra_repo_backup)
        log.info("Extra test Git repo created.")

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        for dirname in (
            cls.admin_repo,
            cls.admin_repo_backup,
            cls.admin_extra_repo,
            cls.admin_extra_repo_backup,
            cls.bare_repo,
            cls.bare_repo_backup,
            cls.bare_extra_repo,
            cls.bare_extra_repo_backup,
        ):
            if dirname is not None:
                shutil.rmtree(dirname, ignore_errors=True)


class GitPillarSSHTestBase(GitPillarTestBase):
    """
    Base class for GitPython and Pygit2 SSH tests
    """

    id_rsa_nopass = id_rsa_withpass = None
    git_ssh = "/tmp/git_ssh"

    def setUp(self):
        """
        Create the SSH server and user, and create the git repo
        """
        log.info("%s.setUp() started...", self.__class__.__name__)
        super().setUp()
        root_dir = os.path.expanduser("~{}".format(self.username))
        if root_dir.startswith("~"):
            raise AssertionError(
                "Unable to resolve homedir for user '{}'".format(self.username)
            )
        self.make_repo(root_dir, user=self.username)
        self.make_extra_repo(root_dir, user=self.username)
        log.info("%s.setUp() complete.", self.__class__.__name__)

    def get_pillar(self, ext_pillar_conf):
        """
        Wrap the parent class' get_pillar() func in logic that temporarily
        changes the GIT_SSH to use our custom script, ensuring that the
        passphraselsess key is used to auth without needing to modify the root
        user's ssh config file.
        """
        with patched_environ(GIT_SSH=self.git_ssh):
            return super().get_pillar(ext_pillar_conf)


class GitPillarHTTPTestBase(GitPillarTestBase):
    """
    Base class for GitPython and Pygit2 HTTP tests
    """

    def setUp(self):
        """
        Create and start the webserver, and create the git repo
        """
        log.info("%s.setUp() started...", self.__class__.__name__)
        super().setUp()
        self.make_repo(self.repo_dir)
        self.make_extra_repo(self.repo_dir)
        log.info("%s.setUp() complete", self.__class__.__name__)
