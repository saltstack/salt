import pytest

from salt.runners import manage


def test_deprecation_58638():
    # check that type error will be raised
    pytest.raises(TypeError, manage.list_state, show_ipv4="data")

    # check that show_ipv4 will raise an error
    try:
        manage.list_state(show_ipv4="data")  # pylint: disable=unexpected-keyword-arg
    except TypeError as no_show_ipv4:
        assert (
            str(no_show_ipv4)
            == "list_state() got an unexpected keyword argument 'show_ipv4'"
        )
