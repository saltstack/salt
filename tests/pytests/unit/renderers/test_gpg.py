import os
from subprocess import PIPE
from textwrap import dedent

import pytest

import salt.renderers.gpg as gpg
from salt.exceptions import SaltRenderError
from tests.support.mock import MagicMock, Mock, call, patch


def _find_unused_pid():
    """Return a PID that is (almost certainly) not currently running."""
    for candidate in (4194303, 4194302, 4194301, 999999, 888888):
        try:
            os.kill(candidate, 0)
        except OSError:
            return candidate
    raise RuntimeError("Unable to locate an unused PID for testing")


@pytest.fixture
def configure_loader_modules(minion_opts):
    """
    GPG renderer configuration
    """
    minion_opts["gpg_decrypt_must_succeed"] = True
    return {gpg: {"__opts__": minion_opts}}


def test__get_gpg_exec():
    """
    test _get_gpg_exec
    """
    gpg_exec = "/bin/gpg"

    with patch("salt.utils.path.which", MagicMock(return_value=gpg_exec)):
        assert gpg._get_gpg_exec() == gpg_exec

    with patch("salt.utils.path.which", MagicMock(return_value=False)):
        pytest.raises(SaltRenderError, gpg._get_gpg_exec)


def test__decrypt_ciphertext():
    """
    test _decrypt_ciphertext
    """
    key_dir = "/etc/salt/gpgkeys"
    secret = "Use more salt."
    crypted = "-----BEGIN PGP MESSAGE-----!@#$%^&*()_+-----END PGP MESSAGE-----"

    multisecret = "password is {0} and salt is {0}".format(secret)
    multicrypted = "password is {0} and salt is {0}".format(crypted)

    class GPGDecrypt:
        def communicate(self, *args, **kwargs):
            return [secret, None]

    class GPGNotDecrypt:
        def communicate(self, *args, **kwargs):
            return [None, "decrypt error"]

    with patch(
        "salt.renderers.gpg._get_key_dir", MagicMock(return_value=key_dir)
    ), patch("salt.utils.path.which", MagicMock()):
        with patch("salt.renderers.gpg.Popen", MagicMock(return_value=GPGDecrypt())):
            assert gpg._decrypt_ciphertexts(crypted) == secret
            assert gpg._decrypt_ciphertexts(multicrypted) == multisecret
        with patch("salt.renderers.gpg.Popen", MagicMock(return_value=GPGNotDecrypt())):
            with pytest.raises(SaltRenderError) as decrypt_error:
                gpg._decrypt_ciphertexts(crypted)
            # Assertions must be made after closure of context manager
            assert decrypt_error.value.args[0].startswith("Could not decrypt cipher ")
            assert crypted in decrypt_error.value.args[0]
            assert "decrypt error" in decrypt_error.value.args[0]
            with pytest.raises(SaltRenderError) as multidecrypt_error:
                gpg._decrypt_ciphertexts(multicrypted)
            assert multidecrypt_error.value.args[0].startswith(
                "Could not decrypt cipher "
            )
            # Function will raise on a single ciphertext even if multiple are passed
            assert crypted in multidecrypt_error.value.args[0]
            assert "decrypt error" in multidecrypt_error.value.args[0]


def test__decrypt_object():
    """
    test _decrypt_object
    """
    secret = "Use more salt."
    crypted = "-----BEGIN PGP MESSAGE-----!@#$%^&*()_+-----END PGP MESSAGE-----"

    secret_map = {"secret": secret}
    crypted_map = {"secret": crypted}

    secret_list = [secret]
    crypted_list = [crypted]

    with patch(
        "salt.renderers.gpg._decrypt_ciphertext", MagicMock(return_value=secret)
    ):
        assert gpg._decrypt_object(secret) == secret
        assert gpg._decrypt_object(crypted) == secret
        assert gpg._decrypt_object(crypted_map) == secret_map
        assert gpg._decrypt_object(crypted_list) == secret_list
        assert gpg._decrypt_object(None) is None


def test_render():
    """
    test render
    """
    key_dir = "/etc/salt/gpgkeys"
    secret = "Use more salt."
    crypted = "-----BEGIN PGP MESSAGE-----!@#$%^&*()_+"

    with patch("salt.renderers.gpg._get_gpg_exec", MagicMock(return_value=True)):
        with patch("salt.renderers.gpg._get_key_dir", MagicMock(return_value=key_dir)):
            with patch(
                "salt.renderers.gpg._decrypt_object", MagicMock(return_value=secret)
            ):
                assert gpg.render(crypted) == secret


def test_render_bytes():
    """
    test rendering bytes
    """
    key_dir = "/etc/salt/gpgkeys"
    binfo = b"User more salt."

    with patch("salt.renderers.gpg._get_gpg_exec", MagicMock(return_value=True)):
        with patch("salt.renderers.gpg._get_key_dir", MagicMock(return_value=key_dir)):
            assert gpg.render(binfo) == binfo.decode()


