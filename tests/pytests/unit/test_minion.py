import pytest
import salt.ext.tornado.gen
import salt.minion
from tests.support.mock import MagicMock, patch


def test_minion_load_grains_false():
    """
    Minion does not generate grains when load_grains is False
    """
    opts = {"random_startup_delay": 0, "grains": {"foo": "bar"}}
    with patch("salt.loader.grains") as grainsfunc:
        minion = salt.minion.Minion(opts, load_grains=False)
        assert minion.opts["grains"] == opts["grains"]
        grainsfunc.assert_not_called()


def test_minion_load_grains_true():
    """
    Minion generates grains when load_grains is True
    """
    opts = {"random_startup_delay": 0, "grains": {}}
    with patch("salt.loader.grains") as grainsfunc:
        minion = salt.minion.Minion(opts, load_grains=True)
        assert minion.opts["grains"] != {}
        grainsfunc.assert_called()


def test_minion_load_grains_default():
    """
    Minion load_grains defaults to True
    """
    opts = {"random_startup_delay": 0, "grains": {}}
    with patch("salt.loader.grains") as grainsfunc:
        minion = salt.minion.Minion(opts)
        assert minion.opts["grains"] != {}
        grainsfunc.assert_called()


@pytest.mark.parametrize(
    "req_channel",
    [
        (
            "salt.transport.client.AsyncReqChannel.factory",
            lambda load, timeout, tries: salt.ext.tornado.gen.maybe_future(tries),
        ),
        (
            "salt.transport.client.ReqChannel.factory",
            lambda load, timeout, tries: tries,
        ),
    ],
)
def test_send_req_tries(req_channel):
    channel_enter = MagicMock()
    channel_enter.send.side_effect = req_channel[1]
    channel = MagicMock()
    channel.__enter__.return_value = channel_enter

    with patch(req_channel[0], return_value=channel):
        opts = {
            "random_startup_delay": 0,
            "grains": {},
            "return_retry_tries": 30,
            "minion_sign_messages": False,
        }
        with patch("salt.loader.grains"):
            minion = salt.minion.Minion(opts)

            load = {"load": "value"}
            timeout = 60

            if "Async" in req_channel[0]:
                rtn = minion._send_req_async(load, timeout).result()
            else:
                rtn = minion._send_req_sync(load, timeout)

            assert rtn == 30


@patch("salt.transport.client.ReqChannel.factory")
def test_mine_send_tries(req_channel_factory):
    channel_enter = MagicMock()
    channel_enter.send.side_effect = lambda load, timeout, tries: tries
    channel = MagicMock()
    channel.__enter__.return_value = channel_enter
    req_channel_factory.return_value = channel

    opts = {
        "random_startup_delay": 0,
        "grains": {},
        "return_retry_tries": 20,
        "minion_sign_messages": False,
    }
    with patch("salt.loader.grains"):
        minion = salt.minion.Minion(opts)
        minion.tok = "token"

        data = {}
        tag = "tag"

        rtn = minion._mine_send(tag, data)
        assert rtn == 20
