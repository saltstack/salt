# -*- coding: utf-8 -*-
'''
    :codeauthor: Bo Maryniuk <bo@suse.de>
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import patch, MagicMock, NO_MOCK, NO_MOCK_REASON
from salt.modules import saltsupport
import datetime

try:
    import pytest
except ImportError:
    pytest = None


@skipIf(not bool(pytest), 'Pytest required')
@skipIf(NO_MOCK, NO_MOCK_REASON)
class SaltSupportModuleTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.support::SaltSupportModule
    '''
    def setup_loader_modules(self):
        return {saltsupport: {}}

    @patch('tempfile.gettempdir', MagicMock(return_value='/mnt/storage'))
    @patch('salt.modules.saltsupport.__grains__', {'fqdn': 'c-3po'})
    @patch('time.strftime', MagicMock(return_value='000'))
    def test_get_archive_name(self):
        '''
        Test archive name construction.

        :return:
        '''
        assert saltsupport.SaltSupportModule()._get_archive_name() == '/mnt/storage/c-3po-support-000-000.bz2'

    @patch('tempfile.gettempdir', MagicMock(return_value='/mnt/storage'))
    @patch('salt.modules.saltsupport.__grains__', {'fqdn': 'c-3po'})
    @patch('time.strftime', MagicMock(return_value='000'))
    def test_get_custom_archive_name(self):
        '''
        Test get custom archive name.

        :return:
        '''
        support = saltsupport.SaltSupportModule()
        temp_name = support._get_archive_name(archname='Darth Wader')
        assert temp_name == '/mnt/storage/c-3po-darthwader-000-000.bz2'
        temp_name = support._get_archive_name(archname='Яйця з сіллю')
        assert temp_name == '/mnt/storage/c-3po-support-000-000.bz2'
        temp_name = support._get_archive_name(archname='!@#$%^&*()Fillip J. Fry')
        assert temp_name == '/mnt/storage/c-3po-fillipjfry-000-000.bz2'

    @patch('salt.cli.support.get_profiles', MagicMock(return_value={'message': 'Feature was not beta tested'}))
    def test_profiles_format(self):
        '''
        Test profiles format.

        :return:
        '''
        profiles = saltsupport.SaltSupportModule().profiles()
        assert 'custom' in profiles
        assert 'standard' in profiles
        assert 'message' in profiles['standard']
        assert profiles['custom'] == []
        assert profiles['standard']['message'] == 'Feature was not beta tested'

    @patch('tempfile.gettempdir', MagicMock(return_value='/mnt/storage'))
    @patch('os.listdir', MagicMock(return_value=['one-support-000-000.bz2', 'two-support-111-111.bz2', 'trash.bz2',
                                                 'hostname-000-000.bz2', 'three-support-wrong222-222.bz2',
                                                 '000-support-000-000.bz2']))
    def test_get_existing_archives(self):
        '''
        Get list of existing archives.

        :return:
        '''
        support = saltsupport.SaltSupportModule()
        out = support.archives()
        assert len(out) == 3
        for name in ['/mnt/storage/one-support-000-000.bz2', '/mnt/storage/two-support-111-111.bz2',
                     '/mnt/storage/000-support-000-000.bz2']:
            assert name in out


