import logging
import os
import re
import tempfile
import textwrap
import time
from typing import Optional

import attr
import importlib_metadata
import pytest
import saltfactories.cli.salt
from pytestshellutils.utils import ports
from saltfactories.daemons.container import SaltMinion
from saltfactories.utils import random_string

import salt.utils.yaml
from tests.support.runtests import RUNTIME_VARS

_outarg_regex = re.compile(r"^--out(?:put)?(?:=(.*))?$")
log = logging.getLogger(__name__)


@attr.s(kw_only=True)
class Salt(saltfactories.cli.salt.Salt):
    """``salt`` command-line factory that defaults to YAML instead of JSON.

    Unlike JSON, YAML supports bytes objects via the ``!!binary`` tag.

    TODO: Modify saltfactories.bases.SaltCli to support --out=yaml and delete
    this class.
    """

    out: str = "yaml"
    minion_tgt: Optional[str] = None

    def cmdline(self, *args, minion_tgt=None, **kwargs):
        self.minion_tgt = minion_tgt
        has_out = False
        for i, arg in enumerate(args):
            m = _outarg_regex.fullmatch(arg)
            if not m:
                continue
            has_out = True
            fmt = m.group(1)
            arg_next = args[i + 1] if len(args) > i else None
            self.out = fmt if fmt is not None else arg_next
            if not self.out:
                raise ValueError("missing outputter name")
            break
        if not has_out:
            args = ["--out", self.out] + list(args)
        return super().cmdline(*args, minion_tgt=minion_tgt, **kwargs)

    def process_output(self, stdout, stderr, cmdline=None):
        try:
            obj = self._decode(stdout)
        except NotImplementedError:
            return super().process_output(stdout, stderr, cmdline)
        t = self.minion_tgt
        if t is not None and t != "*" and not isinstance(obj, str) and t in obj:
            obj = obj[t]
        return (stdout, stderr, obj)

    def _decode(self, out):
        if self.out != "yaml":
            raise NotImplementedError(f"unsupported outputter: {self.out!r}")
        # yaml.load() (when using CLoader at least) does not accept subclasses
        # of str or bytes, but out is probably a
        # pytestshellutils.utils.processes.MatchString which is a subclass of
        # str.  Convert subclasses of str/bytes to actual str/bytes objects.
        if isinstance(out, str) and type(out) != str:
            out = str(out)
        elif isinstance(out, bytes) and type(out) != bytes:
            out = bytes(out)
        return salt.utils.yaml.load(out)


@pytest.fixture(scope="module")
def salt_yaml_cli(salt_master):
    assert salt_master.is_running()
    return salt_master.salt_cli(factory_class=Salt)


