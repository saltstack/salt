from unittest.mock import MagicMock

import salt.key


def test_key_destroy_is_idempotent():
    key = object.__new__(salt.key.Key)
    event = MagicMock()
    key.__dict__["event"] = event

    key.destroy()
    key.destroy()

    event.destroy.assert_called_once_with()
    assert "event" not in key.__dict__


def test_key_cli_context_destroys_local_key():
    key_cli = object.__new__(salt.key.KeyCLI)
    key_cli.opts = {"eauth": ""}
    key_cli.key = MagicMock()

    with key_cli:
        pass

    key_cli.key.destroy.assert_called_once_with()


def test_key_cli_context_does_not_destroy_key_class_for_eauth():
    key_cli = object.__new__(salt.key.KeyCLI)
    key_cli.opts = {"eauth": "pam"}
    key_cli.key = salt.key.Key

    with key_cli:
        pass
