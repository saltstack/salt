import logging
import pathlib

import pytest

import salt.states.ssh_auth as ssh_auth_state
import salt.utils.files

log = logging.getLogger(__name__)

# A modern pubkey: Python 3.12+ validates OpenSSH key blobs with
# base64.b64decode(..., validate=True); legacy ssh-dss samples fail that check.
_TEST_PUBKEY_ENC = "ssh-ed25519"
_TEST_PUBKEY_KEY = (
    "AAAAC3NzaC1lZDI1NTE5AAAAINEIiNXlqUlqiVg69lJkzMfyBWAansuwqW6bw7zox7kR"
)
_TEST_PUBKEY_COMMENT = "regression@70792"
_TEST_PUBKEY = f"{_TEST_PUBKEY_ENC} {_TEST_PUBKEY_KEY} {_TEST_PUBKEY_COMMENT}"
_TEST_OPTIONS = ['from="192.0.2.1"']


@pytest.fixture
def configure_loader_modules(modules, minion_opts):
    loader = {"__salt__": modules, "__opts__": minion_opts, "__env__": "base"}
    return {ssh_auth_state: loader}


@pytest.fixture(scope="module")
def system_user():
    with pytest.helpers.create_account() as system_account:
        yield system_account


@pytest.fixture
def ssh_auth_context_primed(modules):
    """
    Prime a real-dict ``__context__`` on the loaded ``salt.modules.test``
    module. ``ssh_auth`` state helpers read
    ``sys.modules[__salt__["test.ping"].__module__].__context__`` to surface
    error messages captured by ``ssh.check_key_file``. In the functional
    loader harness that attribute can resolve to a ``NamedLoaderContext``
    whose wrapped value is ``None``, which raises ``TypeError`` on ``.pop``.
    Priming with a plain dict shims around that harness quirk so the state
    code can actually run.
    """
    import sys

    mod_name = modules.test.ping.__module__
    mod = sys.modules.get(mod_name)
    original = getattr(mod, "__context__", None)
    try:
        mod.__context__ = {}
        yield
    finally:
        if original is None:
            try:
                del mod.__context__
            except AttributeError:
                pass
        else:
            mod.__context__ = original


@pytest.fixture
def seeded_authorized_keys(system_user):
    """
    Seed ~/.ssh/authorized_keys for the test user with a single key that has
    NO options, then yield the path. Cleans the file afterward.
    """
    user_ssh_dir = pathlib.Path(system_user.info.home, ".ssh")
    user_ssh_dir.mkdir(mode=0o700, exist_ok=True)
    authorized_keys = user_ssh_dir / "authorized_keys"
    authorized_keys.write_text(_TEST_PUBKEY + "\n")
    import os
    import pwd

    pw = pwd.getpwnam(system_user.username)
    os.chown(str(user_ssh_dir), pw.pw_uid, pw.pw_gid)
    os.chown(str(authorized_keys), pw.pw_uid, pw.pw_gid)
    authorized_keys.chmod(0o600)
    try:
        yield authorized_keys
    finally:
        try:
            authorized_keys.unlink()
        except FileNotFoundError:
            pass


@pytest.mark.skip_if_not_root
@pytest.mark.destructive_test
@pytest.mark.slow_test
def test_ssh_auth_config(tmp_path, system_user, state_tree):
    """
    test running ssh_auth state when
    different config is set. Ensure
    it does not edit the default config.
    """
    userdetails = system_user.info
    user_ssh_dir = pathlib.Path(userdetails.home, ".ssh")
    # Use a modern pubkey: Python 3.12+ validates OpenSSH key blobs with
    # base64.b64decode(..., validate=True); the legacy ssh-dss sample used here
    # fails that check ("Excess padding"), so ssh.set_auth_key never wrote a file.
    test_pubkey = (
        "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAINEIiNXlqUlqiVg69lJkzMfyBWAansuwqW6bw7zox7kR "
        "root@domain"
    )
    ret = ssh_auth_state.manage(
        name="test",
        user=system_user.username,
        ssh_keys=[test_pubkey],
    )
    with salt.utils.files.fopen(user_ssh_dir / "authorized_keys") as fp:
        pre_data = fp.read()
    file_contents = test_pubkey
    new_auth_file = tmp_path / "authorized_keys3"
    with pytest.helpers.temp_file("authorized", file_contents, state_tree):
        ssh_auth_state.manage(
            name="test",
            user=system_user.username,
            source="salt://authorized",
            config=str(new_auth_file),
            ssh_keys=[""],
        )
    with salt.utils.files.fopen(user_ssh_dir / "authorized_keys") as fp:
        post_data = fp.read()
    assert pre_data == post_data
    with salt.utils.files.fopen(new_auth_file) as fp:
        data = fp.read().strip()
    assert data == file_contents


