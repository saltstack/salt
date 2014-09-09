# coding: utf-8
import json
import urllib

import yaml

from tests.utils import BaseToolsTest


class TestOutFormats(BaseToolsTest):
    _cp_config = {
        'tools.hypermedia_out.on': True,
    }

    def test_default_accept(self):
        request, response = self.request('/')
        self.assertEqual(response.headers['Content-type'], 'application/json')

    def test_unsupported_accept(self):
        request, response = self.request('/', headers=(
            ('Accept', 'application/ms-word'),
        ))
        self.assertEqual(response.status, '406 Not Acceptable')

    def test_json_out(self):
        request, response = self.request('/', headers=(
            ('Accept', 'application/json'),
        ))
        self.assertEqual(response.headers['Content-type'], 'application/json')

    def test_yaml_out(self):
        request, response = self.request('/', headers=(
            ('Accept', 'application/x-yaml'),
        ))
        self.assertEqual(response.headers['Content-type'], 'application/x-yaml')


class TestInFormats(BaseToolsTest):
    _cp_config = {
        'tools.hypermedia_in.on': True,
    }

    def test_urlencoded_ctype(self):
        data = {'valid': 'stuff'}
        request, response = self.request('/', method='POST',
            body=urllib.urlencode(data), headers=(
                ('Content-type', 'application/x-www-form-urlencoded'),
        ))
        self.assertEqual(response.status, '200 OK')
        self.assertDictEqual(request.unserialized_data, data)

    def test_json_ctype(self):
        data = {'valid': 'stuff'}
        request, response = self.request('/', method='POST',
            body=json.dumps(data), headers=(
                ('Content-type', 'application/json'),
        ))
        self.assertEqual(response.status, '200 OK')
        self.assertDictEqual(request.unserialized_data, data)

    def test_json_as_text_out(self):
        '''
        Some service send JSON as text/plain for compatibility purposes
        '''
        data = {'valid': 'stuff'}
        request, response = self.request('/', method='POST',
            body=json.dumps(data), headers=(
                ('Content-type', 'text/plain'),
        ))
        self.assertEqual(response.status, '200 OK')
        self.assertDictEqual(request.unserialized_data, data)

    def test_yaml_ctype(self):
        data = {'valid': 'stuff'}
        request, response = self.request('/', method='POST',
            body=yaml.dump(data), headers=(
                ('Content-type', 'application/x-yaml'),
        ))
        self.assertEqual(response.status, '200 OK')
        self.assertDictEqual(request.unserialized_data, data)
