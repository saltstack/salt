# -*- coding: utf-8 -*-

'''
salt daemons raet unit test package

To run  the unittests:

from salt.daemons import test
test.run()

'''
# pylint: skip-file
# pylint: disable=C0103

import sys
if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest
import os


from ioflo.base.consoling import getConsole
console = getConsole()
console.reinit(verbosity=console.Wordage.concise)

def run(start=None):
    '''
    Run unittests starting at directory given by start
    Default start is the location of the raet package
    '''
    top = os.path.dirname(os.path.dirname(os.path.abspath(
        sys.modules.get(__name__).__file__)))

    if not start:
        start = top

    console.terse("\nRunning all salt.daemons unit tests in '{0}', starting at '{1}'\n".format(top, start))
    loader = unittest.TestLoader()
    suite = loader.discover(start, 'test_*.py', top )
    unittest.TextTestRunner(verbosity=2).run(suite)

if __name__ == "__main__":
    run()
