"""
Simple script to dump the contents of msgpack files to the terminal
"""

# pylint: disable=resource-leakage

import os
import pprint
import sys

import salt.utils.msgpack


def dump(path: str) -> None:
    """
    Read in a path and dump the contents to the screen
    """
    if not os.path.isfile(path):
        print("Not a file", file=sys.stderr)
        return
    with open(path, "rb") as fp_:
        data = salt.utils.msgpack.loads(fp_.read())
        pprint.pprint(data)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <path>", file=sys.stderr)
        sys.exit(1)
    dump(sys.argv[1])
