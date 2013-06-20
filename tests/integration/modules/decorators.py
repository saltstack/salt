import integration


class DecoratorTest(integration.ModuleCase):
    def test_module(self):
        self.assertTrue(
                self.run_function(
                    'runtests_decorators.working_function'
                    )
                )

    def not_test_depends(self):
        ret = self.run_function('runtests_decorators.depends')
        self.assertTrue(ret['ret'])
        self.assertTrue(type(ret['time']) == float)

    def test_missing_depends(self):
        self.assertIn(
                'is not available',
                self.run_function('runtests_decorators.missing_depends'
                    )
                )

    def not_test_depends_will_fallback(self):
        ret = self.run_function('runtests_decorators.depends_will_fallback')
        self.assertTrue(ret['ret'])
        self.assertTrue(type(ret['time']) == float)

    def test_missing_depends_again(self):
        self.assertIn(
                'fallback',
                self.run_function(
                    'runtests_decorators.missing_depends_will_fallback'
                    )
                )

