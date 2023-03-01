import logging

import pytest
from saltfactories.utils.functional import MultiStateResult

pytestmark = [
    pytest.mark.skip_on_windows,
]

log = logging.getLogger(__name__)


def test_check_imports(salt_cli, salt_minion):
    """
    Test imports
    """
    ret = salt_cli.run("state.sls", "check_imports", minion_tgt=salt_minion.id)
    assert ret.returncode == 0
    assert ret.data
    result = MultiStateResult(raw=ret.data)
    for state_ret in result:
        assert state_ret.result is True
