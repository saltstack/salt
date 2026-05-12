"""
This runner is used only for test purposes and serves no production purpose
"""

import time


def arg(*args, **kwargs):
    """
    Output the given args and kwargs

    Kwargs will be filtered for 'private' keynames.

    CLI Example:

    .. code-block:: bash

        salt-run test.arg foo bar=baz
    """
    kwargs = {k: v for k, v in kwargs.items() if not k.startswith("__")}

    ret = {
        "args": args,
        "kwargs": kwargs,
    }
    return ret


def raw_arg(*args, **kwargs):
    """
    Output the given args and kwargs

    CLI Example:

    .. code-block:: bash

        salt-run test.arg foo __bar=baz
    """
    ret = {
        "args": args,
        "kwargs": kwargs,
    }
    return ret


def metasyntactic(locality="us"):
    """
    Return common metasyntactic variables for the given locality

    CLI Example:

    .. code-block:: bash

        salt-run test.metasyntactic locality=uk
    """
    lookup = {
        "us": [
            "foo",
            "bar",
            "baz",
            "qux",
            "quux",
            "quuz",
            "corge",
            "grault",
            "garply",
            "waldo",
            "fred",
            "plugh",
            "xyzzy",
            "thud",
        ],
        "uk": ["wibble", "wobble", "wubble", "flob"],
    }
    return lookup.get(locality, None)


def stdout_print():
    """
    Print 'foo' and return 'bar'

    CLI Example:

    .. code-block:: bash

        salt-run test.stdout_print
    """
    print("foo")
    return "bar"


def sleep(s_time=10):
    """
    Sleep t seconds, then return True

    CLI Example:

    .. code-block:: bash

        salt-run test.sleep s_time=5
    """
    print(s_time)
    time.sleep(s_time)
    return True


def stream():
    """
    Fire a stream of 100 test events, then return True

    CLI Example:

    .. code-block:: bash

        salt-run test.stream
    """
    ret = True
    for i in range(1, 100):
        __jid_event__.fire_event({"message": f"Runner is {i}% done"}, "progress")
        time.sleep(0.1)
    return ret


def get_opts():
    """
    .. versionadded:: 2018.3.0

    Return the configuration options of the master.

    CLI Example:

    .. code-block:: bash

        salt-run test.get_opts
    """
    return __opts__
