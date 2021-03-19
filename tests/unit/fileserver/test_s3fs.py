# -*- coding: utf-8 -*-
'''
    :codeauthor: Gareth Greenaway <gareth@saltstack.com>
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import copy
import logging
try:
    import pwd  # pylint: disable=unused-import
except ImportError:
    pass

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase
from tests.support.mock import patch, Mock, MagicMock

# Import salt libs
import salt.fileserver.s3fs as s3fs
import salt.utils.s3 as s3_utils

log = logging.getLogger(__name__)

S3_KEYID = 'GKTADJGHEIQSXMKKRBJ08H'
S3_KEY = 'askdjghsdfjkghWupUjasdflkdfklgjsdfjajkghs'

OPTS = {
    'fileserver_backend': ['s3fs'],
    'fileserver_events': True,
    's3.keyid': S3_KEYID,
    's3.key': S3_KEY,
    'transport': 'zeromq',
    '__role': 'master',
}


def _mock_json_response(data, status_code=200, reason=""):
    '''
    Mock helper for http response
    '''
    response = MagicMock()
    response.json = MagicMock(return_value=data)
    response.status_code = status_code
    response.reason = reason
    response.content = ""
    return Mock(return_value=response)


class S3fsConfigTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        opts = copy.deepcopy(OPTS)
        return {
            s3fs: {
                '__opts__': opts,
                '__utils__': {
                    's3.query': MagicMock(),
                },
            }
        }

    def test_get_file_from_s3_path_argument(self):
        path = 'http://example.s3.amazonaws.com/example/unstable/example_0.1.1-alpha.1+57dfd57_armhf.deb'
        with patch('os.path.isfile', MagicMock(return_value=False)):
            s3fs._get_file_from_s3(None, 'base', 'bucket_name', path, None)
            s3fs.__utils__['s3.query'].assert_called_with(bucket='bucket_name',
                                                          https_enable=None,
                                                          key=S3_KEY,
                                                          keyid=S3_KEYID,
                                                          kms_keyid=S3_KEYID,
                                                          local_file=None,
                                                          location=None,
                                                          path=path,
                                                          path_style=None,
                                                          service_url=None,
                                                          verify_ssl=None)

    def test_get_file_from_s3_with_spaces(self):
        path = 'example/unstable/filename with spaces.txt'
        expected_url = 'http://bucket_name.s3.amazonaws.com/example/unstable/filename%20with%20spaces.txt?'
        mock = _mock_json_response({})
        with patch('os.path.isfile', MagicMock(return_value=False)):
            with patch.dict(s3fs.__utils__, {'s3.query': s3_utils.query}):
                with patch('salt.utils.aws.get_location', MagicMock(return_value='dummy_location')):
                    with patch('requests.request', mock):
                        s3fs._get_file_from_s3(None, 'base', 'bucket_name', path, None)
                        self.assertEqual(expected_url, mock.call_args[0][1])
