# -*- coding: utf-8 -*-
'''
    :codeauthor: Bo Maryniuk <bo@suse.de>
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import patch, MagicMock, NO_MOCK, NO_MOCK_REASON
from tests.support.helpers import dedent
from salt.modules import saltsupport
import salt.exceptions
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

    @patch('tempfile.gettempdir', MagicMock(return_value=os.path.join('mnt', 'storage')))
    @patch('salt.modules.saltsupport.__grains__', {'fqdn': 'c-3po'})
    @patch('time.strftime', MagicMock(return_value='000'))
    def test_get_archive_name(self):
        '''
        Test archive name construction.

        :return:
        '''
        support = saltsupport.SaltSupportModule()
        assert support._get_archive_name() == os.path.join('mnt', 'storage', 'c-3po-support-000-000.bz2')

    @patch('tempfile.gettempdir', MagicMock(return_value=os.path.join('mnt', 'storage')))
    @patch('salt.modules.saltsupport.__grains__', {'fqdn': 'c-3po'})
    @patch('time.strftime', MagicMock(return_value='000'))
    def test_get_custom_archive_name(self):
        '''
        Test get custom archive name.

        :return:
        '''
        support = saltsupport.SaltSupportModule()
        temp_name = support._get_archive_name(archname='Darth Wader')
        assert temp_name == os.path.join('mnt', 'storage', 'c-3po-darthwader-000-000.bz2')
        temp_name = support._get_archive_name(archname='Яйця з сіллю')
        assert temp_name == os.path.join('mnt', 'storage', 'c-3po-support-000-000.bz2')
        temp_name = support._get_archive_name(archname='!@#$%^&*()Fillip J. Fry')
        assert temp_name == os.path.join('mnt', 'storage', 'c-3po-fillipjfry-000-000.bz2')

    @patch('salt.cli.support.get_profiles', MagicMock(return_value={'message': 'Feature was not beta tested'}))
    def test_profiles_format(self):
        '''
        Test profiles format.

        :return:
        '''
        support = saltsupport.SaltSupportModule()
        profiles = support.profiles()
        assert 'custom' in profiles
        assert 'standard' in profiles
        assert 'message' in profiles['standard']
        assert profiles['custom'] == []
        assert profiles['standard']['message'] == 'Feature was not beta tested'

    @patch('tempfile.gettempdir', MagicMock(return_value=os.path.join('mnt', 'storage')))
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
        files = [
            os.path.join('mnt', 'storage', 'one-support-000-000.bz2'),
            os.path.join('mnt', 'storage', 'two-support-111-111.bz2'),
            os.path.join('mnt', 'storage', '000-support-000-000.bz2'),
        ]
        for name in files:
            assert name in out

    def test_last_archive(self):
        '''
        Get last archive name
        :return:
        '''
        support = saltsupport.SaltSupportModule()
        files = [
            os.path.join('mnt', 'storage', 'one-support-000-000.bz2'),
            os.path.join('mnt', 'storage', 'two-support-111-111.bz2'),
            os.path.join('mnt', 'storage', 'three-support-222-222.bz2'),
        ]
        support.archives = MagicMock(return_value=files)
        assert support.last_archive() == os.path.join('mnt', 'storage', 'three-support-222-222.bz2')

    @patch('os.unlink', MagicMock(return_value=True))
    def test_delete_all_archives_success(self):
        '''
        Test delete archives
        :return:
        '''
        support = saltsupport.SaltSupportModule()
        files = [
            os.path.join('mnt', 'storage', 'one-support-000-000.bz2'),
            os.path.join('mnt', 'storage', 'two-support-111-111.bz2'),
            os.path.join('mnt', 'storage', 'three-support-222-222.bz2'),
        ]
        support.archives = MagicMock(return_value=files)
        ret = support.delete_archives()
        assert 'files' in ret
        assert 'errors' in ret
        assert not bool(ret['errors'])
        assert bool(ret['files'])
        assert isinstance(ret['errors'], dict)
        assert isinstance(ret['files'], dict)

        for arc in support.archives():
            assert ret['files'][arc] == 'removed'

    @patch('os.unlink', MagicMock(return_value=False, side_effect=[OSError('Decreasing electron flux'),
                                                                   OSError('Solar flares interference'),
                                                                   None]))
    def test_delete_all_archives_failure(self):
        '''
        Test delete archives failure
        :return:
        '''
        support = saltsupport.SaltSupportModule()
        files = [
            os.path.join('mnt', 'storage', 'one-support-000-000.bz2'),
            os.path.join('mnt', 'storage', 'two-support-111-111.bz2'),
            os.path.join('mnt', 'storage', 'three-support-222-222.bz2'),
        ]
        support.archives = MagicMock(return_value=files)
        ret = support.delete_archives()
        assert 'files' in ret
        assert 'errors' in ret
        assert bool(ret['errors'])
        assert bool(ret['files'])
        assert isinstance(ret['errors'], dict)
        assert isinstance(ret['files'], dict)

        assert ret['files'][os.path.join('mnt', 'storage', 'three-support-222-222.bz2')] == 'removed'
        assert ret['files'][os.path.join('mnt', 'storage', 'one-support-000-000.bz2')] == 'left'
        assert ret['files'][os.path.join('mnt', 'storage', 'two-support-111-111.bz2')] == 'left'

        assert len(ret['errors']) == 2
        assert ret['errors'][os.path.join('mnt', 'storage', 'one-support-000-000.bz2')] == 'Decreasing electron flux'
        assert ret['errors'][os.path.join('mnt', 'storage', 'two-support-111-111.bz2')] == 'Solar flares interference'

    def test_format_sync_stats(self):
        '''
        Test format rsync stats for preserving ordering of the keys

        :return:
        '''
        support = saltsupport.SaltSupportModule()
        stats = dedent('''
        robot: Bender
        cute: Leela
        weird: Zoidberg
        professor: Farnsworth
        ''')
        f_stats = support.format_sync_stats({'retcode': 0, 'stdout': stats})
        assert list(f_stats['transfer'].keys()) == ['robot', 'cute', 'weird', 'professor']
        assert list(f_stats['transfer'].values()) == ['Bender', 'Leela', 'Zoidberg', 'Farnsworth']

    @patch('tempfile.mkstemp', MagicMock(return_value=(0, 'dummy')))
    @patch('os.close', MagicMock())
    def test_sync_no_archives_failure(self):
        '''
        Test sync failed when no archives specified.

        :return:
        '''
        support = saltsupport.SaltSupportModule()
        support.archives = MagicMock(return_value=[])

        with pytest.raises(salt.exceptions.SaltInvocationError) as err:
            support.sync('group-name')
        assert 'No archives found to transfer' in str(err)

    @patch('tempfile.mkstemp', MagicMock(return_value=(0, 'dummy')))
    @patch('os.path.exists', MagicMock(return_value=False))
    def test_sync_last_picked_archive_not_found_failure(self):
        '''
        Test sync failed when archive was not found (last picked)

        :return:
        '''
        support = saltsupport.SaltSupportModule()
        support.archives = MagicMock(return_value=['/mnt/storage/one-support-000-000.bz2',
                                                   '/mnt/storage/two-support-111-111.bz2',
                                                   '/mnt/storage/three-support-222-222.bz2'])

        with pytest.raises(salt.exceptions.SaltInvocationError) as err:
            support.sync('group-name')
        assert ' Support archive "/mnt/storage/three-support-222-222.bz2" was not found' in str(err)

    @patch('tempfile.mkstemp', MagicMock(return_value=(0, 'dummy')))
    @patch('os.path.exists', MagicMock(return_value=False))
    def test_sync_specified_archive_not_found_failure(self):
        '''
        Test sync failed when archive was not found (last picked)

        :return:
        '''
        support = saltsupport.SaltSupportModule()
        support.archives = MagicMock(return_value=['/mnt/storage/one-support-000-000.bz2',
                                                   '/mnt/storage/two-support-111-111.bz2',
                                                   '/mnt/storage/three-support-222-222.bz2'])

        with pytest.raises(salt.exceptions.SaltInvocationError) as err:
            support.sync('group-name', name='lost.bz2')
        assert ' Support archive "lost.bz2" was not found' in str(err)

    @patch('tempfile.mkstemp', MagicMock(return_value=(0, 'dummy')))
    @patch('os.path.exists', MagicMock(return_value=False))
    @patch('os.close', MagicMock())
    def test_sync_no_archive_to_transfer_failure(self):
        '''
        Test sync failed when no archive was found to transfer

        :return:
        '''
        support = saltsupport.SaltSupportModule()
        support.archives = MagicMock(return_value=[])
        with pytest.raises(salt.exceptions.SaltInvocationError) as err:
            support.sync('group-name', all=True)
        assert 'No archives found to transfer' in str(err)

    @patch('tempfile.mkstemp', MagicMock(return_value=(0, 'dummy')))
    @patch('os.path.exists', MagicMock(return_value=True))
    @patch('os.close', MagicMock())
    @patch('os.write', MagicMock())
    @patch('os.unlink', MagicMock())
    @patch('salt.modules.saltsupport.__salt__', {'rsync.rsync': MagicMock(return_value={})})
    def test_sync_archives(self):
        '''
        Test sync archives
        :return:
        '''
        support = saltsupport.SaltSupportModule()
        support.archives = MagicMock(return_value=['/mnt/storage/one-support-000-000.bz2',
                                                   '/mnt/storage/two-support-111-111.bz2',
                                                   '/mnt/storage/three-support-222-222.bz2'])
        out = support.sync('group-name', host='buzz', all=True, move=False)
        assert 'files' in out
        for arc_name in out['files']:
            assert out['files'][arc_name] == 'copied'
        assert saltsupport.os.unlink.call_count == 1
        assert saltsupport.os.unlink.call_args_list[0][0][0] == 'dummy'
        calls = []
        for call in saltsupport.os.write.call_args_list:
            assert len(call) == 2
            calls.append(call[0])
        assert calls == [(0, b'one-support-000-000.bz2'),
                         (0, os.linesep.encode()), (0, b'two-support-111-111.bz2'), (0, os.linesep.encode()),
                         (0, b'three-support-222-222.bz2'), (0, os.linesep.encode())]

    @patch('salt.modules.saltsupport.__pillar__', {})
    @patch('salt.modules.saltsupport.SupportDataCollector', MagicMock())
    def test_run_support(self):
        '''
        Test run support
        :return:
        '''
        saltsupport.SupportDataCollector(None, None).archive_path = 'dummy'
        support = saltsupport.SaltSupportModule()
        support.collect_internal_data = MagicMock()
        support.collect_local_data = MagicMock()
        out = support.run()

        for section in ['messages', 'archive']:
            assert section in out
        assert out['archive'] == 'dummy'
        for section in ['warning', 'error', 'info']:
            assert section in out['messages']
        ld_call = support.collect_local_data.call_args_list[0][1]
        assert 'profile' in ld_call
        assert ld_call['profile'] == 'default'
        assert 'profile_source' in ld_call
        assert ld_call['profile_source'] is None
        assert support.collector.open.call_count == 1
        assert support.collector.close.call_count == 1
        assert support.collect_internal_data.call_count == 1


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
