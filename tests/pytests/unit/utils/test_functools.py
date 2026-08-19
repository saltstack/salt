"""
Unit tests for salt.utils.functools
"""

import salt.utils.functools


def _func_with_kwonly_default(bar=None, *args, baz="default"):
    return (bar, args, baz)


def test_namespaced_function_preserves_kwdefaults():
    """
    namespaced_function must preserve keyword-only argument defaults so that
    calling the clone without those keyword arguments does not raise TypeError.
    """
    cloned = salt.utils.functools.namespaced_function(
        _func_with_kwonly_default, globals()
    )
    assert cloned.__kwdefaults__ == _func_with_kwonly_default.__kwdefaults__
    # Would raise "missing 1 required keyword-only argument: 'baz'" without the fix
    assert cloned("a") == ("a", (), "default")  # pylint: disable=not-callable


def test_alias_function_preserves_kwdefaults():
    """
    alias_function must preserve keyword-only argument defaults so that calling
    the alias without those keyword arguments does not raise TypeError.
    """
    aliased = salt.utils.functools.alias_function(_func_with_kwonly_default, "aliased")
    assert aliased.__kwdefaults__ == _func_with_kwonly_default.__kwdefaults__
    assert aliased("a") == ("a", (), "default")  # pylint: disable=not-callable
