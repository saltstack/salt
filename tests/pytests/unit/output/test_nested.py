"""
Unit tests for the Nested outputter
"""

import pytest

import salt.output.nested as nested


@pytest.fixture
def configure_loader_modules():
    return {nested: {"__opts__": {"extension_modules": "", "color": True}}}


@pytest.fixture
def data():
    # The example from the documentation for the test.arg execution function
    # Same function from the highstate outputter
    return {
        "local": {
            "args": (1, "two", 3.1),
            "kwargs": {
                "__pub_pid": 25938,
                "wow": {"a": 1, "b": "hello"},
                "__pub_fun": "test.arg",
                "__pub_jid": "20171207105927331329",
                "__pub_tgt": "salt-call",
                "txt": "hello",
            },
        }
    }


def test_output_with_colors(data):
    # Should look exactly like that, with the default color scheme:
    #
    # local:
    #    ----------
    #    args:
    #        - 1
    #        - two
    #        - 3.1
    #    kwargs:
    #        ----------
    #        __pub_fun:
    #            test.arg
    #        __pub_jid:
    #            20171207105927331329
    #        __pub_pid:
    #            25938
    #        __pub_tgt:
    #            salt-call
    #        txt:
    #            hello
    #        wow:
    #            ----------
    #            a:
    #                1
    #            b:
    #                hello
    expected_output_str = (
        "\x1b[0;36mlocal\x1b[0;0m:\n    \x1b[0;36m----------\x1b[0;0m\n   "
        " \x1b[0;36margs\x1b[0;0m:\n        \x1b[0;1;33m- 1\x1b[0;0m\n       "
        " \x1b[0;32m- two\x1b[0;0m\n        \x1b[0;1;33m- 3.1\x1b[0;0m\n   "
        " \x1b[0;36mkwargs\x1b[0;0m:\n        \x1b[0;36m----------\x1b[0;0m\n      "
        "  \x1b[0;36m__pub_fun\x1b[0;0m:\n            \x1b[0;32mtest.arg\x1b[0;0m\n"
        "        \x1b[0;36m__pub_jid\x1b[0;0m:\n           "
        " \x1b[0;32m20171207105927331329\x1b[0;0m\n       "
        " \x1b[0;36m__pub_pid\x1b[0;0m:\n            \x1b[0;1;33m25938\x1b[0;0m\n  "
        "      \x1b[0;36m__pub_tgt\x1b[0;0m:\n           "
        " \x1b[0;32msalt-call\x1b[0;0m\n        \x1b[0;36mtxt\x1b[0;0m:\n          "
        "  \x1b[0;32mhello\x1b[0;0m\n        \x1b[0;36mwow\x1b[0;0m:\n           "
        " \x1b[0;36m----------\x1b[0;0m\n            \x1b[0;36ma\x1b[0;0m:\n       "
        "         \x1b[0;1;33m1\x1b[0;0m\n            \x1b[0;36mb\x1b[0;0m:\n      "
        "          \x1b[0;32mhello\x1b[0;0m"
    )
    ret = nested.output(data)
    assert ret == expected_output_str


