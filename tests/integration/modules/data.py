# -*- coding: utf-8 -*-

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration


class DataModuleTest(integration.ModuleCase):
    '''
    Validate the data module
    '''
    def _clear_db(self):
        '''
        Clear out the database
        '''
        self.run_function('data.clear')

    def test_load_dump(self):
        '''
        data.load
        data.dump
        '''
        self._clear_db()
        self.assertTrue(self.run_function('data.dump', ['{"foo": "bar"}']))
        self.assertEqual(self.run_function('data.load'), {'foo': 'bar'})
        self._clear_db()

    def test_get_update(self):
        '''
        data.getval
        data.update
        data.getvals
        '''
        self._clear_db()
        self.assertTrue(
                self.run_function(
                    'data.update',
                    ['spam', 'eggs']
                    )
                )
        self.assertEqual(
                self.run_function(
                    'data.getval',
                    ['spam']
                    ),
                'eggs'
                )
        self.assertTrue(
                self.run_function(
                    'data.update',
                    ['unladen', 'swallow']
                    )
                )
        self.assertEqual(
                self.run_function(
                    'data.getvals',
                    ['spam', 'unladen']
                    ),
                ['eggs', 'swallow']
                )
        self._clear_db()


if __name__ == '__main__':
    from integration import run_tests
    run_tests(DataModuleTest)
