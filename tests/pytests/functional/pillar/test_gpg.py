import copy
import logging
import pathlib
import shutil
import subprocess
import textwrap

import pytest
from pytestshellutils.utils.processes import ProcessResult

import salt.pillar
import salt.utils.stringutils

pytestmark = [
    pytest.mark.skip_if_binaries_missing("gpg"),
    pytest.mark.requires_random_entropy,
]

log = logging.getLogger(__name__)


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
        """\
        secrets:
          vault:
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
            bar: this was unencrypted already
            baz: |
              -----BEGIN PGP MESSAGE-----

              hQEMAw2B674HRhwSAQf+Ne+IfsP2IcPDrUWct8sTJrga47jQvlPCmO+7zJjOVcqz
              gLjUKvMajrbI/jorBWxyAbF+5E7WdG9WHHVnuoywsyTB9rbmzuPqYCJCe+ZVyqWf
              9qgJ+oUjcvYIFmH3h7H68ldqbxaAUkAOQbTRHdr253wwaTIC91ZeX0SCj64HfTg7
              Izwk383CRWonEktXJpientApQFSUWNeLUWagEr/YPNFA3vzpPF5/Ia9X8/z/6oO2
              q+D5W5mVsns3i2HHbg2A8Y+pm4TWnH6mTSh/gdxPqssi9qIrzGQ6H1tEoFFOEq1V
              kJBe0izlfudqMq62XswzuRB4CYT5Iqw1c97T+1RqENJCASG0Wz8AGhinTdlU5iQl
              JkLKqBxcBz4L70LYWyHhYwYROJWjHgKAywX5T67ftq0wi8APuZl9olnOkwSK+wrY
              1OZi
              =7epf
              -----END PGP MESSAGE-----
            qux:
              - foo
              - bar
              - |
                -----BEGIN PGP MESSAGE-----

                hQEMAw2B674HRhwSAQgAg1YCmokrweoOI1c9HO0BLamWBaFPTMblOaTo0WJLZoTS
                ksbQ3OJAMkrkn3BnnM/djJc5C7vNs86ZfSJ+pvE8Sp1Rhtuxh25EKMqGOn/SBedI
                gR6N5vGUNiIpG5Tf3DuYAMNFDUqw8uY0MyDJI+ZW3o3xrMUABzTH0ew+Piz85FDA
                YrVgwZfqyL+9OQuu6T66jOIdwQNRX2NPFZqvon8liZUPus5VzD8E5cAL9OPxQ3sF
                f7/zE91YIXUTimrv3L7eCgU1dSxKhhfvA2bEUi+AskMWFXFuETYVrIhFJAKnkFmE
                uZx+O9R9hADW3hM5hWHKH9/CRtb0/cC84I9oCWIQPdI+AaPtICxtsD2N8Q98hhhd
                4M7I0sLZhV+4ZJqzpUsOnSpaGyfh1Zy/1d3ijJi99/l+uVHuvmMllsNmgR+ZTj0=
                =LrCQ
                -----END PGP MESSAGE-----
        """
    )


