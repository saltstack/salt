"""
Unit tests for salt.utils.napalm.
"""

import types

import salt.utils.napalm as napalm_utils
from tests.support.mock import MagicMock, patch


def test_get_device_opts_null_optional_args():
    # ``optional_args: null`` in the config yields None from ``.get(..., {})``
    # (the default only applies to a missing key), which then crashed the
    # ``"config_lock" not in ...`` membership test.
    opts = {"napalm": {"driver": "junos", "optional_args": None}}
    device = napalm_utils.get_device_opts(opts)
    assert isinstance(device["OPTIONAL_ARGS"], dict)
    assert device["OPTIONAL_ARGS"]["config_lock"] is False


def test_get_device_opts_does_not_mutate_caller():
    # The injected config_lock / keepalive must land in a copy, not in the
    # caller's live opts / pillar ``optional_args`` dict.
    optional_args = {"port": 830}
    opts = {"napalm": {"driver": "junos", "optional_args": optional_args}}
    napalm_utils.get_device_opts(opts)
    assert optional_args == {"port": 830}


def _wrapped_with_opts(opts):
    """A ``proxy_napalm_wrap``-decorated function whose module globals carry the
    given ``__opts__`` (so we can drive the wrapper without a real minion)."""

    def _fn(*args, **kwargs):
        return "ok"

    func_globals = {
        "__opts__": opts,
        "__proxy__": {},
        "__salt__": {"config.get": MagicMock(return_value={"driver": "junos"})},
    }
    fn = types.FunctionType(_fn.__code__, func_globals, "_fn")
    return napalm_utils.proxy_napalm_wrap(fn)


def test_proxy_napalm_wrap_force_reconnect_straight_minion():
    # force_reconnect on a straight (non-proxy) minion has no ``opts['proxy']``;
    # the wrapper must not blindly do ``opts['proxy'].update(...)`` (KeyError).
    # The override reaches the device through clean_kwargs on the straight path.
    opts = {"napalm": {"driver": "junos"}}
    wrapped = _wrapped_with_opts(opts)
    get_device = MagicMock(return_value={"DRIVER": MagicMock()})
    with patch("salt.utils.napalm.get_device", get_device):
        result = wrapped(force_reconnect=True)
    assert result == "ok"
    get_device.assert_called_once()
    assert get_device.call_args[0][0]["napalm"].get("force_reconnect") is True
