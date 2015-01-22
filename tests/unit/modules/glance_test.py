# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.modules import glance


@skipIf(NO_MOCK, NO_MOCK_REASON)
class GlanceTestCase(TestCase):
    '''
    Test cases for salt.modules.glance
    '''
    def test_image_create(self):
        '''
        Test for Create an image (glance image-create)
        '''
        with patch.object(glance, '_auth', retur_value=True):
            with patch.object(glance, 'image_list', return_value={'name': 'A'}):
                self.assertEqual(glance.image_create(), {'A': {'name': 'A'}})

    def test_image_delete(self):
        '''
        Test for Delete an image (glance image-delete)
        '''
        class MockObjects(object):
            def __init__(self):
                self.name = 'A'
                self.id = 1
                self.checksum = 'B'
                self.container_format = 'C'
                self.created_at = 'D'
                self.deleted = 'E'
                self.disk_format = 'F'
                self.is_public = 'G'
                self.min_disk = 'H'
                self.min_ram = 'I'
                self.owner = 'J'
                self.protected = 'K'
                self.size = 'L'
                self.status = 'M'
                self.updated_at = 'N'

        class MockImages(object):
            def list(self):
                return [MockObjects()]

            def delete(self, key):
                return

        class MockClient(object):
            def __init__(self):
                self.images = MockImages()

        mock_lst = MagicMock(return_value=MockClient())
        with patch.object(glance, '_auth', mock_lst):
            self.assertEqual(glance.image_delete(id=1, name='A', profile='B'),
                             'Deleted image with ID 1 (A)')

        with patch.object(glance, '_auth', return_value=True):
            self.assertEqual(glance.image_delete(),
                             {'Error': 'Unable to resolve image id'})

    def test_image_show(self):
        '''
        Test to return details about a specific image (glance image-show)
        '''
        with patch.object(glance, '_auth', return_value=True):
            self.assertEqual(glance.image_show(),
                             {'Error': 'Unable to resolve image id'})

        class MockObjects(object):
            def __init__(self):
                self.name = 'A'
                self.id = 1
                self.checksum = 'B'
                self.container_format = 'C'
                self.created_at = 'D'
                self.deleted = 'E'
                self.disk_format = 'F'
                self.is_public = 'G'
                self.min_disk = 'H'
                self.min_ram = 'I'
                self.owner = 'J'
                self.protected = 'K'
                self.size = 'L'
                self.status = 'M'
                self.updated_at = 'N'

        class MockImages(object):
            def list(self):
                return [MockObjects()]

            def get(self, key):
                return MockObjects()

        class MockClient(object):
            def __init__(self):
                self.images = MockImages()

        mock_lst = MagicMock(return_value=MockClient())
        with patch.object(glance, '_auth', mock_lst):
            self.assertDictEqual(glance.image_show(name='A', profile='B'),
                                 {'A': {'status': 'M',
                                        'deleted': 'E',
                                        'container_format': 'C',
                                        'min_ram': 'I',
                                        'updated_at': 'N',
                                        'owner': 'J',
                                        'min_disk': 'H',
                                        'is_public': 'G',
                                        'id': 1,
                                        'size': 'L',
                                        'name': 'A',
                                        'checksum': 'B',
                                        'created_at': 'D',
                                        'disk_format': 'F',
                                        'protected': 'K'}})

    def test_image_list(self):
        '''
        Test to return a list of available images (glance image-list)
        '''
        class MockObjects(object):
            def __init__(self):
                self.name = 'A'
                self.id = 1
                self.checksum = 'B'
                self.container_format = 'C'
                self.created_at = 'D'
                self.deleted = 'E'
                self.disk_format = 'F'
                self.is_public = 'G'
                self.min_disk = 'H'
                self.min_ram = 'I'
                self.owner = 'J'
                self.protected = 'K'
                self.size = 'L'
                self.status = 'M'
                self.updated_at = 'N'

        class MockImages(object):
            def list(self):
                return [MockObjects()]

            def get(self, key):
                return MockObjects()

        class MockClient(object):
            def __init__(self):
                self.images = MockImages()

        mock_lst = MagicMock(return_value=MockClient())
        with patch.object(glance, '_auth', mock_lst):
            self.assertDictEqual(glance.image_list(id=1, profile='B'),
                                 {'checksum': 'B',
                                  'container_format': 'C',
                                  'created_at': 'D',
                                  'deleted': 'E',
                                  'disk_format': 'F',
                                  'id': 1,
                                  'is_public': 'G',
                                  'min_disk': 'H',
                                  'min_ram': 'I',
                                  'name': 'A',
                                  'owner': 'J',
                                  'protected': 'K',
                                  'size': 'L',
                                  'status': 'M',
                                  'updated_at': 'N'})
            self.assertDictEqual(glance.image_list(),
                                 {'A':
                                  {'checksum': 'B',
                                   'container_format': 'C',
                                   'created_at': 'D',
                                   'deleted': 'E',
                                   'disk_format': 'F',
                                   'id': 1,
                                   'is_public': 'G',
                                   'min_disk': 'H',
                                   'min_ram': 'I',
                                   'name': 'A',
                                   'owner': 'J',
                                   'protected': 'K',
                                   'size': 'L',
                                   'status': 'M',
                                   'updated_at': 'N'}})

if __name__ == '__main__':
    from integration import run_tests
    run_tests(GlanceTestCase, needs_daemon=False)
