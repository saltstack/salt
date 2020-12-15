import pytest
from tests.support.helpers import slowTest

pytestmark = [pytest.mark.windows_whitelisted]


@slowTest
def test_sync_grains(salt_call_cli):
    ret = salt_call_cli.run("saltutil.sync_grains")
    assert ret.exitcode == 0
    assert ret.json == []
