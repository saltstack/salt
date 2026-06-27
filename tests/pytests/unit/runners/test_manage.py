import pytest

from salt.runners import manage
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {
        manage: {"__opts__": {"conf_file": "", "timeout": 5, "gather_job_timeout": 10}}
    }


def test_deprecation_58638():
    # check that type error will be raised
    pytest.raises(TypeError, manage.list_state, show_ipv4="data")

    # check that show_ipv4 will raise an error
    try:
        manage.list_state(show_ipv4="data")  # pylint: disable=unexpected-keyword-arg
    except TypeError as no_show_ipv4:
        # Python 3.13+ appends a ``. Did you mean 'show_ip'?`` suggestion to
        # the TypeError when an unexpected kwarg matches a similar parameter.
        # ``startswith`` accepts both the older bare message and the newer
        # one with the trailing suggestion.
        assert str(no_show_ipv4).startswith(
            "list_state() got an unexpected keyword argument 'show_ipv4'"
        )


def test_status_reports_unresponsive_minion_as_down():
    """
    manage.status/up/down must classify a key-accepted but unresponsive minion
    as down, not up.

    Regression (3008.0): _ping gathers test.ping returns via
    LocalClient.get_cli_event_returns and counts every yielded minion id as a
    return. When get_cli_event_returns is called with expect_minions=True (its
    default since 3008.0), the gather yields a
    ``{"out": "no_return", "ret": "Minion did not return..."}`` placeholder for
    every non-responder, so _ping counted non-responders as up and "down" was
    always empty. _ping must request only real returns (expect_minions=False).
    """
    mock_client = MagicMock()
    mock_client.run_job.return_value = {
        "jid": "20260101000000000000",
        "minions": ["alive-minion", "dead-minion"],
    }
    mock_client._get_timeout.return_value = 5
    # With expect_minions=False, only the responder yields a return; the
    # non-responder produces no entry (no timeout placeholder).
    mock_client.get_cli_event_returns.return_value = iter(
        [{"alive-minion": {"ret": True}}]
    )

    with patch("salt.client.get_local_client") as get_local_client:
        get_local_client.return_value.__enter__.return_value = mock_client
        result = manage.status(tgt="*")

    assert result == {"up": ["alive-minion"], "down": ["dead-minion"]}
    # The fix: _ping must opt out of the per-target timeout placeholders.
    _, kwargs = mock_client.get_cli_event_returns.call_args
    assert kwargs.get("expect_minions") is False
