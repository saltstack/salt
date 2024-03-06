import logging
import pathlib
import shutil
import subprocess
import textwrap

import pytest
from pytestshellutils.utils.processes import ProcessResult

log = logging.getLogger(__name__)


# The following fixtures are copied from pytests/functional/pillar/test_gpg.py


@pytest.fixture(scope="module")
def test_key():
    """
    Private key for setting up GPG pillar environment.
    """
    return textwrap.dedent(
        """\
        -----BEGIN PGP PRIVATE KEY BLOCK-----

        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
        =06Tz
        -----END PGP PRIVATE KEY BLOCK-----
        """
    )


@pytest.fixture(scope="module")
def gpg_pillar_yaml():
    """
    Yaml data for testing GPG pillar.
    """
    return textwrap.dedent(
        """
        #!yaml|gpg
        secrets:
          foo: |
            -----BEGIN PGP MESSAGE-----

            hQEMAw2B674HRhwSAQgAhTrN8NizwUv/VunVrqa4/X8t6EUulrnhKcSeb8sZS4th
            W1Qz3K2NjL4lkUHCQHKZVx/VoZY7zsddBIFvvoGGfj8+2wjkEDwFmFjGE4DEsS74
            ZLRFIFJC1iB/O0AiQ+oU745skQkU6OEKxqavmKMrKo3rvJ8ZCXDC470+i2/Hqrp7
            +KWGmaDOO422JaSKRm5D9bQZr9oX7KqnrPG9I1+UbJyQSJdsdtquPWmeIpamEVHb
            VMDNQRjSezZ1yKC4kCWm3YQbBF76qTHzG1VlLF5qOzuGI9VkyvlMaLfMibriqY73
            zBbPzf6Bkp2+Y9qyzuveYMmwS4sEOuZL/PetqisWe9JGAWD/O+slQ2KRu9hNww06
            KMDPJRdyj5bRuBVE4hHkkP23KrYr7SuhW2vpe7O/MvWEJ9uDNegpMLhTWruGngJh
            iFndxegN9w==
            =bAuo
            -----END PGP MESSAGE-----
        """
    )


@pytest.fixture(scope="module")
def gpg_homedir(salt_master, test_key):
    """
    Setup gpg environment
    """
    _gpg_homedir = pathlib.Path(salt_master.config_dir) / "gpgkeys"
    _gpg_homedir.mkdir(0o700)
    agent_started = False
    try:
        cmd_prefix = ["gpg", "--homedir", str(_gpg_homedir)]

        cmd = cmd_prefix + ["--list-keys"]
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=True,
            text=True,
        )
        ret = ProcessResult(
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr or "",
            cmdline=proc.args,
        )
        log.debug("Instantiating gpg keyring...\n%s", ret)

        cmd = cmd_prefix + ["--import", "--allow-secret-key-import"]
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=True,
            text=True,
            input=test_key,
        )
        ret = ProcessResult(
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr or "",
            cmdline=proc.args,
        )
        log.debug("Importing keypair...:\n%s", ret)

        agent_started = True

        yield _gpg_homedir
    finally:
        if agent_started:
            try:
                cmd = ["gpg-connect-agent", "--homedir", str(_gpg_homedir)]
                proc = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    check=True,
                    text=True,
                    input="KILLAGENT",
                )
                ret = ProcessResult(
                    returncode=proc.returncode,
                    stdout=proc.stdout,
                    stderr=proc.stderr or "",
                    cmdline=proc.args,
                )
                log.debug("Killed gpg-agent...\n%s", ret)
            except (OSError, subprocess.CalledProcessError):
                log.debug("No need to kill: old gnupg doesn't start the agent.")
        shutil.rmtree(str(_gpg_homedir), ignore_errors=True)


