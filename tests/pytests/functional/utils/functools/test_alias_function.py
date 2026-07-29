from salt.utils.functools import alias_function


def test_kwarg_defaults_preserved():
    def func(_arg, *, default="foo"):
        return default

    func2 = alias_function(func, "func2")

    assert func(None) == "foo"
    assert func2(None) == "foo"
