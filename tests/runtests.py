#!/usr/bin/env python
'''
Discover all instances of unittest.TestCase in this directory.

The current working directory must be set to the build of the salt you want to test.
'''

# Import python libs
from os.path import dirname, abspath, relpath, splitext, normpath
import sys
import os
import fnmatch

# Import salt libs
from saltunittest import TestLoader, TextTestRunner, TestCase
import salt
import salt.config
import salt.master
import salt.minion

TEST_DIR = dirname(normpath(abspath(__file__)))
SALT_BUILD = os.getcwd()
TEST_FILES = '*.py'

sys.path.insert(0, TEST_DIR)
sys.path.insert(0, SALT_BUILD)

def main():
    names = find_tests()
    tests = TestLoader().loadTestsFromNames(names)
    TextTestRunner(verbosity=1).run(tests)

def find_tests():
    names = []
    for root, _, files in os.walk(TEST_DIR):
        for name in files:
            if fnmatch.fnmatch(name, TEST_FILES) \
                    and not name == 'runtests.py':
                module = get_test_name(root, name)
                if module: names.append(module)
    return names
def get_test_name(root, name):
    if name.startswith("_"): return None
    rel = relpath(root, TEST_DIR).lstrip(".")
    prefix = "%s." % rel.replace('/','.') if rel else ""
    return "".join((prefix, splitext(name)[0]))


if __name__ == "__main__":
    main()
