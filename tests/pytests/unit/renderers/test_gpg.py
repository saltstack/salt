import os
from subprocess import PIPE
from textwrap import dedent

import pytest
import salt.config
import salt.renderers.gpg as gpg
from salt.exceptions import SaltRenderError
from tests.support.mock import MagicMock, Mock, call, patch


@pytest.fixture
def configure_loader_modules():
    return {gpg: {}}


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
            assert gpg._decrypt_ciphertexts(crypted) == crypted
            assert gpg._decrypt_ciphertexts(multicrypted) == multicrypted


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


def test_render_with_cache():
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

    minion_opts = salt.config.DEFAULT_MINION_OPTS.copy()
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
