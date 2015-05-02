# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import

# Import Salt Libs
import salt.utils.url

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import NO_MOCK, NO_MOCK_REASON
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')


@skipIf(NO_MOCK, NO_MOCK_REASON)
class UrlTestCase(TestCase):
    '''
    TestCase for salt.utils.url module
    '''

    def test_parse_path(self):
        '''
        Test parsing an ordinary path
        '''
        path = 'interesting?/path&.conf:and other things'
        self.assertEqual(salt.utils.url.parse(path), (path, None))

    def test_parse_salt_url(self):
        '''
        Test parsing a 'salt://' URL
        '''
        path = '?funny/path with {interesting|chars}'
        url = 'salt://' + path
        self.assertEqual(salt.utils.url.parse(url), (path, None))

    def test_parse_salt_env(self):
        '''
        Test parsing a 'salt://' URL with an '?env=' query
        '''
        env = 'milieu'
        path = '?funny/path&with {interesting|chars}'
        url = 'salt://' + path + '?env=' + env
        self.assertEqual(salt.utils.url.parse(url), (path, env))

    def test_parse_salt_saltenv(self):
        '''
        Test parsing a 'salt://' URL with a '?saltenv=' query
        '''
        saltenv = 'ambience'
        path = '?funny/path&with {interesting|chars}'
        url = 'salt://' + path + '?saltenv=' + saltenv
        self.assertEqual(salt.utils.url.parse(url), (path, saltenv))

    def test_create_url(self):
        '''
        Test creating a salt:// URL
        '''
        path = '? interesting/&path.filetype'
        url = 'salt://' + path
        self.assertEqual(salt.utils.url.create(path), url)

    def test_create_url_saltenv(self):
        '''
        Test creating a salt:// URL with a saltenv
        '''
        saltenv = 'raumklang'
        path = '? interesting/&path.filetype'
        url = 'salt://' + path + '?saltenv=' + saltenv
        self.assertEqual(salt.utils.url.create(path, saltenv), url)

    def test_validate_valid(self):
        '''
        Test URL valid validation
        '''
        url = 'salt://config/file.name?saltenv=vapid'
        protos = ['salt', 'pepper', 'cinnamon', 'melange']
        self.assertTrue(salt.utils.url.validate(url, protos))

    def test_validate_invalid(self):
        '''
        Test URL invalid validation
        '''
        url = 'cumin://config/file.name?saltenv=vapid'
        protos = ['salt', 'pepper', 'cinnamon', 'melange']
        self.assertFalse(salt.utils.url.validate(url, protos))

    def test_strip_url_with_scheme(self):
        '''
        Test stripping of URL scheme
        '''
        scheme = 'git+salt+rsync+AYB://'
        resource = 'all/the/things.stuff;parameter?query=I guess'
        url = scheme + resource
        self.assertEqual(salt.utils.url.strip_proto(url), resource)

    def test_strip_url_without_scheme(self):
        '''
        Test stripping of a URL without a scheme
        '''
        resource = 'all/the/things.stuff;parameter?query=I guess'
        self.assertEqual(salt.utils.url.strip_proto(resource), resource)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(UrlTestCase, needs_daemon=False)
