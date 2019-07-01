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
from tests.support.mock import patch, MagicMock

# Import salt libs
import salt.fileserver.s3fs as s3fs

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
