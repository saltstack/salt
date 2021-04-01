"""
This runner is used only for test purposes and servers no production purpose
"""

import time


def arg(*args, **kwargs):
    """
    Output the given args and kwargs

    Kwargs will be filtered for 'private' keynames.
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
    """
    ret = {
        "args": args,
        "kwargs": kwargs,
    }
    return ret


def metasyntactic(locality="us"):
    """
    Return common metasyntactic variables for the given locality
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
    """
    print("foo")
    return "bar"


def sleep(s_time=10):
    """
    Sleep t seconds, then return True
    """
    print(s_time)
    time.sleep(s_time)
    return True


def stream():
    """
    Return True
    """
    ret = True
    for i in range(1, 100):
        __jid_event__.fire_event(
            {"message": "Runner is {}% done".format(i)}, "progress"
        )
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
