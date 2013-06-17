import integration


class DecoratorTest(integration.ModuleCase):
    def test_module(self):
        self.assertTrue(self.run_function('runtests_decorators.working_function'))

    def test_depends(self):
        ret_val, time = self.run_function('runtests_decorators.depends')
        self.assertTrue(ret_val)
        self.assertTrue(type(time) == float)

    def test_missing_depends(self):
        self.assertTrue('is not available' in self.run_function('runtests_decorators.missing_depends'))

    def test_depends_will_fallback(self):
        ret_val, time = self.run_function('runtests_decorators.depends_will_fallback')
        self.assertTrue(ret_val)
        self.assertTrue(type(time) == float)

    def test_missing_depends(self):
        self.assertTrue('fallback' in self.run_function('runtests_decorators.missing_depends_will_fallback'))

