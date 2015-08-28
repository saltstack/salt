# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import

# Import Salt Libs
import salt.utils.url

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

ensure_in_syspath('../../')


@patch('salt.utils.is_windows', MagicMock(return_value=False))
@skipIf(NO_MOCK, NO_MOCK_REASON)
class UrlTestCase(TestCase):
    '''
    TestCase for salt.utils.url module
    '''

    # parse tests

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
        url = 'salt://' + path + '?saltenv=' + env

        self.assertEqual(salt.utils.url.parse(url), (path, env))

    def test_parse_salt_saltenv(self):
        '''
        Test parsing a 'salt://' URL with a '?saltenv=' query
        '''
        saltenv = 'ambience'
        path = '?funny/path&with {interesting|chars}'
        url = 'salt://' + path + '?saltenv=' + saltenv

        self.assertEqual(salt.utils.url.parse(url), (path, saltenv))

    # create tests

    def test_create_url(self):
        '''
        Test creating a 'salt://' URL
        '''
        path = '? interesting/&path.filetype'
        url = 'salt://' + path

        self.assertEqual(salt.utils.url.create(path), url)

    def test_create_url_saltenv(self):
        '''
        Test creating a 'salt://' URL with a saltenv
        '''
        saltenv = 'raumklang'
        path = '? interesting/&path.filetype'

        url = 'salt://' + path + '?saltenv=' + saltenv

        self.assertEqual(salt.utils.url.create(path, saltenv), url)

    # is_escaped tests

    def test_is_escaped_windows(self):
        '''
        Test not testing a 'salt://' URL on windows
        '''
        url = 'salt://dir/file.ini'

        with patch('salt.utils.is_windows', MagicMock(return_value=True)):
            self.assertFalse(salt.utils.url.is_escaped(url))

    def test_is_escaped_escaped_path(self):
        '''
        Test testing an escaped path
        '''
        path = '|dir/file.conf?saltenv=basic'

        self.assertTrue(salt.utils.url.is_escaped(path))

    def test_is_escaped_unescaped_path(self):
        '''
        Test testing an unescaped path
        '''
        path = 'dir/file.conf'

        self.assertFalse(salt.utils.url.is_escaped(path))

    def test_is_escaped_escaped_url(self):
        '''
        Test testing an escaped 'salt://' URL
        '''
        url = 'salt://|dir/file.conf?saltenv=basic'

        self.assertTrue(salt.utils.url.is_escaped(url))

    def test_is_escaped_unescaped_url(self):
        '''
        Test testing an unescaped 'salt://' URL
        '''
        url = 'salt://dir/file.conf'

        self.assertFalse(salt.utils.url.is_escaped(url))

    def test_is_escaped_generic_url(self):
        '''
        Test testing an unescaped 'salt://' URL
        '''
        url = 'https://gentoo.org/'

        self.assertFalse(salt.utils.url.is_escaped(url))

    # escape tests

    def test_escape_windows(self):
        '''
        Test not escaping a 'salt://' URL on windows
        '''
        url = 'salt://dir/file.ini'

        with patch('salt.utils.is_windows', MagicMock(return_value=True)):
            self.assertEqual(salt.utils.url.escape(url), url)

    def test_escape_escaped_path(self):
        '''
        Test escaping an escaped path
        '''
        resource = '|dir/file.conf?saltenv=basic'

        self.assertEqual(salt.utils.url.escape(resource), resource)

    def test_escape_unescaped_path(self):
        '''
        Test escaping an unescaped path
        '''
        path = 'dir/file.conf'
        escaped_path = '|' + path

        self.assertEqual(salt.utils.url.escape(path), escaped_path)

    def test_escape_escaped_url(self):
        '''
        Test testing an escaped 'salt://' URL
        '''
        url = 'salt://|dir/file.conf?saltenv=basic'

        self.assertEqual(salt.utils.url.escape(url), url)

    def test_escape_unescaped_url(self):
        '''
        Test testing an unescaped 'salt://' URL
        '''
        path = 'dir/file.conf'
        url = 'salt://' + path
        escaped_url = 'salt://|' + path

        self.assertEqual(salt.utils.url.escape(url), escaped_url)

    def test_escape_generic_url(self):
        '''
        Test testing an unescaped 'salt://' URL
        '''
        url = 'https://gentoo.org/'

        self.assertEqual(salt.utils.url.escape(url), url)

    # unescape tests

    def test_unescape_windows(self):
        '''
        Test not escaping a 'salt://' URL on windows
        '''
        url = 'salt://dir/file.ini'

        with patch('salt.utils.is_windows', MagicMock(return_value=True)):
            self.assertEqual(salt.utils.url.unescape(url), url)

    def test_unescape_escaped_path(self):
        '''
        Test escaping an escaped path
        '''
        resource = 'dir/file.conf?saltenv=basic'
        escaped_path = '|' + resource

        self.assertEqual(salt.utils.url.unescape(escaped_path), resource)

    def test_unescape_unescaped_path(self):
        '''
        Test escaping an unescaped path
        '''
        path = 'dir/file.conf'

        self.assertEqual(salt.utils.url.unescape(path), path)

    def test_unescape_escaped_url(self):
        '''
        Test testing an escaped 'salt://' URL
        '''
        resource = 'dir/file.conf?saltenv=basic'
        url = 'salt://' + resource
        escaped_url = 'salt://|' + resource

        self.assertEqual(salt.utils.url.unescape(escaped_url), url)

    def test_unescape_unescaped_url(self):
        '''
        Test testing an unescaped 'salt://' URL
        '''
        url = 'salt://dir/file.conf'

        self.assertEqual(salt.utils.url.unescape(url), url)

    def test_unescape_generic_url(self):
        '''
        Test testing an unescaped 'salt://' URL
        '''
        url = 'https://gentoo.org/'

        self.assertEqual(salt.utils.url.unescape(url), url)

    # add_env tests

    def test_add_env_not_salt(self):
        '''
        Test not adding a saltenv to a non 'salt://' URL
        '''
        saltenv = 'higgs'
        url = 'https://pdg.lbl.gov/'

        self.assertEqual(salt.utils.url.add_env(url, saltenv), url)

    def test_add_env(self):
        '''
        Test adding a saltenv to a 'salt://' URL
        '''
        saltenv = 'erstwhile'
        url = 'salt://salted/file.conf'
        url_env = url + '?saltenv=' + saltenv

        self.assertEqual(salt.utils.url.add_env(url, saltenv), url_env)

    # split_env tests

    def test_split_env_non_salt(self):
        '''
        Test not splitting a saltenv from a non 'salt://' URL
        '''
        saltenv = 'gravitodynamics'
        url = 'https://arxiv.org/find/all/?' + saltenv

        self.assertEqual(salt.utils.url.split_env(url), (url, None))

    def test_split_env(self):
        '''
        Test splitting a 'salt://' URL
        '''
        saltenv = 'elsewhere'
        url = 'salt://salted/file.conf'
        url_env = url + '?saltenv=' + saltenv

        self.assertEqual(salt.utils.url.split_env(url_env), (url, saltenv))

    # validate tests

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

    # strip tests

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

    def test_http_basic_auth(self):
        '''
        Tests that adding basic auth to a URL works as expected
        '''
        # ((user, password), expected) tuples
        test_inputs = (
            ((None, None), 'http://example.com'),
            (('user', None), 'http://user@example.com'),
            (('user', 'pass'), 'http://user:pass@example.com'),
        )
        for (user, password), expected in test_inputs:
            kwargs = {
                'url': 'http://example.com',
                'user': user,
                'password': password,
            }
            # Test http
            result = salt.utils.url.add_http_basic_auth(**kwargs)
            self.assertEqual(result, expected)
            # Test https
            kwargs['url'] = kwargs['url'].replace('http://', 'https://', 1)
            expected = expected.replace('http://', 'https://', 1)
            result = salt.utils.url.add_http_basic_auth(**kwargs)
            self.assertEqual(result, expected)

    def test_http_basic_auth_https_only(self):
        '''
        Tests that passing a non-https URL with https_only=True will raise a
        ValueError.
        '''
        kwargs = {
            'url': 'http://example.com',
            'user': 'foo',
            'password': 'bar',
            'https_only': True,
        }
        self.assertRaises(
            ValueError,
            salt.utils.url.add_http_basic_auth,
            **kwargs
        )

    def test_redact_http_basic_auth(self):
        sensitive_outputs = (
            'https://deadbeaf@example.com',
            'https://user:pw@example.com',
        )
        sanitized = 'https://<redacted>@example.com'
        for sensitive_output in sensitive_outputs:
            result = salt.utils.url.redact_http_basic_auth(sensitive_output)
            self.assertEqual(result, sanitized)

    def test_redact_non_auth_output(self):
        non_auth_output = 'This is just normal output'
        self.assertEqual(
            non_auth_output,
            salt.utils.url.redact_http_basic_auth(non_auth_output)
        )


if __name__ == '__main__':
    from integration import run_tests
    run_tests(UrlTestCase, needs_daemon=False)
