import os

from salt.cli.call import SaltCall
from tests.support.mock import MagicMock, patch


def test_passing_cachedir_to_extension_modules(tmp_path):
    """
    Test passing `cachedir` CLI parameter to `extension_modules` opts
    """
    # Only set ``root_dir`` so every other path (pki, cache, logs) is derived
    # from it, instead of falling back to the system defaults in /etc and /var.
    root_dir = tmp_path / "root"
    config_dir = tmp_path / "conf"
    config_dir.mkdir()
    (config_dir / "minion").write_text(f"root_dir: {root_dir}\n")
    test_cache_dir = str(root_dir / "new_cache_tmp")
    with patch(
        "sys.argv",
        [
            "salt-call",
            "--local",
            "--config-dir",
            str(config_dir),
            "--cachedir",
            test_cache_dir,
            "test.true",
        ],
    ), patch("salt.utils.verify.verify_files", MagicMock()), patch(
        "salt._logging.impl.setup_logfile_handler", MagicMock()
    ):
        salt_call = SaltCall()
        with patch("salt.cli.caller.Caller.factory", MagicMock()) as caller_mock:
            salt_call.run()
            assert salt_call.config["cachedir"] == test_cache_dir
            assert salt_call.config["extension_modules"] == os.path.join(
                test_cache_dir, "extmods"
            )
