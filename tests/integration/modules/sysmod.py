# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import re

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration

# Import 3rd-party libs
import salt.ext.six as six


class SysModuleTest(integration.ModuleCase):
    '''
    Validate the sys module
    '''
    def test_list_functions(self):
        '''
        sys.list_functions
        '''
        # Get all functions
        funcs = self.run_function('sys.list_functions')
        self.assertIn('hosts.list_hosts', funcs)
        self.assertIn('pkg.install', funcs)

        # Just sysctl
        funcs = self.run_function('sys.list_functions', ('sysctl',))
        self.assertNotIn('sys.doc', funcs)
        self.assertIn('sysctl.get', funcs)

        # Just sys
        funcs = self.run_function('sys.list_functions', ('sys.',))
        self.assertNotIn('sysctl.get', funcs)
        self.assertIn('sys.doc', funcs)

        # Staring with sys
        funcs = self.run_function('sys.list_functions', ('sys',))
        self.assertNotIn('sysctl.get', funcs)
        self.assertIn('sys.doc', funcs)

    def test_list_modules(self):
        '''
        sys.list_modules
        '''
        mods = self.run_function('sys.list_modules')
        self.assertTrue('hosts' in mods)
        self.assertTrue('pkg' in mods)

    def test_list_modules_with_arg(self):
        '''
        sys.list_modules u*

        Tests getting the list of modules looking for the "user" module
        '''
        mods = self.run_function('sys.list_modules', 'u*')
        self.assertIn('user', mods)

    def test_list_modules_with_arg_exact_match(self):
        '''
        sys.list_modules user

        Tests getting the list of modules looking for the "user" module with
        an exact match of 'user' being passed at the CLI instead of something
        with '*'.
        '''
        mods = self.run_function('sys.list_modules', 'user')
        self.assertIn('user', mods)

    def test_valid_docs(self):
        '''
        Make sure no functions are exposed that don't have valid docstrings
        '''
        docs = self.run_function('sys.doc')
        nodoc = set()
        noexample = set()
        allow_failure = (
                'cp.recv',
                'lxc.run_cmd',
                'pkg.expand_repo_def',
                'runtests_decorators.depends',
                'runtests_decorators.depends_will_fallback',
                'runtests_decorators.missing_depends',
                'runtests_decorators.missing_depends_will_fallback',
                'yumpkg.expand_repo_def',
                'yumpkg5.expand_repo_def',
                'container_resource.run',
                'nspawn.stop',
                'nspawn.restart',
                'lowpkg.bin_pkg_info',
                'state.apply',
        )

        for fun in docs:
            if fun.startswith('runtests_helpers'):
                continue
            if fun in allow_failure:
                continue
            if not isinstance(docs[fun], six.string_types):
                nodoc.add(fun)
            elif not re.search(r'([E|e]xample(?:s)?)+(?:.*)::?', docs[fun]):
                noexample.add(fun)

        if not nodoc and not noexample:
            return

        raise AssertionError(
            'There are some functions which do not have a docstring or do not '
            'have an example:\nNo docstring:\n{0}\nNo example:\n{1}\n'.format(
                '\n'.join(['  - {0}'.format(f) for f in sorted(nodoc)]),
                '\n'.join(['  - {0}'.format(f) for f in sorted(noexample)]),
            )
        )


if __name__ == '__main__':
    from integration import run_tests
    run_tests(SysModuleTest)
