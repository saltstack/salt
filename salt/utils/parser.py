# -*- coding: utf-8 -*-
"""
    salt.utils.parser
    ~~~~~~~~~~~~~~~~~

    :copyright: © 2012 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: Apache 2.0, see LICENSE for more details.
"""

import sys
import optparse
from salt import version


class OptionParser(optparse.OptionParser):

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("version", version.__version__)
        kwargs.setdefault('usage', '%prog')
        optparse.OptionParser.__init__(self, *args, **kwargs)

    def parse_args(self, args=None, values=None):
        options, args = optparse.OptionParser.parse_args(self, args, values)
        if options.versions_report:
            self.print_versions_report()
        return options, args

    def _add_version_option(self):
        optparse.OptionParser._add_version_option(self)
        self.add_option(
            '--versions-report', action='store_true',
            help="show program's dependencies version number and exit"
        )

    def print_versions_report(self, file=sys.stdout):
        print >> file, '\n'.join(version.versions_report())
        self.exit()