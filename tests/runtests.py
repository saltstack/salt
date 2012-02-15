#!/usr/bin/env python
'''
Discover all instances of unittest.TestCase in this directory.
'''
# Import python libs
import os
# Import salt libs
import saltunittest

TEST_DIR = os.path.dirname(os.path.normpath(os.path.abspath(__file__)))

def main():
    saltunittest.TestDaemon()
    loader = saltunittest.TestLoader()
    tests = loader.discover(os.path.join(TEST_DIR, 'modules'), '*.py')
    saltunittest.TextTestRunner(verbosity=1).run(tests)


if __name__ == "__main__":
    main()