@pytest.mark.skip_if_not_root
@pytest.mark.destructive_test
@pytest.mark.slow_test
def test_present_test_mode_honors_state_options(
    system_user, state_tree, seeded_authorized_keys, ssh_auth_context_primed
):
    """
    Regression for saltstack/salt#70792.

    When:
      - the on-disk authorized_keys has an entry WITHOUT options,
      - the source file has the same key WITHOUT options,
      - the state call supplies `options=['from="192.0.2.1"']`,

    then `state.apply test=True` MUST predict a change (result is None,
    changes non-empty) because a real apply with the same arguments WILL
    replace the entry (ssh.set_auth_key_from_file threads `options=` through).

    Pre-fix behaviour: _present_test calls ssh.check_key_file without
    `options=`, so the preview reports "already present" and result is True.
    Apply then actually replaces the entry, producing a preview/apply mismatch.
    """
    # Source file in the salt fileserver containing the same key, no options.
    source_contents = _TEST_PUBKEY + "\n"
    from tests.support.mock import patch

    with pytest.helpers.temp_file("source_70792.pub", source_contents, state_tree):
        # --- 1. test=True preview --- must predict a change
        with patch.dict(ssh_auth_state.__opts__, {"test": True}):
            preview = ssh_auth_state.present(
                name=_TEST_PUBKEY_KEY,
                user=system_user.username,
                enc=_TEST_PUBKEY_ENC,
                comment=_TEST_PUBKEY_COMMENT,
                source="salt://source_70792.pub",
                options=list(_TEST_OPTIONS),
            )
        log.info("test=True preview for #70792 present: %r", preview)

        # The state options differ from what's on disk, so the preview MUST
        # indicate a pending change. This assertion is what currently fails.
        assert preview["result"] is None, (
            f"Expected test=True preview to predict a change "
            f"(result=None) because state options {_TEST_OPTIONS!r} differ "
            f"from the on-disk entry's lack of options, but got "
            f"result={preview['result']!r} comment={preview['comment']!r}"
        )

        # --- 2. Apply with test=False --- the real apply MUST replace.
        with patch.dict(ssh_auth_state.__opts__, {"test": False}):
            applied = ssh_auth_state.present(
                name=_TEST_PUBKEY_KEY,
                user=system_user.username,
                enc=_TEST_PUBKEY_ENC,
                comment=_TEST_PUBKEY_COMMENT,
                source="salt://source_70792.pub",
                options=list(_TEST_OPTIONS),
            )
        log.info("apply result for #70792 present: %r", applied)

        # The on-disk file should now contain the key WITH options.
        on_disk = seeded_authorized_keys.read_text()
        assert 'from="192.0.2.1"' in on_disk, (
            f"Expected apply to have rewritten authorized_keys with options; "
            f"file content was:\n{on_disk}"
        )

        # --- 3. Preview and apply must agree. If the preview said 'no change'
        # but apply produced a change, that is the #70792 mismatch.
        preview_predicted_change = preview["result"] is None
        apply_produced_change = bool(applied.get("changes"))
        assert preview_predicted_change == apply_produced_change, (
            f"test=True preview and apply disagree: "
            f"preview.result={preview['result']!r} "
            f"apply.changes={applied.get('changes')!r} (#70792)"
        )


# Note: a functional/E2E counterpart for ``_absent_test`` is intentionally
# omitted. The absent-state's apply path (``ssh.rm_auth_key`` /
# ``ssh.rm_auth_key_from_file``) matches entries by key blob — options are
# never consulted — so the preview and apply agree on the "remove" outcome
# today even though ``_absent_test`` still fails to thread ``options`` into
# ``ssh.check_key_file``. The signature-level regression is still guarded
# by ``tests/pytests/unit/states/test_ssh_auth.py::
# test__absent_test_passes_options_to_check_key_file`` (same #70792 marker).
