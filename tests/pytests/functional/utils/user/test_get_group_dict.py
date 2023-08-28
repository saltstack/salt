import logging

import pytest

import salt.utils.platform
import salt.utils.user
from tests.support.mock import patch

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.skip_unless_on_linux(
        reason="Should only run in platforms which have duplicate GID support"
    ),
]


def test_get_group_dict_with_improper_duplicate_root_group():
    with patch("salt.utils.user.get_group_list", return_value=["+", "root"]):
        group_list = salt.utils.user.get_group_dict("root")
        assert group_list == {"root": 0}