@pytest.fixture(scope="module")
def gpg_pillar_encrypted():
    """
    Pillar data structure with GPG blocks not decrypted.
    """
    return {
        "secrets": {
            "vault": {
                "foo": (
                    "-----BEGIN PGP MESSAGE-----\n"
                    "\n"
                    "hQEMAw2B674HRhwSAQgAhTrN8NizwUv/VunVrqa4/X8t6EUulrnhKcSeb8sZS4th\n"
                    "W1Qz3K2NjL4lkUHCQHKZVx/VoZY7zsddBIFvvoGGfj8+2wjkEDwFmFjGE4DEsS74\n"
                    "ZLRFIFJC1iB/O0AiQ+oU745skQkU6OEKxqavmKMrKo3rvJ8ZCXDC470+i2/Hqrp7\n"
                    "+KWGmaDOO422JaSKRm5D9bQZr9oX7KqnrPG9I1+UbJyQSJdsdtquPWmeIpamEVHb\n"
                    "VMDNQRjSezZ1yKC4kCWm3YQbBF76qTHzG1VlLF5qOzuGI9VkyvlMaLfMibriqY73\n"
                    "zBbPzf6Bkp2+Y9qyzuveYMmwS4sEOuZL/PetqisWe9JGAWD/O+slQ2KRu9hNww06\n"
                    "KMDPJRdyj5bRuBVE4hHkkP23KrYr7SuhW2vpe7O/MvWEJ9uDNegpMLhTWruGngJh\n"
                    "iFndxegN9w==\n"
                    "=bAuo\n"
                    "-----END PGP MESSAGE-----\n"
                ),
                "bar": "this was unencrypted already",
                "baz": (
                    "-----BEGIN PGP MESSAGE-----\n"
                    "\n"
                    "hQEMAw2B674HRhwSAQf+Ne+IfsP2IcPDrUWct8sTJrga47jQvlPCmO+7zJjOVcqz\n"
                    "gLjUKvMajrbI/jorBWxyAbF+5E7WdG9WHHVnuoywsyTB9rbmzuPqYCJCe+ZVyqWf\n"
                    "9qgJ+oUjcvYIFmH3h7H68ldqbxaAUkAOQbTRHdr253wwaTIC91ZeX0SCj64HfTg7\n"
                    "Izwk383CRWonEktXJpientApQFSUWNeLUWagEr/YPNFA3vzpPF5/Ia9X8/z/6oO2\n"
                    "q+D5W5mVsns3i2HHbg2A8Y+pm4TWnH6mTSh/gdxPqssi9qIrzGQ6H1tEoFFOEq1V\n"
                    "kJBe0izlfudqMq62XswzuRB4CYT5Iqw1c97T+1RqENJCASG0Wz8AGhinTdlU5iQl\n"
                    "JkLKqBxcBz4L70LYWyHhYwYROJWjHgKAywX5T67ftq0wi8APuZl9olnOkwSK+wrY\n"
                    "1OZi\n"
                    "=7epf\n"
                    "-----END PGP MESSAGE-----\n"
                ),
                "qux": [
                    "foo",
                    "bar",
                    "-----BEGIN PGP MESSAGE-----\n"
                    "\n"
                    "hQEMAw2B674HRhwSAQgAg1YCmokrweoOI1c9HO0BLamWBaFPTMblOaTo0WJLZoTS\n"
                    "ksbQ3OJAMkrkn3BnnM/djJc5C7vNs86ZfSJ+pvE8Sp1Rhtuxh25EKMqGOn/SBedI\n"
                    "gR6N5vGUNiIpG5Tf3DuYAMNFDUqw8uY0MyDJI+ZW3o3xrMUABzTH0ew+Piz85FDA\n"
                    "YrVgwZfqyL+9OQuu6T66jOIdwQNRX2NPFZqvon8liZUPus5VzD8E5cAL9OPxQ3sF\n"
                    "f7/zE91YIXUTimrv3L7eCgU1dSxKhhfvA2bEUi+AskMWFXFuETYVrIhFJAKnkFmE\n"
                    "uZx+O9R9hADW3hM5hWHKH9/CRtb0/cC84I9oCWIQPdI+AaPtICxtsD2N8Q98hhhd\n"
                    "4M7I0sLZhV+4ZJqzpUsOnSpaGyfh1Zy/1d3ijJi99/l+uVHuvmMllsNmgR+ZTj0=\n"
                    "=LrCQ\n"
                    "-----END PGP MESSAGE-----\n",
                ],
            },
        },
    }


@pytest.fixture(scope="module")
def gpg_pillar_decrypted():
    """
    Pillar data structure with GPG blocks decrypted.
    """
    return {
        "secrets": {
            "vault": {
                "foo": "supersecret",
                "bar": "this was unencrypted already",
                "baz": "rosebud",
                "qux": ["foo", "bar", "baz"],
            },
        },
    }


@pytest.fixture(scope="module")
def gpg_pillar_yaml_bad():
    """
    Random data pretending to be ciphertext.
    """
    return textwrap.dedent(
        """\
        fail: |
          -----BEGIN PGP MESSAGE-----

          OzyJmQJJVPxGQqyxwIcAl0wWqdSTHpMXYPLrDoRU8H1xa2DhE5DeUihjm4fHUcHp
          -----END PGP MESSAGE-----
        """
    )


@pytest.fixture(scope="module")
def gpg_pillar_encrypted_bad():
    """
    Random data pretending to be ciphertext almost always does not decrypt.
    """
    return {
        "fail": (
            "-----BEGIN PGP MESSAGE-----\n"
            "\n"
            "OzyJmQJJVPxGQqyxwIcAl0wWqdSTHpMXYPLrDoRU8H1xa2DhE5DeUihjm4fHUcHp\n"
            "-----END PGP MESSAGE-----\n"
        ),
    }