def test_multi_render():
    key_dir = "/etc/salt/gpgkeys"
    secret = "Use more salt."
    expected = "\n".join([secret] * 3)
    crypted = dedent(
        """\
        -----BEGIN PGP MESSAGE-----
        !@#$%^&*()_+
        -----END PGP MESSAGE-----
        -----BEGIN PGP MESSAGE-----
        !@#$%^&*()_+
        -----END PGP MESSAGE-----
        -----BEGIN PGP MESSAGE-----
        !@#$%^&*()_+
        -----END PGP MESSAGE-----
    """
    )

    with patch("salt.renderers.gpg._get_gpg_exec", MagicMock(return_value=True)):
        with patch("salt.renderers.gpg._get_key_dir", MagicMock(return_value=key_dir)):
            with patch(
                "salt.renderers.gpg._decrypt_ciphertext",
                MagicMock(return_value=secret),
            ):
                assert gpg.render(crypted) == expected


def test_render_with_binary_data_should_return_binary_data():
    key_dir = "/etc/salt/gpgkeys"
    secret = b"Use\x8b more\x8b salt."
    expected = b"\n".join([secret] * 3)
    crypted = dedent(
        """\
        -----BEGIN PGP MESSAGE-----
        !@#$%^&*()_+
        -----END PGP MESSAGE-----
        -----BEGIN PGP MESSAGE-----
        !@#$%^&*()_+
        -----END PGP MESSAGE-----
        -----BEGIN PGP MESSAGE-----
        !@#$%^&*()_+
        -----END PGP MESSAGE-----
    """
    )

    with patch("salt.renderers.gpg._get_gpg_exec", MagicMock(return_value=True)):
        with patch("salt.renderers.gpg._get_key_dir", MagicMock(return_value=key_dir)):
            with patch(
                "salt.renderers.gpg._decrypt_ciphertext",
                MagicMock(return_value=secret),
            ):
                assert gpg.render(crypted, encoding="utf-8") == expected


def test_render_with_translate_newlines_should_translate_newlines():
    key_dir = "/etc/salt/gpgkeys"
    secret = b"Use\x8b more\x8b salt."
    expected = b"\n\n".join([secret] * 3)
    crypted = dedent(
        """\
        -----BEGIN PGP MESSAGE-----
        !@#$%^&*()_+
        -----END PGP MESSAGE-----\\n
        -----BEGIN PGP MESSAGE-----
        !@#$%^&*()_+
        -----END PGP MESSAGE-----\\n
        -----BEGIN PGP MESSAGE-----
        !@#$%^&*()_+
        -----END PGP MESSAGE-----
    """
    )

    with patch("salt.renderers.gpg._get_gpg_exec", MagicMock(return_value=True)):
        with patch("salt.renderers.gpg._get_key_dir", MagicMock(return_value=key_dir)):
            with patch(
                "salt.renderers.gpg._decrypt_ciphertext",
                MagicMock(return_value=secret),
            ):
                assert (
                    gpg.render(crypted, translate_newlines=True, encoding="utf-8")
                    == expected
                )


def test_render_without_cache():
    key_dir = "/etc/salt/gpgkeys"
    secret = "Use more salt."
    expected = "\n".join([secret] * 3)
    crypted = dedent(
        """\
        -----BEGIN PGP MESSAGE-----
        !@#$%^&*()_+
        -----END PGP MESSAGE-----
        -----BEGIN PGP MESSAGE-----
        !@#$%^&*()_+
        -----END PGP MESSAGE-----
        -----BEGIN PGP MESSAGE-----
        !@#$%^&*()_+
        -----END PGP MESSAGE-----
    """
    )

    with patch("salt.renderers.gpg.Popen") as popen_mock:
        popen_mock.return_value = Mock(
            communicate=lambda *args, **kwargs: (secret, None),
        )
        with patch(
            "salt.renderers.gpg._get_gpg_exec",
            MagicMock(return_value="/usr/bin/gpg"),
        ):
            with patch(
                "salt.renderers.gpg._get_key_dir", MagicMock(return_value=key_dir)
            ):
                assert gpg.render(crypted) == expected
                gpg_call = call(
                    [
                        "/usr/bin/gpg",
                        "--homedir",
                        "/etc/salt/gpgkeys",
                        "--status-fd",
                        "2",
                        "--no-tty",
                        "-d",
                    ],
                    shell=False,
                    stderr=PIPE,
                    stdin=PIPE,
                    stdout=PIPE,
                )
                popen_mock.assert_has_calls([gpg_call] * 3)


