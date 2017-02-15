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
    def test_valid_docs(self):
        '''
        Make sure no functions are exposed that don't have valid docstrings
        '''
        mods = self.run_function('sys.list_modules')
        nodoc = set()
        noexample = set()
        allow_failure = (
            'container_resource.run',
            'cmd.win_runas',
            'cp.recv',
            'glance.warn_until',
            'ipset.long_range',
            'libcloud_dns.get_driver',
            'log.critical',
            'log.debug',
            'log.error',
            'log.exception',
            'log.info',
            'log.warning',
            'lowpkg.bin_pkg_info',
            'lxc.run_cmd',
            'nspawn.restart',
            'nspawn.stop',
            'pkg.expand_repo_def',
            'pip.iteritems',
            'runtests_decorators.depends',
            'runtests_decorators.depends_will_fallback',
            'runtests_decorators.missing_depends',
            'runtests_decorators.missing_depends_will_fallback',
            'state.apply',
            'status.list2cmdline',
            'swift.head',
            'travisci.parse_qs',
            'vsphere.clean_kwargs',
            'vsphere.disconnect',
            'vsphere.get_service_instance_via_proxy',
            'vsphere.gets_service_instance_via_proxy',
            'vsphere.supports_proxies',
            'vsphere.test_vcenter_connection',
            'vsphere.wraps',
            'yumpkg.expand_repo_def',
            'yumpkg5.expand_repo_def',
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
                if isinstance(docs, dict) and not isinstance(docs[fun], six.string_types):
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
