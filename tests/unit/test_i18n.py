# -*- coding: utf-8 -*-
'''
   Test the ability to process characters present in non English operating systems.
   In German, volume is Datenträger, executed is ausgeführt
   Current Windows issue: ü results in UnicodeDecodeError: 'utf8' codec can't decode byte 0xfc
'''

# Import Python libs
from __future__ import absolute_import
import errno
import logging
import os
import shutil

# Import Salt Testing libs
from tests.support.mixins import AdaptedConfigurationTestCaseMixin, LoaderModuleMockMixin
from tests.support.mock import patch, Mock, MagicMock
from tests.support.unit import TestCase
from tests.support.runtests import RUNTIME_VARS

# Import Salt libs
from salt.ext.six.moves import range
from salt import fileclient
from salt.ext import six
from tests.support.helpers import with_tempdir
import salt.utils.files

log = logging.getLogger(__name__)


class i18nTestCase(TestCase):
    @with_tempdir()
    def test_i18n_characters_with_file_line(self, tempdir):
        tempfile = os.path.join(tempdir, 'temp_file')
        content_in = "äü"
        with salt.utils.files.fopen(tempfile, 'w') as fp:
            fp.write(content_in)
        ret = self.run_state('file.line',
                             name=tempfile,
                             content='{}'.format(content_in),
                             mode='insert',
                             location='start')
        self.assertSaltTrueReturn(ret)
        with salt.utils.files.fopen(tempfile, 'r') as fp:
            content_out = fp.read()
        self.assertEqual(content_in, content_out)
