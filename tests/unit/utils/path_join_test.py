# -*- coding: utf-8 -*-
'''
    tests.unit.utils.path_join_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2012 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.
'''

# Import python libs
import os
import sys
import posixpath
import ntpath
import platform
import tempfile

if __name__ == "__main__":
    sys.path.insert(
        0, os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    )

# Import salt libs
from saltunittest import TestCase, TextTestRunner
from salt.utils import path_join


class PathJoinTestCase(TestCase):

    PLATFORM_FUNC = platform.system
    BUILTIN_MODULES = sys.builtin_module_names

    NIX_PATHS = (
        (('/', 'key'), '/key'),
        (('/etc/salt', '/etc/salt/pki'), '/etc/salt/etc/salt/pki'),
        (('/usr/local', '/etc/salt/pki'), '/usr/local/etc/salt/pki')

    )

    WIN_PATHS = (
        (('c:', 'temp', 'foo'), 'c:\\temp\\foo'),
        (('c:', r'\temp', r'\foo'), 'c:\\temp\\foo'),
        (('c:\\', r'\temp', r'\foo'), 'c:\\temp\\foo'),
        ((r'c:\\', r'\temp', r'\foo'), 'c:\\temp\\foo'),
        (('c:', r'\temp', r'\foo', 'bar'), 'c:\\temp\\foo\\bar'),
        (('c:', r'\temp', r'\foo\bar'), 'c:\\temp\\foo\\bar'),
        (('c', r'\temp', r'\foo\bar'), 'c:\\temp\\foo\\bar')
    )

    def test_nix_paths(self):
        if platform.system().lower() == "windows":
            self.skipTest(
                "Windows platform found. not running *nix path_join tests"
            )
        for idx, (parts, expected) in enumerate(self.NIX_PATHS):
            path = path_join(*parts)
            self.assertEqual(
                '{0}: {1}'.format(idx, path),
                '{0}: {1}'.format(idx, expected)
            )

    def test_windows_paths(self):
        if platform.system().lower() != "windows":
            self.skipTest(
                'Non windows platform found. not running non patched os.path '
                'path_join tests'
            )

        for idx, (parts, expected) in enumerate(self.WIN_PATHS):
            path = path_join(*parts)
            self.assertEqual(
                '{0}: {1}'.format(idx, path),
                '{0}: {1}'.format(idx, expected)
            )

    def test_windows_paths_patched_path_module(self):
        if platform.system().lower() == "windows":
            self.skipTest(
                'Windows platform found. not running patched os.path '
                'path_join tests'
            )

        self.__patch_path()

        for idx, (parts, expected) in enumerate(self.WIN_PATHS):
            path = path_join(*parts)
            self.assertEqual(
                '{0}: {1}'.format(idx, path),
                '{0}: {1}'.format(idx, expected)
            )

        self.__unpatch_path()

    def __patch_path(self):
        import imp
        modules = list(self.BUILTIN_MODULES[:])
        modules.pop(modules.index('posix'))
        modules.append('nt')

        code = """'''Salt unittest loaded NT module'''"""
        module = imp.new_module('nt')
        exec code in module.__dict__
        sys.modules['nt'] = module

        sys.builtin_module_names = modules
        platform.system = lambda: "windows"

        for module in (ntpath, os, os.path, tempfile):
            reload(module)

    def __unpatch_path(self):
        del sys.modules['nt']
        sys.builtin_module_names = self.BUILTIN_MODULES[:]
        platform.system = self.PLATFORM_FUNC

        for module in (posixpath, os, os.path, tempfile, platform):
            reload(module)

if __name__ == "__main__":
    loader = PathJoinTestCase()
    tests = loader.loadTestsFromTestCase(PathJoinTestCase)
    TextTestRunner(verbosity=1).run(tests)
