# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import logging
import re

log = logging.getLogger(__name__)

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
        sys.list_moduels
        '''
        mods = self.run_function('sys.list_modules')
        self.assertTrue('hosts' in mods)
        self.assertTrue('pkg' in mods)

    def test_valid_docs(self):
        '''
        Make sure no functions are exposed that don't have valid docstrings
        '''
        mods = self.run_function('sys.list_modules')
        nodoc = set()
        noexample = set()
        allow_failure = (
                'cp.recv',
                'lxc.run_cmd',
                'ipset.long_range',
                'pkg.expand_repo_def',
                'runtests_decorators.depends',
                'runtests_decorators.depends_will_fallback',
                'runtests_decorators.missing_depends',
                'runtests_decorators.missing_depends_will_fallback',
                'swift.head',
                'glance.warn_until',
                'yumpkg.expand_repo_def',
                'yumpkg5.expand_repo_def',
                'container_resource.run',
                'nspawn.stop',
                'nspawn.restart',
                'lowpkg.bin_pkg_info',
                'state.apply',
                'pip.iteritems',
        )

        batches = 2
        mod_count = len(mods)
        batch_size = mod_count / float(batches)
        if batch_size.is_integer():
            batch_size = int(batch_size)
        else:
            # Check if the module count is evenly divisible by the number of
            # batches. If not, increase the batch_size by the number of batches
            # being run. This ensures that we get the correct number of
            # batches, and that we don't end up running sys.doc an extra time
            # to cover the remainder. For example, if we had a batch count of 2
            # and 121 modules, if we just divided by 2 we'd end up running
            # sys.doc 3 times.
            batch_size = int(batch_size) + batches

        log.debug('test_valid_docs batch size = %s', batch_size)
        start = 0
        end = batch_size
        while start <= mod_count:
            log.debug('running sys.doc on mods[%s:%s]', start, end)
            docs = self.run_function('sys.doc', mods[start:end])
            if docs == 'VALUE TRIMMED':
                self.fail(
                    'sys.doc output trimmed. It may be necessary to increase '
                    'the number of batches'
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
            start += batch_size
            end += batch_size

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
