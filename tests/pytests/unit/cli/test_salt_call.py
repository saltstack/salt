import os

from salt.cli.call import SaltCall
from tests.support.mock import MagicMock, patch


def test_passing_cachedir_to_extension_modules(temp_salt_minion):
    """
    Test passing `cachedir` CLI parameter to `extension_modules` opts
    """
    test_cache_dir = os.path.join(temp_salt_minion.config["root_dir"], "new_cache_tmp")
    with patch(
        "sys.argv",
        [
            "salt-call",
            "--local",
            "--config-dir",
            temp_salt_minion.config["root_dir"],
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
