import salt.returners.sentry_return as sentry


def test_get_message():
    ret = {
        "id": "12345",
        "fun": "mytest.func",
        "fun_args": ["arg1", "arg2", {"foo": "bar"}],
        "jid": "54321",
        "return": "Long Return containing a Traceback",
    }

    assert sentry._get_message(ret) == "salt func: mytest.func arg1 arg2 foo=bar"
    assert (
        sentry._get_message({"fun": "test.func", "fun_args": []})
        == "salt func: test.func"
    )
    assert sentry._get_message({"fun": "test.func"}) == "salt func: test.func"
