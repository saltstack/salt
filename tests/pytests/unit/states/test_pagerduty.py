"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest
import salt.states.pagerduty as pagerduty
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {pagerduty: {}}


def test_create_event():
    """
    Test to create an event on the PagerDuty service.
    """
    name = "This is a server warning message"
    details = "This is a much more detailed message"
    service_key = "9abcd123456789efabcde362783cdbaf"
    profile = "my-pagerduty-account"

    ret = {"name": name, "result": None, "comment": "", "changes": {}}

    with patch.dict(pagerduty.__opts__, {"test": True}):
        comt = "Need to create event: {}".format(name)
        ret.update({"comment": comt})
        assert pagerduty.create_event(name, details, service_key, profile) == ret

    with patch.dict(pagerduty.__opts__, {"test": False}):
        mock_t = MagicMock(return_value=True)
        with patch.dict(pagerduty.__salt__, {"pagerduty.create_event": mock_t}):
            comt = "Created event: {}".format(name)
            ret.update({"comment": comt, "result": True})
            assert pagerduty.create_event(name, details, service_key, profile) == ret
