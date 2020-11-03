# -*- coding: utf-8 -*-
# pylint: disable=resource-leakage

# Import Python libs
from __future__ import absolute_import, print_function

import hashlib
import optparse
import pprint
import subprocess

# Import Salt libs
import salt.utils.color
import salt.utils.files
import salt.utils.yaml

# Import 3rd-party libs
from salt.ext import six

colors = salt.utils.color.get_colors()


def parse():
    """
    Parse command line options
    """
    parser = optparse.OptionParser()
    parser.add_option(
        "-r",
        "--runs",
        dest="runs",
        default=10,
        type=int,
        help="Specify the number of times to run the consistency check",
    )
    parser.add_option(
        "-c",
        "--command",
        dest="command",
        default="state.show_highstate",
        help="The command to execute",
    )

    options, args = parser.parse_args()
    return options.__dict__


def run(command):
    """
    Execute a single command and check the returns
    """
    cmd = r"salt \* {0} --yaml-out -t 500 > high".format(command)
    subprocess.call(cmd, shell=True)
    with salt.utils.files.fopen("high") as fp_:
        data = salt.utils.yaml.safe_load(fp_)
    hashes = set()
    for key, val in six.iteritems(data):
        has = hashlib.md5(str(val)).hexdigest()
        if has not in hashes:
            print("{0}:".format(has))
            pprint.pprint(val)
        hashes.add(has)
    if len(hashes) > 1:
        print(
            "{0}Command: {1} gave inconsistent returns{2}".format(
                colors["LIGHT_RED"], command, colors["ENDC"]
            )
        )


if __name__ == "__main__":
    opts = parse()
    for _ in opts["runs"]:
        for command in opts["command"].split(","):
            print("-" * 30)
            print("Running command {0}".format(command))
            run(command)
