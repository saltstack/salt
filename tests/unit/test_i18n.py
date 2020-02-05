# -*- coding: utf-8 -*-
'''
   Test the ability to process characters present in non English operating systems.
   In German, volume is Datenträger, executed is ausgeführt
   Current Windows issue: ü results in UnicodeDecodeError: 'utf8' codec can't decode byte 0xfc
'''

# Import Python libs
from __future__ import absolute_import
import logging
import os

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.helpers import with_tempdir
from tests.support.unit import skipIf

# Import Salt libs
import salt.utils.files
import salt.utils.platform

log = logging.getLogger(__name__)


@skipIf(not salt.utils.platform.is_windows(), 'Windows test only')
class i18nTestClass(ModuleCase):
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
