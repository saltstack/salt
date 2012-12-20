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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(SysModuleTest)
