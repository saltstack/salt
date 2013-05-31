import re
import integration


class SysModuleTest(integration.ModuleCase):
    '''
    Validate the sys module
    '''
    def test_list_functions(self):
        '''
        sys.list_functions
        '''
        funcs = self.run_function('sys.list_functions')
        self.assertTrue('hosts.list_hosts' in funcs)
        self.assertTrue('pkg.install' in funcs)

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
        docs = self.run_function('sys.doc')
        nodoc = set()
        noexample = set()
        allow_failure = ('pkg.expand_repo_def',)
        for fun in docs:
            if fun.startswith('runtests_helpers'):
                continue
            if fun in allow_failure:
                continue
            if not isinstance(docs[fun], basestring):
                nodoc.add(fun)
            elif not re.search(r'([E|e]xample(?:s)?)+(?:.*)::', docs[fun]):
                noexample.add(fun)

        if not nodoc and not noexample:
            return

        raise AssertionError(
            'There are some functions which do not have a doctring or do not '
            'have an example:\nNo doctring:\n{0}\nNo example:\n{1}\n'.format(
                '\n'.join(['  - {0}'.format(f) for f in sorted(nodoc)]),
                '\n'.join(['  - {0}'.format(f) for f in sorted(noexample)]),
            )
        )

if __name__ == '__main__':
    from integration import run_tests
    run_tests(SysModuleTest)
