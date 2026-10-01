"""
Unit tests for the salt-key CLI (salt.cli.key.SaltKey).
"""

import pytest

from salt.cli.key import SaltKey
from tests.support.mock import MagicMock, patch


def _fake_saltkey():
    """
    A stand-in ``SaltKey`` self with just the attributes ``run()`` touches,
    so the method can be exercised without full CLI parsing.
    """
    fake = MagicMock()
    fake.options.delete_all = False
    fake.args = []
    fake.config = {"user": "root"}
    return fake


def _fake_keycli():
    """
    A stand-in for the ``salt.key.KeyCLI`` instance ``SaltKey.run()`` uses
    as a context manager (``with salt.key.KeyCLI(self.config) as key:``).

    A bare ``MagicMock()`` doesn't wire its auto-generated ``__enter__``/
    ``__exit__`` to any real behavior, so ``__enter__()`` would return a
    *different* mock than ``fake_keycli`` (making ``key`` inside the
    ``with`` block not the object the test asserts against), and
    ``__exit__()`` would be a no-op instead of calling ``destroy()``. Wire
    both to mirror ``KeyCLI.__enter__``/``__exit__`` for real -- ``__exit__``
    must return ``None`` (falsy) so exceptions raised inside the ``with``
    block are propagated, not swallowed.
    """
    fake_keycli = MagicMock()
    fake_keycli.__enter__.return_value = fake_keycli

    def _exit(*args):
        fake_keycli.destroy()

    fake_keycli.__exit__.side_effect = _exit
    return fake_keycli


def test_run_destroys_keycli_on_normal_exit():
    """
    Regression test for the ``salt-key`` sibling of GH #70174: ``salt-key``
    leaked its ``KeyCLI`` (and the ``WheelClient`` it eagerly creates)
    because it was never ``destroy()``'d, relying instead on ``__del__``'s
    GC-time safety net -- which now logs a loud ``[WARNING ] unclosed
    WheelClient ...`` record that reaches stdout/stderr and breaks
    consumers of ``salt-key --out json``. ``destroy()`` must run on the
    normal, successful exit path.
    """
    fake = _fake_saltkey()
    fake_keycli = _fake_keycli()
    with (
        patch("salt.key.KeyCLI", return_value=fake_keycli),
        patch("salt.cli.key.check_user", return_value=True),
    ):
        SaltKey.run(fake)
    fake_keycli.run.assert_called_once()
    fake_keycli.destroy.assert_called_once()


def test_run_destroys_keycli_when_check_user_false():
    """
    ``check_user`` returning False skips ``key.run()``, but the ``KeyCLI``
    was already constructed and its ``WheelClient`` must still be released.
    """
    fake = _fake_saltkey()
    fake_keycli = _fake_keycli()
    with (
        patch("salt.key.KeyCLI", return_value=fake_keycli),
        patch("salt.cli.key.check_user", return_value=False),
    ):
        SaltKey.run(fake)
    fake_keycli.run.assert_not_called()
    fake_keycli.destroy.assert_called_once()


def test_run_destroys_keycli_when_keyrun_raises():
    """
    ``destroy()`` must still run when ``key.run()`` raises.
    """
    fake = _fake_saltkey()
    fake_keycli = _fake_keycli()
    fake_keycli.run.side_effect = RuntimeError("boom")
    with (
        patch("salt.key.KeyCLI", return_value=fake_keycli),
        patch("salt.cli.key.check_user", return_value=True),
    ):
        with pytest.raises(RuntimeError, match="boom"):
            SaltKey.run(fake)
    fake_keycli.destroy.assert_called_once()


def test_keycli_destroy_calls_client_destroy():
    """
    ``KeyCLI.destroy()`` must forward to ``self.client.destroy()`` (the
    ``WheelClient`` whose leak triggers the ``[WARNING ] unclosed
    WheelClient`` log record).
    """
    import salt.key

    with patch("salt.wheel.WheelClient") as WheelClient:
        fake_client = MagicMock()
        WheelClient.return_value = fake_client
        cli = salt.key.KeyCLI({"eauth": "pam"})
        cli.destroy()
    fake_client.destroy.assert_called_once()
    assert cli.client is None


def test_keycli_destroy_is_idempotent():
    """
    A second ``destroy()`` after ``self.client`` has already been released
    must be a no-op, not raise.
    """
    import salt.key

    with patch("salt.wheel.WheelClient") as WheelClient:
        fake_client = MagicMock()
        WheelClient.return_value = fake_client
        cli = salt.key.KeyCLI({"eauth": "pam"})
        cli.destroy()
        cli.destroy()
    fake_client.destroy.assert_called_once()


def test_keycli_as_context_manager_destroys_on_exit():
    """
    ``KeyCLI`` must work as a context manager (``__enter__`` returns the
    instance, ``__exit__`` calls ``destroy()``), which is how
    ``salt/cli/key.py:SaltKey.run()`` releases the ``WheelClient``.
    """
    import salt.key

    with patch("salt.wheel.WheelClient") as WheelClient:
        fake_client = MagicMock()
        WheelClient.return_value = fake_client
        with salt.key.KeyCLI({"eauth": "pam"}) as cli:
            assert isinstance(cli, salt.key.KeyCLI)
            fake_client.destroy.assert_not_called()
    fake_client.destroy.assert_called_once()