@attr.s(kw_only=True, slots=True)
class SlapdMinion(SaltMinion):
    """Minion in a Docker container with OpenLDAP installed and running."""

    base: str = "dc=example,dc=org"
    password: str = "adminpassword"
    port: int = attr.ib(default=attr.Factory(ports.get_unused_localhost_port))
    user: str = "admin"

    @property
    def userdn(self) -> str:
        return f"cn={self.user},{self.base}"

    @property
    def uri(self) -> str:
        """LDAP URI for use inside and outside the container.

        This URI works both inside and outside because the network mode is set
        to "host".
        """
        return f"ldap://localhost:{self.port}"

    @property
    def connect_spec(self):
        return {
            "url": self.uri,
            "bind": {
                "method": "simple",
                "dn": self.userdn,
                "password": self.password,
            },
        }

    @classmethod
    def default_config(cls, *args, **kwargs):
        cfg = super().default_config(*args, **kwargs)

        # Requirements on the minion daemon user:
        #
        #   * The `RUNTIME_VARS.CODE_DIR` directory must be readable by the
        #     minion daemon user, otherwise Python will fail to import required
        #     modules during minion start-up.
        #
        #   * As of 2022-10-05, the minion code requires the minion daemon user
        #     to have an entry in the password database (`/etc/passwd`).
        #
        # The current user (`os.getuid()`) can access `RUNTIME_VARS.CODE_DIR`,
        # but is unlikely to have an entry in the Docker container's password
        # database.  We could pick a user that is known to exist in the image,
        # but that user might not have access to `RUNTIME_VARS.CODE_DIR`.  The
        # easiest way to ensure that both requirements are satisfied is to run
        # the minion as root.  If the password database entry requirement is
        # removed, the minion can be run as the current user by replacing
        # `"root"` here with `os.getuid()` and changing `cmdline()` to pass
        # `["--user", f"{os.getuid()}:{os.getgid()}"]`.
        cfg.setdefault("user", "root")

        return cfg

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.container_run_kwargs.setdefault("environment", {}).update(
            {
                "LDAP_ADMIN_PASSWORD": self.password,
                "LDAP_ADMIN_USERNAME": self.user,
                "LDAP_PORT_NUMBER": self.port,
                "LDAP_ROOT": self.base,
            },
        )
        # Note that the target directories have the same names as the source
        # directories.  This avoids the need to translate path names.
        self.container_run_kwargs.setdefault("volumes", {}).update(
            {
                # Bind mount the checked-out source code into the Docker
                # container so that a minion daemon started inside the container
                # will run the code to be tested.
                RUNTIME_VARS.CODE_DIR: {
                    "bind": RUNTIME_VARS.CODE_DIR,
                    "mode": "z",
                },
                RUNTIME_VARS.TMP: {"bind": RUNTIME_VARS.TMP, "mode": "z"},
            },
        )
        # Use host network mode so that we don't have to define a network and
        # configure the minion with the master's IP address (we can simply use
        # localhost).  Note that port mapping (the "ports" option) is not
        # applicable in host mode.
        self.container_run_kwargs["network_mode"] = "host"
        self.check_ports[self.port] = self.port
        self.container_start_check(self.__start_check)

    def __run_unpriv(self, args):
        ret = self.run(*args, user=f"{os.getuid()}:{os.getgid()}")
        cmd_str = " ".join(args)
        msg = f"command '{cmd_str}' returned {ret.returncode}"
        if ret.stdout:
            msg += f"\n  >>>>> STDOUT >>>>>\n{ret.stdout}"
            if not msg.endswith("\n"):
                msg += "\n"
            msg += "  <<<<< STDOUT <<<<<"
        if ret.stderr:
            msg += f"\n  >>>>> STDERR >>>>>\n{ret.stderr}"
            if not msg.endswith("\n"):
                msg += "\n"
            msg += "  <<<<< STDERR <<<<<"
        if ret.returncode != 0:
            raise Exception(msg)
        log.debug(msg)
        return ret

    def __slapd_running(self) -> bool:
        try:
            self.__run_unpriv(
                [
                    "ldapsearch",
                    "-H",
                    self.uri,
                    "-x",
                    "-D",
                    self.userdn,
                    "-w",
                    self.password,
                    "-b",
                    self.base,
                ],
            )
            log.debug("slapd is running")
            return True
        except Exception as ex:  # pylint: disable=broad-except
            log.debug(ex)
        log.debug("slapd is not running yet")
        return False

    def __start_check(self, timeout_at) -> bool:
        while time.time() <= timeout_at:
            if self.__slapd_running():
                return True
            time.sleep(1)
        return False

    def cmdline(self, *args):
        cmd = list(super().cmdline(*args))
        # See the comment in `default_config()` for why the minion runs as root.
        cmd[2:2] = ["--user", "0:0"]
        return cmd

    def ldapadd(self, ldif):
        if isinstance(ldif, str):
            ldif = ldif.encode()
        tmpf = tempfile.NamedTemporaryFile(dir=RUNTIME_VARS.TMP, suffix=".ldif")
        with tmpf as f:
            f.write(ldif)
            f.flush()
            self.__run_unpriv(["cat", f.name])
            self.__run_unpriv(
                [
                    "ldapadd",
                    "-H",
                    self.uri,
                    "-x",
                    "-D",
                    self.userdn,
                    "-w",
                    self.password,
                    "-f",
                    # RUNTIME_VARS.TMP is bind-mounted to RUNTIME_VARS.TMP so
                    # the path name is the same inside and outside the
                    # container.
                    f.name,
                ],
            )

    def ldapdelete(self, *dns, recursive=False):
        cmd = [
            "ldapdelete",
            "-H",
            self.uri,
            "-x",
            "-D",
            self.userdn,
            "-w",
            self.password,
        ]
        if recursive:
            cmd.append("-r")
        cmd.extend(dns)
        self.__run_unpriv(cmd)


