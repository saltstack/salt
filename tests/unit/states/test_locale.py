# -*- coding: utf-8 -*-
'''
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
'''

# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase
from tests.support.mock import (
    MagicMock,
    patch,
)

# Import Salt Libs
import salt.states.locale as locale


class LocaleTestCase(TestCase, LoaderModuleMockMixin):
    '''
        Validate the locale state
    '''
    def setup_loader_modules(self):
        return {locale: {}}

    def test_system(self):
        '''
            Test to set the locale for the system
        '''
        ret = [{'changes': {}, 'comment': 'System locale salt already set',
                'name': 'salt', 'result': True},
               {'changes': {},
                'comment': 'System locale saltstack needs to be set',
                'name': 'saltstack', 'result': None},
               {'changes': {'locale': 'saltstack'},
                'comment': 'Set system locale saltstack', 'name': 'saltstack',
                'result': True},
               {'changes': {},
                'comment': 'Failed to set system locale to saltstack',
                'name': 'saltstack', 'result': False}]

        mock = MagicMock(return_value="salt")
        with patch.dict(locale.__salt__, {"locale.get_locale": mock}):
            self.assertDictEqual(locale.system("salt"), ret[0])

            with patch.dict(locale.__opts__, {"test": True}):
                self.assertDictEqual(locale.system("saltstack"), ret[1])

            with patch.dict(locale.__opts__, {"test": False}):
                mock = MagicMock(side_effect=[True, False])
                with patch.dict(locale.__salt__, {"locale.set_locale": mock}):
                    self.assertDictEqual(locale.system("saltstack"), ret[2])

                    self.assertDictEqual(locale.system("saltstack"), ret[3])

    def test_present(self):
        '''
            Test to generate a locale if it is not present
        '''
        ret = [{'changes': {},
                'comment': 'Locale salt is already present', 'name': 'salt',
                'result': True},
               {'changes': {},
                'comment': 'Locale salt needs to be generated', 'name': 'salt',
                'result': None},
               {'changes': {'locale': 'salt'},
                'comment': 'Generated locale salt', 'name': 'salt',
                'result': True},
               {'changes': {}, 'comment': 'Failed to generate locale salt',
                'name': 'salt', 'result': False}]

        mock = MagicMock(side_effect=[True, False, False, False])
        with patch.dict(locale.__salt__, {"locale.avail": mock}):
            self.assertDictEqual(locale.present("salt"), ret[0])

            with patch.dict(locale.__opts__, {"test": True}):
                self.assertDictEqual(locale.present("salt"), ret[1])

            with patch.dict(locale.__opts__, {"test": False}):
                mock = MagicMock(side_effect=[True, False])
                with patch.dict(locale.__salt__, {"locale.gen_locale": mock}):
                    self.assertDictEqual(locale.present("salt"), ret[2])

                    self.assertDictEqual(locale.present("salt"), ret[3])
