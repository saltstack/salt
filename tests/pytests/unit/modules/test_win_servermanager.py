import os

import pytest
import salt.modules.win_servermanager as win_servermanager
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {win_servermanager: {}}


def test_install():
    mock_out = {
        "FeatureResult": {

        }
    }

    with patch.object(win_servermanager, "_pshell_json", return_value=""):

