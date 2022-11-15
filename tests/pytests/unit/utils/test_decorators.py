import pytest

import salt.utils.decorators


def test_classproperty():
    class Foo:
        @salt.utils.decorators.classproperty
        def prop(cls):  # pylint: disable=no-self-argument
            return cls

    assert Foo.prop is Foo
    assert Foo().prop is Foo


def test_classproperty_getter():
    class Foo:
        @salt.utils.decorators.classproperty
        def prop(cls):  # pylint: disable=no-self-argument
            return "old"

        @prop.getter
        def prop(cls):  # pylint: disable=no-self-argument
            return "new"

    assert Foo.prop == "new"
    assert Foo().prop == "new"


def test_classproperty_setter():
    with pytest.raises(NotImplementedError):

        class Foo:
            @salt.utils.decorators.classproperty
            def prop(cls):  # pylint: disable=no-self-argument
                return "getter"

            @prop.setter
            def prop(cls, val):  # pylint: disable=no-self-argument
                return "setter"


def test_classproperty_deleter():
    with pytest.raises(NotImplementedError):

        class Foo:
            @salt.utils.decorators.classproperty
            def prop(cls):  # pylint: disable=no-self-argument
                return "getter"

            @prop.deleter
            def prop(cls):  # pylint: disable=no-self-argument
                return "deleter"
