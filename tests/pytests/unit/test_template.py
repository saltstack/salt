import salt.state
from salt import template
from salt.config import minion_config
from tests.support.mock import MagicMock, patch


def test_compile_template_str_mkstemp_cleanup():
    with patch("os.unlink", MagicMock()) as unlinked:
        _config = minion_config(None)
        _config["file_client"] = "local"
        _state = salt.state.State(_config)
        assert template.compile_template_str(
            "{'val':'test'}",
            _state.rend,
            _state.opts["renderer"],
            _state.opts["renderer_blacklist"],
            _state.opts["renderer_whitelist"],
        ) == {"val": "test"}
        unlinked.assert_called_once()
