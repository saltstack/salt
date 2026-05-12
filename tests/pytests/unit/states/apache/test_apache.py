"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.states.apache as apache
import salt.utils.files
from tests.support.mock import MagicMock, mock_open, patch


@pytest.fixture
def configure_loader_modules():
    return {apache: {}}


def test_configfile():
    """
    Test to allows for inputting a yaml dictionary into a file
    for apache configuration files.
    """
    with patch("os.path.exists", MagicMock(return_value=True)):
        name = "/etc/distro/specific/apache.conf"
        config = 'VirtualHost: this: "*:80"'
        new_config = 'LiteralHost: that: "*:79"'

        ret = {"name": name, "result": True, "changes": {}, "comment": ""}

        with patch.object(salt.utils.files, "fopen", mock_open(read_data=config)):
            mock_config = MagicMock(return_value=config)
            with patch.dict(apache.__salt__, {"apache.config": mock_config}):
                ret.update({"comment": "Configuration is up to date."})
                assert apache.configfile(name, config) == ret

        with patch.object(salt.utils.files, "fopen", mock_open(read_data=config)):
            mock_config = MagicMock(return_value=new_config)
            with patch.dict(apache.__salt__, {"apache.config": mock_config}):
                ret.update(
                    {
                        "comment": "Configuration will update.",
                        "changes": {"new": new_config, "old": config},
                        "result": None,
                    }
                )
                with patch.dict(apache.__opts__, {"test": True}):
                    assert apache.configfile(name, new_config) == ret

        with patch.object(salt.utils.files, "fopen", mock_open(read_data=config)):
            mock_config = MagicMock(return_value=new_config)
            with patch.dict(apache.__salt__, {"apache.config": mock_config}):
                ret.update(
                    {"comment": "Successfully created configuration.", "result": True}
                )
                with patch.dict(apache.__opts__, {"test": False}):
                    assert apache.configfile(name, config) == ret