def test_cleanup_stale_lockfiles_removes_dead_pid_locks_68869(tmp_path):
    """
    Regression test for #68869.

    GnuPG writes ``dotlock`` files (``.#lk<addr>.<host>.<pid>``) when
    acquiring a lock on a keyring file. If the gpg process is killed before
    it can rename the dotlock to its final ``<file>.lock`` name (for example
    when its parent salt-master worker is terminated mid-decrypt), the
    dotlock is orphaned. Over time these accumulate in ``gpg_keydir``.

    The cleanup helper must remove dotlock files whose owning PID is no
    longer running, and must leave any other files (including a dotlock
    owned by a live PID) alone.
    """
    dead_pid = _find_unused_pid()
    live_pid = os.getpid()

    # Layout mirrors the report in the issue: ``host pid`` payload, padded
    # to ``host.pid`` style filenames.
    stale = tmp_path / f".#lk0x00005fead0da9180.salt.{dead_pid}"
    stale.write_text(f"salt {dead_pid}")
    live = tmp_path / f".#lk0x00005fead0da9181.salt.{live_pid}"
    live.write_text(f"salt {live_pid}")
    unrelated = tmp_path / "pubring.kbx"
    unrelated.write_text("not a lock")

    gpg._cleanup_stale_lockfiles(str(tmp_path))

    assert not stale.exists()
    assert live.exists()
    assert unrelated.exists()


def test_cleanup_stale_lockfiles_handles_missing_keydir_68869(tmp_path):
    """
    The helper must not raise if the keydir does not exist or is not a
    directory; the renderer is called before any keys are configured in
    some setups.
    """
    missing = tmp_path / "does-not-exist"
    # Should be a no-op rather than raising.
    gpg._cleanup_stale_lockfiles(str(missing))
    gpg._cleanup_stale_lockfiles(None)


def test__decrypt_ciphertext_cleans_stale_lockfiles_68869():
    """
    Regression test for #68869: ``_decrypt_ciphertext`` must run the
    stale-lockfile cleanup against the keydir before invoking ``gpg``.
    """
    key_dir = "/etc/salt/gpgkeys"
    secret = "Use more salt."
    crypted = "-----BEGIN PGP MESSAGE-----!@#$%^&*()_+-----END PGP MESSAGE-----"

    class GPGDecrypt:
        def communicate(self, *args, **kwargs):
            return [secret, None]

    with patch(
        "salt.renderers.gpg._get_key_dir", MagicMock(return_value=key_dir)
    ), patch("salt.utils.path.which", MagicMock()), patch(
        "salt.renderers.gpg.Popen", MagicMock(return_value=GPGDecrypt())
    ), patch(
        "salt.renderers.gpg._cleanup_stale_lockfiles"
    ) as cleanup_mock:
        gpg._decrypt_ciphertexts(crypted)
        cleanup_mock.assert_called_with(key_dir)


def test_render_with_cache(minion_opts):
    key_dir = "/etc/salt/gpgkeys"
    secret = "Use more salt."
    expected = "\n".join([secret] * 3)
    crypted = dedent(
        """\
        -----BEGIN PGP MESSAGE-----
        !@#$%^&*()_+
        -----END PGP MESSAGE-----
        -----BEGIN PGP MESSAGE-----
        !@#$%^&*()_+
        -----END PGP MESSAGE-----
        -----BEGIN PGP MESSAGE-----
        !@#$%^&*()_+
        -----END PGP MESSAGE-----
    """
    )

    minion_opts["gpg_cache"] = True
    with patch.dict(gpg.__opts__, minion_opts):
        with patch("salt.renderers.gpg.Popen") as popen_mock:
            popen_mock.return_value = Mock(
                communicate=lambda *args, **kwargs: (secret, None),
            )
            with patch(
                "salt.renderers.gpg._get_gpg_exec",
                MagicMock(return_value="/usr/bin/gpg"),
            ):
                with patch(
                    "salt.renderers.gpg._get_key_dir",
                    MagicMock(return_value=key_dir),
                ):
                    with patch(
                        "salt.utils.atomicfile.atomic_open",
                        MagicMock(),
                    ) as atomic_open_mock:
                        assert gpg.render(crypted) == expected
                        gpg_call = call(
                            [
                                "/usr/bin/gpg",
                                "--homedir",
                                "/etc/salt/gpgkeys",
                                "--status-fd",
                                "2",
                                "--no-tty",
                                "-d",
                            ],
                            shell=False,
                            stderr=PIPE,
                            stdin=PIPE,
                            stdout=PIPE,
                        )
                        popen_mock.assert_has_calls([gpg_call] * 1)
                        atomic_open_mock.assert_has_calls(
                            [
                                call(
                                    os.path.join(minion_opts["cachedir"], "gpg_cache"),
                                    "wb+",
                                )
                            ]
                        )
