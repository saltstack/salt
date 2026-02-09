import salt.client
from tests.support.mock import patch


class DummyLocalClient:
    def __init__(self):
        self.calls = []

    def cmd(self, minion, fun, args=None, **kwargs):
        self.calls.append((minion, fun, args))
        if fun == "sys.list_functions":
            return {minion: ["cp.get_file_str"]}
        if fun == "cp.get_file_str":
            return {minion: "payload"}
        return {minion: None}


def test_functionwrapper_dot_notation_executes_module_call():
    dummy = DummyLocalClient()
    with patch("salt.client.LocalClient", return_value=dummy):
        wrapper = salt.client.FunctionWrapper(
            {"conf_file": "/etc/salt/master"}, "minion-id"
        )

    result = wrapper.cp.get_file_str("salt://foo")

    assert result == {"minion-id": "payload"}
    assert dummy.calls[-1][1] == "cp.get_file_str"

