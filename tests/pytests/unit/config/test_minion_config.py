import salt.config
from tests.support.mock import MagicMock, patch


def test___cli_path_is_expanded():
    defaults = salt.config.DEFAULT_MINION_OPTS.copy()
    overrides = {}
    with patch(
        "salt.utils.path.expand", MagicMock(return_value="/path/to/testcli")
    ) as expand_mock:
        opts = salt.config.apply_minion_config(overrides, defaults)
        assert expand_mock.called
        assert opts["__cli"] == "testcli"