@skipIf(not bool(pytest), 'Pytest required')
@skipIf(NO_MOCK, NO_MOCK_REASON)
class LogCollectorTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.support::LogCollector
    '''
    def setup_loader_modules(self):
        return {saltsupport: {}}

    def test_msg(self):
        '''
        Test message to the log collector.

        :return:
        '''
        utcmock = MagicMock()
        utcmock.utcnow = MagicMock(return_value=datetime.datetime.utcfromtimestamp(0))
        with patch('datetime.datetime', utcmock):
            msg = 'Upgrading /dev/null device'
            out = saltsupport.LogCollector()
            out.msg(msg, title='Here')
            assert saltsupport.LogCollector.INFO in out.messages
            assert type(out.messages[saltsupport.LogCollector.INFO]) == saltsupport.LogCollector.MessagesList
            assert out.messages[saltsupport.LogCollector.INFO] == ['00:00:00.000 - {0}: {1}'.format('Here', msg)]

    def test_info_message(self):
        '''
        Test info message to the log collector.

        :return:
        '''
        utcmock = MagicMock()
        utcmock.utcnow = MagicMock(return_value=datetime.datetime.utcfromtimestamp(0))
        with patch('datetime.datetime', utcmock):
            msg = 'SIMM crosstalk during tectonic stress'
            out = saltsupport.LogCollector()
            out.info(msg)
            assert saltsupport.LogCollector.INFO in out.messages
            assert type(out.messages[saltsupport.LogCollector.INFO]) == saltsupport.LogCollector.MessagesList
            assert out.messages[saltsupport.LogCollector.INFO] == ['00:00:00.000 - {}'.format(msg)]

    def test_put_message(self):
        '''
        Test put message to the log collector.

        :return:
        '''
        utcmock = MagicMock()
        utcmock.utcnow = MagicMock(return_value=datetime.datetime.utcfromtimestamp(0))
        with patch('datetime.datetime', utcmock):
            msg = 'Webmaster kidnapped by evil cult'
            out = saltsupport.LogCollector()
            out.put(msg)
            assert saltsupport.LogCollector.INFO in out.messages
            assert type(out.messages[saltsupport.LogCollector.INFO]) == saltsupport.LogCollector.MessagesList
            assert out.messages[saltsupport.LogCollector.INFO] == ['00:00:00.000 - {}'.format(msg)]

    def test_warning_message(self):
        '''
        Test warning message to the log collector.

        :return:
        '''
        utcmock = MagicMock()
        utcmock.utcnow = MagicMock(return_value=datetime.datetime.utcfromtimestamp(0))
        with patch('datetime.datetime', utcmock):
            msg = 'Your e-mail is now being delivered by USPS'
            out = saltsupport.LogCollector()
            out.warning(msg)
            assert saltsupport.LogCollector.WARNING in out.messages
            assert type(out.messages[saltsupport.LogCollector.WARNING]) == saltsupport.LogCollector.MessagesList
            assert out.messages[saltsupport.LogCollector.WARNING] == ['00:00:00.000 - {}'.format(msg)]

    def test_error_message(self):
        '''
        Test error message to the log collector.

        :return:
        '''
        utcmock = MagicMock()
        utcmock.utcnow = MagicMock(return_value=datetime.datetime.utcfromtimestamp(0))
        with patch('datetime.datetime', utcmock):
            msg = 'Learning curve appears to be fractal'
            out = saltsupport.LogCollector()
            out.error(msg)
            assert saltsupport.LogCollector.ERROR in out.messages
            assert type(out.messages[saltsupport.LogCollector.ERROR]) == saltsupport.LogCollector.MessagesList
            assert out.messages[saltsupport.LogCollector.ERROR] == ['00:00:00.000 - {}'.format(msg)]

    def test_hl_message(self):
        '''
        Test highlighter message to the log collector.

        :return:
        '''
        utcmock = MagicMock()
        utcmock.utcnow = MagicMock(return_value=datetime.datetime.utcfromtimestamp(0))
        with patch('datetime.datetime', utcmock):
            out = saltsupport.LogCollector()
            out.highlight('The {} TTYs became {} TTYs and vice versa', 'real', 'pseudo')
            assert saltsupport.LogCollector.INFO in out.messages
            assert type(out.messages[saltsupport.LogCollector.INFO]) == saltsupport.LogCollector.MessagesList
            assert out.messages[saltsupport.LogCollector.INFO] == ['00:00:00.000 - The real TTYs became '
                                                                   'pseudo TTYs and vice versa']
