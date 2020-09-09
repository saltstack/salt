"""
Base classes for gitfs/git_pillar integration tests
"""


import copy
import errno
import logging
import os
import pathlib
import pprint
import shutil
import tempfile
import textwrap

import salt.utils.files
import salt.utils.path
import salt.utils.platform
import salt.utils.yaml
from salt.fileserver import gitfs
from salt.pillar import git_pillar
from saltfactories.utils.ports import get_unused_localhost_port
from saltfactories.utils.processes.bases import FactoryDaemonScriptBase
from saltfactories.utils.processes.helpers import start_daemon, terminate_process
from saltfactories.utils.processes.sshd import SshdDaemon
from tests.support.case import ModuleCase
from tests.support.helpers import patched_environ, requires_system_grains
from tests.support.mixins import (
    AdaptedConfigurationTestCaseMixin,
    LoaderModuleMockMixin,
    SaltReturnAssertsMixin,
)
from tests.support.mock import patch
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import SkipTest

try:
    import psutil
except ImportError:
    pass

log = logging.getLogger(__name__)

USERNAME = "gitpillaruser"
PASSWORD = "saltrules"

_OPTS = {
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
PROC_TIMEOUT = 10


class UwsgiDaemon(FactoryDaemonScriptBase):
    def __init__(self, *args, **kwargs):
        config_dir = kwargs.pop("config_dir")
        check_port = kwargs.pop("check_port")
        super().__init__(*args, **kwargs)
        self.config_dir = config_dir
        self.check_port = check_port

    def get_log_prefix(self):
        return "[uWSGI] "

    def get_base_script_args(self):
        """
        Returns any additional arguments to pass to the CLI script
        """
        return ["--yaml", os.path.join(self.config_dir, "uwsgi.yml")]

    def get_check_ports(self):
        """
        Return a list of ports to check against to ensure the daemon is running
        """
        return [self.check_port]


class NginxDaemon(FactoryDaemonScriptBase):
    def __init__(self, *args, **kwargs):
        config_dir = kwargs.pop("config_dir")
        check_port = kwargs.pop("check_port")
        super().__init__(*args, **kwargs)
        self.config_dir = config_dir
        self.check_port = check_port

    def get_log_prefix(self):
        return "[Nginx] "

    def get_base_script_args(self):
        """
        Returns any additional arguments to pass to the CLI script
        """
        return ["-c", os.path.join(self.config_dir, "nginx.conf")]

    def get_check_ports(self):
        """
        Return a list of ports to check against to ensure the daemon is running
        """
        return [self.check_port]


class SaltClientMixin(ModuleCase):

    client = None

    @classmethod
    @requires_system_grains
    def setUpClass(cls, grains=None):  # pylint: disable=arguments-differ
        # Cent OS 6 has too old a version of git to handle the make_repo code, as
        # it lacks the -c option for git itself.
        make_repo = getattr(cls, "make_repo", None)
        if (
            callable(make_repo)
            and grains["os_family"] == "RedHat"
            and grains["osmajorrelease"] < 7
        ):
            raise SkipTest("RHEL < 7 has too old a version of git to run these tests")
        # Late import
        import salt.client

        mopts = AdaptedConfigurationTestCaseMixin.get_config(
            "master", from_scratch=True
        )
        cls.user = mopts["user"]
        cls.client = salt.client.get_local_client(mopts=mopts)

    @classmethod
    def tearDownClass(cls):
        cls.client = None

    @classmethod
    def cls_run_function(cls, function, *args, **kwargs):
        orig = cls.client.cmd("minion", function, arg=args, timeout=300, kwarg=kwargs)
        return orig["minion"]


class SSHDMixin(SaltClientMixin, SaltReturnAssertsMixin):
    """
    Functions to stand up an SSHD server to serve up git repos for tests.
    """

    sshd_proc = None
    prep_states_ran = False
    known_hosts_setup = False

    @classmethod
    def setUpClass(cls):  # pylint: disable=arguments-differ
        super().setUpClass()
        try:
            log.info("%s: prep_server()", cls.__name__)
            cls.sshd_bin = salt.utils.path.which("sshd")
            cls.sshd_config_dir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
            cls.sshd_config = os.path.join(cls.sshd_config_dir, "sshd_config")
            cls.sshd_port = get_unused_localhost_port(cached_seconds=120)
            cls.url = "ssh://{username}@127.0.0.1:{port}/~/repo.git".format(
                username=cls.username, port=cls.sshd_port
            )
            cls.url_extra_repo = "ssh://{username}@127.0.0.1:{port}/~/extra_repo.git".format(
                username=cls.username, port=cls.sshd_port
            )
            home = "/root/.ssh"
            cls.ext_opts = {
                "url": cls.url,
                "url_extra_repo": cls.url_extra_repo,
                "privkey_nopass": os.path.join(home, cls.id_rsa_nopass),
                "pubkey_nopass": os.path.join(home, cls.id_rsa_nopass + ".pub"),
                "privkey_withpass": os.path.join(home, cls.id_rsa_withpass),
                "pubkey_withpass": os.path.join(home, cls.id_rsa_withpass + ".pub"),
                "passphrase": cls.passphrase,
            }

            if cls.prep_states_ran is False:
                ret = cls.cls_run_function(
                    "state.apply",
                    mods="git_pillar.ssh",
                    pillar={
                        "git_pillar": {
                            "git_ssh": cls.git_ssh,
                            "id_rsa_nopass": cls.id_rsa_nopass,
                            "id_rsa_withpass": cls.id_rsa_withpass,
                            "sshd_bin": cls.sshd_bin,
                            "sshd_port": cls.sshd_port,
                            "sshd_config_dir": cls.sshd_config_dir,
                            "master_user": cls.user,
                            "user": cls.username,
                        }
                    },
                )
                assert next(iter(ret.values()))["result"] is True
                cls.prep_states_ran = True
                log.info("%s: States applied", cls.__name__)
            if cls.sshd_proc is not None:
                if not psutil.pid_exists(cls.sshd_proc.pid):
                    log.info(
                        "%s: sshd started but appears to be dead now. Will try to restart it.",
                        cls.__name__,
                    )
                    cls.sshd_proc = None
            if cls.sshd_proc is None:
                cls.sshd_proc = start_daemon(
                    cls.sshd_bin,
                    SshdDaemon,
                    config_dir=pathlib.Path(cls.sshd_config_dir),
                    serve_port=cls.sshd_port,
                )
                log.info("%s: sshd started", cls.__name__)
        except AssertionError:
            cls.tearDownClass()
            raise

        if cls.known_hosts_setup is False:
            known_hosts_ret = cls.cls_run_function(
                "ssh.set_known_host",
                user=cls.user,
                hostname="127.0.0.1",
                port=cls.sshd_port,
                enc="ssh-rsa",
                fingerprint="fd:6f:7f:5d:06:6b:f2:06:0d:26:93:9e:5a:b5:19:46",
                hash_known_hosts=False,
                fingerprint_hash_type="md5",
            )
            if "error" in known_hosts_ret:
                cls.tearDownClass()
                raise AssertionError(
                    "Failed to add key to {} user's known_hosts "
                    "file: {}".format(cls.master_opts["user"], known_hosts_ret["error"])
                )
            cls.known_hosts_setup = True

    @classmethod
    def tearDownClass(cls):
        if cls.sshd_proc is not None:
            log.info(
                "[%s] Stopping %s",
                cls.sshd_proc.get_log_prefix(),
                cls.sshd_proc.__class__.__name__,
            )
            terminate_process(cls.sshd_proc.pid, kill_children=True, slow_stop=True)
            log.info(
                "[%s] %s stopped",
                cls.sshd_proc.get_log_prefix(),
                cls.sshd_proc.__class__.__name__,
            )
            cls.sshd_proc = None
        if cls.prep_states_ran:
            ret = cls.cls_run_function(
                "state.single", "user.absent", name=cls.username, purge=True
            )
            try:
                if ret and "minion" in ret:
                    ret_data = next(iter(ret["minion"].values()))
                    if not ret_data["result"]:
                        log.warning("Failed to delete test account %s", cls.username)
            except KeyError:
                log.warning(
                    "Failed to delete test account. Salt return:\n%s",
                    pprint.pformat(ret),
                )
            cls.prep_states_ran = False
            cls.known_hosts_setup = False
        shutil.rmtree(cls.sshd_config_dir, ignore_errors=True)
        ssh_dir = os.path.expanduser("~/.ssh")
        for filename in (
            cls.id_rsa_nopass,
            cls.id_rsa_nopass + ".pub",
            cls.id_rsa_withpass,
            cls.id_rsa_withpass + ".pub",
            cls.git_ssh,
        ):
            try:
                os.remove(os.path.join(ssh_dir, filename))
            except OSError as exc:
                if exc.errno != errno.ENOENT:
                    raise
        super().tearDownClass()


class WebserverMixin(SaltClientMixin, SaltReturnAssertsMixin):
    """
    Functions to stand up an nginx + uWSGI + git-http-backend webserver to
    serve up git repos for tests.
    """

    nginx_proc = uwsgi_proc = None
    prep_states_ran = False

    @classmethod
    def setUpClass(cls):  # pylint: disable=arguments-differ
        """
        Set up all the webserver paths. Designed to be run once in a
        setUpClass function.
        """
        super().setUpClass()
        cls.root_dir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        cls.config_dir = os.path.join(cls.root_dir, "config")
        cls.nginx_conf = os.path.join(cls.config_dir, "nginx.conf")
        cls.uwsgi_conf = os.path.join(cls.config_dir, "uwsgi.yml")
        cls.git_dir = os.path.join(cls.root_dir, "git")
        cls.repo_dir = os.path.join(cls.git_dir, "repos")
        cls.venv_dir = os.path.join(cls.root_dir, "venv")
        cls.uwsgi_bin = os.path.join(cls.venv_dir, "bin", "uwsgi")
        cls.nginx_port = cls.uwsgi_port = get_unused_localhost_port(cached_seconds=120)
        cls.uwsgi_port = get_unused_localhost_port(cached_seconds=120)
        cls.url = "http://127.0.0.1:{port}/repo.git".format(port=cls.nginx_port)
        cls.url_extra_repo = "http://127.0.0.1:{port}/extra_repo.git".format(
            port=cls.nginx_port
        )
        cls.ext_opts = {"url": cls.url, "url_extra_repo": cls.url_extra_repo}
        # Add auth params if present (if so this will trigger the spawned
        # server to turn on HTTP basic auth).
        for credential_param in ("user", "password"):
            if hasattr(cls, credential_param):
                cls.ext_opts[credential_param] = getattr(cls, credential_param)
        auth_enabled = hasattr(cls, "username") and hasattr(cls, "password")
        pillar = {
            "git_pillar": {
                "config_dir": cls.config_dir,
                "git_dir": cls.git_dir,
                "venv_dir": cls.venv_dir,
                "root_dir": cls.root_dir,
                "nginx_port": cls.nginx_port,
                "uwsgi_port": cls.uwsgi_port,
                "auth_enabled": auth_enabled,
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
            cls.tearDownClass()
            raise AssertionError(
                "{} not found. Either git is not installed, or the test "
                "class needs to be updated.".format(git_core)
            )

        pillar["git_pillar"]["git-http-backend"] = os.path.join(
            git_core, "git-http-backend"
        )
        try:
            if cls.prep_states_ran is False:
                ret = cls.cls_run_function(
                    "state.apply", mods="git_pillar.http", pillar=pillar
                )
                assert next(iter(ret.values()))["result"] is True
                cls.prep_states_ran = True
                log.info("%s: States applied", cls.__name__)
            if cls.uwsgi_proc is not None:
                if not psutil.pid_exists(cls.uwsgi_proc.pid):
                    log.warning(
                        "%s: uWsgi started but appears to be dead now. Will try to restart it.",
                        cls.__name__,
                    )
                    cls.uwsgi_proc = None
            if cls.uwsgi_proc is None:
                cls.uwsgi_proc = start_daemon(
                    cls.uwsgi_bin,
                    UwsgiDaemon,
                    config_dir=cls.config_dir,
                    check_port=cls.uwsgi_port,
                )
                log.info("%s: %s started", cls.__name__, cls.uwsgi_bin)
            if cls.nginx_proc is not None:
                if not psutil.pid_exists(cls.nginx_proc.pid):
                    log.warning(
                        "%s: nginx started but appears to be dead now. Will try to restart it.",
                        cls.__name__,
                    )
                    cls.nginx_proc = None
            if cls.nginx_proc is None:
                cls.nginx_proc = start_daemon(
                    "nginx",
                    NginxDaemon,
                    config_dir=cls.config_dir,
                    check_port=cls.nginx_port,
                )
                log.info("%s: nginx started", cls.__name__)
        except AssertionError:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        if cls.nginx_proc is not None:
            log.info(
                "[%s] Stopping %s",
                cls.nginx_proc.get_log_prefix(),
                cls.nginx_proc.__class__.__name__,
            )
            terminate_process(cls.nginx_proc.pid, kill_children=True, slow_stop=True)
            log.info(
                "[%s] %s stopped",
                cls.nginx_proc.get_log_prefix(),
                cls.nginx_proc.__class__.__name__,
            )
            cls.nginx_proc = None
        if cls.uwsgi_proc is not None:
            log.info(
                "[%s] Stopping %s",
                cls.uwsgi_proc.get_log_prefix(),
                cls.uwsgi_proc.__class__.__name__,
            )
            terminate_process(cls.uwsgi_proc.pid, kill_children=True, slow_stop=True)
            log.info(
                "[%s] %s stopped",
                cls.uwsgi_proc.get_log_prefix(),
                cls.uwsgi_proc.__class__.__name__,
            )
            cls.uwsgi_proc = None
        shutil.rmtree(cls.root_dir, ignore_errors=True)
        cls.prep_states_ran = False
        super().tearDownClass()


class GitTestBase(ModuleCase):
    """
    Base class for all gitfs/git_pillar tests. Must be subclassed and paired
    with either SSHDMixin or WebserverMixin to provide the server.
    """

    maxDiff = None
    git_opts = '-c user.name="Foo Bar" -c user.email=foo@bar.com'
    ext_opts = {}

    def make_repo(self, root_dir, user="root"):
        raise NotImplementedError()


class GitFSTestBase(GitTestBase, LoaderModuleMockMixin):
    """
    Base class for all gitfs tests
    """

    @requires_system_grains
    def setup_loader_modules(self, grains):  # pylint: disable=W0221
        return {gitfs: {"__opts__": copy.copy(_OPTS), "__grains__": grains}}

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
        return {git_pillar: {"__opts__": copy.copy(_OPTS), "__grains__": grains}}

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


class GitPillarSSHTestBase(GitPillarTestBase, SSHDMixin):
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


class GitPillarHTTPTestBase(GitPillarTestBase, WebserverMixin):
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