@pytest.fixture(scope="module")
def openldap_minion(salt_master, salt_yaml_cli, salt_key_cli):
    name = random_string("openldap-minion-")
    c = salt_master.salt_minion_daemon(
        name,
        image="ghcr.io/saltstack/salt-ci-containers/openldap-minion:latest",
        factory_class=SlapdMinion,
        pull_before_start=True,
        skip_on_pull_failure=True,
        skip_if_docker_client_not_connectable=True,
    )
    # For some reason passing this as an argument to the salt_minion_daemon()
    # call above fails with "TypeError: type object got multiple values for
    # keyword argument 'python_executable'".
    c.python_executable = "python3"

    # Workaround for:
    # https://github.com/saltstack/pytest-salt-factories/issues/139
    def _after_start():
        v = importlib_metadata.version("pytest-salt-factories")
        for cmd in [
            ("install_packages", "python3-pip"),
            ("pip", "install", f"pytest-salt-factories=={v}"),
        ]:
            ret = c.run(*cmd, user="0:0")
            assert ret.returncode == 0, ret
    c.after_start(_after_start)

    log.debug(f"starting OpenLDAP minion container {name}...")
    with c.started():
        assert c.is_running()
        ret = salt_yaml_cli.run("test.ping", minion_tgt=c.id)
        assert ret.returncode == 0, ret
        assert ret.data is True
        yield c
        log.debug(f"stopping OpenLDAP minion container {name}...")
    assert not c.is_running()
    salt_key_cli.run("-y", "-d", c.id)
    log.debug(f"OpenLDAP minion container {name} stopped")


@pytest.fixture(scope="module")
def openldap_minion_run(openldap_minion, salt_yaml_cli):
    def _run(fn, *args, **kwargs):
        if fn.startswith("ldap3."):
            kwargs.setdefault("connect_spec", openldap_minion.connect_spec)
        ret = salt_yaml_cli.run(
            fn,
            *args,
            minion_tgt=openldap_minion.id,
            **kwargs,
        )
        assert ret.returncode == 0, ret
        return ret.data

    yield _run


@pytest.fixture(scope="module")
def openldap_minion_apply(salt_master, openldap_minion, openldap_minion_run):
    def _apply(fn, **kwargs):
        has_name = "name" in kwargs
        name = kwargs.pop("name", "x")
        if fn.startswith("ldap."):
            kwargs.setdefault("connect_spec", openldap_minion.connect_spec)
        sls_data = {
            name: {
                fn: [{k: v} for k, v in kwargs.items()],
            },
        }
        sls_yaml = salt.utils.yaml.dump(sls_data)
        with salt_master.state_tree.base.temp_file("test_state.sls", sls_yaml):
            ret = openldap_minion_run("state.apply", "test_state")
            # Normalize the return value for easier checking.
            assert len(ret) == 1
            (ret,) = ret.values()
            assert ret["name"] == name
            entries = ["changes", "comment", "result"]
            if has_name:
                entries.append("name")
            ret = {k: ret[k] for k in entries if k in ret}
            return ret

    yield _apply


@pytest.fixture
def subtree(openldap_minion, request):
    dc = request.function.__name__
    dn = f"dc={dc},{openldap_minion.base}"
    log.debug(f"Creating and populating temporary subtree {dn}...")
    openldap_minion.ldapadd(
        textwrap.dedent(
            f"""\
                dn: {dn}
                objectClass: dcObject
                objectClass: organization
                dc: {dc}
                o: {dc}

                dn: cn=u0,{dn}
                objectClass: person
                cn: u0
                sn: Lastname
                description: desc
                description: another desc
            """,
        ),
    )
    log.debug("Created temporary subtree")
    yield dn
    log.debug("Cleaning up temporary subtree...")
    openldap_minion.ldapdelete(dn, recursive=True)
    log.debug("Temporary subtree cleaned up")


@pytest.fixture
def u0dn(subtree):
    yield f"cn=u0,{subtree}"
