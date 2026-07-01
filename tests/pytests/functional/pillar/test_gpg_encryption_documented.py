"""
Round-trip GPG encryption examples from the pillar encryption documentation.

These tests cover the issues:

- 62733 (shebang renderer ``#!yaml|gpg`` for per-file decryption)
- 65682 (``--homedir`` must be passed to ``gpg`` when encrypting)
- 59539 (GPG terminology consistency: encrypted block markers are
  ``BEGIN PGP MESSAGE``)

The tests prove that the documented command-line invocations actually
produce ciphertexts that the gpg renderer can decrypt.  A fresh,
short-lived keypair is generated inside a tmp homedir for each test
module so the round-trip exercises real encrypt + decrypt.
"""

import logging
import pathlib
import shutil
import subprocess
import textwrap

import pytest

import salt.pillar

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.skip_if_binaries_missing("gpg"),
    pytest.mark.requires_random_entropy,
    pytest.mark.slow_test,
]


GEN_BATCH = textwrap.dedent(
    """\
    %no-protection
    Key-Type: RSA
    Key-Length: 2048
    Subkey-Type: RSA
    Subkey-Length: 2048
    Name-Real: Salt Pillar Doctest
    Name-Email: doctest@salt.example
    Expire-Date: 0
    %commit
    """
)
TEST_RECIPIENT = "doctest@salt.example"


@pytest.fixture(scope="module", autouse=True)
def gpg_homedir(salt_master):
    """
    Tmp gpg homedir loaded with a freshly generated keypair.

    The documented setup uses ``/etc/salt/gpgkeys`` and ``--homedir`` is
    passed for every gpg command.  We do the same here but rooted at the
    salt-master config dir so cleanup is automatic.
    """
    _gpg_homedir = pathlib.Path(salt_master.config_dir) / "gpgkeys"
    _gpg_homedir.mkdir(0o700)
    agent_started = False
    try:
        cmd_prefix = ["gpg", "--homedir", str(_gpg_homedir)]

        proc = subprocess.run(
            cmd_prefix + ["--list-keys"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=True,
            text=True,
        )
        log.debug("Instantiating gpg keyring: %s", proc.stdout)

        proc = subprocess.run(
            cmd_prefix + ["--batch", "--gen-key"],
            capture_output=True,
            check=True,
            text=True,
            input=GEN_BATCH,
        )
        log.debug("Generated keypair: %s %s", proc.stdout, proc.stderr)

        agent_started = True
        yield _gpg_homedir
    finally:
        if agent_started:
            try:
                subprocess.run(
                    ["gpg-connect-agent", "--homedir", str(_gpg_homedir)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    check=True,
                    text=True,
                    input="KILLAGENT",
                )
            except (OSError, subprocess.CalledProcessError):
                log.debug("No need to kill: old gnupg doesn't start the agent.")
        shutil.rmtree(str(_gpg_homedir), ignore_errors=True)


def _encrypt(plaintext, gpg_homedir):
    """
    Run the gpg encryption command that the docs prescribe and return the
    armored ciphertext.

    The documented command is::

        echo -n 'supersecret' | gpg --homedir /etc/salt/gpgkeys \\
            --trust-model always --armor --batch \\
            --encrypt -r <KEY-ID>

    The fix in issue 65682 was that the doc had to pass ``--homedir`` for
    the command to succeed when running as a non-root user.  Without it,
    gpg looks up the recipient in ``~/.gnupg`` and fails with
    ``encryption failed: No public key``.
    """
    cmd = [
        "gpg",
        "--homedir",
        str(gpg_homedir),
        "--armor",
        "--batch",
        "--trust-model",
        "always",
        "--encrypt",
        "-r",
        TEST_RECIPIENT,
    ]
    proc = subprocess.run(
        cmd,
        input=plaintext,
        capture_output=True,
        check=True,
        text=True,
    )
    return proc.stdout


def test_doc_encrypt_command_round_trip(
    salt_master, grains, gpg_homedir, pillar_state_tree
):
    """
    Encrypt with the exact command line documented in the renderers
    section, then round-trip the ciphertext through the pillar GPG
    decryption flow.

    Validates fix for issue 65682: passing ``--homedir`` is required for
    the documented encrypt command to succeed.
    """
    plaintext = "supersecret"
    ciphertext = _encrypt(plaintext, gpg_homedir)

    assert ciphertext.startswith("-----BEGIN PGP MESSAGE-----")
    assert ciphertext.rstrip().endswith("-----END PGP MESSAGE-----")

    indented = textwrap.indent(ciphertext.rstrip("\n"), "      ")
    sls_body = "secrets:\n" "  vault:\n" "    api_key: |\n" + indented + "\n"

    top_sls = "base:\n  '*':\n    - gpg\n"
    with pytest.helpers.temp_file(
        "top.sls", top_sls, pillar_state_tree
    ), pytest.helpers.temp_file("gpg.sls", sls_body, pillar_state_tree):
        opts = salt_master.config.copy()
        opts["decrypt_pillar"] = ["secrets:vault"]
        pillar_obj = salt.pillar.Pillar(opts, grains, "test", "base")
        ret = pillar_obj.compile_pillar()

    assert ret["secrets"]["vault"]["api_key"] == plaintext


def test_doc_shebang_renderer_decrypts(
    salt_master, grains, gpg_homedir, pillar_state_tree
):
    """
    Validate fix for issue 62733: a pillar file with a ``#!yaml|gpg``
    shebang has its GPG-encrypted scalars decrypted at compile time
    without needing ``decrypt_pillar`` to be configured on the master.
    """
    plaintext = "supersecret"
    ciphertext = _encrypt(plaintext, gpg_homedir)

    indented = textwrap.indent(ciphertext.rstrip("\n"), "    ")
    sls_body = "#!yaml|gpg\n\napi_key: |\n" + indented + "\n"

    top_sls = "base:\n  '*':\n    - gpg\n"
    with pytest.helpers.temp_file(
        "top.sls", top_sls, pillar_state_tree
    ), pytest.helpers.temp_file("gpg.sls", sls_body, pillar_state_tree):
        opts = salt_master.config.copy()
        # Note: NO decrypt_pillar config; the shebang alone must do the work.
        pillar_obj = salt.pillar.Pillar(opts, grains, "test", "base")
        ret = pillar_obj.compile_pillar()

    assert ret.get("api_key") == plaintext
