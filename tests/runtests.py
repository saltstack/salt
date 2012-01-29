#!/usr/bin/env python
'''
Discover all instances of unittest.TestCase in this directory.

The current working directory must be set to the build of the salt you want to test.
'''
from os.path import dirname, abspath, relpath, splitext, normpath
import sys, os, fnmatch

# Since all the salt tests are written under python 2.7 they take
# advantage of all the new functionality that was added in that
# version. We need to use the unittest2 module on python < 2.7
if sys.version_info[0:2] < (2,7):
    try:
        from unittest2 import TestLoader, TextTestRunner
    except ImportError:
        print "You need to install unittest2 to run the salt tests"
        sys.exit(1)
else:
    from unittest import TestLoader, TextTestRunner

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
