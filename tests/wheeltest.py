#!/usr/bin/env python
"""
Test interacting with the wheel system. This script is useful when testing
wheel modules
"""


import optparse
import pprint

import salt.auth
import salt.config
import salt.wheel


def parse():
    """
    Parse the command line options
    """
    parser = optparse.OptionParser()
    parser.add_option(
        "-f", "--fun", "--function", dest="fun", help="The wheel function to execute"
    )
    parser.add_option(
        "-a",
        "--auth",
        dest="eauth",
        help="The external authentication mechanism to use",
    )

    options, args = parser.parse_args()

    cli = options.__dict__

    for arg in args:
        if "=" in arg:
            comps = arg.split("=")
            cli[comps[0]] = comps[1]
    return cli


class Wheeler:
    """
    Set up communication with the wheel interface
    """

    def __init__(self, cli):
        self.opts = salt.config.master_config("/etc/salt")
        self.opts.update(cli)
        self.__eauth()
        self.wheel = salt.wheel.Wheel(self.opts)

    def __eauth(self):
        """
        Fill in the blanks for the eauth system
        """
        if self.opts["eauth"]:
            resolver = salt.auth.Resolver(self.opts)
            res = resolver.cli(self.opts["eauth"])
        self.opts.update(res)

    def run(self):
        """
        Execute the wheel call
        """
        return self.wheel.master_call(**self.opts)


if __name__ == "__main__":
    wheeler = Wheeler(parse())
    pprint.pprint(wheeler.run())
