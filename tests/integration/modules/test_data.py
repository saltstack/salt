# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
import tests.integration as integration


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
        data.get
        data.update
        '''
        self._clear_db()
        self.assertTrue(self.run_function('data.update', ['spam', 'eggs']))
        self.assertEqual(self.run_function('data.get', ['spam']), 'eggs')

        self.assertTrue(self.run_function('data.update', ['unladen', 'swallow']))
        self.assertEqual(self.run_function('data.get', ['["spam", "unladen"]']), ['eggs', 'swallow'])
        self._clear_db()

    def test_cas_update(self):
        '''
        data.update
        data.cas
        data.get
        '''
        self._clear_db()
        self.assertTrue(self.run_function('data.update', ['spam', 'eggs']))
        self.assertTrue(self.run_function('data.cas', ['spam', 'green', 'eggs']))
        self.assertEqual(self.run_function('data.get', ['spam']), 'green')