@pytest.fixture(scope="module")
def pillar_setup(base_env_pillar_tree_root_dir, gpg_pillar_yaml, salt_minion):
    """
    Setup gpg pillar
    """
    saltutil_contents = f"""
    saltutil: {{{{ salt["saltutil.runner"]("mine.get", tgt="{salt_minion.id}", fun="test.ping") | json }}}}
    """
    top_file_contents = """
    base:
      '*':
        - gpg
        - saltutil
    """
    with pytest.helpers.temp_file(
        "top.sls", top_file_contents, base_env_pillar_tree_root_dir
    ), pytest.helpers.temp_file(
        "gpg.sls", gpg_pillar_yaml, base_env_pillar_tree_root_dir
    ), pytest.helpers.temp_file(
        "saltutil.sls", saltutil_contents, base_env_pillar_tree_root_dir
    ):
        yield


@pytest.mark.skip_if_binaries_missing("gpg")
@pytest.mark.usefixtures("pillar_setup", "gpg_homedir")
def test_gpg_pillar(salt_ssh_cli):
    """
    Ensure that GPG-encrypted pillars can be decrypted, i.e. the
    gpg_keydir should not be overridden. This is issue #60002,
    which has the same cause as the one below.
    """
    ret = salt_ssh_cli.run("pillar.items")
    assert ret.returncode == 0
    assert isinstance(ret.data, dict)
    assert ret.data
    _assert_gpg_pillar(ret.data)


def _assert_gpg_pillar(ret):
    assert "secrets" in ret
    assert "foo" in ret["secrets"]
    assert "BEGIN PGP MESSAGE" not in ret["secrets"]["foo"]
    assert ret["secrets"]["foo"] == "supersecret"
    assert "_errors" not in ret


@pytest.mark.usefixtures("pillar_setup")
def test_saltutil_runner(salt_ssh_cli, salt_minion):
    """
    Ensure that during pillar compilation, the cache dir is not
    overridden. For a history, see PR #50489 and issue #36796,
    notice that the initial description is probably unrelated
    to this.
    """
    ret = salt_ssh_cli.run("pillar.items")
    assert ret.returncode == 0
    assert isinstance(ret.data, dict)
    assert ret.data
    _assert_saltutil_runner_pillar(ret.data, salt_minion.id)


def _assert_saltutil_runner_pillar(ret, salt_minion_id):
    assert "saltutil" in ret
    assert isinstance(ret["saltutil"], dict)
    assert ret["saltutil"]
    assert salt_minion_id in ret["saltutil"]
    assert ret["saltutil"][salt_minion_id] is True
    assert "_errors" not in ret


@pytest.mark.skip_if_binaries_missing("gpg")
@pytest.mark.usefixtures("pillar_setup", "gpg_homedir")
def test_gpg_pillar_orch(salt_ssh_cli, salt_run_cli):
    """
    Ensure that GPG-encrypted pillars can be decrypted when Salt-SSH is
    called during an orchestration or via saltutil.cmd.
    This is issue #65670.
    """
    # Use salt_run_cli since the config paths are different between
    # test master and test minion.
    ret = salt_run_cli.run(
        "salt.cmd",
        "saltutil.cmd",
        salt_ssh_cli.target_host,
        "pillar.items",
        ssh=True,
        roster_file=str(salt_ssh_cli.roster_file),
        ssh_priv=str(salt_ssh_cli.client_key),
    )
    assert ret.returncode == 0
    assert isinstance(ret.data, dict)
    assert ret.data
    _assert_gpg_pillar(ret.data[salt_ssh_cli.target_host]["return"])


@pytest.mark.usefixtures("pillar_setup")
def test_saltutil_runner_orch(salt_ssh_cli, salt_run_cli, salt_minion):
    """
    Ensure that runner calls in the pillar succeed when Salt-SSH is
    called during an orchestration or via saltutil.cmd.
    This is a variant of issue #65670.
    """
    # Use salt_run_cli since the config paths are different between
    # test master and test minion.
    ret = salt_run_cli.run(
        "salt.cmd",
        "saltutil.cmd",
        salt_ssh_cli.target_host,
        "pillar.items",
        ssh=True,
        roster_file=str(salt_ssh_cli.roster_file),
        ssh_priv=str(salt_ssh_cli.client_key),
    )
    assert ret.returncode == 0
    assert isinstance(ret.data, dict)
    assert ret.data
    _assert_saltutil_runner_pillar(
        ret.data[salt_ssh_cli.target_host]["return"], salt_minion.id
    )
