# -*- coding: utf-8 -*-
'''
    :codeauthor: Anthony Shaw <anthonyshaw@apache.org>
'''

# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)
import salt.states.libcloud_dns as libcloud_dns


_ZONES = [
    {
        'id': '12345',
        'domain': 'test.com',
        'type': 'master',
        'ttl': 3600,
        'extra': {'k': 'v'}
    },
    {
        'id': '455677',
        'domain': 'test2.com',
        'type': 'slave',
        'ttl': 3600,
        'extra': {'k': 'v'}
    }
]


_RECORDS = [
    {
        'id': '45678',
        'name': 'www',
        'type': 'A',
        'data': '127.0.0.1',
        'ttl': 600,
        'extra': {'y': 'x'},
        'zone': _ZONES[0]
    },
    {
        'id': '56789',
        'name': 'mail',
        'type': 'MX',
        'data': '127.0.0.1',
        'ttl': 600,
        'extra': {'y': 'x'},
        'zone': _ZONES[0]
    }
]

_CREATED_RECORD = {
    'id': '45678',
    'name': 'mail',
    'type': 'A',
    'data': '127.0.0.1',
    'ttl': 600,
    'extra': {'ttl': 600, 'y': 'x'},
    'zone': _ZONES[0]
}

_CREATED_ZONE = {
    'id': '455677',
    'domain': 'test3.com',
    'type': 'master',
    'ttl': 3600,
    'extra': {'k': 'v'}
}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class LibcloudDnsModuleTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        return {
            libcloud_dns: {
                '__salt__': {},
                '__opts__': {
                    'test': False
                }
            }
        }

    def test_present_record_exists(self):
        '''
        Try and create a record that already exists
        '''
        ret = {'changes': {},
               'comment': 'Record already exists.',
               'name': 'www',
               'result': True}

        list_zones = MagicMock(return_value=_ZONES)
        list_records = MagicMock(return_value=_RECORDS)
        create_record = MagicMock(return_value='abcdef')

        with patch.dict(libcloud_dns.__salt__,
                        {'libcloud_dns.list_zones': list_zones,
                         'libcloud_dns.list_records': list_records,
                         'libcloud_dns.create_record': create_record}):
            result = libcloud_dns.record_present(name='www', zone='test.com', type='A',
                                                 data='127.0.0.1', profile='test', extra={'y': 'x'})
            assert result == ret
            assert list_zones.called
            list_zones.assert_called_with('test')
            assert not create_record.called

    def test_present_record_exists_mx(self):
        '''
        Try and create a record that already exists (MX)
        '''
        ret = {'changes': {},
               'comment': 'Record already exists.',
               'name': 'mail',
               'result': True}

        list_zones = MagicMock(return_value=_ZONES)
        list_records = MagicMock(return_value=_RECORDS)
        create_record = MagicMock(return_value='abcdef')

        with patch.dict(libcloud_dns.__salt__,
                        {'libcloud_dns.list_zones': list_zones,
                         'libcloud_dns.list_records': list_records,
                         'libcloud_dns.create_record': create_record}):
            result = libcloud_dns.record_present(name='mail', zone='test.com', type='MX',
                                                 data='127.0.0.1', profile='test', extra={'y': 'x'})
            assert result == ret
            assert list_zones.called
            list_zones.assert_called_with('test')
            assert not create_record.called

    def test_present_record_exists_new_ttl(self):
        '''
        Try and change the extra data on a record
        '''
        ret = {'changes': {},
               'comment': 'Record already exists.',
               'name': 'mail',
               'result': True}

        list_zones = MagicMock(return_value=_ZONES)
        list_records = MagicMock(return_value=_RECORDS)
        create_record = MagicMock(return_value='abcdef')
        update_record = MagicMock(return_value=_RECORDS[0])

        with patch.dict(libcloud_dns.__salt__,
                        {'libcloud_dns.list_zones': list_zones,
                         'libcloud_dns.list_records': list_records,
                         'libcloud_dns.create_record': create_record,
                         'libcloud_dns.update_record': update_record}):
            result = libcloud_dns.record_present(name='mail', zone='test.com', type='MX',
                                                 data='127.0.0.1', profile='test', extra={'y': 'x', 'ttl': 500})
            assert result == ret
            assert list_zones.called
            list_zones.assert_called_with('test')
            assert not create_record.called
            assert update_record.called

    def test_present_record_exists_missing_zone(self):
        '''
        Try and create a record with a zone that does not exist
        '''
        ret = {'changes': {},
               'comment': 'Zone could not be found.',
               'name': 'www',
               'result': False}

        list_zones = MagicMock(return_value=_ZONES)
        list_records = MagicMock(return_value=_RECORDS)
        create_record = MagicMock(return_value='abcdef')

        with patch.dict(libcloud_dns.__salt__,
                        {'libcloud_dns.list_zones': list_zones,
                         'libcloud_dns.list_records': list_records,
                         'libcloud_dns.create_record': create_record}):
            result = libcloud_dns.record_present('www', 'notadomain.com', 'A', '127.0.0.1', 'test', extra={'y': 'x'})
            assert result == ret
            assert list_zones.called
            list_zones.assert_called_with('test')
            assert not create_record.called

    def test_present_record_does_not_exist(self):
        '''
        Try and create a record that does not exist
        '''
        ret = {'changes': _CREATED_RECORD,
               'comment': 'Created new record.',
               'name': 'mail',
               'result': True}

        list_zones = MagicMock(return_value=_ZONES)
        list_records = MagicMock(return_value=_RECORDS)
        create_record = MagicMock(return_value=_CREATED_RECORD)

        with patch.dict(libcloud_dns.__salt__,
                        {'libcloud_dns.list_zones': list_zones,
                         'libcloud_dns.list_records': list_records,
                         'libcloud_dns.create_record': create_record}):
            result = libcloud_dns.record_present('mail', 'test.com', 'A', '127.0.0.1', 'test', extra={'y': 'x'})
            assert result == ret
            assert list_zones.called
            list_zones.assert_called_with('test')
            assert create_record.called
            create_record.assert_called_with('mail', '12345', 'A', '127.0.0.1', 'test', extra={'y': 'x'})

    def test_present_record_does_not_exist_test_mode(self):
        '''
        Try and create a record that does not exist in test mode
        '''
        _TEST_RECORD = _CREATED_RECORD.copy()
        _TEST_RECORD['id'] = None  # ID is not set in test mode
        ret = {'changes': _TEST_RECORD,
               'comment': 'Will create new record.',
               'name': 'mail',
               'result': None}

        list_zones = MagicMock(return_value=_ZONES)
        list_records = MagicMock(return_value=_RECORDS)
        create_record = MagicMock(return_value=_CREATED_RECORD)

        with patch.dict(libcloud_dns.__opts__, {'test': True}):
            with patch.dict(libcloud_dns.__salt__,
                            {'libcloud_dns.list_zones': list_zones,
                             'libcloud_dns.list_records': list_records,
                             'libcloud_dns.create_record': create_record}):
                result = libcloud_dns.record_present('mail', 'test.com', 'A', '127.0.0.1', 'test', extra={'y': 'x', 'ttl': 600})
                assert result == ret
                assert list_zones.called
                list_zones.assert_called_with('test')
                assert not create_record.called

    def test_absent_record_exists(self):
        '''
        Try and deny a record that already exists
        '''
        ret = {'changes': [_RECORDS[0]],
               'comment': 'Removed 1 records.',
               'name': 'www',
               'result': True}

        list_zones = MagicMock(return_value=_ZONES)
        list_records = MagicMock(return_value=_RECORDS)
        delete_record = MagicMock(return_value=True)

        with patch.dict(libcloud_dns.__salt__,
                        {'libcloud_dns.list_zones': list_zones,
                         'libcloud_dns.list_records': list_records,
                         'libcloud_dns.delete_record': delete_record}):
            result = libcloud_dns.record_absent('www', 'test.com', 'A', '127.0.0.1', 'test')
            assert result == ret
            assert list_zones.called
            list_zones.assert_called_with('test')
            assert delete_record.called
            delete_record.assert_called_with('12345', '45678', 'test')

    def test_absent_record_does_not_exist(self):
        '''
        Try and deny a record that already exists
        '''
        ret = {'changes': {},
               'comment': 'Records already absent.',
               'name': 'mail',
               'result': True}

        list_zones = MagicMock(return_value=_ZONES)
        list_records = MagicMock(return_value=_RECORDS)
        delete_record = MagicMock(return_value=True)

        with patch.dict(libcloud_dns.__salt__,
                        {'libcloud_dns.list_zones': list_zones,
                         'libcloud_dns.list_records': list_records,
                         'libcloud_dns.delete_record': delete_record}):
            result = libcloud_dns.record_absent('mail', 'test.com', 'A', '127.0.0.1', 'test')
            assert result == ret
            assert list_zones.called
            list_zones.assert_called_with('test')
            assert not delete_record.called

    def test_present_zone_not_found(self):
        '''
        Assert that when you try and ensure present state for a record to a zone that doesn't exist
        it fails gracefully
        '''
        ret = {'changes': {},
               'comment': 'Zone could not be found.',
               'name': 'salty_record',
               'result': False}

        list_zones = MagicMock(return_value=_ZONES)
        create_record = MagicMock(return_value=_CREATED_RECORD)

        with patch.dict(libcloud_dns.__salt__,
                        {'libcloud_dns.list_zones': list_zones,
                         'libcloud_dns.create_record': create_record}):
            result = libcloud_dns.record_present(name='salty_record', zone='test3.com', type='A', profile='test',
                                                 data='127.0.0.1')
            assert result == ret
            assert list_zones.called
            list_zones.assert_called_with('test')
            assert not create_record.called

    def test_absent_zone_not_found(self):
        '''
        Assert that when you try and ensure absent state for a record to a zone that doesn't exist
        it fails gracefully
        '''
        ret = {'changes': {},
               'comment': 'Zone could not be found.',
               'name': 'salty_record',
               'result': False}

        list_zones = MagicMock(return_value=_ZONES)
        create_record = MagicMock(return_value=_CREATED_RECORD)

        with patch.dict(libcloud_dns.__salt__,
                        {'libcloud_dns.list_zones': list_zones,
                         'libcloud_dns.create_record': create_record}):
            result = libcloud_dns.record_absent(name='salty_record', zone='test3.com', type='A', profile='test',
                                                data='127.0.0.1')
            assert result == ret
            assert list_zones.called
            list_zones.assert_called_with('test')
            assert not create_record.called

    def test_zone_present(self):
        '''
        Assert that a zone is present (that did not exist)
        '''
        ret = {'changes': _CREATED_ZONE,
               'comment': 'Created new zone.',
               'name': 'salty_zone',
               'result': True}

        list_zones = MagicMock(return_value=_ZONES)
        create_zone = MagicMock(return_value=_CREATED_ZONE)

        with patch.dict(libcloud_dns.__salt__,
                        {'libcloud_dns.list_zones': list_zones,
                         'libcloud_dns.create_zone': create_zone}):
            result = libcloud_dns.zone_present(name='salty_zone', domain='test3.com', type='master', profile='test', ttl=600)
            assert result == ret
            assert list_zones.called
            list_zones.assert_called_with('test')
            assert create_zone.called
            create_zone.assert_called_with(domain='test3.com', type='master', ttl=600, extra={}, profile='test')

    def test_zone_present_change_ttl(self):
        '''
        Assert that a zone is present (that did exist) with a new ttl
        '''
        _TEST_ZONE = _ZONES[0].copy()
        _TEST_ZONE['ttl'] = 900
        ret = {'changes': _TEST_ZONE,
               'comment': 'Updated zone.',
               'name': 'salty_zone',
               'result': True}

        list_zones = MagicMock(return_value=_ZONES)
        create_zone = MagicMock(return_value='foo')
        update_zone = MagicMock(return_value=_TEST_ZONE)

        with patch.dict(libcloud_dns.__salt__,
                        {'libcloud_dns.list_zones': list_zones,
                         'libcloud_dns.create_zone': create_zone,
                         'libcloud_dns.update_zone': update_zone}):
            result = libcloud_dns.zone_present(name='salty_zone', domain='test.com', type='master', profile='test', ttl=900)
            assert result == ret
            assert list_zones.called
            list_zones.assert_called_with('test')
            assert not create_zone.called
            assert update_zone.called
            update_zone.assert_called_with(zone_id='12345', domain='test.com', type='master', ttl=900, extra={}, profile='test')

    def test_zone_present_test_mode(self):
        '''
        Assert that a zone is present (that did not exist) in test mode
        '''
        _TEST_ZONE = _CREATED_ZONE.copy()
        _TEST_ZONE['id'] = None
        ret = {'changes': _TEST_ZONE,
               'comment': 'Will create new zone.',
               'name': 'salty_zone',
               'result': None}

        list_zones = MagicMock(return_value=_ZONES)
        create_zone = MagicMock(return_value=_CREATED_ZONE)

        with patch.dict(libcloud_dns.__opts__, {'test': True}):
            with patch.dict(libcloud_dns.__salt__,
                            {'libcloud_dns.list_zones': list_zones,
                             'libcloud_dns.create_zone': create_zone}):
                result = libcloud_dns.zone_present(name='salty_zone', domain='test3.com', type='master',
                                                   profile='test', ttl=3600, extra={'k': 'v'})
                assert result == ret
                assert list_zones.called
                list_zones.assert_called_with('test')
                assert not create_zone.called

    def test_zone_already_present(self):
        '''
        Assert that a zone is present (that did exist)
        '''
        ret = {'changes': {},
               'comment': 'Zone already exists.',
               'name': 'salty_zone',
               'result': True}

        list_zones = MagicMock(return_value=_ZONES)
        create_zone = MagicMock(return_value=_CREATED_ZONE)

        with patch.dict(libcloud_dns.__salt__,
                        {'libcloud_dns.list_zones': list_zones,
                         'libcloud_dns.create_zone': create_zone}):
            result = libcloud_dns.zone_present(name='salty_zone', domain='test.com', type='master',
                                               profile='test', ttl=3600, extra={'k': 'v'})
            assert result == ret
            assert list_zones.called
            list_zones.assert_called_with('test')
            assert not create_zone.called

    def test_zone_absent(self):
        '''
        Assert that a zone that did exist is absent
        '''
        ret = {'changes': {'domain': 'test.com'},
               'comment': 'Deleted zone.',
               'name': 'salty_zone',
               'result': True}

        list_zones = MagicMock(return_value=_ZONES)
        delete_zone = MagicMock(return_value=True)

        with patch.dict(libcloud_dns.__salt__,
                        {'libcloud_dns.list_zones': list_zones,
                         'libcloud_dns.delete_zone': delete_zone}):
            result = libcloud_dns.zone_absent(name='salty_zone', domain='test.com', profile='test')
            assert result == ret
            assert list_zones.called
            list_zones.assert_called_with('test')
            assert delete_zone.called
            delete_zone.assert_called_with('12345', 'test')

    def test_zone_absent_test_mode(self):
        '''
        Assert that a zone that did exist is absent in test mode
        '''
        ret = {'changes': {'domain': 'test.com'},
               'comment': 'Will delete zone.',
               'name': 'salty_zone',
               'result': None}

        list_zones = MagicMock(return_value=_ZONES)
        delete_zone = MagicMock(return_value=True)

        with patch.dict(libcloud_dns.__opts__, {'test': True}):
            with patch.dict(libcloud_dns.__salt__,
                            {'libcloud_dns.list_zones': list_zones,
                             'libcloud_dns.delete_zone': delete_zone}):
                result = libcloud_dns.zone_absent(name='salty_zone', domain='test.com', profile='test')
                assert result == ret
                assert list_zones.called
                list_zones.assert_called_with('test')
                assert not delete_zone.called

    def test_zone_already_absent(self):
        '''
        Assert that a zone that did not exist is absent
        '''
        ret = {'changes': {},
               'comment': 'Zone already absent.',
               'name': 'salty_zone',
               'result': True}

        list_zones = MagicMock(return_value=_ZONES)
        delete_zone = MagicMock(return_value=True)

        with patch.dict(libcloud_dns.__salt__,
                        {'libcloud_dns.list_zones': list_zones,
                         'libcloud_dns.delete_zone': delete_zone}):
            result = libcloud_dns.zone_absent(name='salty_zone', domain='test3.com', profile='test')
            assert result == ret
            assert list_zones.called
            list_zones.assert_called_with('test')
            assert not delete_zone.called
