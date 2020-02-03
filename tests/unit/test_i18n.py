# -*- coding: utf-8 -*-
'''
   Test the ability to process characters present in non English operating systems.
   In German, volume is Datenträger, executed is ausgeführt 
   Current Windows issue: ü results in UnicodeDecodeError: 'utf8' codec can't decode byte 0xfc
'''
from __future__ import absolute_import
from tests.support.unit import TestCase
from tests.support.helpers import with_tempdir
import os
import io


class i18nTestCase(TestCase):
    @with_tempdir()
    def test_i18n_characters_with_file_line(self, tempdir):
        tempfile = os.path.join(tempdir, 'temp_file')
        content_in = "äü"
        with io.open(tempfile, 'w', encoding='utf8') as fp:
            fp.write(content_in)
        ret = self.run_state('file.line',
                             name=tempfile,
                             content='{}'.format(content_in),
                             mode='insert',
                             location='start')
        self.assertSaltTrueReturn(ret)
        with io.open(tempfile, 'r', encoding='utf8') as fp:
            content_out = fp.read()
        self.assertEqual(content_in, content_out)