def test_output_with_retcode(data):
    # Non-zero retcode should change the colors
    # Same output format as above, just different colors
    expected_output_str = (
        "\x1b[0;31mlocal\x1b[0;0m:\n    \x1b[0;31m----------\x1b[0;0m\n   "
        " \x1b[0;31margs\x1b[0;0m:\n        \x1b[0;1;33m- 1\x1b[0;0m\n       "
        " \x1b[0;32m- two\x1b[0;0m\n        \x1b[0;1;33m- 3.1\x1b[0;0m\n   "
        " \x1b[0;31mkwargs\x1b[0;0m:\n        \x1b[0;31m----------\x1b[0;0m\n      "
        "  \x1b[0;31m__pub_fun\x1b[0;0m:\n            \x1b[0;32mtest.arg\x1b[0;0m\n"
        "        \x1b[0;31m__pub_jid\x1b[0;0m:\n           "
        " \x1b[0;32m20171207105927331329\x1b[0;0m\n       "
        " \x1b[0;31m__pub_pid\x1b[0;0m:\n            \x1b[0;1;33m25938\x1b[0;0m\n  "
        "      \x1b[0;31m__pub_tgt\x1b[0;0m:\n           "
        " \x1b[0;32msalt-call\x1b[0;0m\n        \x1b[0;31mtxt\x1b[0;0m:\n          "
        "  \x1b[0;32mhello\x1b[0;0m\n        \x1b[0;31mwow\x1b[0;0m:\n           "
        " \x1b[0;31m----------\x1b[0;0m\n            \x1b[0;31ma\x1b[0;0m:\n       "
        "         \x1b[0;1;33m1\x1b[0;0m\n            \x1b[0;31mb\x1b[0;0m:\n      "
        "          \x1b[0;32mhello\x1b[0;0m"
    )
    # You can notice that in test_output_with_colors the color code is \x1b[0;36m, i.e., GREEN,
    # while here the color code is \x1b[0;31m, i.e., RED (failure)
    ret = nested.output(data, _retcode=1)
    assert ret == expected_output_str


def test_output_with_indent(data):
    # Everything must be indented by exactly two spaces
    # (using nested_indent=2 sent to nested.output as kwarg)
    expected_output_str = (
        "  \x1b[0;36m----------\x1b[0;0m\n  \x1b[0;36mlocal\x1b[0;0m:\n     "
        " \x1b[0;36m----------\x1b[0;0m\n      \x1b[0;36margs\x1b[0;0m:\n         "
        " \x1b[0;1;33m- 1\x1b[0;0m\n          \x1b[0;32m- two\x1b[0;0m\n         "
        " \x1b[0;1;33m- 3.1\x1b[0;0m\n      \x1b[0;36mkwargs\x1b[0;0m:\n         "
        " \x1b[0;36m----------\x1b[0;0m\n          \x1b[0;36m__pub_fun\x1b[0;0m:\n "
        "             \x1b[0;32mtest.arg\x1b[0;0m\n         "
        " \x1b[0;36m__pub_jid\x1b[0;0m:\n             "
        " \x1b[0;32m20171207105927331329\x1b[0;0m\n         "
        " \x1b[0;36m__pub_pid\x1b[0;0m:\n              \x1b[0;1;33m25938\x1b[0;0m\n"
        "          \x1b[0;36m__pub_tgt\x1b[0;0m:\n             "
        " \x1b[0;32msalt-call\x1b[0;0m\n          \x1b[0;36mtxt\x1b[0;0m:\n        "
        "      \x1b[0;32mhello\x1b[0;0m\n          \x1b[0;36mwow\x1b[0;0m:\n       "
        "       \x1b[0;36m----------\x1b[0;0m\n             "
        " \x1b[0;36ma\x1b[0;0m:\n                  \x1b[0;1;33m1\x1b[0;0m\n        "
        "      \x1b[0;36mb\x1b[0;0m:\n                  \x1b[0;32mhello\x1b[0;0m"
    )
    ret = nested.output(data, nested_indent=2)
    assert ret == expected_output_str


def test_display_with_integer_keys():
    """
    Test display output when ret contains a combination of integer and
    string keys. See issue #56909
    """
    nest = nested.NestDisplay(retcode=0)
    test_dict = {1: "test int 1", 2: "test int 2", "three": "test text three"}
    lines = nest.display(ret=test_dict, indent=2, prefix="", out=[])
    expected = [
        "  \x1b[0;36m----------\x1b[0;0m",
        "  \x1b[0;36m1\x1b[0;0m:",
        "      \x1b[0;32mtest int 1\x1b[0;0m",
        "  \x1b[0;36m2\x1b[0;0m:",
        "      \x1b[0;32mtest int 2\x1b[0;0m",
        "  \x1b[0;36mthree\x1b[0;0m:",
        "      \x1b[0;32mtest text three\x1b[0;0m",
    ]
    assert lines == expected
