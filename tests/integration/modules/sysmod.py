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
        bad = set()
        for fun in docs:
            if fun.startswith('runtests_helpers'):
                continue
            if not isinstance(docs[fun], basestring):
                bad.add(fun)
            elif not 'Example::' in docs[fun]:
                if not 'Examples::' in docs[fun]:
                    bad.add(fun)
        if bad:
            import pprint
            pprint.pprint(sorted(bad))
        self.assertFalse(bool(bad))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(SysModuleTest)