@pytest.fixture(scope="module", autouse=True)
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
            universal_newlines=True,
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
            universal_newlines=True,
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
                    universal_newlines=True,
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
def pillar_homedir(pillar_state_tree, gpg_pillar_yaml):
    """
    Setup gpg pillar
    """
    top_file_contents = """
    base:
      '*':
        - gpg
    """
    with pytest.helpers.temp_file(
        "top.sls", top_file_contents, pillar_state_tree
    ), pytest.helpers.temp_file("gpg.sls", gpg_pillar_yaml, pillar_state_tree):
        # Need to yield something so that pytest closes the context as a
        # callback after the test rather than immediately
        yield None


@pytest.fixture(scope="module")
def pillar_homedir_bad(pillar_state_tree, gpg_pillar_yaml_bad):
    """
    Setup gpg pillar with bad data
    """
    top_file_contents = """
    base:
      '*':
        - gpg
    """
    with pytest.helpers.temp_file(
        "top.sls", top_file_contents, pillar_state_tree
    ), pytest.helpers.temp_file("gpg.sls", gpg_pillar_yaml_bad, pillar_state_tree):
        # Need to yield something so that pytest closes the context as a
        # callback after the test rather than immediately
        yield None


def test_decrypt_pillar_default_renderer(
    salt_master, grains, pillar_homedir, gpg_pillar_decrypted
):
    """
    Test recursive decryption of secrets:vault as well as the fallback to
    default decryption renderer.
    """
    opts = salt_master.config.copy()
    opts["decrypt_pillar"] = ["secrets:vault"]
    pillar_obj = salt.pillar.Pillar(opts, grains, "test", "base")
    ret = pillar_obj.compile_pillar()
    assert ret == gpg_pillar_decrypted


@pytest.mark.slow_test
def test_decrypt_pillar_alternate_delimiter(
    salt_master, grains, pillar_homedir, gpg_pillar_decrypted
):
    """
    Test recursive decryption of secrets:vault using a pipe instead of a
    colon as the nesting delimiter.

        decrypt_pillar_delimiter: '|'
        decrypt_pillar:
          - 'secrets|vault'
    """
    opts = salt_master.config.copy()
    opts["decrypt_pillar"] = ["secrets|vault"]
    opts["decrypt_pillar_delimiter"] = "|"
    pillar_obj = salt.pillar.Pillar(opts, grains, "test", "base")
    ret = pillar_obj.compile_pillar()
    assert ret == gpg_pillar_decrypted


def test_decrypt_pillar_deeper_nesting(
    salt_master, grains, pillar_homedir, gpg_pillar_encrypted, gpg_pillar_decrypted
):
    """
    Test recursive decryption, only with a more deeply-nested target. This
    should leave the other keys in secrets:vault encrypted.

        decrypt_pillar:
          - 'secrets:vault:qux'
    """
    opts = salt_master.config.copy()
    opts["decrypt_pillar"] = ["secrets:vault:qux"]
    pillar_obj = salt.pillar.Pillar(opts, grains, "test", "base")
    ret = pillar_obj.compile_pillar()
    expected = copy.deepcopy(gpg_pillar_encrypted)
    expected["secrets"]["vault"]["qux"][-1] = gpg_pillar_decrypted["secrets"]["vault"][
        "qux"
    ][-1]
    assert ret == expected


def test_decrypt_pillar_explicit_renderer(
    salt_master, grains, pillar_homedir, gpg_pillar_decrypted
):
    """
    Test recursive decryption of secrets:vault, with the renderer
    explicitly defined, overriding the default. Setting the default to a
    nonexistent renderer so we can be sure that the override happened.

        decrypt_pillar_default: asdf
        decrypt_pillar_renderers:
          - asdf
          - gpg
        decrypt_pillar:
          - 'secrets:vault': gpg
    """
    opts = salt_master.config.copy()
    opts["decrypt_pillar"] = [{"secrets:vault": "gpg"}]
    opts["decrypt_pillar_default"] = "asdf"
    opts["decrypt_pillar_renderers"] = ["asdf", "gpg"]
    pillar_obj = salt.pillar.Pillar(opts, grains, "test", "base")
    ret = pillar_obj.compile_pillar()
    assert ret == gpg_pillar_decrypted


def test_decrypt_pillar_missing_renderer(
    salt_master, grains, pillar_homedir, gpg_pillar_encrypted
):
    """
    Test decryption using a missing renderer. It should fail, leaving the
    encrypted keys intact, and add an error to the pillar dictionary.

        decrypt_pillar_default: asdf
        decrypt_pillar_renderers:
          - asdf
        decrypt_pillar:
          - 'secrets:vault'
    """
    opts = salt_master.config.copy()
    opts["decrypt_pillar"] = ["secrets:vault"]
    opts["decrypt_pillar_default"] = "asdf"
    opts["decrypt_pillar_renderers"] = ["asdf"]
    pillar_obj = salt.pillar.Pillar(opts, grains, "test", "base")
    ret = pillar_obj.compile_pillar()
    expected = copy.deepcopy(gpg_pillar_encrypted)
    expected["_errors"] = [
        "Failed to decrypt pillar key 'secrets:vault': Decryption renderer 'asdf' is"
        " not available"
    ]
    assert ret["_errors"] == expected["_errors"]
    assert ret["secrets"]["vault"]["foo"] == expected["secrets"]["vault"]["foo"]
    assert ret["secrets"]["vault"]["bar"] == expected["secrets"]["vault"]["bar"]
    assert ret["secrets"]["vault"]["baz"] == expected["secrets"]["vault"]["baz"]
    assert ret["secrets"]["vault"]["qux"] == expected["secrets"]["vault"]["qux"]


def test_decrypt_pillar_invalid_renderer(
    salt_master, grains, pillar_homedir, gpg_pillar_encrypted
):
    """
    Test decryption using a renderer which is not permitted. It should
    fail, leaving the encrypted keys intact, and add an error to the pillar
    dictionary.

        decrypt_pillar_default: foo
        decrypt_pillar_renderers:
          - foo
          - bar
        decrypt_pillar:
          - 'secrets:vault': gpg
    """
    opts = salt_master.config.copy()
    opts["decrypt_pillar"] = [{"secrets:vault": "gpg"}]
    opts["decrypt_pillar_default"] = "foo"
    opts["decrypt_pillar_renderers"] = ["foo", "bar"]
    pillar_obj = salt.pillar.Pillar(opts, grains, "test", "base")
    ret = pillar_obj.compile_pillar()
    expected = copy.deepcopy(gpg_pillar_encrypted)
    expected["_errors"] = [
        "Failed to decrypt pillar key 'secrets:vault': 'gpg' is not a valid decryption"
        " renderer. Valid choices are: foo, bar"
    ]
    assert ret["_errors"] == expected["_errors"]
    assert ret["secrets"]["vault"]["foo"] == expected["secrets"]["vault"]["foo"]
    assert ret["secrets"]["vault"]["bar"] == expected["secrets"]["vault"]["bar"]
    assert ret["secrets"]["vault"]["baz"] == expected["secrets"]["vault"]["baz"]
    assert ret["secrets"]["vault"]["qux"] == expected["secrets"]["vault"]["qux"]


def test_gpg_decrypt_must_succeed(
    salt_master, grains, pillar_homedir_bad, gpg_pillar_encrypted_bad
):
    """
    Test that gpg rendering fails when ``gpg_decrypt_must_succeed`` is
    ``True`` and decryption fails.

        gpg_decrypt_must_succeed: True
        decrypt_pillar:
          - fail
    """
    opts = salt_master.config.copy()
    opts["gpg_decrypt_must_succeed"] = True
    opts["decrypt_pillar"] = ["fail"]
    pillar_obj = salt.pillar.Pillar(opts, grains, "test", "base")
    ret = pillar_obj.compile_pillar()
    expected = copy.deepcopy(gpg_pillar_encrypted_bad)
    expected_error = "Failed to decrypt pillar key 'fail': Could not decrypt cipher "

    assert "_errors" in ret
    assert len(ret["_errors"]) == 1
    assert ret["_errors"][0].startswith(expected_error)
    assert "fail" in ret
    assert ret["fail"] == expected["fail"]


def test_gpg_decrypt_may_succeed(
    salt_master, grains, pillar_homedir_bad, gpg_pillar_encrypted_bad
):
    """
    Test that gpg rendering does not fail when ``gpg_decrypt_must_succeed`` is
    ``False`` and decryption fails.

        gpg_decrypt_must_succeed: False
        decrypt_pillar:
          - fail
    """
    opts = salt_master.config.copy()
    opts["gpg_decrypt_must_succeed"] = False
    opts["decrypt_pillar"] = ["fail"]
    pillar_obj = salt.pillar.Pillar(opts, grains, "test", "base")
    ret = pillar_obj.compile_pillar()
    expected = copy.deepcopy(gpg_pillar_encrypted_bad)

    assert "_errors" not in ret
    assert "fail" in ret
    assert len(ret.keys()) == 1
    # Presence of trailing whitespace in encrypted/decrypted blocks is not
    # well-defined
    assert ret["fail"].rstrip() == expected["fail"].rstrip()
